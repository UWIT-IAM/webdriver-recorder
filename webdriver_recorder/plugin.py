import datetime
import html
import itertools
import json
import logging
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from string import ascii_uppercase
from typing import Any, Callable, Dict, List, Optional

import jinja2
import pytest
from _pytest.fixtures import FixtureRequest
from pydantic import BaseModel, root_validator
from selenium import webdriver

from .browser import BrowserError, BrowserRecorder, Chrome, Remote

TEMPLATE_FILE = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "report.template.html"
)

log = logging.getLogger(__name__)

_here = os.path.abspath(os.path.dirname(__file__))


def pytest_addoption(parser):
    group = parser.getgroup("webdriver_recorder")
    group.addoption(
        "--selenium-server",
        action="store",
        dest="selenium_server",
        default=None,
        help="Remote selenium webdriver to connect to (eg localhost:4444)",
    )
    group.addoption(
        "--report-dir",
        action="store",
        dest="report_dir",
        default=os.path.join(os.getcwd(), "webdriver-report"),
        help="The path to the directory where artifacts should be stored.",
    )
    group.addoption(
        "--jinja-template",
        action="store",
        dest="report_template",
        default=os.path.join(_here, "report.template.html"),
    )
    group.addoption(
        "--report-title",
        action="store",
        dest="report_title",
        default=None,
        help="An optional title for your report; if not provided, "
        "the url of the final test-case executed before generation will be used. "
        "You may provide a constant default by overriding the report_title fixture.",
    )


class HTMLEscapeBaseModel(BaseModel):
    """
    Base model that automatically escapes all strings passed into it.
    """

    @root_validator(pre=True)
    def escape_strings(cls, values) -> Dict[str, Any]:
        values = dict(values)
        for k, v in values.items():
            if isinstance(v, str):
                values[k] = html.escape(str(v))
        return values


class ResultFailure(HTMLEscapeBaseModel):
    message: str
    url: Optional[str]
    loglines: Optional[List[str]]


class ResultAttributes(HTMLEscapeBaseModel):
    link: str
    doc: Optional[str]
    nodeid: str
    pngs: List[bytes]
    failure: Optional[ResultFailure]
    time1: str
    time2: str


class ResultHeader(HTMLEscapeBaseModel):
    link: str
    is_failed: bool
    description: str


class ReportResult(object):
    """
    A test result for passing to the report_test fixture.
    report -- a pytest test outcome
    excinfo -- exception info if there is any
    doc -- the docstring for the test if there is any
    """

    def __init__(self, report, excinfo, doc):
        self.report = report
        self.excinfo = excinfo
        self.doc = doc


@pytest.fixture(scope="session")
def selenium_server(request) -> Optional[str]:
    """Returns a non-empty string or None"""
    return (
        # CLI arg takes precedence
        request.config.getoption("selenium_server")
        # Otherwise, we look for a non-empty string
        or os.environ.get('SELENIUM_SERVER', '').strip()
        # If the result is still Falsey, we always return None.
        or None
    )


@pytest.fixture(scope="session")
def template_filename():
    return TEMPLATE_FILE


@pytest.fixture(scope="session")
def chrome_options():
    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_experimental_option("w3c", False)
    options.add_argument("--incognito")
    options.add_argument("--disable-application-cache")
    return options


@pytest.fixture(scope="session")
def session_browser(selenium_server, chrome_options):
    if selenium_server and selenium_server.strip():  # pragma: no cover
        logging.info(f"Creating connection to remote selenium server {selenium_server}")
        browser = Remote(
            options=chrome_options, command_executor=f"http://{selenium_server}/wd/hub"
        )
    else:
        browser = Chrome(options=chrome_options)
    try:
        yield browser
    finally:
        browser.quit()


@pytest.fixture(scope="session")
def browser_context(request: FixtureRequest) -> Callable[..., Chrome]:
    """
    This fixture allows you to create a fresh context for a given
    browser instance.

    The default behavior of the `browser` fixture is to always run in a context of the session scope, so
    you only need to use this if you are not using (or are overriding) the `browser` fixture.

    The fixture itself simply passes the context manager, so you can use it like so:

        def test_something(browser_context):
            with browser_context() as browser:
                browser.get('https://www.uw.edu')

    You may also provide a list of urls to visit to clear cookies at the end of your session,
    if the default 'delete_all_cookies' behavior is not enough to cover your use case.
    """

    @contextmanager
    def inner(
        browser: Optional[Chrome] = None, cookie_urls: Optional[List[str]] = None
    ):
        if not browser:
            # Only loads this fixture if no override is present
            # to avoid creating session_browsers if the
            # dependent does not to.
            browser = request.getfixturevalue('session_browser')
        browser.open_tab()
        cookie_urls = cookie_urls or []
        try:
            yield browser
        finally:
            browser.delete_all_cookies()
            for url in cookie_urls:
                browser.get(url)
                browser.delete_all_cookies()
            browser.close_tab()

    return inner


@pytest.fixture(scope="class")
def class_browser(request, browser_context) -> Chrome:
    with browser_context() as browser:
        request.cls.browser = browser
        yield browser


@pytest.fixture
def browser(browser_context) -> BrowserRecorder:
    """
    The default browser fixture. This default behavior will lazily
    instantiate a `session_browser` if one does not exist. To
    override this behavior and create your own context, you can
    redefine this fixture.
    """
    with browser_context() as browser:
        yield browser


@pytest.fixture(scope="session")
def report_dir(request):
    return request.config.getoption("report_dir")


@pytest.fixture(scope="session", autouse=True)
def report_generator(generate_report, report_dir) -> str:
    """Fixture returning the directory containing our report files. Overridable using `--report-dir`"""
    os.makedirs(report_dir, exist_ok=True)
    worker_file = tempfile.mktemp(prefix="worker.", dir=report_dir)
    Path(worker_file).touch()
    try:
        yield report_dir
    finally:
        os.remove(worker_file)
        workers = list(f for f in os.listdir(report_dir) if f.startswith("worker."))
        if not workers:
            generate_report()


@pytest.fixture(autouse=True)
def report_test(report_generator, request):
    """
    Print the results to report_file after a test run. Without this, the results of the test will not be saved.
    You can ensure this is always run by including the following in your conftest.py:

    @pytest.fixture(autouse=True)
    def report_test(report_test):
        return report_test
    """
    time1 = str(datetime.datetime.now())
    yield
    time2 = str(datetime.datetime.now())
    try:
        # TODO: Sometimes this line causes problems, but I can't
        #       remember the context surrounding it. I think if there
        #       is an error setting up a test fixture, `report_call` is not
        #       defined, or something. Anyway, it'd be a great
        #       to figure out a graceful solution.
        #       In the meantime this'll be nicer output.
        nodeid = request.node.report_call.report.nodeid
    except Exception:  # pragma: no cover
        logging.error(
            f"Unable to extract nodeid from node: {request.node}; "
            "not preparing report segment"
        )
        return
    is_failed = request.node.report_call.report.failed
    # TODO: Figure out a way to include class docs if they exist
    #       class TestFooBar:
    #           """
    #           When Foo is bar
    #           """
    #           def test_a_baz(self):
    #               """and baz is bop"""
    #               do_work('bop')
    #   The report output should then read "When foo is bar and baz is bop"
    doc = request.node.report_call.doc
    slug = re.sub(r"\W", "-", nodeid)
    header = ResultHeader(link=slug, is_failed=is_failed, description=nodeid)
    failure = None
    if is_failed:
        exc_info = request.node.report_call.excinfo
        if isinstance(exc_info.value, BrowserError):
            e = exc_info.value
            failure = ResultFailure(
                message=e.message,
                url=e.url,
                loglines=[log.get("message", "") for log in e.logs],
            )
        else:
            failure = ResultFailure(message=str(exc_info))

    report = ResultAttributes(
        link=slug,
        doc=doc,
        nodeid=nodeid,
        pngs=BrowserRecorder.pngs,
        failure=failure,
        time1=time1,
        time2=time2,
    )

    filename = os.path.join(report_generator, f"result.{slug}.html")
    headerfile = os.path.join(report_generator, f"head.{slug}.html")

    with open(headerfile, "w") as fd:
        fd.write(header.json())
    with open(filename, "w") as fd:
        fd.write(report.json())
    BrowserRecorder.pngs.clear()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    This gives us hooks from which to report status post test-run.
    Import this into your conftest.py.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        doc = getattr(getattr(item, "function", None), "__doc__", None)
        item.report_call = ReportResult(report=report, excinfo=call.excinfo, doc=doc)


def lettergen():
    """
    Used to generate unique alpha tags.
    :return: A, B, C, ..., AA, AB, AC, ..., BA, BB, BC, ...
    """
    for repeat in range(1, 10):
        for item in itertools.product(ascii_uppercase, repeat=repeat):
            yield "".join(item)


@pytest.fixture(scope="session")
def report_title(request) -> str:
    return request.config.getoption("report_title", default="Webdriver Recorder Summary")


@pytest.fixture(scope="session", autouse=True)
def generate_report(template_filename, report_title, report_dir):
    """
    Uses the included HTML template to generate the final report, using the results found in `report_dir`. Can be
    called explicitly in order to do this at any time.
    """

    def inner(output_dir: Optional[str] = None):
        output_dir = output_dir or report_dir
        with open(template_filename) as fd:
            template = jinja2.Template(fd.read())

        template.globals.update(
            {"date": str(datetime.datetime.now()), "lettergen": lettergen, "zip": zip}
        )

        headers = iterfiles(output_dir, "head.")
        results = iterfiles(output_dir, "result.")
        stream = template.stream(headers=headers, results=results, project=report_title)
        artifact = os.path.join(output_dir, "index.html")
        stream.dump(artifact)
        logging.info(f"Created report: {artifact}")

    return inner


def iterfiles(dir, prefix):
    """
    Iterate through the objects contained in files starting with prefix.
    Delete afterwards.
    """
    files = (f for f in os.listdir(dir) if f.startswith(prefix))
    for filename in sorted(files):
        filename = os.path.join(dir, filename)
        with open(filename) as fd:
            data = json.load(fd)
        yield data
        os.remove(filename)

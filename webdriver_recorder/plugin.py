import datetime
import html
import itertools
import json
import logging
import os
import re
import secrets
import tempfile
from contextlib import contextmanager
from pathlib import Path
from string import ascii_uppercase
from typing import Any, Callable, Dict, List, Optional, Type, Union

import jinja2
import pytest
from pydantic import BaseModel, BaseSettings, root_validator, validator
from selenium import webdriver
from webdriver_recorder.plugin import ResultHeader

from .browser import BrowserError, BrowserRecorder, Chrome, Remote

TEMPLATE_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "report.template.html")

_here = os.path.abspath(os.path.dirname(__file__))

logger = logging.getLogger(__name__)


class EnvSettings(BaseSettings):
    """
    Automatically derives from environment variables and
    translates truthy/falsey strings into bools. Only required
    for code that must be conditionally loaded; all others
    should be part of 'pytest_addoption()'
    """

    # If set to True, will generate a new browser instance within every request
    # for a given scope, instead of only creating a single instance and generating
    # contexts for each test.
    # This has a significant performance impact,
    # but sometimes cannot be avoided.
    disable_session_browser: Optional[bool] = False

    @validator("*", pre=True)
    def handle_empty_string(cls, v):
        if not v:
            return None


_SETTINGS = EnvSettings()


def pytest_addoption(parser):
    group = parser.getgroup("webdriver_recorder")
    group.addoption(
        "--selenium-server",
        action="store",
        dest="selenium_server",
        default=os.environ.get("REMOTE_SELENIUM"),
        help="Remote selenium webdriver to connect to (eg localhost:4444)",
    )
    group.addoption(
        "--report-dir",
        action="store",
        dest="report_dir",
        default=os.environ.get("REPORT_DIR", os.path.join(os.getcwd(), "webdriver-report")),
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
    header: ResultHeader
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
    value = request.config.getoption("selenium_server")
    if value:
        return value.strip()
    return None


@pytest.fixture(scope="session")
def template_filename():
    return TEMPLATE_FILE


@pytest.fixture(scope="session")
def chrome_options() -> webdriver.ChromeOptions:
    """
    An extensible instance of ChromeOptions with default
    options configured for a balance between performance
    and test isolation.

    You can extend this:
        @pytest.fixture(scope='session')
        def chrome_options(chrome_options) -> ChromeOptions:
            chrome_options.add_argument("--option-name")
            return chrome_options

    or override it entirely:
        @pytest.fixture(scope='session')
        def chrome_options() -> ChromeOptions:
            return ChromeOptions()
    """
    options = webdriver.ChromeOptions()

    # Our default options promote a balance between
    # performance and test isolation.
    options.add_argument("--headless")
    options.add_argument("--incognito")
    options.add_argument("--disable-application-cache")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return options


@pytest.fixture(scope="session")
def browser_args(selenium_server, chrome_options) -> Dict[str, Optional[Union[webdriver.ChromeOptions, str]]]:
    args = {"options": chrome_options}
    if selenium_server:
        args["command_executor"] = f"http://{selenium_server}/wd/hub"
    return args


@pytest.fixture(scope="session")
def browser_class(browser_args) -> Type[BrowserRecorder]:
    if browser_args.get("command_executor"):
        return Remote
    return Chrome


@pytest.fixture(scope="session")
def build_browser(browser_args, browser_class) -> Callable[..., BrowserRecorder]:
    logger.info(
        "Browser generator will build instances using the following settings:\n"
        f"   Browser class: {browser_class.__name__}\n"
        f"   Browser args: {dict(browser_args)}"
    )

    def inner() -> BrowserRecorder:
        return browser_class(**browser_args)

    return inner


@pytest.fixture(scope="session")
def session_browser(build_browser) -> BrowserRecorder:
    """
    A browser instance that is kept open for the entire test run.
    Only instantiated if it is used, but by default will be used in both the
    'browser' and 'class_browser' fixtures, unless "disable_session_browser=1"
    is set in the environment.
    """
    browser = build_browser()
    try:
        yield browser
    finally:
        browser.quit()


@pytest.fixture(scope="session")
def browser_context() -> Callable[..., Chrome]:
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
    def inner(browser: BrowserRecorder, cookie_urls: Optional[List[str]] = None) -> BrowserRecorder:
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


if _SETTINGS.disable_session_browser:
    logger.info("Disabling auto-use of 'session_browser', this may significantly decrease test performance.")

    @pytest.fixture
    def browser(build_browser) -> BrowserRecorder:
        """Creates a fresh instance of the browser using the configured chrome_options fixture."""
        browser = build_browser()
        try:
            yield browser
        finally:
            browser.quit()

    @pytest.fixture(scope="class")
    def class_browser(build_browser, request) -> BrowserRecorder:
        """
        Creates a fresh instance of the browser for use in the requesting class, using the configure
        chrome_options fixture.
        """
        browser = build_browser()
        request.cls.browser = browser
        try:
            yield browser
        finally:
            browser.quit()

else:
    logger.info(
        "Enabling auto-use of 'session_browser'; if your tests appear stuck, try disabling "
        "by setting 'disable_session_browser=1' in your environment."
    )

    @pytest.fixture
    def browser(session_browser, browser_context) -> BrowserRecorder:
        """
        Creates a function-scoped tab context for the session_browser which cleans
        up after itself (to the best of its ability). If you need a fresh instance
        each test, you can set `disable_session_browser=1` in your environment.
        """
        with browser_context(session_browser) as browser:
            yield browser

    @pytest.fixture(scope="class")
    def class_browser(request, session_browser, browser_context) -> BrowserRecorder:
        """
        Creates a class-scoped tab context and binds it to the requesting class
        as 'self.browser'; this tab will close once all tests in the class have run,
        and will clean up after itself (to the best of its ability). If you need
        a fresh browser instance for each class, you can set `disable_session_browser=1` in your
        environment.
        """
        with browser_context(session_browser) as browser:
            request.cls.browser = browser
            yield browser


@pytest.fixture(scope="session")
def report_dir(request):
    dir_ = request.config.getoption("report_dir")
    os.makedirs(dir_, exist_ok=True)
    return dir_


@pytest.fixture(scope='session')
def worker_file(report_dir):
    worker_file = tempfile.mktemp(prefix="worker.", dir=report_dir)
    Path(worker_file).touch()
    try:
        yield worker_file
    finally:
        try:
            os.remove(worker_file)
        except Exception as e:
            logger.exception(e)


@pytest.fixture(scope="session", autouse=True)
def report_generator(generate_report, report_dir, session_results) -> str:
    """Fixture returning the directory containing our report files. Overridable using `--report-dir`"""
    worker_file = tempfile.mktemp(prefix="worker.", dir=report_dir)
    try:
        yield
    finally:
        if session_results:
            with open(os.path.join(f'results.{worker_file}.json', 'wb')) as f:
                f.write(session_results.json())
        os.remove(worker_file)
        workers = list(f for f in os.listdir(report_dir) if f.startswith("worker."))
        if not workers:
            generate_report()


class SessionResults(BaseModel):
    results: List[ResultAttributes] = []


@pytest.fixture(scope='session', autouse=True)
def session_results() -> SessionResults:
    return SessionResults()


@pytest.fixture(autouse=True)
def report_test(report_generator, request, session_results):
    """
    Print the results to report_file after a test run. Without this, the results of the test will not be saved.
    """
    time1 = str(datetime.datetime.now())
    try:
        yield
    finally:
        time2 = str(datetime.datetime.now())
    if hasattr(request.node, 'report_call'):
        node_id = request.node.report_call.report.nodeid
    else:
        logging.error(f"Unable to extract nodeid from node: {request.node}; " "not preparing report segment")
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
    slug = re.sub(r"\W", "-", node_id)
    header = ResultHeader(link=slug, is_failed=is_failed, description=node_id)
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
        nodeid=node_id,
        pngs=BrowserRecorder.pngs,
        failure=failure,
        time1=time1,
        time2=time2,
        header=header,
    )
    session_results.results.append(report)

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


@pytest.fixture(scope="session")
def report_title(request) -> str:
    return request.config.getoption("report_title", default="Webdriver Recorder Summary")


@pytest.fixture(scope="session", autouse=True)
def generate_report(template_filename, report_title, report_dir, session_results):
    """
    Uses the included HTML template to generate the final report, using the results found in `report_dir`. Can be
    called explicitly in order to do this at any time.
    """

    def inner(output_dir: Optional[str] = None):
        output_dir = output_dir or report_dir
        with open(template_filename) as fd:
            template = jinja2.Template(fd.read())

        template.globals.update({"date": str(datetime.datetime.now())})
        stream = template.stream(results=session_results)
        artifact = os.path.join(output_dir, "index.html")
        stream.dump(artifact)
        logger.info(f"Created report: {artifact}")

    return inner


class ReportGenerator:
    def __init__(self, results_directory: str):
        self.worker_results_files = [
            os.path.join(results_directory, f)
            for f in os.listdir(results_directory) if
            f.startswith('results.worker')
        ]
        self.worker_results = self.load_results_files()
        self.modules = {}
        self.sort_results()
        self.annotations = []

    def load_results_files(self) -> List[ResultAttributes]:
        aggregate = []
        for f in self.worker_results_files:
            with open(f) as results:
                aggregate.extends([
                    ResultAttributes.parse_obj(o)
                    for o in json.loads(results.read())
                ])
        return aggregate

    def sort_results(self):
        for result in self.worker_results:
            # test_zorp.py::test_foo[blah] becomes
            # ["test_zorp.py", "test_foo[blah]"]
            taxonomy = result.header.link.split('::')
            if re.match(r'^\[.*]$', taxonomy[-1]):  # test_foo[blah]
                case = taxonomy.pop(-1)
                test_func, params = case.split('[')  # test_foo, blah]
                params = params[:-1]  # Remove the trailing `]`
            context = self.modules
            for layer in taxonomy:  # ["test_zorp.py", "test_foo", "blah"]
                if taxonomy[-1] == layer:  # On innermost context
                    context[layer] = result
                elif layer in context:
                    context = context[layer]
                else:
                    context = {}
                    context[layer] = context
            # self.modules ==
            #   {"test_zorp.py": {"test_foo": {"blah": ResultAttributes(...)}}}



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

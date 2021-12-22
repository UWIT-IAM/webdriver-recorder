import logging
import os
import sys
import tempfile
from contextlib import contextmanager
from typing import Callable, Dict, List, Optional, Type, Union

import pytest
from pydantic import BaseSettings, validator
from selenium import webdriver

from .browser import BrowserError, BrowserRecorder, Chrome, Remote
from .models import Outcome, Report, ReportResult, TestResult, Timed
from .report_exporter import ReportExporter

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

    @validator("*", pre=True, always=True)
    def handle_empty_string(cls, v):
        if not v:
            return None
        return v


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
        default="Webdriver Recorder Summary",
        help="An optional title for your report; if not provided, a default will be used. "
        "You may also provide a constant default by overriding the report_title fixture.",
    )


@pytest.fixture(scope="session", autouse=True)
def clean_screenshots(report_dir):
    screenshots_dir = os.path.join(report_dir, "screenshots")
    if os.path.exists(screenshots_dir):
        old_screenshots = os.listdir(screenshots_dir)
        for png in old_screenshots:
            os.remove(os.path.join(screenshots_dir, png))


@pytest.fixture(scope="session", autouse=True)
def test_report(report_title) -> Report:
    args = []
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])

    return Report(
        arguments=" ".join(args),
        outcome=Outcome.never_started,
        title=report_title,
    )


@pytest.fixture(scope="session")
def selenium_server(request) -> Optional[str]:
    """Returns a non-empty string or None"""
    value = request.config.getoption("selenium_server")
    if value:
        return value.strip()
    return None


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
    logger.warning("Disabling auto-use of 'session_browser', this may significantly decrease test performance.")

    @pytest.fixture(scope="session")
    def session_browser_disabled() -> bool:
        return True

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
    def session_browser_disabled() -> bool:
        return False


@pytest.fixture(scope="session")
def report_dir(request):
    dir_ = request.config.getoption("report_dir")
    os.makedirs(dir_, exist_ok=True)
    return dir_


@pytest.fixture(scope="session", autouse=True)
def report_generator(report_dir, test_report):
    with tempfile.NamedTemporaryFile(prefix="worker.", dir=report_dir) as worker_file:
        suffix = ".".join(worker_file.name.split(".")[1:])
        yield
    test_report.stop_timer()
    exporter = ReportExporter()
    workers = list(f for f in os.listdir(report_dir) if f.startswith("worker."))
    worker_results = list(f for f in os.listdir(report_dir) if f.endswith(".result.json"))
    if not workers:
        test_report.outcome = Outcome.success
        # Aggregate worker reports into this "root" report.
        for result_file in [os.path.join(report_dir, f) for f in worker_results]:
            worker_report = Report.parse_file(result_file)
            test_report.results.extend(worker_report.results)
            os.remove(result_file)
        exporter.export_all(test_report, report_dir)
    else:
        # If there are other workers, only export the report json of the
        # current worker. The last worker running will be responsible for aggregating and reporting results.
        exporter.export_json(test_report, report_dir, dest_filename=f"{suffix}.result.json")


@pytest.fixture(autouse=True)
def report_test(report_generator, request, test_report):
    """
    Print the results to report_file after a test run. Without this, the results of the test will not be saved.
    """
    tb = None
    console_logs = []
    timer: Timed
    with Timed() as timer:
        yield

    call_summary = getattr(request.node, "report_result", None)

    if call_summary:
        doc = call_summary.doc
        test_name = call_summary.report.nodeid
        outcome = Outcome.failure if call_summary.report.failed else Outcome.success
        if call_summary and call_summary.excinfo and not tb:
            outcome = Outcome.failure
            exception: BaseException = call_summary.excinfo.value
            exception_msg = f"{exception.__class__.__name__}: {str(exception)}"
            if isinstance(exception, BrowserError):
                if exception.orig:
                    tb = f"{exception_msg}\n{exception.orig=}"
                console_logs = [log.get("message", "") for log in exception.logs]
            if not tb:
                tb = f"{exception_msg}\n(No traceback is available)"

    else:
        logging.error(
            f"Test {request.node} reported no outcomes; "
            f"this usually indicates a fixture caused an error when setting up the test."
        )
        doc = None
        test_name = f"{request.node.name}"
        outcome = Outcome.never_started

    # TODO: Figure out a way to include class docs if they exist
    #       class TestFooBar:
    #           """
    #           When Foo is bar
    #           """
    #           def test_a_baz(self):
    #               """and baz is bop"""
    #               do_work('bop')
    #   The report output should then read "When foo is bar and baz is bop"

    result = TestResult(
        pngs=BrowserRecorder.pngs,
        test_name=test_name,
        test_description=doc,
        outcome=outcome,
        start_time=timer.start_time,
        end_time=timer.end_time,
        traceback=tb,
        console_errors=console_logs,
    )
    BrowserRecorder.pngs = []

    test_report.results.append(result)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    This gives us hooks from which to report status post test-run.
    """
    outcome = yield

    report = outcome.get_result()
    if report.when == "call":
        doc = getattr(getattr(item, "function", None), "__doc__", None)
        item.report_result = ReportResult(report=report, excinfo=call.excinfo, doc=doc)


@pytest.fixture(scope="session")
def report_title(request) -> str:
    return request.config.getoption("report_title")

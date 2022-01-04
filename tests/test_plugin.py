# Enables testing failure cases in plugin logic by dynamically generating
# and running plugin tests.
import glob
import logging
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest import mock

import pytest

# Enables testing failure cases in plugin logic by dynamically generating
# and running plugin tests.
import webdriver_recorder
from webdriver_recorder.browser import XPathWithSubstringLocator
from webdriver_recorder.plugin import EnvSettings

print(webdriver_recorder.__file__)
from webdriver_recorder.models import Report, Outcome

pytest_plugins = ["pytester"]


@pytest.fixture
def report_subdir(report_dir):
    subdir = os.path.join(report_dir, "test_plugin")
    if os.path.exists(subdir):  # From a previous test that errored
        shutil.rmtree(subdir, ignore_errors=True)
    os.makedirs(subdir, exist_ok=True)
    try:
        yield subdir
    finally:
        shutil.rmtree(subdir, ignore_errors=True)


@pytest.fixture
def make_test_file(pytester):
    def inner(content):
        content = f"""
        {content}
        """
        logging.info("Creating temporary python test file with content:\n" f"{content}")
        pytester.makepyfile(content)

    return inner


@pytest.fixture(scope="session")
def register_plugin() -> bool:
    # When running in docker, we don't want to install the plugin,
    # because it can wrangle coverage data. Instead, we leave it as
    # a source directory (see Dockerfile::webdriver-source).
    # Because we have no [need for a] virtualenv in the container,
    # we have to explicitly tell pytest that we want to use
    # this plugin.
    #
    # So, when setting up our test session, we check for a file that always
    # exists when running inside a docker container.
    return os.path.exists("/.dockerenv")


@pytest.fixture
def run_pytest(pytester, report_subdir, register_plugin):
    def inner(*args, **kwargs):
        if "--report-dir" not in args:
            args = list(args)
            args.extend(["--report-dir", report_subdir])

        if "plugins" not in kwargs:
            kwargs["plugins"] = []
        if register_plugin and "webdriver_recorder.plugin" not in kwargs["plugins"]:
            kwargs["plugins"].append("webdriver_recorder.plugin")
        return pytester.runpytest(*args, **kwargs)

    return inner


def test_happy_chrome(browser, load_page):
    """
    A simple test case to ensure the fixture itself works; the heavy lifting is all tested in the browser tests.
    """
    _test_happy_case(browser)


def test_browser_context(browser, browser_context):
    mock_get_patcher = mock.patch.object(browser, "get")
    mock_get = mock_get_patcher.start()
    mock_delete_cookies_patcher = mock.patch.object(browser, "delete_all_cookies")
    mock_delete_cookies = mock_delete_cookies_patcher.start()
    try:
        with browser_context(
            browser,
            cookie_urls=[
                "https://idp.uw.edu/signout",
                "https://identity.uw.edu/logout",
            ],
        ) as browser:
            browser.get("https://identity.uw.edu")
            mock_get.assert_called_once_with("https://identity.uw.edu")

        assert mock_get.call_count == 3
        # Despite only 2 cookies being passed above, the context
        # always calls the delete_all_cookies method on the
        # current domain, which brings the total to 3.
        assert mock_delete_cookies.call_count == 3
        mock_get.assert_called_with("https://identity.uw.edu/logout")
    finally:
        mock_get_patcher.stop()
        mock_delete_cookies_patcher.stop()


@pytest.fixture(scope="class")
def track_tabs(request, class_browser):
    request.cls.pre_test_tab_count = len(class_browser.window_handles)


@pytest.mark.usefixtures("class_browser", "track_tabs")
class TestClassBrowser:
    def validate_new_tab_state(self):
        assert len(self.browser.window_handles) == self.pre_test_tab_count + 1
        assert self.browser.get_cookie("foo")["value"] == "bar"
        assert self.browser.current_url == "https://www.example.com/"

    def test_browser_new_tab(self):
        # At the beginning of the test, the "root" tab for the session will be open
        # as well as the "root" tab for the class.
        assert len(self.browser.window_handles) == self.pre_test_tab_count
        self.browser.get("https://www.washington.edu")
        assert self.browser.current_url == "https://www.washington.edu/"
        # We'll open another tab that we'll expect to be preserved.
        self.browser.open_tab()
        self.browser.get("https://www.example.com")
        self.browser.add_cookie({"name": "foo", "value": "bar"})
        self.validate_new_tab_state()

    def test_browser_close_tab(self):
        # Validate that nothing was auto-closed between tests
        self.validate_new_tab_state()
        self.browser.close_tab()
        assert len(self.browser.window_handles) == self.pre_test_tab_count
        assert self.browser.current_url == "https://www.washington.edu/"


def test_browser_error_failure_reporting(run_pytest, local_html_path, report_subdir, make_test_file):
    """
    Assert that the right cleanup behavior takes place when a BrowserError
    is bubbled from within a test.
    """
    make_test_file(
        content=f"""
        from webdriver_recorder.browser import BrowserError
        import pytest

        def test_force_failure(browser):
            browser.get("file://{local_html_path}")
            browser.wait_for_tag('a', 'does-not-exist', timeout=0)
    """
    )
    result = run_pytest()
    try:
        result.assert_outcomes(failed=1)
    except ValueError:
        logging.error(f"Could not parse output from pytest.")
        if result.outlines:
            lines = "\n".join(result.outlines)
            logging.error(f"No summary found in:\n {lines}")
        else:
            logging.error("No STDOUT from test execution")
        if result.errlines:
            lines = "\n".join(result.errlines)
            logging.error(f"Execution resulted in errors\n:{lines}")
        raise
    expected_filename = os.path.join(report_subdir, f"report.json")
    report = Report.parse_file(expected_filename)
    assert report.outcome == Outcome.failure
    assert "BrowserError" in report.results[0].traceback


def test_failure_reporting(run_pytest, local_html_path, report_subdir, make_test_file):
    """
    Similar to test_browser_error_failure_reporting, but with a generic AssertionError. This is what we would expect
    to see under most failure circumstances.
    """
    make_test_file(
        f"""
        from webdriver_recorder.browser import BrowserError
        import pytest

        def test_force_failure(session_browser, report_test):
            session_browser.get("file://{local_html_path}")
            assert False
        """
    )
    result = run_pytest()
    result.assert_outcomes(failed=1)
    expected_filename = os.path.join(report_subdir, "report.json")
    report = Report.parse_file(expected_filename)
    assert report.outcome == Outcome.failure
    assert "AssertionError" in report.results[0].traceback


def test_selenium_server_arg(run_pytest, make_test_file):
    make_test_file(
        f"""
        def test_selenium_server(selenium_server):
            assert selenium_server == 'foo'
        """
    )

    result = run_pytest("--selenium-server", "foo")
    result.assert_outcomes(passed=1)


def test_worker_results(make_test_file, run_pytest, report_subdir, local_html_path):
    def count_files(glob_: str) -> int:
        return len([os.path.basename(p) for p in glob.glob(f"{report_subdir}/{glob_}")])

    with NamedTemporaryFile(prefix="worker.", dir=report_subdir):
        existing_workers = count_files("worker.*")
        existing_results = count_files("*.result.json")
        assert existing_workers == 1, "Precondition failed"
        assert existing_results == 0, "Precondition failed"
        make_test_file(
            f"""
            def test_a_thing(browser):
                browser.get("file://{local_html_path}", snap=True)
            """
        )
        run_pytest()
        assert count_files("worker.*") == 1
        assert count_files("*.result.json") == 1
        assert count_files("report.json") == 0


def test_aggregate_worker_reports(run_pytest, report_subdir, make_test_file):
    make_test_file(
        f"""
        def test_a_thing(browser):
            pass
        """
    )
    run_pytest()
    report_json = os.path.join(report_subdir, "report.json")
    test_1_rename = os.path.join(report_subdir, "t1.result.json")
    assert os.path.exists(report_json)
    shutil.move(report_json, test_1_rename)
    assert not os.path.exists(report_json)
    assert os.path.exists(test_1_rename)
    run_pytest()
    assert os.path.exists(report_json)
    assert not os.path.exists(test_1_rename)
    report = Report.parse_file(report_json)
    assert len(report.results) == 2


def test_no_outcomes(run_pytest, report_subdir, make_test_file):
    make_test_file(
        f"""
        import pytest
        
        @pytest.fixture
        def bad_fixture():
            raise RuntimeError
            
        def test_a_thing(bad_fixture, browser):
            pass
        """
    )
    run_pytest()
    logging.error("If you just saw an error message, you can ignore it. " "It was on purpose, and part of a test.")
    report_json = os.path.join(report_subdir, "report.json")
    report = Report.parse_file(report_json)
    assert report.results[0].outcome.value == "never started"
    assert report.outcome == Outcome.failure
    assert report.results[0].test_name == "test_a_thing"


def test_docstring_capture(run_pytest, report_subdir, make_test_file):
    make_test_file(
        f"""
        def test_a_thing(browser):
            '''hello'''
            pass
        """
    )
    run_pytest()
    report_json = os.path.join(report_subdir, "report.json")
    report = Report.parse_file(report_json)
    assert report.results[0].test_description == "hello"


def test_call_exception(run_pytest, report_subdir, make_test_file):
    make_test_file(
        f"""
        def test_a_thing(browser):
            raise RuntimeError("????")
        """
    )
    run_pytest()
    report = Report.parse_file(os.path.join(report_subdir, "report.json"))
    assert "RuntimeError" in report.results[0].traceback


def test_remote_context(run_pytest, make_test_file):
    make_test_file(
        f"""
        def test_selenium_server(selenium_server):
            assert selenium_server == 'foo'
            
        def test_browser_class(browser_class):
            assert browser_class.__name__ == "Remote"
            
        def test_browser_args(browser_args):
            assert browser_args['command_executor'] == "http://foo/wd/hub"
        """
    )

    result = run_pytest("--selenium-server", "foo")
    result.assert_outcomes(passed=3)


@pytest.mark.parametrize(
    "env_value, expected", [("", None), ("1", True), ("true", True), ("0", False), ("false", False)]
)
def test_env_settings(env_value, expected):
    with mock.patch.dict(os.environ, clear=True) as environ:
        environ["disable_session_browser"] = env_value
        assert EnvSettings().disable_session_browser == expected


def test_report_generator(run_pytest, local_html_path, report_subdir, make_test_file):
    """
    While the report generator could be tested by invoking directly, this test adds an extra layer of ensuring
    the correct default behavior is to write the report even if the test itself fails.
    """
    expected_filename = os.path.join(report_subdir, "index.html")
    assert not os.path.exists(expected_filename)
    make_test_file(
        f"""
        import pytest

        def test_force_failure(session_browser):
            session_browser.get("file://{local_html_path}")
            session_browser.snap()
        """
    )
    run_pytest("--report-dir", report_subdir)
    assert os.path.exists(expected_filename)


# The underscore here keeps pytest from executing this as a test itself.
def _test_happy_case(browser):
    browser.wait_for(XPathWithSubstringLocator(tag="button", displayed_substring="update"))
    browser.send_inputs("boundless")
    browser.click_button("update")
    browser.wait_for(XPathWithSubstringLocator(tag="p", displayed_substring="boundless"))
    assert len(browser.pngs) == 3


def test_clean_screenshots_on_startup(pytester, make_test_file, run_pytest, report_subdir):
    screens_dir = os.path.join(report_subdir, "screenshots")
    screenshot = os.path.join(screens_dir, "foo.png")
    pytester.mkdir(screens_dir)
    Path(screenshot).touch(exist_ok=True)
    make_test_file(
        f"""
    def test_a_thing(browser):
        pass
    """
    )
    assert os.path.exists(screenshot)
    run_pytest()
    assert not os.path.exists(screenshot)

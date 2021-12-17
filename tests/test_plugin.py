import json
import os
import shutil
from unittest import mock

import pytest

from webdriver_recorder.browser import Chrome, XPathWithSubstringLocator
from webdriver_recorder.plugin import lettergen

# Enables testing failure cases in plugin logic by dynamically generating
# and running plugin tests.
pytest_plugins = ["pytester"]


def test_happy_chrome(browser, load_page):
    """
    A simple test case to ensure the fixture itself works; the heavy lifting is all tested in the browser tests.
    """
    _test_happy_case(browser)


def test_browser_context(browser, browser_context):
    mock_get_patcher = mock.patch.object(browser, "get")
    mock_get = mock_get_patcher.start()
    mock_get = mock.patch.object(browser, "get").start()
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


def test_browser_error_failure_reporting(testdir, local_html_path, report_generator):
    """
    This uses the pytester plugin to execute ad-hoc tests in a new testing instance. This is the only way to test
    the logic of fixtures after their included `yield` statement, and is what the pytester plugin was designed to do.
    Here, we are asserting that the right cleanup behavior takes place when a BroswerError is bubbled from within
    a test.
    """
    testdir.makepyfile(
        f"""
        from webdriver_recorder.browser import BrowserError
        import pytest

        def test_force_failure(browser, report_test):
            browser.get("file://{local_html_path}")
            raise BrowserError(browser, 'forced failure')
        """
    )
    result = testdir.runpytest("--report-dir", report_generator)
    expected_slug = "test_browser_error_failure_reporting-py--test_force_failure"
    result.assert_outcomes(failed=1)
    expected_filename = os.path.join(report_generator, f"result.{expected_slug}.html")
    with open(expected_filename) as f:
        result = json.loads(f.read())

    assert result["failure"]["message"] == "forced failure"


def test_failure_reporting(testdir, local_html_path, report_generator):
    """
    Similar to test_browser_error_failure_reporting, but with a generic AssertionError. This is what we would expect
    to see under most failure circumstances.
    """
    testdir.makepyfile(
        f"""
        from webdriver_recorder.browser import BrowserError
        import pytest

        def test_force_failure(session_browser, report_test):
            session_browser.get("file://{local_html_path}")
            assert False
        """
    )
    result = testdir.runpytest("--report-dir", report_generator)
    expected_slug = "test_failure_reporting-py--test_force_failure"
    result.assert_outcomes(failed=1)
    expected_filename = os.path.join(report_generator, f"result.{expected_slug}.html")
    with open(expected_filename) as f:
        result = json.loads(f.read())

    assert "AssertionError" in result["failure"]["message"]


def test_report_generator(
    testdir,
    local_html_path,
):
    """
    While the report generator could be tested by invoking directly, this test adds an extra layer of ensuring
    the correct default behavior is to write the report even if the test itself fails.
    """
    report_dir = os.path.join(os.getcwd(), "tmp", "test-report")
    os.makedirs(report_dir, exist_ok=True)
    try:
        expected_filename = os.path.join(report_dir, "index.html")
        assert not os.path.exists(expected_filename)
        testdir.makepyfile(
            f"""
            import pytest

            def test_force_failure(session_browser, report_test):
                session_browser.get("file://{local_html_path}")
                session_browser.snap()
            """
        )
        result = testdir.runpytest("--report-dir", report_dir)
        expected_filename = os.path.join(report_dir, "index.html")
        assert os.path.exists(expected_filename)
    finally:
        shutil.rmtree(report_dir)


def test_lettergen():
    sequence = list(zip(lettergen(), list(range(1, 73715))))
    assert sequence[0] == ("A", 1)
    assert sequence[-1] == ("DEAD", 73714)


# The underscore here keeps pytest from executing this as a test itself.
def _test_happy_case(browser):
    browser.wait_for(XPathWithSubstringLocator(tag="button", displayed_substring="update"))
    browser.send_inputs("boundless")
    browser.click_button("update")
    browser.wait_for(XPathWithSubstringLocator(tag="p", displayed_substring="boundless"))
    assert len(browser.pngs) == 3

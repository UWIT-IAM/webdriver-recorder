import json
import os
import shutil

import pytest

from webdriver_recorder.browser import XPathWithSubstringLocator
from webdriver_recorder.plugin import lettergen

# Enables testing failure cases in plugin logic by dynamically generating
# and running plugin tests.
pytest_plugins = ['pytester']

@pytest.fixture(autouse=True)
def load_page(browser, local_html_path):
    """
    Opens the local testing example html without recording any snapshots (in order to keep the `pngs` clean by default).
    """
    with browser.autocapture_off():  # Don't generate any PNGs as part of the autoused fixture.
        browser.get(f'file://{local_html_path}')

def test_happy_chrome(chrome):
    """
    A simple test case to ensure the fixture itself works; the heavy lifting is all tested in the browser tests.
    """
    _test_happy_case(chrome)


def test_browser_error_failure_reporting(chrome, testdir, local_html_path, report_dir):
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
    result = testdir.runpytest('--report-dir', report_dir)
    expected_slug = 'test_browser_error_failure_reporting-py--test_force_failure'
    result.assert_outcomes(failed=1)
    expected_filename = os.path.join(report_dir,
                                     f'result.{expected_slug}.html')
    with open(expected_filename) as f:
        result = json.loads(f.read())

    assert result['failure']['message'] == 'forced failure'


def test_failure_reporting(chrome, testdir, local_html_path, report_dir):
    """
    Similar to test_browser_error_failure_reporting, but with a generic AssertionError. This is what we would expect
    to see under most failure circumstances.
    """
    testdir.makepyfile(
        f"""
        from webdriver_recorder.browser import BrowserError
        import pytest

        def test_force_failure(browser, report_test):
            browser.get("file://{local_html_path}")
            assert False
        """
    )
    result = testdir.runpytest('--report-dir', report_dir)
    expected_slug = 'test_failure_reporting-py--test_force_failure'
    result.assert_outcomes(failed=1)
    expected_filename = os.path.join(report_dir,
                                     f'result.{expected_slug}.html')
    with open(expected_filename) as f:
        result = json.loads(f.read())

    assert 'AssertionError' in result['failure']['message']


def test_report_generator(browser, report_generator, testdir, local_html_path):
    """
    While the report generator could be tested by invoking directly, this test adds an extra layer of ensuring
    the correct default behavior is to write the report even if the test itself fails.
    """
    report_dir = os.path.join(os.getcwd(), 'tmp', 'test-report')
    os.makedirs(report_dir, exist_ok=True)
    try:
        expected_filename = os.path.join(report_dir, 'index.html')
        assert not os.path.exists(expected_filename)
        testdir.makepyfile(
            f"""
            from webdriver_recorder.browser import BrowserError
            import pytest

            def test_force_failure(browser, report_test):
                browser.get("file://{local_html_path}")
                browser.snap()
            """
        )
        result = testdir.runpytest('--report-dir', report_dir)
        expected_filename = os.path.join(report_dir, 'index.html')
        assert os.path.exists(expected_filename)
    finally:
        shutil.rmtree(report_dir)


def test_lettergen():
    sequence = list(zip(lettergen(), list(range(1, 73715))))
    assert sequence[0] == ('A', 1)
    assert sequence[-1] == ('DEAD', 73714)


@pytest.mark.xfail(reason="The remote fixture is hard to test because it requires a locally running selenium instance, "
                          "which itself requires extra dependencies and configuration. "
                          "As long as we don't have anything relying on this, it's probably more trouble than "
                          "it's worth to setup.")
def test_happy_remote_chrome(remote_chrome):
    _test_happy_case(remote_chrome)


# The underscore here keeps pytest from executing this as a test itself.
def _test_happy_case(browser):
    browser.wait_for(XPathWithSubstringLocator(tag='button', displayed_substring='update'))
    browser.send_inputs('boundless')
    browser.click_button('update')
    browser.wait_for(XPathWithSubstringLocator(tag='p', displayed_substring='boundless'))
    assert len(browser.pngs) == 3

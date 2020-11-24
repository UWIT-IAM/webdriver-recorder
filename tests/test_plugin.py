import json
import os
import shutil
from contextlib import contextmanager
from typing import Any, Optional

import pytest

from webdriver_recorder.browser import XPathWithSubstringLocator, Chrome
from webdriver_recorder.plugin import lettergen

# Enables testing failure cases in plugin logic by dynamically generating
# and running plugin tests.
pytest_plugins = ['pytester']


@contextmanager
def preserve_environment_variable(var_name, new_value: Optional[Any] = None):
    """
    Preserves the state of an environment variable, re-setting it
    when the context exits.

    This seems verbose, but it's that way on purpose. MacOS comes with a
    vulnerability to a memory leak when setting environment variables without
    unsetting them first. The python docs warn about this, but also state that this
    is the recommended way to interact with environment variables, so this will
    explicitly unset variables before setting them to avoid this (probably not
    high-risk) leak vector.
    """
    existing_value = os.environ.get(var_name)
    if existing_value is not None:
        # Explicitly unset to avoid a memory leak on MacOS
        del os.environ[var_name]
    if new_value is not None:
        os.environ[var_name] = new_value
    yield
    if var_name in os.environ:
        del os.environ[var_name]
    if existing_value is not None:
        os.environ[var_name] = existing_value


@pytest.mark.parametrize('env_var, fixture, fixture_value', [
    ('NO_HEADLESS', 'disable_headless', True),
    ('W3C_COMPLY', 'disable_w3c', False)
])
@pytest.mark.parametrize('env_value, expected_results', [
    ("1", dict(passed=1)),
    (None, dict(failed=1)),
    ("", dict(failed=1)),
])
def test_env_var_fixtures(env_var, fixture, env_value, fixture_value,
                          expected_results, testdir):
    with preserve_environment_variable(env_var, new_value=env_value):
        testdir.makepyfile(
            f"""
            def test_fixture({fixture}):
                assert {fixture} is {fixture_value}
            """
        )
        result = testdir.runpytest()
        result.assert_outcomes(**expected_results)


def test_incorrect_chromedriver_bin(testdir):
    with preserve_environment_variable('CHROME_BIN', '/does/not/exist'):
        with preserve_environment_variable('NO_HEADLESS'):
            testdir.makepyfile(
                f"""
                def test_chromedriver_bin(browser):
                    browser.get('https://www.uw.edu')
                """
            )
            result = testdir.runpytest()
            result.assert_outcomes(error=1)



def test_browser_error_failure_reporting(testdir, local_html_path, report_dir):
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


def test_failure_reporting(testdir, local_html_path, report_dir):
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


def test_report_generator(testdir, local_html_path):
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
        result.assert_outcomes(passed=1)
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
                          "it's worth to set up.")
def test_happy_remote_chrome():
    assert False


def test_happy_case(testdir, local_html_path):
    testdir.makepyfile(
        f"""
        def test_happy_case(browser):
            browser.get({local_html_path})
            browser.wait_for(XPathWithSubstringLocator(tag='button', displayed_substring='update'))
            browser.send_inputs('boundless')
            browser.click_button('update')
            browser.wait_for(XPathWithSubstringLocator(tag='p', displayed_substring='boundless'))
            assert len(browser.pngs) == 3
        """
    )

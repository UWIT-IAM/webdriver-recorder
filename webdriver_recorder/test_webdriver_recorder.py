from webdriver_recorder import browser
import pytest
import time

def test_basic(browser):
    browser.get('https://en.wiktionary.org')
    time.sleep(1)
    browser.snap()
    browser.send_inputs('boundless')
    browser.send('\n')
    browser.wait_for('h1', 'boundless')
    browser.click('a', 'unbounded')
    assert len(browser.pngs) == 3


@pytest.fixture(autouse=True)
def report_test(report_test):
    """Turn on autouse for this module."""
    return report_test

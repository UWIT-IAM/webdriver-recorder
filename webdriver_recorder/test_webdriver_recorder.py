from webdriver_recorder import browser
import pytest
import time

def test_basic(browser):
    browser.get('https://google.com')
    time.sleep(1)
    browser.snap()
    browser.send('keyboard cat\n')
    browser.wait_for('a', 'keyboard cat')
    browser.click('a', 'images')
    assert len(browser.pngs) == 3


def test_xdist(browser):
    """pytest-xdist will run many tests in parallel. Test that."""
    browser.get('https://google.com')
    time.sleep(1)
    browser.snap()
    browser.send('kool aid man\n')
    browser.wait_for('a', 'kool aid man')
    browser.click('a', 'images')
    assert len(browser.pngs) == 3


@pytest.fixture(autouse=True)
def report_test(report_test):
    """Turn on autouse for this module."""
    return report_test

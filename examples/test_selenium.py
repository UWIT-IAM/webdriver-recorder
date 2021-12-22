import pytest

from webdriver_recorder.browser import BrowserError, By, Locator


@pytest.mark.parametrize('url', ('www.google.com', 'washington.edu', 'directory.uw.edu'))
def test_visit_sites(url, browser):
    """Visit a website and take a screenshot."""
    browser.get(f'https://{url}', snap=True)
    browser.wait_for(
        Locator(search_method=By.ID, search_value='search'),
        timeout=0.25
    )


def test_forced_failure(browser):
    raise BrowserError(browser, 'I made this happen.')


def test_lots_of_examples(browser):
    browser.get(f'https://weather.gov', snap=True)
    for i in range(25):
        browser.snap(context=f"Snap #{i + 1}")

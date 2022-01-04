import pytest
from webdriver_recorder.browser import By, Locator


class Locators:
    about_the_uw = Locator(search_method=By.ID, search_value='about-the-uw')


def test_visit_uw(browser):
    """
    Visits the UW home page. Note that if the home page changes,
    this test might fail! That's OK for this example.
    """
    browser.get('https://www.uw.edu', snap=True, caption="Be boundless.")
    browser.click_tag('a', 'About')
    browser.wait_for_tag('h2', 'About the UW', caption="🐺")


def test_force_failure(browser):
    browser.get('https://directory.uw.edu', snap=True)
    if not browser.find_elements(By.ID, 'does-not-exist'):
        browser.snap(
            caption="Manual error capture, but the test continues.",
            is_error=True
        )
    browser.wait_for(Locator(search_method=By.ID, search_value="does-not-exist"))

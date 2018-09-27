from webdriver_recorder import browser
import time

def test_basic(browser):
    browser.get('https://google.com')
    time.sleep(1)
    browser.snap()
    browser.send('keyboard cat\n')
    browser.click('a', 'images for keyboard cat')
    browser.wait_for('a', 'google images home')
    assert len(browser.pngs) == 3

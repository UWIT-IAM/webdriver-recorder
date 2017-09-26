from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_browser(
        *args, driver=webdriver.PhantomJS,
        default_width=400, default_height=800, default_wait_seconds=5,
        **kwargs):
    """Return an instance of a browser of type driver."""
    class BrowserRecorder(driver):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.set_window_size(width=default_width, height=default_height)
            self.pngs = []  # where to store the screenshots
            self.wait = Waiter(self, default_wait_seconds)

        def click(self, tag, substring=''):
            """
            Find tag containing substring and click it. No wait so it should
            already be in the DOM.
            """
            search = (By.XPATH, f"//{tag}[contains(.,'{substring}')]")
            self.find_element(*search).click()

        def click_button(self, substring=''):
            """
            Wait for a button with substring to become clickable then click it.
            """
            search = (By.XPATH,
                      f"//button[contains(.,'{substring}')]")
            self.wait.until(EC.element_to_be_clickable(search))
            self.find_element(*search).click()

        def wait_for(self, tag, substring):
            """Wait for tag containing substring to show up in the DOM."""
            search = (By.XPATH, f"//{tag}[contains(.,'{substring}')]")
            self.wait.until(EC.visibility_of_element_located(search))

        def snap(self):
            """Grab a screenshot and store it."""
            self.pngs.append(self.get_screenshot_as_base64())

        def send(self, *strings):
            """
            Send the list of strings to the window, with a TAB between each
            string.
            """
            chain = ActionChains(self)
            chain.send_keys(Keys.TAB.join(strings)).perform()

    return BrowserRecorder(*args, **kwargs)


class Waiter(WebDriverWait):
    """Custom WebDriverWait object that grabs a screenshot after every wait."""
    def __init__(self, driver, *args, **kwargs):
        super().__init__(driver, *args, **kwargs)
        self.__driver = driver

    def until(self, *arg, **kwargs):
        """Every time we wait, take a screenshot of the outcome."""
        try:
            super().until(*arg, **kwargs)
        finally:
            self.__driver.snap()


if __name__ == '__main__':
    browser = get_browser('node_modules/.bin/phantomjs')
    browser.get('https://github.com/UWIT-IAM/webdriver-recorder')
    browser.wait_for('a', 'webdriver-recorder')
    png = browser.pngs.pop()
    browser.close()
    print('<html><body><h1>Your result</h1>')
    print(f'<img src="data:image/png;base64,{png}">')
    print('</body></html>')

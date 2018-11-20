"""
BrowserRecorder class for recording snapshots between waits.
"""
import os
import time
from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class BrowserRecorder(webdriver.PhantomJS):
    """
    A selenium webdriver with some extra convenience utilities and some
    automatic screenshot capturing.
    """
    def __init__(self, *args, width=400, height=200, **kwargs):
        project_phantomjs = os.path.join('node_modules', '.bin', 'phantomjs')
        if not args and os.path.isfile(project_phantomjs):
            # First arg is path to phantomjs. See if it's in node_modules/.
            args = (project_phantomjs,)

        super().__init__(*args, **kwargs)
        self.set_window_size(width=width, height=height)
        self.pngs = []  # where to store the screenshots
        # optionally set by the caller for decryption in send_secret
        self.autocapture = True   # automatically capture screenshots

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.quit()

    @contextmanager
    def autocapture_off(self):
        """Context manager temporarily disabling automatic screenshot generation."""
        previous_autocapture = self.autocapture  # for nesting
        self.autocapture = False
        try:
            yield
        finally:
            self.autocapture = previous_autocapture

    def clear(self):
        """Clear the active element."""
        self.switch_to.active_element.clear()

    def click(self, tag, substring='', wait=True, timeout=5, capture_delay=0):
        """
        Find tag containing substring and click it.
        wait - give it time to show up in the DOM.
        """
        search = (By.XPATH, xpath_contains(f'//{tag}', substring))
        with self.wrap_exception(f'find tag "{tag}" with string "{substring}"'):
            if wait and timeout:
                wait = Waiter(self, timeout)
                wait.until(EC.element_to_be_clickable(search),
                            capture_delay=capture_delay)
            self.find_element(*search).click()

    def click_button(self, substring=''):
        """
        Wait for a button with substring to become clickable then click it.
        """
        search = (By.XPATH, xpath_contains(f'//button', substring))
        with self.wrap_exception(f'click button with string "{substring}" when clickable'):
            wait = Waiter(self, getattr(self, 'default_wait', 5))
            wait.until(EC.element_to_be_clickable(search))
            self.find_element(*search).click()

    def wait_for(self, tag, substring, timeout=None, capture_delay=0):
        """Wait for tag containing substring to show up in the DOM."""
        if timeout is None:
            timeout = getattr(self, 'default_wait', 5)
        search = (By.XPATH, xpath_contains(f'//{tag}', substring))
        with self.wrap_exception(f'wait for visibility of tag "{tag}" with string "{substring}"'):
            wait = Waiter(self, timeout)
            wait.until(EC.visibility_of_element_located(search),
                        capture_delay=capture_delay)

    def run_commands(self, commands):
        """
        Run a series of commands. The first item in a command is the
        browser method to call and the remaining items are the args to
        pass it.
        """
        for method, *args in commands:
            getattr(self, method)(*args)

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

    def send_inputs(self, *strings):
        elements = self.find_elements_by_css_selector('input')
        for element, string in zip(elements, strings):
            element.send_keys(string)

    def hide_inputs(self):
        """Obscure all text inputs on the current screen."""
        javascript = """
            var inputsToHide = document.querySelectorAll('input');
            Array.prototype.forEach.call(inputsToHide, function(el){
                if (!el.attributes['type'] || el.attributes['type'].value === 'text')
                    el.setAttribute('type', 'password');
            })
        """
        self.execute_script(javascript)

    def send_secret(self, *encrypted_strings):
        """
        Send the list of strings to the window, decrypting them first.
        We do this encrypted to keep the secrets from appearing in
        Tracebacks.
        """
        strings = [self.decrypt(string) for string in encrypted_strings]
        self.send(*strings)

    def decrypt(self, encrypted_text):
        """Method to decrypt text to be overridden."""
        raise NotImplementedError('decrypt should be overridden')

    @contextmanager
    def wrap_exception(self, message):
        """Wrap any exceptions caught in a BrowserError with message."""
        try:
            yield
        except Exception as e:
            if not self.autocapture:
                self.snap()
            raise BrowserError(self, message, str(e))


class Waiter(WebDriverWait):
    """Custom WebDriverWait object that grabs a screenshot after every wait."""
    def __init__(self, driver, timeout, *args, **kwargs):
        super().__init__(driver, timeout, *args, **kwargs)
        self.__driver = driver

    def until(self, *arg, capture_delay=0, **kwargs):
        """
        Every time we wait, take a screenshot of the outcome.
        capture_delay - when we're done waiting, wait just  a little longer
          for whatever animations to take effect.
        """
        try:
            super().until(*arg, **kwargs)
        finally:
            if self.__driver.autocapture:
                if capture_delay:
                    time.sleep(capture_delay)
                self.__driver.snap()


class BrowserError(Exception):
    """Error to raise for a meaningful browser error report."""
    def __init__(self, browser, message, *args):
        self.message = message
        self.url = browser.current_url
        self.logs = browser.get_log('browser')
        super().__init__(message, self.url, self.logs, *args)


def xpath_contains(node, substring):
    lc_translate = "translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"
    if '"' in substring:
        raise ValueError('double quotes in substring not supported')
    substring = substring.lower()
    return f'{node}[contains({lc_translate}, "{substring}")]'


if __name__ == '__main__':
    with BrowserRecorder() as browser:
        browser.get('https://github.com/UWIT-IAM/webdriver-recorder')
        browser.wait_for('a', 'webdriver-recorder')
        png = browser.pngs.pop()
    print('<html><body><h1>Your result</h1>')
    print(f'<img src="data:image/png;base64,{png}">')
    print('</body></html>')
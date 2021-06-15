"""BrowserRecorder class for recording snapshots between waits.
"""
import json
import os
import pprint
import time
from contextlib import contextmanager
from enum import Enum
from logging import getLogger
from typing import Optional, List, Tuple, TypeVar

import selenium.webdriver.remote.webdriver
from pydantic import BaseModel, Field
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = getLogger(__name__)

__all__ = [
    "BrowserRecorder",
    "Waiter",
    "BrowserError",
    "Chrome",
    "Remote",
    "Locator",
    "XPathWithSubstringLocator",
    "SearchMethod",
]


class SearchMethod(Enum):
    """
    An Enum based on selenium's By object, so that values can be explicitly declared.
    """

    ID = By.ID
    XPATH = By.XPATH
    LINK_TEXT = By.LINK_TEXT
    PARTIAL_LINK_TEXT = By.PARTIAL_LINK_TEXT
    NAME = By.NAME
    TAG_NAME = By.TAG_NAME
    CLASS_NAME = By.CLASS_NAME
    CSS_SELECTOR = By.CSS_SELECTOR


class Locator(BaseModel):
    """
    A base class for defining selenium search locators. Essentially this is meant to just be
    passed into selenium's _find_element/_find_elements functions. In some of the high-level selenium abstractions,
    this behavior is invisible, or must be late-bound. This allows for more flexibility with the webdriver_recorder
    API.

    Usage:

        danger_locator = Locator(search_method=SearchMethod.CSS_SELECTOR, search_value='div.panel.panel-danger')
        browser.find_element(*danger_locator.payload)
    """

    search_method: SearchMethod
    search_value: Optional[str]

    @property
    def payload(self) -> Tuple:
        return self.search_method.value, self._search_value

    @property
    def _search_value(self) -> str:
        return self.search_value or ""

    @property
    def state_description(self) -> str:
        return f"wait for {self._search_value} to be visible by method: {self.search_method.value}"


class XPathWithSubstringLocator(Locator):
    """
    The CSS spec does not allow for selectors based on element text, making XPath ideal for
    such searches. This subclass searches for a given tag with the substring displayed; matches are
    case-insensitive.

    locator = XPathWithSubstringLocator(tag='div', displayed_substring='hello')  # will match <div>HELLO</div>
    """

    search_method = Field(SearchMethod.XPATH, const=True)
    tag: str
    displayed_substring: str

    @property
    def _search_value(self) -> str:
        return _xpath_contains(f"//{self.tag}", self.displayed_substring)

    @property
    def state_description(self) -> str:
        return (
            f'wait for {self.tag} with contents "{self.displayed_substring}" '
            f"to be visible via xpath {self._search_value}"
        )


WebDriverType = TypeVar(
    "WebDriverType", bound=selenium.webdriver.remote.webdriver.WebDriver
)


class BrowserRecorder(selenium.webdriver.remote.webdriver.WebDriver):
    """
    A selenium webdriver with extra convenience utilities and
    automatic screenshot capturing.
    """

    pngs: List[bytes] = []  # store screenshots here. intentionally global

    def __init__(self, *args, width=400, height=200, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_window_size(width=width, height=height)
        self.autocapture = True  # automatically capture screenshots

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

    def get(self, url):

        return super().get(url)

    def delete_all_cookies(self):
        pass

    def clear(self):
        """Clear the active element."""
        self.switch_to.active_element.clear()

    def click(
        self,
        locator: Locator,
        wait: bool = True,
        timeout: int = 5,
        capture_delay: int = 0,
    ):
        """
        Find tag containing substring and click it.
        wait - give it time to show up in the DOM.
        """
        with self.wrap_exception(locator.state_description):
            if wait and timeout:
                wait = Waiter(self, timeout)
                element = wait.until(
                    EC.element_to_be_clickable(locator.payload),
                    capture_delay=capture_delay,
                )
            else:
                element = self.find_element(*locator.payload)
            element.click()

    def click_tag(self, tag: str, with_substring: str, **kwargs):
        """See wait_for_tag; this does the same thing for clicking on random elements."""
        return self.click(
            XPathWithSubstringLocator(tag=tag, displayed_substring=with_substring),
            **kwargs,
        )

    def click_button(self, substring: str = "", **kwargs):
        """
        Wait for a button with substring to become clickable then click it.
        """
        return self.click_tag("button", substring, **kwargs)

    def wait_for(
        self, locator: Locator, timeout: Optional[int] = None, capture_delay: int = 0
    ):
        """Wait for tag containing substring to show up in the DOM."""
        if timeout is None:
            timeout = getattr(self, "default_wait", 5)
        with self.wrap_exception(locator.state_description):
            wait = Waiter(self, timeout)
            return wait.until(
                EC.visibility_of_element_located(locator.payload),
                capture_delay=capture_delay,
            )

    def wait_for_tag(self, tag: str, with_substring: str, **kwargs):
        """
        Since the XPathWithSubstringLocator is still the best way to search by text, this shim provides
        easy access to it for dependents who want to upgrade to V3.0 but not have to use XPathWithSubstringLocator
        all over the place. This has the same signature as the legacy `wait_for`.
        """
        return self.wait_for(
            XPathWithSubstringLocator(tag=tag, displayed_substring=with_substring),
            **kwargs,
        )

    def run_commands(self, commands):
        """
        Run a series of commands. The first item in a command is the
        browser method to call and the remaining items are the args to
        pass it.
        """
        for method, *args in commands:
            getattr(self, method)(*args)

    def snap(self):
        """
        Store the screenshot as a base64 png in memory.
        Resize the window ahead of time so the full page shows in the shot.
        """
        size = self.get_window_size()
        height = int(self.execute_script("return document.body.scrollHeight"))
        # For remote webdriver the scrollHeight still shows a scroll bar.
        # Bump it up just a little.
        size["height"] = height + 120
        self.set_window_size(**size)
        self.pngs.append(self.get_screenshot_as_base64())

    def send(self, *strings):
        """
        Send the list of strings to the window, with a TAB between each
        string.
        """
        chain = ActionChains(self)
        chain.send_keys(Keys.TAB.join(strings)).perform()

    def send_inputs(self, *strings):
        elements = self.find_elements_by_css_selector("input")
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

    def open_tab(self):
        self.execute_script("window.open('');")
        self.switch_to.window(self.window_handles[-1])

    def close_tab(self):
        self.close()
        if self.window_handles:
            self.switch_to.window(self.window_handles[-1])

    @contextmanager
    def tab_context(self):
        self.open_tab()
        try:
            yield
        finally:
            self.close_tab()

    def send_secret(self, *encrypted_strings):
        """
        Send the list of strings to the window, decrypting them first.
        We do this encrypted to keep the secrets from appearing in
        Tracebacks.
        """
        strings = [self.decrypt(string) for string in encrypted_strings]
        self.send(*strings)

    def decrypt(self, encrypted_text):  # pragma: no cover
        """Method to decrypt text to be overridden."""
        raise NotImplementedError("decrypt should be overridden")

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

    def until(self, *arg, capture_delay: int = 0, **kwargs):
        """
        Every time we wait, take a screenshot of the outcome.
        capture_delay - when we're done waiting, wait just  a little longer
          for whatever animations to take effect.
        """
        try:
            element = super().until(*arg, **kwargs)
        finally:
            if self.__driver.autocapture:
                if capture_delay:
                    time.sleep(capture_delay)
                self.__driver.snap()
        return element


class BrowserError(Exception):
    """Error to raise for a meaningful browser error report."""

    def __init__(self, browser, message, *args):
        self.message = message
        self.url = browser.current_url
        self.logs = browser.get_log("browser")
        self.log_last_http(browser)
        super().__init__(message, self.url, self.logs, *args)

    @staticmethod
    def log_last_http(browser):
        """Log the last http transaction as an error."""

        if "har" not in browser.log_types:
            return
        logs = browser.get_log("har")
        if not logs:
            return
        last_message = json.loads(logs[-1].get("message", {}))
        entries = last_message.get("log", {}).get("entries", [])
        if not entries:
            return
        message = pprint.pformat(entries[-1])
        logger.error(f"Last HTTP transaction: {message}")


def _xpath_contains(node, substring):
    lc_translate = (
        "translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"
    )
    if '"' in substring:
        raise ValueError("double quotes in substring not supported")
    substring = substring.lower()
    return f'{node}[contains({lc_translate}, "{substring}")]'


class Chrome(BrowserRecorder, webdriver.Chrome):
    def __init__(self, *args, options=None, **kwargs):
        if not options:
            options = webdriver.ChromeOptions()
            options.binary_location = os.environ.get("CHROME_BIN")
            options.headless = True  # default to what works in CI.
            options.add_experimental_option("w3c", False)
        super().__init__(*args, options=options, **kwargs)


class Remote(BrowserRecorder, webdriver.Remote):
    capabilities = DesiredCapabilities

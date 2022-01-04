import json
import pprint
import string
import time
from contextlib import contextmanager
from enum import Enum
from hashlib import sha256
from logging import getLogger
from typing import Any, Callable, List, Optional, Tuple, Union

import selenium.webdriver.remote.webdriver
from pydantic import BaseModel, Field
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By as By_
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from webdriver_recorder.models import Image

logger = getLogger(__name__)

__all__ = [
    "BrowserRecorder",
    "Waiter",
    "BrowserError",
    "Chrome",
    "Remote",
    "Locator",
    "XPathWithSubstringLocator",
    "By",
]

_XPATH_TRANSLATE_CASE = f"translate(., '{string.ascii_uppercase}', '{string.ascii_lowercase}')"


class By(Enum):
    """
    An Enum based on selenium's By object, so that values can be explicitly declared.
    """

    ID = By_.ID
    XPATH = By_.XPATH
    LINK_TEXT = By_.LINK_TEXT
    PARTIAL_LINK_TEXT = By_.PARTIAL_LINK_TEXT
    NAME = By_.NAME
    TAG_NAME = By_.TAG_NAME
    CLASS_NAME = By_.CLASS_NAME
    CSS_SELECTOR = By_.CSS_SELECTOR


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

    search_method: By
    search_value: Optional[str]

    @property
    def payload(self) -> Tuple:
        return self.search_method.value, self._search_value

    @property
    def _search_value(self) -> str:
        return self.search_value or ""

    @property
    def description(self) -> str:
        desc = f"{self.search_method.value}"
        if self.search_value:
            desc = f'{desc} whose value is "{self.search_value}"'
        return desc


class XPathWithSubstringLocator(Locator):
    """
    The CSS spec does not allow for selectors based on element text, making XPath ideal for
    such searches. This subclass searches for a given tag with the substring displayed; matches are
    case-insensitive.

    locator = XPathWithSubstringLocator(tag='div', displayed_substring='hello')  # will match <div>HELLO</div>
    """

    search_method = Field(By.XPATH, const=True)
    tag: str
    displayed_substring: str

    @property
    def _search_value(self) -> str:
        return _xpath_contains(f"//{self.tag}", self.displayed_substring)

    @property
    def description(self) -> str:
        desc = f"tag[{self.tag}]"
        if self.displayed_substring:
            desc = f'{desc} containing the string "{self.displayed_substring}"'
        return desc


class BrowserRecorder(selenium.webdriver.remote.webdriver.WebDriver):
    """
    A selenium webdriver with extra convenience utilities and
    automatic screenshot capturing.
    """

    pngs: List[Image] = []  # store screenshots here. intentionally global

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maximize_window()
        self.autocapture = True  # automatically capture screenshots
        self.default_wait = kwargs.get("default_wait", 5)

    @contextmanager
    def autocapture_off(self):
        """Context manager temporarily disabling automatic screenshot generation."""
        previous_autocapture = self.autocapture  # for nesting
        self.autocapture = False
        try:
            yield
        finally:
            self.autocapture = previous_autocapture

    def _resolve_timeout(self, timeout_in: Optional[int]):
        if timeout_in is None:
            return self.default_wait
        return timeout_in

    def clear(self):
        """Clear the active element."""
        self.switch_to.active_element.clear()

    def click(self, locator: Locator, **kwargs):
        if "caption" not in kwargs:
            kwargs["caption"] = f"Click on {locator.description}"

        element = self.wait_until(locator, EC.element_to_be_clickable, **kwargs)
        element.click()
        return element

    def click_tag(self, tag: str, with_substring: str, **kwargs):
        """See wait_for_tag; this does the same thing for clicking on random elements."""
        return self.click(
            XPathWithSubstringLocator(tag=tag, displayed_substring=with_substring),
            **kwargs,
        )

    def find_element(self, by: Union[By, str] = By_.ID, value: Optional[Any] = None) -> WebElement:
        """Overrides the base find_element method to support the 'By' enum"""
        if isinstance(by, By):
            by = by.value
        return super().find_element(by, value)

    def find_elements(self, by: Union[By, str] = By_.ID, value: Optional[Any] = None) -> List[WebElement]:
        """Overrides the base find_element method to support the 'By' enum"""
        if isinstance(by, By):
            by = by.value
        return super().find_elements(by, value)

    def click_button(self, substring: str = "", **kwargs):
        """
        Wait for a button with substring to become clickable then click it.
        """
        return self.click_tag("button", substring, **kwargs)

    def wait_for(self, locator: Locator, **kwargs):
        """Wait for tag containing substring to show up in the DOM."""
        if "caption" not in kwargs:
            kwargs["caption"] = f"Wait for {locator.description}"

        return self.wait_until(locator, EC.visibility_of_element_located, **kwargs)

    def wait_until(
        self, locator: Locator, condition: Callable, timeout: Optional[int] = None, capture_delay: int = 0, **kwargs
    ):
        timeout = self._resolve_timeout(timeout)
        with self.wrap_exception(locator.description):
            wait = Waiter(self, timeout)
            return wait.until(
                condition(locator.payload),
                capture_delay=capture_delay,
                **kwargs,
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

    @contextmanager
    def _resize_for_screenshot(self):
        original_size = self.get_window_size()
        required_width = self.execute_script("return document.body.parentNode.scrollWidth")
        required_height = self.execute_script("return document.body.parentNode.scrollHeight")
        self.set_window_size(required_width, required_height)
        yield
        self.set_window_size(original_size["width"], original_size["height"])

    def get(self, url: string, snap: bool = False, caption: Optional[str] = None):
        self.execute_script("console.clear();")
        super().get(url)
        if self.autocapture and snap:
            if not caption:
                caption = f"Render {url}"
            self.snap(caption=caption)

    def snap(self, caption: Optional[str] = None, is_error: bool = False):
        """
        Store the screenshot as a base64 png in memory.
        Resize the window ahead of time so the full page shows in the shot.
        """
        with self._resize_for_screenshot():
            b64_image = self.find_element(By_.TAG_NAME, "body").screenshot_as_base64
        # The sha256 digest is used to fingerprint the image.
        # This can SIGNIFICANTLY reduce the payload of a report
        # artifact bundle by de-duplicating images, especially
        # in parametrized tests.
        b64_sha = sha256(b64_image.encode("UTF-8")).hexdigest()
        self.pngs.append(
            Image(
                url=f"screenshots/{b64_sha}.png",
                base64=b64_image,
                caption=caption,
                is_error=is_error,
            )
        )

    def send(self, *strings):
        """
        Send the list of strings to the window, with a TAB between each
        string.
        """
        chain = ActionChains(self)
        chain.send_keys(Keys.TAB.join(strings)).perform()

    def send_inputs(self, *strings):
        elements = self.find_elements(By.TAG_NAME.value, "input")
        for element, val in zip(elements, strings):
            element.send_keys(val)

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
            if not isinstance(e, BrowserError):
                err = BrowserError(self, message)
                err.orig = e
            else:
                err = e

            # Only capture this screenshot if the error occurred
            # in a context that didn't automatically log the error.
            if not self.pngs or not self.pngs[-1].is_error:
                try:
                    self.snap(caption=f"Python error: {type(e).__name__}", is_error=True)
                except WebDriverException:  # pragma: no cover
                    logger.warning(f"Could not take screenshot after encountering error {e=}.")

            raise err from None


class Waiter(WebDriverWait):
    """Custom WebDriverWait object that grabs a screenshot after every wait."""

    def __init__(self, driver, timeout, *args, **kwargs):
        super().__init__(driver, timeout, *args, **kwargs)
        self.__driver = driver

    def until(
        self, *args, capture_delay: int = 0, caption: Optional[str] = None, is_error: Optional[bool] = False, **kwargs
    ) -> WebElement:
        """
        Every time we wait, take a screenshot of the outcome.
        capture_delay - when we're done waiting, wait just  a little longer
          for whatever animations to take effect.
        """
        found = False
        caption = caption or ""
        err = None
        try:
            element = super().until(*args, **kwargs)
            found = True
        except Exception as e:
            err = BrowserError(self.__driver, str(e))
            err.orig = e
            raise err from None
        finally:
            if self.__driver.autocapture or err:
                if capture_delay:
                    time.sleep(capture_delay)
                self.__driver.snap(caption=caption, is_error=not found)
        return element


class BrowserError(Exception):
    """Error to raise for a meaningful browser error report."""

    def __init__(self, browser: BrowserRecorder, message, *args):
        self.message = message
        self.url = browser.current_url
        self.logs = browser.get_log("browser")
        self.log_last_http(browser)
        self.orig = None
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
    if '"' in substring:
        raise ValueError("double quotes in substring not supported")
    substring = substring.lower()
    return f'{node}[contains({_XPATH_TRANSLATE_CASE}, "{substring}")]'


class Chrome(BrowserRecorder, webdriver.Chrome):
    pass


class Remote(BrowserRecorder, webdriver.Remote):
    pass

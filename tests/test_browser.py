import json
import time
from datetime import datetime
from typing import Any, NoReturn, Optional
from unittest import mock

import pytest
from selenium.webdriver.remote.command import Command

from webdriver_recorder.browser import (
    BrowserError,
    By,
    Chrome,
    Locator,
    XPathWithSubstringLocator,
    _xpath_contains,
    logger,
)


@pytest.fixture
def url(local_html_path):
    return f"file://{local_html_path}"


def _fill_in_and_wait(browser, value: str, locator: Locator, capture_delay: int = 0) -> Any:
    browser.send_inputs(value)
    browser.click_button("update")
    return browser.wait_for(locator, capture_delay=capture_delay)


def be_boundless_and_wait(browser: Chrome, capture_delay: int = 0) -> NoReturn:
    """
    A convenience function for testing the same interactive path under different circumstances.
    :param browser:
    :param capture_delay:
    :return:
    """
    return _fill_in_and_wait(
        browser,
        value="be boundless",
        locator=XPathWithSubstringLocator(tag="p", displayed_substring="be boundless"),
        capture_delay=capture_delay,
    )


@pytest.mark.parametrize(
    "locator",
    [
        XPathWithSubstringLocator(tag="p", displayed_substring="be boundless"),
        Locator(search_method=By.CSS_SELECTOR, search_value="div#outputDiv"),
        Locator(search_method=By.ID, search_value="outputDiv"),
    ],
)
def test_wait_for(locator, browser, load_page):
    element = _fill_in_and_wait(browser, "be boundless", locator)
    assert element.text == "be boundless"


def test_wait_for_tag(browser, load_page):
    """Ensure that when wait_for is called using a tag with text, the element is found."""
    browser.send_inputs("be boundless")
    browser.click_button("update")
    assert browser.wait_for_tag("p", "be boundless")


def test_fill_and_clear(browser, load_page):
    browser.send_inputs("boundless")
    assert browser.switch_to.active_element.get_attribute("value") == "boundless"
    browser.clear()
    assert not browser.switch_to.active_element.get_attribute("value")


def test_run_commands(browser, load_page):
    browser.run_commands(
        [
            ("send_inputs", "boundless"),
            ("click_button", "update"),
            (
                "wait_for",
                XPathWithSubstringLocator(tag="p", displayed_substring="boundless"),
            ),
        ]
    )


def test_open_close_tab(browser, session_browser_disabled, load_page):
    offset = 0
    if session_browser_disabled:
        offset = 1
    assert len(browser.window_handles) == 2 - offset
    browser.open_tab()
    assert len(browser.window_handles) == 3 - offset
    browser.close_tab()
    assert len(browser.window_handles) == 2 - offset


@pytest.mark.parametrize("default_wait, input_wait, expected", [(1, 1, 1), (1, 2, 2), (1, None, 1), (1, 0, 0)])
def test_resolve_timeout(browser, default_wait, input_wait, expected):
    orig = browser.default_wait
    browser.default_wait = default_wait
    try:
        assert browser._resolve_timeout(input_wait) == expected
    finally:
        browser.default_wait = orig


def test_tab_context(browser, session_browser_disabled, load_page):
    offset = 0
    if session_browser_disabled:
        offset = 1
    with pytest.raises(RuntimeError):
        with browser.tab_context():
            assert len(browser.window_handles) == 3 - offset
            raise RuntimeError
    assert len(browser.window_handles) == 2 - offset


def test_snap(browser, load_page):
    assert not browser.pngs
    browser.snap()
    assert len(browser.pngs) == 1


def test_send(browser, load_page):
    time.sleep(0.5)
    browser.send("foo", "bar")
    browser.snap()
    assert browser.find_element(value="inputField").get_attribute("value") == "foo"
    assert browser.find_element(value="inputField2").get_attribute("value") == "bar"


def test_hide_inputs(browser, load_page):
    assert browser.find_element(value="inputField").get_attribute("type") == "text"
    browser.hide_inputs()
    assert browser.find_element(value="inputField").get_attribute("type") == "password"


def test_autocapture_default(browser, load_page):
    be_boundless_and_wait(browser)
    assert len(browser.pngs) == 2


def test_autocapture_off(browser, load_page):
    with browser.autocapture_off():
        be_boundless_and_wait(browser)
    assert not browser.pngs


def test_wait_capture_delay(browser, load_page):
    start_time = datetime.now()
    delay = 5
    be_boundless_and_wait(browser, capture_delay=delay)
    end_time = datetime.now()
    delta = end_time - start_time
    assert (delta.seconds) >= delay


# TODO: (goodtom) The `decrypt` behavior was implemented as abstract but never used; if we ever decide to make
#       practical use of it, this test should be updated, and the `decrypt()` override should be removed from
#       our browser test fixture.
def test_send_secret(browser, load_page):
    def decrypt(val: str):
        return val.replace("secret-", "")

    with mock.patch.object(browser, "decrypt", decrypt):
        time.sleep(0.5)
        browser.send_secret("secret-foo", "secret-bar")
        assert browser.find_element(value="inputField").get_attribute("value") == "foo"
        assert browser.find_element(value="inputField2").get_attribute("value") == "bar"


def test_failure(browser, load_page):
    with pytest.raises(BrowserError):
        browser.wait_for_tag("a", "does not exist", timeout=0)


@pytest.mark.parametrize(
    "locator,expected",
    [
        (Locator(search_method=By.CSS_SELECTOR, search_value="#hi"), 'css selector whose value is "#hi"'),
        (XPathWithSubstringLocator(tag="p", displayed_substring="hi"), 'tag[p] containing the string "hi"'),
    ],
)
def test_locator_description(locator, expected):
    assert locator.description == expected


class LogRecorder:
    def __init__(self):
        self.messages = []


@pytest.fixture
def log_recorder(monkeypatch):
    recorder = LogRecorder()
    monkeypatch.setattr(logger, "error", lambda msg: recorder.messages.append(msg))
    return recorder


def test_log_last_http_no_har(browser, log_recorder):
    err = BrowserError(browser=browser, message="oh no!")
    assert not log_recorder.messages


def test_log_last_http_empty_har(monkeypatch, browser, log_recorder):
    def patch_get_log(log_type):
        return ""

    _patch_and_create_browser_error(browser, monkeypatch, patch_get_log)
    assert not log_recorder.messages


def _patch_and_create_browser_error(browser, monkeypatch, patch_get_log):
    actual_execute = browser.execute

    def patch_execute(*args, **kwargs):
        if args[0] == Command.GET_AVAILABLE_LOG_TYPES:
            return {"value": ["har"]}
        return actual_execute(*args, **kwargs)

    monkeypatch.setattr(browser, "execute", patch_execute)
    monkeypatch.setattr(browser, "get_log", patch_get_log)

    return BrowserError(browser=browser, message="oh no!")


def test_log_last_http_with_har_no_entries(browser, log_recorder, monkeypatch):
    def patch_get_log(log_type):
        return [{"message": json.dumps({"log": {"entries": []}})}]

    _patch_and_create_browser_error(browser, monkeypatch, patch_get_log)
    assert not log_recorder.messages


def test_incorrect_xpath_contains():
    with pytest.raises(ValueError):
        _xpath_contains(None, '"')


def test_log_last_http_with_har(browser, log_recorder, monkeypatch):
    def patch_get_log(log_type):
        return [
            {
                "message": json.dumps(
                    {
                        "log": {
                            "entries": [
                                "entry #1",
                                "entry #2",
                            ]
                        }
                    }
                )
            }
        ]

    _patch_and_create_browser_error(browser, monkeypatch, patch_get_log)

    assert len(log_recorder.messages) == 1
    assert log_recorder.messages[0] == "Last HTTP transaction: 'entry #2'"


def test_wrap_exception_no_autocapture(browser, load_page):
    assert not browser.pngs
    with pytest.raises(BrowserError):
        # We should _always_ capture a snap of the page when something goes wrong,
        # but if there is an issue with the capture, don't worry about it.
        with browser.wrap_exception("expected exception"):
            raise AttributeError("oh noes!")
    assert len(browser.pngs) == 1


def test_locator_defaults():
    locator = Locator(search_method=By.CSS_SELECTOR, search_value="foo")
    assert locator.search_value == "foo"
    assert "css" in locator.description
    assert "foo" in locator.description


def test_click(browser, load_page):
    browser.send_inputs("be boundless")
    output_locator = Locator(search_method=By.CSS_SELECTOR, search_value="#outputDiv")
    button_locator = Locator(search_method=By.CSS_SELECTOR, search_value="#doUpdate")
    output_element = browser.find_element(*output_locator.payload)
    assert not output_element.text
    browser.click(button_locator)
    assert output_element.text == "be boundless"


@pytest.mark.parametrize(
    "snap, caption, expected_caption",
    [
        (True, None, "Render file://{local_html_path}"),
        (True, "Hello", "Hello"),
        (
            False,
            None,
            None,
        ),
    ],
)
def test_get_with_snap(browser, local_html_path, snap: bool, caption: Optional[str], expected_caption: Optional[str]):
    assert not browser.pngs
    browser.get(f"file://{local_html_path}", snap=snap, caption=caption)
    if expected_caption:
        assert browser.pngs[-1].caption == expected_caption.format_map(dict(local_html_path=local_html_path))
    else:
        assert not browser.pngs


def test_find_element_by(browser, load_page):
    assert browser.find_element(By.ID, "outputDiv")


def test_find_elements_by(browser, load_page):
    assert browser.find_elements(By.CSS_SELECTOR, "#outputDiv")

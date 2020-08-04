import json
import os
import time
from datetime import datetime
from typing import NoReturn, Any

import pytest
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.command import Command

from webdriver_recorder.browser import Chrome, BrowserError, logger, _xpath_contains, XPathWithSubstringLocator, \
    Locator, SearchMethod


@pytest.fixture
def url(local_html_path):
    return f'file://{local_html_path}'


@pytest.fixture(scope='session')
def session_browser():
    """Instantiating this is slow; to speed up tests, we'll use a single instance, but clean it up before each test."""
    class TestChrome(Chrome):
        def decrypt(self, encrypted_text):
            """This is never actually defined in our classes, which is not good, but appears to be unused. However,
            its intent seems important enough to leave tested as a stub for now. We can deal with how we want to
            implement our encryption processes when we actually need this in practice.

            This allows us to test the functional paths, even though there is no actual decryption going on.

            :returns: A string that has trimmed a leading `secret-`. ("secret-foo" becomes "foo")
            """
            return encrypted_text.replace('secret-', '')

    return TestChrome()


@pytest.fixture
def browser(session_browser, url) -> Chrome:
    """
    Opens the local testing page without the use of snapshots, to keep `pngs` clean.
    """
    with session_browser.autocapture_off():
        session_browser.get(url)
    yield session_browser
    session_browser.pngs = []


def _fill_in_and_wait(browser: Chrome, value: str, locator: Locator, capture_delay: int = 0) -> Any:
    browser.send_inputs(value)
    browser.click_button('update')
    return browser.wait_for(locator, capture_delay=capture_delay)


def be_boundless_and_wait(browser: Chrome, capture_delay: int = 0) -> NoReturn:
    """
    A convenience function for testing the same interactive path under different circumstances.
    :param browser:
    :param capture_delay:
    :return:
    """
    return _fill_in_and_wait(browser,
                             value='be boundless',
                             locator=XPathWithSubstringLocator(tag='p', displayed_substring='be boundless'),
                             capture_delay=capture_delay)


@pytest.mark.parametrize('locator', [
    XPathWithSubstringLocator(tag='p', displayed_substring='be boundless'),
    Locator(search_method=SearchMethod.CSS_SELECTOR, search_value='div#outputDiv'),
    Locator(search_method=SearchMethod.ID, search_value='outputDiv')
])
def test_wait_for(locator, browser):
    element = _fill_in_and_wait(browser, 'be boundless', locator)
    assert element.text == 'be boundless'


def test_wait_for_tag(browser):
    browser.send_inputs('be boundless')
    browser.click_button('update')
    assert browser.wait_for_tag('p', 'be boundless')


def test_context_stops_client_on_exit(url):
    class TestChrome(Chrome):
        def __init__(self):
            self.is_stopped = False
            super().__init__()

        def stop_client(self):
            self.is_stopped = True

    with TestChrome() as b:
        b.get(url)

    assert b.is_stopped


def test_fill_and_clear(browser):
    browser.send_inputs('boundless')
    assert browser.switch_to.active_element.get_attribute('value') == 'boundless'
    browser.clear()
    assert not browser.switch_to.active_element.get_attribute('value')


def test_run_commands(browser):
    browser.run_commands([
        ('send_inputs', 'boundless'),
        ('click_button', 'update'),
        ('wait_for', XPathWithSubstringLocator(tag='p', displayed_substring='boundless'))
    ])


def test_snap(browser):
    assert not browser.pngs
    browser.snap()
    assert len(browser.pngs) == 1


def test_send(browser):
    time.sleep(.5)
    browser.send('foo', 'bar')
    browser.snap()
    assert browser.find_element(value='inputField').get_attribute('value') == 'foo'
    assert browser.find_element(value='inputField2').get_attribute('value') == 'bar'


def test_hide_inputs(browser):
    assert browser.find_element(value='inputField').get_attribute('type') == 'text'
    browser.hide_inputs()
    assert browser.find_element(value='inputField').get_attribute('type') == 'password'


def test_autocapture_default(browser):
    be_boundless_and_wait(browser)
    assert len(browser.pngs) == 2


def test_autocapture_off(browser):
    with browser.autocapture_off():
        be_boundless_and_wait(browser)
    assert not browser.pngs


def test_wait_capture_delay(browser):
    start_time = datetime.now()
    delay = 5
    be_boundless_and_wait(browser, capture_delay=delay)
    end_time = datetime.now()
    delta = end_time - start_time
    assert(delta.seconds) >= delay


# TODO: (goodtom) The `decrypt` behavior was implemented as abstract but never used; if we ever decide to make
#       practical use of it, this test should be updated, and the `decrypt()` override should be removed from
#       our browser test fixture.
def test_send_secret(browser):
    time.sleep(.5)
    browser.send_secret('secret-foo', 'secret-bar')
    assert browser.find_element(value='inputField').get_attribute('value') == 'foo'
    assert browser.find_element(value='inputField2').get_attribute('value') == 'bar'


class LogRecorder:
    def __init__(self):
        self.messages = []


@pytest.fixture
def log_recorder(monkeypatch):
    recorder = LogRecorder()
    monkeypatch.setattr(logger, 'error', lambda msg: recorder.messages.append(msg))
    return recorder


def test_log_last_http_no_har(browser, log_recorder):
    err = BrowserError(browser=browser, message='oh no!')
    assert not log_recorder.messages


def test_log_last_http_empty_har(monkeypatch, browser, log_recorder):
    def patch_get_log(log_type):
        return ''

    actual_execute = browser.execute

    def patch_execute(*args, **kwargs):
        if args[0] == Command.GET_AVAILABLE_LOG_TYPES:
            return {'value': ['har']}
        return actual_execute(*args, **kwargs)

    monkeypatch.setattr(browser, 'execute', patch_execute)
    monkeypatch.setattr(browser, 'get_log', patch_get_log)

    err = BrowserError(browser=browser, message='oh no!')
    assert not log_recorder.messages


def test_log_last_http_with_har_no_entries(browser, log_recorder, monkeypatch):
    def patch_get_log(log_type):
        return [
            {
                'message': json.dumps({
                    'log': {
                        'entries': [
                        ]
                    }
                })
            }
        ]

    actual_execute = browser.execute

    def patch_execute(*args, **kwargs):
        if args[0] == Command.GET_AVAILABLE_LOG_TYPES:
            return {'value': ['har']}
        return actual_execute(*args, **kwargs)

    monkeypatch.setattr(browser, 'execute', patch_execute)
    monkeypatch.setattr(browser, 'get_log', patch_get_log)

    err = BrowserError(browser=browser, message='oh no!')
    assert not log_recorder.messages


def test_incorrect_chrome_bin():
    os.environ['CHROME_BIN'] = '/path/to/chrome'
    with pytest.raises(WebDriverException):
        browser = Chrome()
    del os.environ['CHROME_BIN']


def test_incorrect_xpath_contains():
    with pytest.raises(ValueError):
        _xpath_contains(None, '"')


def test_log_last_http_with_har(browser, log_recorder, monkeypatch):
    def patch_get_log(log_type):
        return [
            {
                'message': json.dumps({
                    'log': {
                        'entries': [
                            'entry #1',
                            'entry #2',
                        ]
                    }
                })
            }
        ]

    actual_execute = browser.execute

    def patch_execute(*args, **kwargs):
        if args[0] == Command.GET_AVAILABLE_LOG_TYPES:
            return {'value': ['har']}
        return actual_execute(*args, **kwargs)

    monkeypatch.setattr(browser, 'execute', patch_execute)
    monkeypatch.setattr(browser, 'get_log', patch_get_log)

    err = BrowserError(browser=browser, message='oh no!')
    assert len(log_recorder.messages) == 1
    assert log_recorder.messages[0] == "Last HTTP transaction: 'entry #2'"


def test_wrap_exception_no_autocapture(browser):
    assert not browser.pngs
    with pytest.raises(BrowserError):
        # We should _always_ capture a snap of the page when something goes wrong
        with browser.autocapture_off():
            with browser.wrap_exception('expected exception'):
                raise AttributeError('oh noes!')
    assert len(browser.pngs) == 1


def test_locator_defaults():
    locator = Locator(search_method=SearchMethod.CSS_SELECTOR, search_value='foo')
    assert locator.search_value == 'foo'
    assert 'css' in locator.state_description
    assert 'foo' in locator.state_description


@pytest.mark.parametrize('wait', [
    True,
    False
])
def test_click(browser, wait):
    browser.send_inputs('be boundless')
    output_locator = Locator(search_method=SearchMethod.CSS_SELECTOR, search_value='#outputDiv')
    button_locator = Locator(search_method=SearchMethod.CSS_SELECTOR, search_value='#doUpdate')
    output_element = browser.find_element(*output_locator.payload)
    assert not output_element.text
    browser.click(button_locator, wait=wait)
    assert output_element.text == 'be boundless'

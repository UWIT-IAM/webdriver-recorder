"""
webdriver_recorder provides a browser context and some pytest fixtures
for the reporting of recorded snapshots.

get_browser - returns a browser context and is completely independent of
    pytest

pytest fixtures:
browser - a phantomjs instance of get_browser
report_file - a fixture for handling the setup and teardown of the webdriver
   report. This is currently hardwired to write to webdriver-report.html
report_test - a fixture for reporting on an individual test run.
"""
import os
import re
import types
import pytest
import datetime
import itertools
import html
import json
import time
import tempfile
from contextlib import contextmanager, suppress
from string import ascii_uppercase
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import jinja2

TEMPLATE_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'report.template.html')

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


@pytest.fixture(scope='session')
def browser():
    """Keep a PhantomJS browser open while we run our tests."""
    with BrowserRecorder() as browser:
        yield browser


@pytest.fixture(scope='session')
def report_dir():
    """Fixture returning the directory containing our report files."""
    tempdir = os.path.join(os.getcwd(), 'webdriver-report')
    with suppress(FileExistsError):
        os.mkdir(tempdir)
    _, worker_file = tempfile.mkstemp(prefix='worker.', dir=tempdir)
    yield tempdir
    os.remove(worker_file)
    worker_files = (f for f in os.listdir(tempdir) if f.startswith('worker.'))
    if not any(worker_files):
        generate_report(tempdir)


@pytest.fixture()
def report_test(report_dir, request, browser):
    """
    Print the results to report_file after a test run.
    Import this into test files that use the browser.
    """
    yield
    nodeid = request.node.report_call.report.nodeid
    is_failed = request.node.report_call.report.failed
    doc = request.node.report_call.doc
    slug = re.sub(r'\W', '-', nodeid)
    header = {'link': slug, 'is_failed': is_failed, 'description': nodeid}
    failure = None
    if is_failed:
        excinfo = request.node.report_call.excinfo
        if isinstance(excinfo.value, BrowserError):
            e = excinfo.value
            failure = {
                'message': e.message,
                'url': e.url,
                'loglines': [log.get('message', '') for log in e.logs]
            }
        else:
            failure = {'message': str(excinfo)}
    result = {
        'link': slug,
        'doc': doc,
        'nodeid': nodeid,
        'pngs': browser.pngs,
        'failure': failure
    }

    filename = os.path.join(report_dir, f'result.{slug}.html')
    headerfile = os.path.join(report_dir, f'head.{slug}.html')
    with open(headerfile, 'w') as fd:
        json.dump(header, fd)
    with open(filename, 'w') as fd:
        json.dump(result, fd)
    browser.pngs = []  # clear the stored screenshots


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    This gives us hooks from which to report status post test-run.
    Import this into your conftest.py.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when == 'call':
        doc = getattr(getattr(item, 'function', None), '__doc__', None)
        item.report_call = types.SimpleNamespace(
            report=report,
            excinfo=call.excinfo,
            doc=doc)


def lettergen():
    """Return A, B, C, ..., AA, AB, AC, ..., BA, BB, BC, ..."""
    for repeat in range(1, 10):
        for item in itertools.product(ascii_uppercase, repeat=repeat):
            yield ''.join(item)


def xpath_contains(node, substring):
    lc_translate = "translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')"
    if '"' in substring:
        raise ValueError('double quotes in substring not supported')
    substring = substring.lower()
    return f'{node}[contains({lc_translate}, "{substring}")]'


def generate_report(report_dir, project='Identity.UW'):
    with open(TEMPLATE_FILE) as fd:
        template = jinja2.Template(fd.read())
    template.globals.update({
        'date': str(datetime.datetime.now()),
        'lettergen': lettergen,
        'zip': zip
    })
    headers = iterfiles(report_dir, 'head.')
    results = iterfiles(report_dir, 'result.')
    stream = template.stream(headers=headers, results=results, project=project)
    stream.dump(os.path.join(report_dir, 'index.html'))


def iterfiles(dir, prefix):
    """
    Iterate through the objects contained in files starting with prefix.
    Delete afterwards.
    """
    files = (f for f in os.listdir(dir) if f.startswith(prefix))
    for filename in sorted(files):
        filename = os.path.join(dir, filename)
        with open(filename) as fd:
            data = json.load(fd)
            os.remove(filename)
            yield data


if __name__ == '__main__':
    with BrowserRecorder() as browser:
        browser.get('https://github.com/UWIT-IAM/webdriver-recorder')
        browser.wait_for('a', 'webdriver-recorder')
        png = browser.pngs.pop()
    print('<html><body><h1>Your result</h1>')
    print(f'<img src="data:image/png;base64,{png}">')
    print('</body></html>')

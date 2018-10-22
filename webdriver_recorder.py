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
import types
import pytest
import datetime
import itertools
import html
import json
import time
from contextlib import contextmanager
from string import ascii_uppercase
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@contextmanager
def get_browser(
        *args, driver=webdriver.PhantomJS,
        default_width=400, default_height=200, **kwargs):
    """Return a browser context of type driver."""
    class BrowserRecorder(driver):
        """
        A selenium webdriver with some extra convenience utilities and some
        automatic screenshot capturing.
        """
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.set_window_size(width=default_width, height=default_height)
            self.pngs = []  # where to store the screenshots
            # optionally set by the caller for decryption in send_secret
            self.autocapture = True   # automatically capture screenshots

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

    browser = BrowserRecorder(*args, **kwargs)
    try:
        yield browser
    finally:
        browser.quit()


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
    with get_browser('node_modules/.bin/phantomjs') as browser:
        yield browser


@pytest.fixture(scope='session')
def report_file():
    """Open file webdriver-report.html during our test runs."""
    starttime = datetime.datetime.now()
    with open('webdriver-report.html', mode='w') as fd:
        fd.write("""
        <!DOCTYPE html>
        <html>
            <head>
                <title>Identity Signup Storyboard</title>
                <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0-beta/css/bootstrap.min.css" integrity="sha384-/Y6pD6FV/Vv2HJnA6t+vslU6fwYXjCFtcEpHbNJ0lyAFsXTsjBbfaDjzALeQsN6M" crossorigin="anonymous">
                <script src="https://code.jquery.com/jquery-3.2.1.slim.min.js" integrity="sha384-KJ3o2DKtIkvYIK3UENzmM7KCkRr/rE9/Qpg6aAZGJwFDMVNA/GpGFF93hXpG5KkN" crossorigin="anonymous"></script>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.11.0/umd/popper.min.js" integrity="sha384-b/U6ypiBEHpOf/4+1nzFpr53nxSS+GLCkfwBdFNTxtclqqenISfwAzpKaMNFNmj4" crossorigin="anonymous"></script>
                <script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0-beta/js/bootstrap.min.js" integrity="sha384-h0AbiXch4ZDo7tp9hKZ4TsHbi047NrKGLO3SEJAg45jXxnGIfYzk4Si90RDIqNm1" crossorigin="anonymous"></script>
                <style>
                  img {
                    vertical-align: text-top;
                    width: 200px;
                    border: 2px solid #ddd
                  }
                  h2 {
                    page-break-before: always;
                  }
                  .nav-link {
                    padding: 0
                  }
                </style>
            </head>
            <body style="margin: 20px;">
                <h1 class="h4">Results for Identity Signup Scenarios</h1>
                <nav class="nav flex-column"></nav>
        """)
        fd.write(f'<p>Started {starttime}</p>')
        yield fd
        fd.write('</body></html>')


TEST_COUNTER = iter(range(1, 10000))


@pytest.fixture()
def report_test(report_file, report_links, request, browser):
    """
    Print the results to report_file after a test run.
    Import this into test files that use the browser.
    """
    yield
    testnum = next(TEST_COUNTER)
    letters = letter_gen()
    nodeid = request.node.report_call.report.nodeid
    doc = request.node.report_call.doc or nodeid
    report_links.append(dict(name=nodeid, failed=request.node.report_call.report.failed))
    report_file.write(f'<h2 class="h5"><a name="{testnum}">Test #{testnum}</a>: {doc}</h2>')
    pngs = browser.pngs
    browser.pngs = []
    if doc != nodeid:
        report_file.write(f'<h3 class="h6">{nodeid}</p></h3>')
    if request.node.report_call.report.failed:
        excinfo = request.node.report_call.excinfo
        if isinstance(excinfo.value, BrowserError):
            e = excinfo.value
            log_lines = map(lambda data: html.escape(data.get('message', '')),
                            e.logs)
            msg = f"""
            <p><strong>The following action failed:</strong> {e.message}</p>
            <p><strong>Current url:</strong> {e.url}</p>
            <p><strong>Browser logs:</strong> {'<br>'.join(log_lines)}</p>
            """
        else:
            msg = str(excinfo)
        report_file.write(f'<div class="alert alert-danger">{msg}</div>')
    for png in pngs:
        report_file.write(
            f"""
            <figure class="figure">
                <figcaption class="figure-caption text-right">#{testnum}{next(letters)}</figcaption>
                <img src="data:image/png;base64,{png}" class="figure-img img-fluid">
            </figure>
            """)


@pytest.fixture(scope="session")
def report_links(report_file):
    """
    A fixture that gets appended it for every test that gets run to generate a
    table of contents. Each test appends its title, and we generate links from
    that. The link is of the form "#1" and the report_links list is 1-indexed.
    """
    test_results = []
    yield test_results
    links = []
    for index, result in enumerate(test_results, start=1):
        links.append(dict(link=index, title=result['name'], failed=result['failed']))
    links_json = json.dumps(links)

    # We know this after all the tests are run. Here's a little javascript
    # that'll append it to the <nav> element at the top.
    report_file.write("""
        <script>
            $(document).ready(() => {
                let navs = """ + links_json + """;
                let mapToLink = nav => {
                    let linkText = `Test #${nav.link} - ${nav.title}`;
                    if(nav.failed)
                        linkText += ' - <span class="text-danger">FAILED</span>';
                    return `<a class="nav-link" href="#${nav.link}">${linkText}</a>`;
                }
                $('nav').append(navs.map(mapToLink).join(''));
            });
        </script>
        """)


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


def letter_gen():
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


if __name__ == '__main__':
    with get_browser('node_modules/.bin/phantomjs') as browser:
        browser.get('https://github.com/UWIT-IAM/webdriver-recorder')
        browser.wait_for('a', 'webdriver-recorder')
        png = browser.pngs.pop()
    print('<html><body><h1>Your result</h1>')
    print(f'<img src="data:image/png;base64,{png}">')
    print('</body></html>')

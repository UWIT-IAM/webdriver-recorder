import types
import pytest
import datetime
import itertools
from string import ascii_uppercase
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

        def clear(self):
            """Clear the active element."""
            self.switch_to.active_element.clear()

        def click(self, tag, substring=''):
            """
            Find tag containing substring and click it. No wait so it should
            already be in the DOM.
            """
            search = (By.XPATH, xpath_contains(f'//{tag}', substring))
            self.find_element(*search).click()

        def click_button(self, substring=''):
            """
            Wait for a button with substring to become clickable then click it.
            """
            search = (By.XPATH, xpath_contains(f'//button', substring))
            self.wait.until(EC.element_to_be_clickable(search))
            self.find_element(*search).click()

        def wait_for(self, tag, substring):
            """Wait for tag containing substring to show up in the DOM."""
            search = (By.XPATH, xpath_contains(f'//{tag}', substring))
            self.wait.until(EC.visibility_of_element_located(search))

        def run_commands(self, commands):
            """
            Run a series of commands. The first item in a command is the
            browser method to call and the remaining items are the args to
            pass it.
            """
            for method, *args in commands:
                try:
                    getattr(self, method)(*args)
                except Exception as e:
                    inner = f'({e.__class__.__name__}: {e})'
                    msg = f'failed in {method} with {args} {inner}'
                    raise BrowserError(msg, self)

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


class BrowserError(Exception):
    """Error to raise for a meaningful browser error report."""
    def __init__(self, message, browser):
        self.message = message
        self.url = browser.current_url
        self.logs = browser.get_log('browser')
        super().__init__(message, self.url, self.logs)


@pytest.fixture(scope='session')
def browser():
    """Keep a PhantomJS browser open while we run our tests."""
    browser = get_browser('node_modules/.bin/phantomjs')
    yield browser
    browser.quit()


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
                </style>
            </head>
            <body>
                <h1 class="h4">Results for Identity Signup Scenarios</h1>
        """)
        fd.write(f'<p>Started {starttime}</p>')
        yield fd
        fd.write('</body></html>')


TEST_COUNTER = iter(range(1, 10000))


@pytest.fixture()
def report_test(report_file, request, browser):
    """
    Print the results to report_file after a test run.
    Import this into test files that use the browser.
    """
    yield
    testnum = next(TEST_COUNTER)
    letters = letter_gen()
    nodeid = request.node.report_call.report.nodeid
    doc = request.node.report_call.doc or nodeid
    report_file.write(f'<h2 class="h5">Test #{testnum}: {doc}</h2>')
    pngs = browser.pngs
    browser.pngs = []
    if doc != nodeid:
        report_file.write(f'<h3 class="h6">{nodeid}</p>')
    if request.node.report_call.report.failed:
        excinfo = request.node.report_call.excinfo
        if isinstance(excinfo.value, BrowserError):
            e = excinfo.value
            msg = f"""
            <p>{e.message}</p>
            <p><strong>Current url:</strong> {e.url}</p>
            <p><strong>Browser logs:</strong> {e.logs}</p>
            """
        else:
            msg = str(excinfo)
        report_file.write(f'<div class="alert alert-danger">{msg}</div>')
    report_file.write('<div>\n')
    for png in pngs:
        report_file.write(
            f"""
            <figure class="figure">
                <figcaption class="figure-caption text-right">#{testnum}{next(letters)}</figcaption>
                <img src="data:image/png;base64,{png}" class="figure-img img-fluid">
            </figure>
            """)
    report_file.write('</div>\n')


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
    browser = get_browser('node_modules/.bin/phantomjs')
    browser.get('https://github.com/UWIT-IAM/webdriver-recorder')
    browser.wait_for('a', 'webdriver-recorder')
    png = browser.pngs.pop()
    browser.quit()
    print('<html><body><h1>Your result</h1>')
    print(f'<img src="data:image/png;base64,{png}">')
    print('</body></html>')

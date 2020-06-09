import datetime
import html
import itertools
import json
import os
import re
import tempfile
import warnings
from string import ascii_uppercase
from typing import List, Any, Dict, Optional, Callable

import jinja2
import pytest
from pydantic import BaseModel, root_validator
from webdriver_manager.chrome import ChromeDriverManager

from . import browser as browser_

TEMPLATE_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'report.template.html')


def pytest_addoption(parser):
    group = parser.getgroup("webdriver_recorder")
    group.addoption(
        '--selenium-server',
        action='store',
        dest='selenium_server',
        default=None,
        help='Remote selenium webdriver to connect to (eg localhost:4444)',
    )
    group.addoption(
        '--report-dir',
        action='store',
        dest='report_dir',
        default=os.path.join(os.getcwd(), 'webdriver-report'),
        help='The path to the directory where artifacts should be stored.'
    )


class HTMLEscapeBaseModel(BaseModel):
    """
    Base model that automatically escapes all strings passed into it.
    """
    @root_validator(pre=True)
    def escape_strings(cls, values) -> Dict[str, Any]:
        values = dict(values)
        for k, v in values.items():
            if isinstance(v, str):
                values[k] = html.escape(str(v))
        return values


class ResultFailure(HTMLEscapeBaseModel):
    message: str
    url: Optional[str]
    loglines: Optional[List[str]]


class ResultAttributes(HTMLEscapeBaseModel):
    link: str
    doc: Optional[str]
    nodeid: str
    pngs: List[bytes]
    failure: Optional[ResultFailure]
    time1: str
    time2: str


class ResultHeader(HTMLEscapeBaseModel):
    link: str
    is_failed: bool
    description: str


class ReportResult(object):
    """
    A test result for passing to the report_test fixture.
    report -- a pytest test outcome
    excinfo -- exception info if there is any
    doc -- the docstring for the test if there is any
    """
    def __init__(self, report, excinfo, doc):
        self.report = report
        self.excinfo = excinfo
        self.doc = doc


@pytest.fixture(scope='session')
def browser(chrome):
    """Keep a browser open while we run our tests."""
    return chrome


@pytest.fixture(scope='session')
def chrome():
    if 'CHROME_BIN' not in os.environ:
        warnings.warn('Environment variable CHROME_BIN undefined. Using system default for Chrome.')
    with browser_.Chrome(ChromeDriverManager().install()) as browser:
        yield browser


# TODO (goodtom@) Figure out a way to test this
@pytest.fixture(scope='session')
def remote_chrome(request):  # pragma: no cover
    """
    Allows using the recorder as a proxy to a remote selenium server.
    """
    server = request.config.getoption('selenium_server') or os.environ.get('SELENIUM_SERVER', 'localhost:4444')
    capabilities = browser_.Remote.capabilities.CHROME
    browser_ctx = browser_.Remote(
        command_executor=f'http://{server}/wd/hub',
        desired_capabilities=capabilities)
    with browser_ctx as browser:
        yield browser


@pytest.fixture(scope='session')
def report_dir(report_generator, request) -> str:
    """Fixture returning the directory containing our report files. Overridable using `--report-dir`"""
    tempdir = request.config.getoption('report_dir')
    os.makedirs(tempdir, exist_ok=True)
    # Ensures we don't generate reports while tests running (unless explicitly requested) using report_generator().
    # The worker file is created at the beginning of the test session, and removed at the end (after the `yield` below).
    # If multiple testing threads are running concurrently, a report will not be generated until the last one completes.
    _, worker_file = tempfile.mkstemp(prefix='worker.', dir=tempdir)
    yield tempdir
    os.remove(worker_file)
    workers = (f for f in os.listdir(tempdir) if f.startswith('worker.'))
    if not any(workers):
        report_generator(tempdir)


@pytest.fixture(scope='session')
def report_generator() -> Callable:
    """Fixture returning a report_generator which could be customized."""
    return generate_report


@pytest.fixture
def report_test(report_dir, request, browser):
    """
    Print the results to report_file after a test run. Without this, the results of the test will not be saved.
    You can ensure this is always run by including the following in your conftest.py:

    @pytest.fixture(autouse=True)
    def report_test(report_test):
        return report_test
    """
    time1 = str(datetime.datetime.now())
    yield
    time2 = str(datetime.datetime.now())
    nodeid = request.node.report_call.report.nodeid
    is_failed = request.node.report_call.report.failed
    doc = request.node.report_call.doc
    slug = re.sub(r'\W', '-', nodeid)
    header = ResultHeader(link=slug, is_failed=is_failed, description=nodeid)
    failure = None
    if is_failed:
        excinfo = request.node.report_call.excinfo
        if isinstance(excinfo.value, browser_.BrowserError):
            e = excinfo.value
            failure = ResultFailure(
                message=e.message,
                url=e.url,
                loglines=[log.get('message', '') for log in e.logs]
            )
        else:
            failure = ResultFailure(message=str(excinfo))

    report = ResultAttributes(
        link=slug,
        doc=doc,
        nodeid=nodeid,
        pngs=browser.pngs,
        failure=failure,
        time1=time1,
        time2=time2,
    )

    filename = os.path.join(report_dir, f'result.{slug}.html')
    headerfile = os.path.join(report_dir, f'head.{slug}.html')

    with open(headerfile, 'w') as fd:
        fd.write(header.json())
    with open(filename, 'w') as fd:
        fd.write(report.json())
    browser.pngs.clear()


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
        item.report_call = ReportResult(
            report=report,
            excinfo=call.excinfo,
            doc=doc)


def lettergen():
    """
    Used to generate unique alpha tags.
    :return: A, B, C, ..., AA, AB, AC, ..., BA, BB, BC, ...
    """
    for repeat in range(1, 10):
        for item in itertools.product(ascii_uppercase, repeat=repeat):
            yield ''.join(item)


def generate_report(report_dir: str, project: str = 'Identity.UW'):
    """
    Uses the included HTML template to generate the final report, using the results found in `report_dir`. Can be
    called explicitly in order to do this at any time.
    """
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

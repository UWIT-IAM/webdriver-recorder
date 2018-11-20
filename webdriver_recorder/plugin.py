"""
plugin for the following pytest fixtures:

browser - a phantomjs instance BrowserRecorder
report_dir - a fixture for handling the setup and teardown of the webdriver
   report. The result will be written here as index.html.
report_test - a fixture for reporting on an individual test run.
report_generator - fixture that waits for the last worker to finish and
    generates the report.
"""
import os
import re
import tempfile
import itertools
import json
from contextlib import suppress
from string import ascii_uppercase
import datetime
import pytest
import jinja2
from .browser import BrowserRecorder, BrowserError

TEMPLATE_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'report.template.html')


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


@pytest.fixture(scope='session')
def report_generator(report_dir):
    """Fixture to generate the report when the last worker is done."""
    yield
    workers = (f for f in os.listdir(report_dir) if f.startswith('worker.'))
    if not any(workers):
        generate_report(report_dir)


@pytest.fixture()
def report_test(report_dir, request, browser, report_generator):
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
        item.report_call = ReportResult(
            report=report,
            excinfo=call.excinfo,
            doc=doc)


def lettergen():
    """Return A, B, C, ..., AA, AB, AC, ..., BA, BB, BC, ..."""
    for repeat in range(1, 10):
        for item in itertools.product(ascii_uppercase, repeat=repeat):
            yield ''.join(item)


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


class ReportResult(object):
    """
    A test result for passing to the report_test fixture.
    report -- a pytest test outcome
    excinfo -- exception info if there is any
    doc -- the docstring for the test if there is any
    """
    def __init__(self, report, excinfo, doc):
        self.report = report
        self.excinfo = excinfo,
        self.doc = doc

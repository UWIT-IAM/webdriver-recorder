import pytest
import os


CUR_DIR = os.path.dirname(os.path.abspath(__file__))
_local_html_path = os.path.join(CUR_DIR, 'data', 'index.html')


@pytest.fixture(scope='session')
def local_html_path():
    return _local_html_path


@pytest.fixture(autouse=True)
def load_page(browser, local_html_path):
    with browser.autocapture_off():  # Don't generate any PNGs as part of the autoused fixture.
        browser.get(f'file://{local_html_path}')


@pytest.fixture(autouse=True)
def report_test(report_test):
    return report_test

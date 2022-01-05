import os

import pytest

CUR_DIR = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="session")
def local_html_path(selenium_server):
    if selenium_server:
        root_dir = "/tests"
    else:
        root_dir = CUR_DIR
    return os.path.join(root_dir, "data", "index.html")


@pytest.fixture
def load_page(browser, local_html_path):
    assert os.path.exists(f"{local_html_path}")
    with browser.autocapture_off():  # Don't generate any PNGs as part of the autoused fixture.
        browser.get(f"file://{local_html_path}")

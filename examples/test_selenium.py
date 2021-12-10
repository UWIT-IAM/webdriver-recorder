import pytest


@pytest.mark.parametrize('url', ('www.google.com', 'washington.edu', 'directory.uw.edu'))
def test_visit_sites(url, browser):
    browser.get(f'https://{url}')

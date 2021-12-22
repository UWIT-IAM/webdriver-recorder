import pytest

@pytest.fixture(scope='session')
def report_title():
    return 'Webdriver Recorder example storyboards'

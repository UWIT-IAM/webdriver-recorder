import os
import time
from datetime import timedelta

from webdriver_recorder.models import Timed


def test_save_image_blank(browser, load_page):
    browser.snap()
    image = browser.pngs[0]
    image.base64 = None
    image.save("/tmp")
    assert not os.path.exists(os.path.join("/tmp", image.url))


def test_timed_duration():
    timed = Timed()
    time.sleep(1.2)
    assert timed.duration == "1s"


def test_timed_long_duration():
    timed = Timed()
    timed.start_time = timed.start_time - timedelta(minutes=2)
    assert timed.duration == "2m 0s"

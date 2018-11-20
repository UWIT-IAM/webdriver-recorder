# webdriver-recorder
This enhances selenium's webdriver to simplify the interface and capture
screenshots along the way. When run it will output html with screenshots
of different scenarios. This uses python3.4+ only.

## Installation
```
pip install uw-webdriver-recorder
npm install phantomjs-prebuilt  # or use a global phantomjs
```

## Running it
Assume the following file:

```python
"""test_42.py"""
def test_42(browser, report_test):
    """Check the answer."""
    browser.get('https://en.wikipedia.org/wiki/42_(number)')
    browser.wait_for('body', 'life, the universe, and everything')
```

You would then run the test with
```bash
pytest
```
When the test completes, you will have file `webdriver-report/index.html`, with a
screenshot for every `wait_for()` in your test.

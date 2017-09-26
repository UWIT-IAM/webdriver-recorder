# webdriver-recorder
This enhances selenium's webdriver to simplify the interface and capture
screenshots along the way. When run it will output html with screenshots
of different scenarios. This uses python3.6+ only.

## Installation
```
pip install -r requirements.txt
npm install phantomjs-prebuilt
```

## Running it
```
from webdriver_recorder import get_browser
browser = get_browser('node_modules/.bin/phantomjs')
browser.get('https://www.wikipedia.org')
```

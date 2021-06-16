# webdriver-recorder
This enhances selenium's webdriver to simplify the interface and capture
screenshots along the way. When run it will output html with screenshots
of different scenarios.

## Add this to your project

Python versions 3.6+ are supported.
If you rely on an older python3 version, you may want to pin your
version of webdriver-recorder to `<4.0.0`

```
# Using pip
pip install 'uw-webdriver-recorder>=4.0.0,<5.0.0'

# Using poetry
poetry add 'uw-webdriver-recorder>=4.0.0,<5.0.0'
```

## Requirements

`chromedriver` must be discoverable on your test environment PATH. See [Google's 
documentation](https://chromedriver.chromium.org/).

## Pytest Arguments

### `--report-dir`

(Optional). If provided, will override the default (`./webdriver-report`). 
This is the directory where worker locks and report artifacts will be stored.
Your report will be saved here as `index.html`.

### `--jinja-template`

(Optional). If provided, will override the default included with this package.
This must be the absolute path to your report template.

### `--report-title`

(Optional). The title for your report. You may also provide this as a 
test fixture. See [report_title](#report_title)

### `--selenium-server`

(Optional). Defaults to the `SELENIUM_SERVER` environment variable value, which may 
be blank. If not blank, a `Remote` instance will be created instead that will 
connect to the server provided.

## Browser/WebDriver Fixtures

This plugin makes several fixtures available to you:

### `session_browser`

A session-scoped browser instance.

```
def test_a_thing(session_browser):
    session_browser.get('https://www.example.com')
```

### `class_browser`

A class-scoped browser instance that preserves the state for 
the entire test class. The `class_browser` will always be open
to a new, clean tab, which will be closed when all tests
in the class have run.

```
@pytest.mark.usefixtures('class_browser')
class TestCollection:
    def test_a_thing(self):
        self.browser.get('https://www.example.com')
```

### `browser`

A function-scoped browser instance. Each test function 
that uses this fixture will have a fresh, clean tab, which
will be closed when the test function has completed.


### `browser_context`

If you do not want to use one of the above scopes, you 
can use the `browser_context` fixture directly, which 
creates and cleans up a tab for your scope.

When the scope exits, the tab's cookies are deleted, and the tab is closed.
You can optionally supply a list of additional urls to visit and clear cookies using 
the `cookie_urls` parameter. The default behavior (from Selenium) is to only delete
the cookies of the _current_ domain.

```
def test_a_thing(browser_context):
    with browser_context(cookie_urls=['https://www.example.com/']) as browser:
        browser.get('https://www.example.com/')
        browser.add_cookie({'name': 'foo', 'value': 'bar'})
        browser.get('https://www.uw.edu/')
        assert browser.current_url == 'https://www.uw.edu/'
        assert browser.get_cookie('foo')['value'] == 'bar'
    # Outside of the context, the context tab has closed, so the 
    assert not browser.current_url == 'https://www.uw.edu/' 
    browser.get('https://www.example.com/')
    assert not browser.get_all_cookies()
```

Calling `browser_context()` without arguments will use the `session_browser` 
by default; you may pass in your own instance if you choose to.

```
def test_a_thing(browser_context):
    fresh = webdriver_recorder.Chrome()
    with browser_context(fresh) as superfresh:
        superfresh.get('https://www.example.com')
```


## Settings Fixtures

You can fine-tune certain configuration by overriding fixtures. 

While you may find you want to override the `session_browser` or any 
of the above scopes for your tests, the defaults are meant to be 
self-cleaning and work out of the box. 

Before you override the core fixtures, first see if a setting or 
argument can help you make any adjustments you need:

### `chrome_options`

Use this to change which options your recorder uses when setting up the 
Chrome instance:

```
@pytest.fixture(scope='session')
def chrome_options(chrome_options):
    chrome_options.add_argument('--debug')
    return chrome_options
```

### `report_title`

Use this to change the title of your report. This is a better option
than the pytest argument (above) for cases where the title isn't 
expected to change much.

```
@pytest.fixture(scope='session')
def report_title():
    return "Testing all the things"
```


## Maintaining this plugin

### First-time developer setup

- Install [poetry](https://python-poetry.org) (if not already done)
- `poetry install`
- `poetry env use /path/to/python3.6+`

It is **highly recommended** that you use a [pyenv](https://github.com/pyenv/pyenv) version, e.g.:
`poetry env use ~/.pyenv/versions/3.7.7/bin/python`

- Set your chromedriver directory: 
  `export CHROMEDRIVER_DIR="$(poetry env list --full-path | cut -f1 -d' ')/bin"`
- Bootstrap chromedriver:
   - On **MacOS**: `CHROMEDRIVER_DIST=mac64 ./bootstrap_chromedriver.sh`
   - On **Linux**: `./bootstrap_chromedriver.sh`
   - On **Windows**: _Feel free to submit a pull request!_

If your system has chrome installed somewhere undiscoverable, you can explicitly provide the correct path by
setting the CHROME_BIN environment variable:

```
CHROME_BIN="/path/to/google-chrome-stable" pytest
```

### Periodic Setup

#### Updating Chromedriver

Once in a while you will need to re-run the 
`Set your chromedriver directory` and `Bootstrap chromedriver` 
steps above, because chromedriver will fall out of date 
with the Chrome binary. 

#### Patch dependencies

`poetry update && poetry lock && poetry run tox`

### Releasing Changes

To release a change out in the wild, you should use
the Github Actions UI.

1. Visit the [release workflow UI]
2. Click on `Run Workflow`
3. Select the branch you want to release.
4. Leave the `dry-run` option set to `true`.
5. Click `Run`

Wait for the dry run to complete in the `#iam-bots` slack channel.

If the dry run succeeded, validate the generated version number is what you expected 
and, if so, repeat steps 1–3 above, but change the `dry-run` option to `false`.

**This means you can create prereleases for any branch you're working on to test it 
with another package, before merging into `master`!**


#### Manual Release

If you want to release something without the use of
Github Actions, you can follow these steps:

Release changes using poetry: 

- `poetry update`
- `poetry lock`  
- `poetry version [patch|minor|major|prerelease]`
- `tox`
- `poetry publish --build`
  - username: `uw-it-iam`
  - password: Ask @tomthorogood!
  
### Testing Changes

`poetry run tox` (or simply `tox` if you are already in the `poetry shell`)

### Submitting Pull Requests

- (Recommended) Run [black](https://github.com/psf/black) -- this will
  be automated in the future: `black webdriver_recorder/*.py tests/*.py`
- Run validations before submitting using `tox`; this will prevent unnecessary churn in your pull request.


[release workflow ui]: https://github.com/UWIT-IAM/webdriver-recorder/actions/workflows/release.yml

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
pip install 'uw-webdriver-recorder'

# Using poetry
poetry add 'uw-webdriver-recorder'
```

## Requirements

The following table illustrates the compatible versions between
this (webdriver-recorder), python, and selenium:

| webdriver-recorder version | python version(s) | selenium version(s)
| --- | --- | --- |
| <4.0 | 3+ | <=3.141.59
| 4.0 | 3.6+ | <=3.141.59 |
| 5.0+ | 3.7+ | \>=4.1 |


If running without docker, `chromedriver` must be 
discoverable on your test environment PATH. 
See [Google's documentation](https://chromedriver.chromium.org/).

For convenience, you can use `./bootstrap_chromedriver.sh`.

## Running the examples with docker-compose

The provided [docker-compose.yml](docker-compose.yml) should work out of the box to
run simple tests.

The following code should work as-is (note: the result should be a failure!):

```bash
test_dir=$(pwd)/examples docker-compose up --build --exit-code-from test-runner
```

After, you can view the results by opening `./webdriver-report/index.html` in your 
browser of choice.

Note: if you are doing this for the first time, the initial build may take a couple 
of minutes.

If using the provided [docker-compose.yml](docker-compose.yml) to run
tests, you can change the number of nodes of your selenium grid by editing the  
`SE_NODE_MAX_SESSIONS` environment variable. This handle is provided by
the Selenium maintainers.


## Pytest Arguments

### `--report-dir`

Also as environment variable: `REPORT_DIR`

(Optional). If provided, will override the default (`./webdriver-report`). 
This is the directory where worker locks and report artifacts will be stored.
Your report will be saved here as `index.html` and `report.json`.

### `--jinja-template`

(Optional). If provided, will override the default included with this package.
This must be the absolute path to your report template. For more information
on creating or updating templates, see [docs/templating](docs/templating.md).

### `--report-title`

(Optional). The title for your report. You may also provide this as a 
test fixture. See [report_title](#report_title)

### `--selenium-server`

(Optional). Defaults to the `REMOTE_SELENIUM` environment variable value, 
which may be blank. If provided, a `Remote` instance 
will be created instead that will connect to the server provided.

## Browser/WebDriver Fixtures

This plugin makes several fixtures available to you:

### `session_browser`

A session-scoped browser instance. By default, this is always invoked, 
which may pose runtime errors (like stuck tests) if you have a constrained
selenium grid. You can disable this default behavior by 
setting `disable_session_browser=1` in your environment.

Note that you may still invoke the session_browser fixture with this option,
but it will not automatically be used.

```
def test_a_thing(session_browser):
    session_browser.get('https://www.example.com')
    
def test_another_thing(session_browser):
    # The page remains loaded from the previous test.
    assert session_browser.wait_for_tag('h1', 'welcome to example.com')
```


See also [browser](#browser).

### `class_browser`

A class-scoped browser instance that preserves the state for 
the entire test class. The `class_browser` will always be open
to a new, clean tab, which will be closed when all tests
in the class have run.


If you run with `disable_session_browser`, the class_browser will be a fresh
instance of the browser for each class where it is used.

```
@pytest.mark.usefixtures('class_browser')
class TestCollection:
    @pytest.fixture(autouse=True)
    def initialize_collection(class_browser): 
        self.browser = class_browser
        
    def test_a_thing(self):
        self.browser.get('https://www.example.com')
        
    def test_another_thing(self):
        assert self.browser.wait_for_tag('h1', 'welcome to example.com')
```

### `browser`

A function-scoped browser tab that automatically cleans up after itself before the 
tab is closed by deleting browser cookies from its last visited domain.

If running with `disable_session_browser`, a new instance will be created for each 
browser instead. This has significant performance impacts\*, but also guarantees the 
"cleanest" browser experience. 

\* see [Performance](#performance)


### `browser_context`

If you do not want to use one of the above scopes, you 
can use the `browser_context` fixture directly, which 
creates and cleans up a tab for the browser instance you provide. 

When the scope exits, the tab's cookies are deleted, and the tab is closed.
You can optionally supply a list of additional urls to visit and clear cookies using 
the `cookie_urls` parameter. (The default browser behavior is to only delete
the cookies of the _current_ domain.)

```
def test_a_thing(browser_context, chrome_options):
    # Let's create a custom instance of Chrome
    options.add_argument('--hide-scrollbars')
    browser = Chrome(options=chrome_options)
    
    with browser_context(
        browser, 
        cookie_urls=['https://www.example.com/']
    ) as browser:
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
than the pytest argument (above) for cases where you want to 
programmatically assemble the title during test setup.

```
@pytest.fixture(scope='session')
def report_title():
    return "Testing all the things"
```


## Maintaining this plugin

### First-time developer setup

- Install [poetry](https://python-poetry.org) (if not already done)
- `poetry env use /path/to/python3.7+`
- `poetry install`
- Run `./bootstrap_chromedriver.sh` -- doing this _after_ poetry setup will 
  automatically install to your poetry environment.

It is **highly recommended** that you use a [pyenv](https://github.com/pyenv/pyenv) version, e.g.:
`poetry env use ~/.pyenv/versions/3.8.8/bin/python`

### Periodic Setup

#### Updating Chromedriver

- When? If you see a message that chromedriver is out of date
- What do I do? `./bootstrap_chromedriver.sh`

#### Patch dependencies

- When? Whenever you need the latest release of something 
- What do I do? `poetry update && poetry lock && poetry run tox`

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
with another package, before merging into `main`!**


#### Manual Release

If you want to release something without the use of
Github Actions, you can follow these steps:

Release changes using poetry: 

- `poetry update`
- `poetry lock`  
- `poetry version [patch|minor|major|prerelease]`
- `poetry run tox`
- `poetry publish --build`
  - username: `uw-it-iam`
  - password: Ask @tomthorogood! (goodtom@uw.edu)
  
### Testing Changes

`poetry run tox` (or simply `tox` if you are already in the `poetry shell`)


### Submitting Pull Requests

- Run validations before submitting using `poetry run tox`; this will prevent 
unnecessary churn in your pull request.

[release workflow ui]: https://github.com/UWIT-IAM/webdriver-recorder/actions/workflows/release.yml

## Performance

Creating browser instances is very inefficient. It is recommended that you 
use the default behavior that configures a single browser instance
to use for all tests, that comes with an auto-managed context
for the `browser` fixture. 

In our own `tox` tests, you can observe the performance impact
directly. The `disable_session_browser` tox environment typically
takes more than double the amount of time to run than the same tests
using the default behavior.

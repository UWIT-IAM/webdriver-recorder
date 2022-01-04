# Migrating to Webdriver Recorder 5.0

This guide is for people who maintain packages that depend on 
Webdriver Recorder 4.0 and want to upgrade to this latest 
version of Webdriver Recorder.

Webdriver Recorder 5.0 integrates with Selenium 4, in addition to providing
first-class support for running inside Docker containers and some 
streamlined environment configuration.

Many efforts were made to keep the interfaces the same 
between the two versions, however, 5.0 is not strictly backwards compatible,
so dependents who wish to upgrade should follow this guide. The high-level migration 
checklist below should suffice for most dependents.


## High-level Migration Checklist

- [ ] Remove empty uses of `with browser_context()`; now, this always requires
      an argument: the browser with which you wish to create a new context.
      Instead, use: `with browser_context(browser)`
- [ ] Rename `SearchMethod` with `By`, which even more closely apes Selenium.
- [ ] Replace `click_button(..., wait=False)` with `click_button(..., timeout=0)`.
      This is not specific to `click_button` but applies to all `wait_for` and 
      `click_` methods provided by the `BrowserRecorder` class
- [ ] Ensure any artifacts you upload now upload the entire output directory,  
      not just the `index.html`; the new template results in static asset generation,
      instead of embedding all assets directly into the html file. 
- [ ] If your test suite needs to create a new browser instance for each test (not 
  recommended for performance reasons), you must set the `DISABLE_SESSION_BROWSER=true`
  environment variable.

## What changed?

### Bugfixes

- Screenshots no longer grow by 120px for each successive test within a given test case
- Errors during test setup are now more likely to show up on the report artifact
- Timeouts are now consistently applied

### New template features

- The generated template now saves images separately, instead of embedding them into 
  the HTML. This results in a drastic reduction in load time and file size.
- Uses [Twitter bootstrap 5.0](https://www.getbootstrap.com) for styling and 
  components, to provide an easier to use experience.
- Test results are now collapsed directly under the test name, making it easier
  to navigate to, link to, compare, and view test results.
- The report now has an option to only view failed tests, to make it easier to debug
  failures
- Python errors and browser console errors are now displayed in modals, as they are 
  often unhelpful in debugging, and can be confusing
- Screenshots are more easily viewed, and can be linked to
- Captions whose screenshots are marked with `is_error=True` will show up in red.
- The HTML report directly links to the JSON report


### New library features

- Updates Selenium dependencies from 3.141.x to 4.0.x
- Generated screenshots are SHA-256 fingerprinted, meaning two screenshots with the
  same contents will have the same filename. This results in a reduction of overall
  artifact size, as we no longer save duplicate images.
- Reports are saved not only as HTML but also JSON. 
- `click_on`, `get`, and `wait_for` events now automatically caption the resulting 
  screenshot, if no caption is provided.
- You can explicitly caption any of the above methods, as well as `snap()` by 
  providing a  `caption` keyword argument:
  `browser.get('https://www.uw.edu', caption="Load the UW home page")`.
- You may now provide the `is_error: bool` argument when calling `snap()`,
  which sets a flag on the image metadata and can be used in templating
- Directly linking to a test case will auto-expand its storyboard
- A new "Help" modal describes other front-end features.
- Timeouts are much easier to trace and understand now. If `timeout=None`, the 
  browser default (5s) will be used; you can change this by setting the `default_wait` 
  argument when creating a browser instance. If `timeout=0`, there will be no delay.
  While this was the _intended_ behavior before, there were a few different 
  implementations in the package, making it hard to tell what should be happening.
- Calling `click` now returns the element that was clicked; this cascades to any other
  `click_*` methods provided by the `BrowserRecorder` class.
- The `Chrome` and `Remote` classes no longer house any additional configuration, 
  meaning they both simply inherit from `BrowserRecorder`, 
  making it easier to use other browser types natively when desired.
- The `DISABLE_SESSION_BROWSER` environment variable is now the best and only way to
  instantiate a new browser for every test; this is not recommended and is therefore
  not the default.
- Default `chrome_options` have been updated to work more predictably with Selenium 4.
- The `build_browser` fixture now will create new browser instances based on 
  configured defaults.
- The `report_test` fixture now handles errors better, and can now provide some 
  limited failure information in the report for tests who were unable to start. 
  (Previously, tests that couldn't start were not present in the report artifact.)
- When a worker completes, the report of its tests are dumped into JSON; the root worker
  will consume other worker results and aggregate them into a single report when all 
  tests are complete.
- Dropped support for the `wait` argument; use `timeout=0` instead.
- `BrowserErrors` now swallow the exception chains, making output easier to read 
  when things go wrong.

### Better Building and Testing of this library

- `./bootstrap_chromedriver.sh` will now attempt to automatically detect a valid 
  destination and distribution for the chromedriver, making it easier for developers
  to set up and get going with this package.
- `poetry run tox -e bootstrap` will set up your poetry environment and update 
  chromedriver. Poetry must already be installed.
- Automated tests in Github Actions will now directly host the coverage report
  and browser report.
  [See Example](https://github.com/UWIT-IAM/webdriver-recorder/actions/runs/1627465302)
- `poetry run tox` will now:
    - Test with and without a single-browser-instance session 
    - Test with and without a docker container
    - Blacken all code
- `./validate-strict.sh` will run `tox` with a slightly different build variant that 
  does not re-format your code, but will error if it is not properly formatted. 
  (This is used in CI/CD for this package). Additionally, this method will skip some
  environment setup, assuming a clean environment.

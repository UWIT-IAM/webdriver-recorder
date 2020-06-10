# webdriver-recorder
This enhances selenium's webdriver to simplify the interface and capture
screenshots along the way. When run it will output html with screenshots
of different scenarios. This uses python3.4+ only.

## Installation
```
pip install uw-webdriver-recorder
```

## Maintaining this plugin

It is highly recommended that you create a virtualenv in your repository directory:

```
python3 -m virtualenv env  # Run once
source env/bin/activate
```

Otherwise, you'll need to make sure that dependencies for this package are natively discoverable on your system.
See [Requirements](#requirements).

To test this plugin, make sure you have `tox` installed (`pip install tox`) then run `tox`. This will test, lint, and 
run coverage reports. (If you have a virtualenv, make sure to activate it before running tox.)

To build this plugin for release, you can do `python setup.py sdist`, to prepare for uploading to PyPI, or you can
install to a local python environment with `pip install .` or even `python setup.py install`. All of these options 
should work just fine depending on your needs. A

**A note about local installation:** Installing by any means other than `pip install uw-webdriver-recorder` will 
show a version of `0.0.1`; that is because our versioning is managed by our repository tags and is only properly 
resolved by our release process.


## Requirements

You must have `chromedriver` available in your environment. 
See the [official documentation](https://chromedriver.chromium.org/) to understand the driver and its installation 
process. 

### Installing and configuring the chromedriver

For the purposes of testing and maintaining this package, there is a convenience script to help download and install
the `chromedriver`, a required binary for this plugin. For development, it is recommended that you install 
chromedriver to your virtualenv like so:

```
python3 -m virtualenv env
CHROMEDRIVER_DIST=mac64 ./bootstrap_chromedriver.sh   # The default install location is in env/bin
```

Then, it will always be in your path, as long as your working in your virtualenv (`source env/bin/activate`).

This script is not installed as part of this plugin, and is only available from the git repository. There are a number
of solutions available to install chromedriver on your system, but this plugin does not assume that responsibility.

If your system has chromedriver installed somewhere undiscoverable, you can explicitly provide the correct path by
setting the CHROME_BIN environment variable:

```
CHROME_BIN="/path/to/google-chrome-stable" pytest
```

## Running it
Assume the following file:

You would then run the test with
```bash
pytest
```

You can also pass the following options:

```bash
# The directory to store report artifacts. Defaults to ./webdriver-report
--report-dir /path/to/output  
# defaults to localhost:4444, only used with the `remote_chrome` fixture
--selenium-server http://some.remote.selenium/endpoint  
```

When the test completes, you will have file `webdriver-report/index.html`, with a
screenshot for every `wait_for()` in your test. You can also call `browser.snap()` to take a screenshot at any time. 

## Pytest Fixtures

To see examples of these fixtures and how they are used, refer to `tests/test_plugin.py`.

`browser`: The main interface for this plugin. By default, uses Chrome, but you 
may substitute your own as needed. 

`chrome`: Same as above, but is always Chrome.

`remote_chrome`: (_untested_) A Chrome browser proxy to a running remote selenium server.

`report_dir`: The directory where report artifacts are stored (see above)

`report_generator`: Used to explicitly generate reports. Synonymous with `browser_recorder.plugin.generate_report` 
but available as a fixture for convenience. (By default, reports are only generated at the end of a testing session.)

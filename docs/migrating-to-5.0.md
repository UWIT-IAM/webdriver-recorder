# Migrating to Webdriver Recorder 5.0

This guide is for people who maintain packages that depend on 
Webdriver Recorder 4.0 and want to upgrade to this latest 
version of Webdriver Recorder.

Webdriver Recorder 5.0 integrates with Selenium 4, in addition to providing
first-class support for running inside Docker containers and some 
streamlined environment configuration.

Many efforts were made to keep the interfaces the same 
between the two versions, however, 5.0 is not strictly backwards compatible,
so dependents who wish to upgrade should follow this guide. 


## High-level Checklist

- [ ] Remove empty uses of `with browser_context()`; now, this always requires
      an argument: the browser with which you wish to create a new context.
      Instead, use: `with browser_context(browser)`
- [ ] Replace `SearchMethod` with `By`, which even more closely apes Selenium
- [ ] Replace `click_button(..., wait=True)` with `click_button(..., timeout=0)`.
      This is not specific to `click_button` but applies to all `wait_for` and 
      `click_` methods
- 

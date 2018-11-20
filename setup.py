import os
import re
from setuptools import setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
VERSION_FILE = os.path.join(BASE_DIR, 'VERSION')

if os.path.isfile(VERSION_FILE):
    # tag written to 'VERSION' via CI.
    with open(VERSION_FILE) as fd:
        VERSION = fd.read().strip()
    VERSION = re.sub('^v', '', VERSION)
else:
    VERSION = '0.0.1'

desc = 'Enhances a selenium webdriver to record screenshots along the way'
with open(os.path.join(BASE_DIR, 'Readme.md')) as fd:
    long_description = fd.read()


setup(name='uw-webdriver-recorder',
      install_requires=['selenium', 'pytest', 'jinja2'],
      version=VERSION,
      description=desc,
      long_description=long_description,
      long_description_content_type="text/markdown",
      packages=['webdriver_recorder'],
      package_data={'webdriver_recorder': ['report.template.html']},
      python_requires='>=3.4',
      setup_requires=['pytest-runner'],
      entry_points={'pytest11': [
          'uw-webdriver-recorder = webdriver_recorder.plugin']},
      classifiers=["Framework :: Pytest"]
      )

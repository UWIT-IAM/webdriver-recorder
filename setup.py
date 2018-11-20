import os
import re
from setuptools import setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
VERSION_FILE = os.path.join(BASE_DIR, 'webdriver_recorder', 'VERSION')

def strip_comments(line): return line.split('#')[0]
VERSION = ''.join(map(strip_comments, open(VERSION_FILE).readlines())).strip()
VERSION = re.sub('^v', '', VERSION)

desc = 'Enhances a selenium webdriver to record screenshots along the way'
long_description = open(os.path.join(BASE_DIR, 'README.md')).read()


setup(name='uw-webdriver-recorder',
      install_requires=['selenium', 'pytest', 'jinja2'],
      url='https://github.com/UWIT-IAM/webdriver-recorder',
      author='UW-IT Identity and Access Management',
      author_email='jpf@uw.edu',
      version=VERSION,
      description=desc,
      license='Apache License, Version 2.0',
      long_description=long_description,
      long_description_content_type="text/markdown",
      packages=['webdriver_recorder'],
      package_data={'webdriver_recorder': ['VERSION', '*.html']},
      python_requires='>=3.4',
      setup_requires=['pytest-runner'],
      entry_points={'pytest11': [
          'uw-webdriver-recorder = webdriver_recorder.plugin']},
      classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Framework :: Pytest']
      )

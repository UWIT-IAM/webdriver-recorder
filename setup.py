#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from setuptools import setup


def strip_comments(line):
    return line.split('#')[0]


def file_path(*parts):
    CUR_DIR = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(CUR_DIR, *parts)


desc = 'Enhances a selenium webdriver to record screenshots along the way'

with open(file_path('webdriver_recorder/VERSION')) as f:
    version = ''.join(map(strip_comments, f.readlines())).strip()
    version = re.sub('^v', '', version)

with open(file_path('README.md')) as f:
    long_description = f.read()

setup(
    name='uw-webdriver-recorder',
    version=version,
    packages=['webdriver_recorder'],
    package_data={"webdriver_recorder": ['report.template.html', 'VERSION']},
    data_files=['README.md', 'webdriver_recorder/VERSION'],
    author='UW-IT Identity and Access Management',
    author_email='jpf@uw.edu',
    maintainer_email='goodtom@uw.edu',
    license='Apache Software License 2.0',
    url='https://github.com/uwit-iam/webdriver-recorder',
    description='desc',
    long_description=long_description,
    long_description_content_type="text/markdown",
    py_modules=['webdriver_recorder'],
    python_requires='>=3.4',
    install_requires=[
        'pytest>=3.5.0',
        'jinja2',
        'selenium',
        'pydantic',
        'webdriver-manager',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Operating System :: OS Independent',
        'Framework :: Pytest',
        'License :: OSI Approved :: Apache Software License',
    ],
    entry_points={
        'pytest11': [
            'uw-webdriver-recorder = webdriver_recorder.plugin',
        ],
    },
)

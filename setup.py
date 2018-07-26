from setuptools import setup

setup(name='webdriver-recorder',
      install_requires=['selenium', 'pytest'],
      version='0.3',
      description=(
          'Enhances a selenium webdriver to record screenshots along the way'),
      py_modules='webdriver_recorder',
      entry_points={'pytest11': [
          'webdriver_recorder = webdriver_recorder']}
      )

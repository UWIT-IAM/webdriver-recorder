from setuptools import setup

setup(name='webdriver-recorder',
      install_requires=['selenium', 'pytest', 'jinja2'],
      version='0.4',
      description=(
          'Enhances a selenium webdriver to record screenshots along the way'),
      py_modules=['webdriver_recorder'],
      setup_requires=['pytest-runner'],
      entry_points={'pytest11': [
          'webdriver_recorder = webdriver_recorder']}
      )

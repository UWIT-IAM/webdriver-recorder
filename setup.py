from setuptools import setup

setup(name='uw-webdriver-recorder',
      install_requires=['selenium', 'pytest', 'jinja2'],
      version='0.5',
      description=(
          'Enhances a selenium webdriver to record screenshots along the way'),
      packages=['webdriver_recorder'],
      package_data={'webdriver_recorder': ['report.template.html']},
      python_requires='>=3.5',
      setup_requires=['pytest-runner'],
      entry_points={'pytest11': [
          'uw-webdriver-recorder = webdriver_recorder.plugin']},
      classifiers=["Framework :: Pytest"]
      )

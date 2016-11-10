from setuptools import setup

setup(name='dappled',
      version='0.1.0',
      packages=['dappled'],
      entry_points={
          'console_scripts': [
              'dappled = dappled.__main__:main'
          ]
      },
      )
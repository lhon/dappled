from setuptools import setup

setup(name='dappled',
      version='0.1.1',
      packages=['dappled', 'dappled.lib'],
      entry_points={
          'console_scripts': [
              'dappled = dappled.__main__:main'
          ]
      },
      )
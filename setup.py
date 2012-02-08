from setuptools import setup
import os, sys

version = '1.20'

install_requires = [
  'setuptools',
  'zc.buildout',
]

try:
    import xml.etree
except ImportError:
    install_requires.append('elementtree')

try:
    import argparse
except ImportError:
    install_requires.append('argparse')

setup(name='mr.developer',
      version=version,
      description="A zc.buildout extension to ease the development of large projects with lots of packages.",
      long_description=open("README.rst").read() + "\n\n" +
                       open(os.path.join("docs", "HELP.txt")).read() +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Buildout",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
      keywords='',
      author='Florian Schulze',
      author_email='florian.schulze@gmx.net',
      url='http://github.com/fschulze/mr.developer',
      license='BSD',
      packages=['mr', 'mr.developer'],
      package_dir = {'': 'src'},
      namespace_packages=['mr'],
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      test_suite='mr.developer.tests',
      entry_points="""
      [console_scripts]
      develop = mr.developer.develop:develop
      [zc.buildout.extension]
      default = mr.developer.extension:extension
      """,
      )

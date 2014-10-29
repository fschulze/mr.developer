from setuptools import setup
import os
import sys

version = '1.32'

install_requires = [
    'setuptools',
    'zc.buildout']

tests_require = [
    'mock',
    'mr.developer.addon']

try:
    import xml.etree
    xml.etree  # shutup pyflakes
except ImportError:
    install_requires.append('elementtree')

try:
    import argparse
    argparse  # shutup pyflakes
except ImportError:
    install_requires.append('argparse')


def get_text_from_file(fn):
    text = open(fn, 'rb').read()
    if sys.version_info >= (2, 6):
        return text.decode('utf-8')
    return text


setup(name='mr.developer',
      version=version,
      description="A zc.buildout extension to ease the development of large projects with lots of packages.",
      long_description="".join([
          get_text_from_file("README.rst"),
          "\n\n",
          get_text_from_file(os.path.join("docs", "HELP.txt")),
          get_text_from_file(os.path.join("docs", "HISTORY.txt"))]),
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
          "Programming Language :: Python",
          "Programming Language :: Python :: 3",
          "Framework :: Buildout",
          "Topic :: Software Development :: Libraries :: Python Modules"],
      keywords='',
      author='Florian Schulze',
      author_email='florian.schulze@gmx.net',
      url='http://github.com/fschulze/mr.developer',
      license='BSD',
      packages=['mr', 'mr.developer', 'mr.developer.tests'],
      package_dir={'': 'src'},
      namespace_packages=['mr', 'mr.developer'],
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      tests_require=tests_require,
      extras_require={'test': tests_require},
      test_suite='mr.developer.tests',
      entry_points="""
      [console_scripts]
      develop = mr.developer.develop:develop
      [zc.buildout.extension]
      default = mr.developer.extension:extension
      [mr.developer.workingcopytypes]
      svn = mr.developer.svn:SVNWorkingCopy
      git = mr.developer.git:GitWorkingCopy
      gitsvn = mr.developer.gitsvn:GitSVNWorkingCopy
      hg = mr.developer.mercurial:MercurialWorkingCopy
      bzr = mr.developer.bazaar:BazaarWorkingCopy
      fs = mr.developer.filesystem:FilesystemWorkingCopy
      cvs = mr.developer.cvs:CVSWorkingCopy
      darcs = mr.developer.darcs:DarcsWorkingCopy
      """)

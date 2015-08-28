from setuptools import setup
import sys

version = '1.34'

install_requires = [
    'setuptools',
    'zc.buildout']

tests_require = [
    'mock',
    'mr.developer.addon']

try:
    import argparse
    argparse  # shutup pyflakes
except ImportError:
    # python 2.6 doesn't have it.
    install_requires.append('argparse')


def get_text_from_file(fn):
    text = open(fn, 'rb').read()
    return text.decode('utf-8')


setup(name='mr.developer',
      version=version,
      description="A zc.buildout extension to ease the development of large projects with lots of packages.",
      long_description="\n\n".join([
          get_text_from_file("README.rst"),
          get_text_from_file("HELP.rst"),
          get_text_from_file("CHANGES.rst")]),
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
      [mr.developer.commands]
      activate = mr.developer.commands:CmdActivate
      arguments = mr.developer.commands:CmdArguments
      checkout = mr.developer.commands:CmdCheckout
      deactivate = mr.developer.commands:CmdDeactivate
      help = mr.developer.commands:CmdHelp
      info = mr.developer.commands:CmdInfo
      list = mr.developer.commands:CmdList
      pony = mr.developer.commands:CmdPony
      purge = mr.developer.commands:CmdPurge
      rebuild = mr.developer.commands:CmdRebuild
      reset = mr.developer.commands:CmdReset
      status = mr.developer.commands:CmdStatus
      update = mr.developer.commands:CmdUpdate
      """)

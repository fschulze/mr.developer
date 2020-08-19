from pkg_resources import parse_version
from setuptools import setup
import sys


version = '2.0.1'


def has_environment_marker_support():
    """
    Tests that setuptools has support for PEP-426 environment marker support.

    The first known release to support it is 0.7 (and the earliest on PyPI seems to be 0.7.2
    so we're using that), see: http://pythonhosted.org/setuptools/history.html#id142

    References:

    * https://wheel.readthedocs.org/en/latest/index.html#defining-conditional-dependencies
    * https://www.python.org/dev/peps/pep-0426/#environment-markers
    """
    try:
        from setuptools import __version__ as setuptools_version
        return parse_version(setuptools_version) >= parse_version('0.7.2')
    except Exception as exc:
        sys.stderr.write("Could not test setuptools' version: %s\n" % exc)
        return False


install_requires = [
    'setuptools',
    'zc.buildout',
    'six',
    ]

tests_require = [
    'mock']

extras_require = {
    'test': tests_require}

if has_environment_marker_support():
    extras_require[':python_version=="2.6"'] = ['argparse']
else:
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
      # Get more strings from https://pypi.org/classifiers/
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.4",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Framework :: Buildout",
          "Topic :: Software Development :: Libraries :: Python Modules"],
      keywords='buildout extension vcs git develop',
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
      extras_require=extras_require,
      python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*",
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

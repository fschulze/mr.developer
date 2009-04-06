from setuptools import setup, find_packages
import os

version = '0.11'

setup(name='mr.developer',
      version=version,
      description="",
      long_description=open("README.txt").read() + "\n\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from http://www.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
        "Programming Language :: Python",
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
      install_requires=[
          'setuptools',
          'elementtree',
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      [console_scripts]
      develop = mr.developer.develop:develop
      [zc.buildout.extension]
      default = mr.developer.extension:extension
      """,
      )

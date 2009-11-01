# paula.testing.tests.py
#
# You can simply copy this file to your package and adjust it to your needs

from chaoflow.testing.crawler import create_test_suite

# File to test, relative to the package root
# all .py files are found
# all .txt files with corresponding .py file are found
files = [
#        'README.txt'
        ]

# We assume that this modules is in the root of your package
pkgname = __name__[:-6]

test_suite = create_test_suite(pkgname, files)

import doctest
import mr.developer.cvs
import unittest


def test_suite():
    return unittest.TestSuite([doctest.DocTestSuite(mr.developer.cvs)])

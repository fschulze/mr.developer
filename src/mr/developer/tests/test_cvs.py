import unittest
import doctest
import mr.developer.cvs

def test_suite():
    return unittest.TestSuite([doctest.DocTestSuite(mr.developer.cvs)])
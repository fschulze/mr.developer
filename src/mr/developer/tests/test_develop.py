from unittest import TestCase
import os
import tempfile
import shutil


class MockDevelop(object):
    pass


class TestCommand(TestCase):
    def setUp(self):
        self.develop = MockDevelop()
        self.develop.sources = ['foo', 'bar', 'baz', 'ham']
        self.develop.auto_checkout = set(['foo', 'ham'])

    def testEmptyMatchList(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages([])
        self.assertEquals(pkgs, set(['foo', 'bar', 'baz', 'ham']))

    def testEmptyMatchListAuto(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages([], auto_checkout=True)
        self.assertEquals(pkgs, set(['foo', 'ham']))

    def testSingleArgMatchingOne(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages(['ha'])
        self.assertEquals(pkgs, set(['ham']))

    def testSingleArgMatchingMultiple(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages(['ba'])
        self.assertEquals(pkgs, set(['bar', 'baz']))

    def testArgsMatchingOne(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages(['ha', 'zap'])
        self.assertEquals(pkgs, set(['ham']))

    def testArgsMatchingMultiple(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages(['ba', 'zap'])
        self.assertEquals(pkgs, set(['bar', 'baz']))

    def testArgsMatchingMultiple2(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages(['ha', 'ba'])
        self.assertEquals(pkgs, set(['bar', 'baz', 'ham']))

    def testSingleArgMatchingOneAuto(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages(['ha'], auto_checkout=True)
        self.assertEquals(pkgs, set(['ham']))

    def testSingleArgMatchingMultipleAuto(self):
        from mr.developer.develop import Command
        self.assertRaises(SystemExit, Command(self.develop).get_packages,
                          ['ba'], auto_checkout=True)

    def testArgsMatchingOneAuto(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages(['ha', 'zap'],
                                                  auto_checkout=True)
        self.assertEquals(pkgs, set(['ham']))

    def testArgsMatchingMultipleAuto(self):
        from mr.developer.develop import Command
        self.assertRaises(SystemExit, Command(self.develop).get_packages,
                          ['ba', 'zap'], auto_checkout=True)

    def testArgsMatchingMultiple2Auto(self):
        from mr.developer.develop import Command
        pkgs = Command(self.develop).get_packages(['ha', 'ba'],
                                                  auto_checkout=True)
        self.assertEquals(pkgs, set(['ham']))


class TestFindBase(TestCase):
    def setUp(self):
        self.location = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.location)

    def testEnvironmentVar(self):
        from mr.developer.develop import find_base
        subdir = os.path.join(self.location, 'subdir')
        os.mkdir(subdir)
        devdir = os.path.join(self.location, 'devdir')
        os.mkdir(devdir)
        open(os.path.join(devdir, '.mr.developer.cfg'), 'w').close()
        orig_dir = os.getcwd()
        try:
            os.chdir(subdir)
            self.assertRaises(IOError, find_base)
            os.environ['MRDEVELOPER_BASE'] = devdir
            self.assertEqual(find_base(), devdir)
        finally:
            os.chdir(orig_dir)
            if 'MRDEVELOPER_BASE' in os.environ:
                del os.environ['MRDEVELOPER_BASE']

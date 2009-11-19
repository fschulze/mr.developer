from unittest import TestCase


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

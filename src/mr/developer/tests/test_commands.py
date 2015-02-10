from mock import patch
from unittest import TestCase


class MockConfig(object):
    def __init__(self):
        self.develop = {}

    def save(self):
        pass


class MockDevelop(object):
    def __init__(self):
        from mr.developer.develop import ArgumentParser
        self.config = MockConfig()
        self.parser = ArgumentParser()
        self.parsers = self.parser.add_subparsers(title="commands", metavar="")


class MockSource(dict):
    def exists(self):
        return getattr(self, '_exists', True)


class TestCommand(TestCase):
    def setUp(self):
        self.develop = MockDevelop()
        self.develop.sources = ['foo', 'bar', 'baz', 'ham']
        self.develop.auto_checkout = set(['foo', 'ham'])

    def testEmptyMatchList(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages([])
        self.assertEquals(pkgs, set(['foo', 'bar', 'baz', 'ham']))

    def testEmptyMatchListAuto(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages([], auto_checkout=True)
        self.assertEquals(pkgs, set(['foo', 'ham']))

    def testSingleArgMatchingOne(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages(['ha'])
        self.assertEquals(pkgs, set(['ham']))

    def testSingleArgMatchingMultiple(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages(['ba'])
        self.assertEquals(pkgs, set(['bar', 'baz']))

    def testArgsMatchingOne(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages(['ha', 'zap'])
        self.assertEquals(pkgs, set(['ham']))

    def testArgsMatchingMultiple(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages(['ba', 'zap'])
        self.assertEquals(pkgs, set(['bar', 'baz']))

    def testArgsMatchingMultiple2(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages(['ha', 'ba'])
        self.assertEquals(pkgs, set(['bar', 'baz', 'ham']))

    def testSingleArgMatchingOneAuto(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages(['ha'], auto_checkout=True)
        self.assertEquals(pkgs, set(['ham']))

    def testSingleArgMatchingMultipleAuto(self):
        from mr.developer.commands import Command
        self.assertRaises(SystemExit, Command(self.develop).get_packages,
                          ['ba'], auto_checkout=True)

    def testArgsMatchingOneAuto(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages(['ha', 'zap'],
                                                  auto_checkout=True)
        self.assertEquals(pkgs, set(['ham']))

    def testArgsMatchingMultipleAuto(self):
        from mr.developer.commands import Command
        self.assertRaises(SystemExit, Command(self.develop).get_packages,
                          ['ba', 'zap'], auto_checkout=True)

    def testArgsMatchingMultiple2Auto(self):
        from mr.developer.commands import Command
        pkgs = Command(self.develop).get_packages(['ha', 'ba'],
                                                  auto_checkout=True)
        self.assertEquals(pkgs, set(['ham']))


class TestDeactivateCommand(TestCase):
    def setUp(self):
        from mr.developer.commands import CmdDeactivate
        self.develop = MockDevelop()
        self.develop.sources = dict(
            foo=MockSource(),
            bar=MockSource(),
            baz=MockSource(),
            ham=MockSource())
        self.develop.auto_checkout = set(['foo', 'ham'])
        self.develop.config.develop['foo'] = 'auto'
        self.develop.config.develop['ham'] = 'auto'
        self.cmd = CmdDeactivate(self.develop)

    def testDeactivateDeactivatedPackage(self):
        self.develop.config.develop['bar'] = False
        args = self.develop.parser.parse_args(args=['deactivate', 'bar'])
        _logger = patch('mr.developer.develop.logger')
        logger = _logger.__enter__()
        try:
            self.cmd(args)
        finally:
            _logger.__exit__()
        assert self.develop.config.develop == dict(
            bar=False,
            foo='auto',
            ham='auto')
        assert logger.mock_calls == []

    def testDeactivateActivatedPackage(self):
        self.develop.config.develop['bar'] = True
        args = self.develop.parser.parse_args(args=['deactivate', 'bar'])
        _logger = patch('mr.developer.commands.logger')
        logger = _logger.__enter__()
        try:
            self.cmd(args)
        finally:
            _logger.__exit__()
        assert self.develop.config.develop == dict(
            bar=False,
            foo='auto',
            ham='auto')
        assert logger.mock_calls == [
            ('info', ("Deactivated 'bar'.",), {}),
            ('warn', ("Don't forget to run buildout again, so the deactived packages are actually not used anymore.",), {})]

    def testDeactivateAutoCheckoutPackage(self):
        args = self.develop.parser.parse_args(args=['deactivate', 'foo'])
        _logger = patch('mr.developer.commands.logger')
        logger = _logger.__enter__()
        try:
            self.cmd(args)
        finally:
            _logger.__exit__()
        assert self.develop.config.develop == dict(
            foo=False,
            ham='auto')
        assert logger.mock_calls == [
            ('info', ("Deactivated 'foo'.",), {}),
            ('warn', ("Don't forget to run buildout again, so the deactived packages are actually not used anymore.",), {})]

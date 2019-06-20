from mock import patch
import pytest


class MockSource(dict):
    def exists(self):
        return getattr(self, '_exists', True)


class TestCommand:
    @pytest.fixture
    def command(self, develop):
        from mr.developer.commands import Command
        develop.sources = ['foo', 'bar', 'baz', 'ham']
        develop.auto_checkout = set(['foo', 'ham'])
        return Command(develop)

    def testEmptyMatchList(self, command):
        pkgs = command.get_packages([])
        assert pkgs == set(['foo', 'bar', 'baz', 'ham'])

    def testEmptyMatchListAuto(self, command):
        pkgs = command.get_packages([], auto_checkout=True)
        assert pkgs == set(['foo', 'ham'])

    def testSingleArgMatchingOne(self, command):
        pkgs = command.get_packages(['ha'])
        assert pkgs == set(['ham'])

    def testSingleArgMatchingMultiple(self, command):
        pkgs = command.get_packages(['ba'])
        assert pkgs == set(['bar', 'baz'])

    def testArgsMatchingOne(self, command):
        pkgs = command.get_packages(['ha', 'zap'])
        assert pkgs == set(['ham'])

    def testArgsMatchingMultiple(self, command):
        pkgs = command.get_packages(['ba', 'zap'])
        assert pkgs == set(['bar', 'baz'])

    def testArgsMatchingMultiple2(self, command):
        pkgs = command.get_packages(['ha', 'ba'])
        assert pkgs == set(['bar', 'baz', 'ham'])

    def testSingleArgMatchingOneAuto(self, command):
        pkgs = command.get_packages(['ha'], auto_checkout=True)
        assert pkgs == set(['ham'])

    def testSingleArgMatchingMultipleAuto(self, command):
        pytest.raises(
            SystemExit,
            command.get_packages, ['ba'], auto_checkout=True)

    def testArgsMatchingOneAuto(self, command):
        pkgs = command.get_packages(['ha', 'zap'], auto_checkout=True)
        assert pkgs == set(['ham'])

    def testArgsMatchingMultipleAuto(self, command):
        pytest.raises(
            SystemExit,
            command.get_packages, ['ba', 'zap'], auto_checkout=True)

    def testArgsMatchingMultiple2Auto(self, command):
        pkgs = command.get_packages(['ha', 'ba'], auto_checkout=True)
        assert pkgs == set(['ham'])


class TestDeactivateCommand:
    @pytest.fixture
    def develop(self, develop):
        develop.sources = dict(
            foo=MockSource(),
            bar=MockSource(),
            baz=MockSource(),
            ham=MockSource())
        develop.auto_checkout = set(['foo', 'ham'])
        develop.config.develop['foo'] = 'auto'
        develop.config.develop['ham'] = 'auto'
        return develop

    @pytest.fixture
    def cmd(self, develop):
        from mr.developer.commands import CmdDeactivate
        return CmdDeactivate(develop)

    def testDeactivateDeactivatedPackage(self, cmd, develop):
        develop.config.develop['bar'] = False
        args = develop.parser.parse_args(args=['deactivate', 'bar'])
        _logger = patch('mr.developer.develop.logger')
        logger = _logger.__enter__()
        try:
            cmd(args)
        finally:
            _logger.__exit__()
        assert develop.config.develop == dict(
            bar=False,
            foo='auto',
            ham='auto')
        assert logger.mock_calls == []

    def testDeactivateActivatedPackage(self, cmd, develop):
        develop.config.develop['bar'] = True
        args = develop.parser.parse_args(args=['deactivate', 'bar'])
        _logger = patch('mr.developer.commands.logger')
        logger = _logger.__enter__()
        try:
            cmd(args)
        finally:
            _logger.__exit__()
        assert develop.config.develop == dict(
            bar=False,
            foo='auto',
            ham='auto')
        assert logger.mock_calls == [
            ('info', ("Deactivated 'bar'.",), {}),
            ('warn', ("Don't forget to run buildout again, so the deactived packages are actually not used anymore.",), {})]

    def testDeactivateAutoCheckoutPackage(self, cmd, develop):
        args = develop.parser.parse_args(args=['deactivate', 'foo'])
        _logger = patch('mr.developer.commands.logger')
        logger = _logger.__enter__()
        try:
            cmd(args)
        finally:
            _logger.__exit__()
        assert develop.config.develop == dict(
            foo=False,
            ham='auto')
        assert logger.mock_calls == [
            ('info', ("Deactivated 'foo'.",), {}),
            ('warn', ("Don't forget to run buildout again, so the deactived packages are actually not used anymore.",), {})]


class TestHelpCommand:
    @pytest.fixture
    def cmd(self, develop):
        from mr.developer.commands import CmdHelp
        return CmdHelp(develop)

    def testHelp(self, cmd, develop, capsys):
        args = develop.parser.parse_args(args=['help'])
        cmd(args)
        out, err = capsys.readouterr()
        assert 'Available commands' in out

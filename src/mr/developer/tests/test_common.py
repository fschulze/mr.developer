from mr.developer.common import Config, Rewrite
from mr.developer.common import get_commands, parse_buildout_args, version_sorted
import pytest


def test_find_internal_commands():
    cmds = [x.__name__ for x in get_commands()]
    assert 'CmdActivate' in cmds
    assert 'CmdDeactivate' in cmds
    assert 'CmdHelp' in cmds


class TestParseBuildoutArgs:
    def checkOptions(self, options):
        for option in options:
            assert len(option) == 3

    def testTimeoutValue(self):
        options, settings, args = parse_buildout_args(['-t', '5'])
        self.checkOptions(options)

    def testCommands(self):
        options, settings, args = parse_buildout_args(['-t', '5'])
        assert len(args) == 0
        options, settings, args = parse_buildout_args(['-t', '5', 'install', 'partname'])
        assert len(args) == 2

    def testAssignments(self):
        # You can override parameters from buildout sections on the command line.
        options, settings, args = parse_buildout_args(['versions:foo=42'])
        self.checkOptions(options)
        assert options[0] == ('versions', 'foo', '42')
        assert len(args) == 0
        # Without a colon in it, zc.buildout itself defaults to the
        # 'buildout' section.  Issue 151.
        options, settings, args = parse_buildout_args(['foo=42'])
        self.checkOptions(options)
        assert options[0] == ('buildout', 'foo', '42')
        assert len(args) == 0


def test_buildout_args_key_is_str(tempdir):
    config = Config('.')
    config_file = tempdir['config.cfg']
    config_file.create_file(
        "[buildout]",
        "args = './bin/buildout'",
        "       '-c'",
        "       'buildout.cfg'")
    read_config = config.read_config(config_file)
    assert type(read_config.get('buildout', 'args')) == str


class TestRewrites:
    def testMissingSubstitute(self):
        pytest.raises(ValueError, Rewrite, ("url ~ foo"))

    def testInvalidOptions(self):
        pytest.raises(ValueError, Rewrite, ("name ~ foo\nbar"))
        pytest.raises(ValueError, Rewrite, ("path ~ foo\nbar"))

    def testPartialSubstitute(self):
        rewrite = Rewrite("url ~ fschulze(/mr.developer.git)\nme\\1")
        source = dict(url="https://github.com/fschulze/mr.developer.git")
        rewrite(source)
        assert source['url'] == "https://github.com/me/mr.developer.git"

    def testExactMatch(self):
        rewrite = Rewrite("url ~ fschulze(/mr.developer.git)\nme\\1\nkind = git")
        sources = [
            dict(url="https://github.com/fschulze/mr.developer.git", kind='git'),
            dict(url="https://github.com/fschulze/mr.developer.git", kind='gitsvn'),
            dict(url="https://github.com/fschulze/mr.developer.git", kind='svn')]
        for source in sources:
            rewrite(source)
        assert sources[0]['url'] == "https://github.com/me/mr.developer.git"
        assert sources[1]['url'] == "https://github.com/fschulze/mr.developer.git"
        assert sources[2]['url'] == "https://github.com/fschulze/mr.developer.git"

    def testRegexpMatch(self):
        rewrite = Rewrite("url ~ fschulze(/mr.developer.git)\nme\\1\nkind ~= git")
        sources = [
            dict(url="https://github.com/fschulze/mr.developer.git", kind='git'),
            dict(url="https://github.com/fschulze/mr.developer.git", kind='gitsvn'),
            dict(url="https://github.com/fschulze/mr.developer.git", kind='svn')]
        for source in sources:
            rewrite(source)
        assert sources[0]['url'] == "https://github.com/me/mr.developer.git"
        assert sources[1]['url'] == "https://github.com/me/mr.developer.git"
        assert sources[2]['url'] == "https://github.com/fschulze/mr.developer.git"

    def testRegexpMatchAndSubstitute(self):
        rewrite = Rewrite("url ~ fschulze(/mr.developer.git)\nme\\1\nurl ~= ^http:")
        sources = [
            dict(url="http://github.com/fschulze/mr.developer.git"),
            dict(url="https://github.com/fschulze/mr.developer.git"),
            dict(url="https://github.com/fschulze/mr.developer.git")]
        for source in sources:
            rewrite(source)
        assert sources[0]['url'] == "http://github.com/me/mr.developer.git"
        assert sources[1]['url'] == "https://github.com/fschulze/mr.developer.git"
        assert sources[2]['url'] == "https://github.com/fschulze/mr.developer.git"


def test_version_sorted():
    expected = [
        'version-1-0-1',
        'version-1-0-2',
        'version-1-0-10']
    actual = version_sorted([
        'version-1-0-10',
        'version-1-0-2',
        'version-1-0-1'])
    assert expected == actual

from unittest import TestCase


class TestParseBuildoutArgs(TestCase):
    def setUp(self):
        from mr.developer.common import parse_buildout_args
        self.parse_buildout_args = parse_buildout_args

    def checkOptions(self, options):
        for option in options:
            self.assertEquals(len(option), 3)

    def testTimeoutValue(self):
        options, settings, args = self.parse_buildout_args(['-t', '5'])
        self.checkOptions(options)

    def testCommands(self):
        options, settings, args = self.parse_buildout_args(['-t', '5'])
        self.assertEquals(len(args), 0)
        options, settings, args = self.parse_buildout_args(['-t', '5', 'install', 'partname'])
        self.assertEquals(len(args), 2)


class TestRewrites(TestCase):
    def setUp(self):
        from mr.developer.common import Rewrite
        self.Rewrite = Rewrite

    def testMissingSubstitute(self):
        self.assertRaises(ValueError, self.Rewrite, ("url ~ foo"))

    def testInvalidOptions(self):
        self.assertRaises(ValueError, self.Rewrite, ("name ~ foo\nbar"))
        self.assertRaises(ValueError, self.Rewrite, ("path ~ foo\nbar"))

    def testPartialSubstitute(self):
        rewrite = self.Rewrite("url ~ fschulze(/mr.developer.git)\nme\\1")
        source = dict(url="https://github.com/fschulze/mr.developer.git")
        rewrite(source)
        assert source['url'] == "https://github.com/me/mr.developer.git"

    def testExactMatch(self):
        rewrite = self.Rewrite("url ~ fschulze(/mr.developer.git)\nme\\1\nkind = git")
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
        rewrite = self.Rewrite("url ~ fschulze(/mr.developer.git)\nme\\1\nkind ~= git")
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
        rewrite = self.Rewrite("url ~ fschulze(/mr.developer.git)\nme\\1\nurl ~= ^http:")
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
    from mr.developer.common import version_sorted
    expected = [
        'version-1-0-1',
        'version-1-0-2',
        'version-1-0-10']
    actual = version_sorted([
        'version-1-0-10',
        'version-1-0-2',
        'version-1-0-1'])
    assert expected == actual

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

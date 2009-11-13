from copy import deepcopy
from unittest import TestCase
import os
import shutil
import tempfile


class MockBuildout(object):
    def __init__(self, config=None):
        if config is None:
            config = dict()
        self._raw = deepcopy(config)

    def __contains__(self, key):
        return key in self._raw

    def __getitem__(self, key):
        return self._raw[key]

    def get(self, key, default=None):
        return self._raw.get(key, default)

    def __repr__(self):
        return repr(self._raw)


class MockConfig(object):
    def save(self):
        return


class TestExtensionClass(TestCase):
    def setUp(self):
        from mr.developer.extension import Extension

        self.buildout = MockBuildout(dict(
            buildout=dict(
                directory='/',
                parts='',
            ),
            sources={},
        ))

        class MockExtension(Extension):
            def get_config(self):
                config = getattr(self, '_config', None)
                if config is None:
                    self._config = config = MockConfig()
                return config

        self.extension = MockExtension(self.buildout)

    def testPartAdded(self):
        buildout = self.buildout
        self.failIf('_mr.developer' in buildout['buildout']['parts'])
        self.extension()
        self.failUnless('_mr.developer' in buildout)
        self.failUnless('_mr.developer' in buildout['buildout']['parts'])

    def testArgsIgnoredIfNotBuildout(self):
        self.extension()
        self.failIf(hasattr(self.extension.get_config(), 'buildout_args'))

    def testBuildoutArgsSaved(self):
        self.extension.executable = 'buildout'
        self.extension()
        self.failUnless(hasattr(self.extension.get_config(), 'buildout_args'))


class TestExtension(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.buildout = MockBuildout(dict(
            buildout=dict(
                directory=self.tempdir,
                parts='',
            ),
            sources={},
        ))

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def testConfigCreated(self):
        from mr.developer.extension import extension
        extension(self.buildout)
        self.failUnless('.mr.developer.cfg' in os.listdir(self.tempdir))

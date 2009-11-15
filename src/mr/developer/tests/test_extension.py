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
    def __init__(self):
        self.buildout_args = []
        self.develop = {}
        self.rewrites = []

    def save(self):
        return


class MockWorkingCopies(object):
    def __init__(self, sources):
        self.sources = sources
        self._events = []

    def checkout(self, packages, **kwargs):
        self._events.append(('checkout', packages, kwargs))
        return False


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
            def get_workingcopies(self):
                wcs = getattr(self, '_wcs', None)
                if wcs is None:
                    self._wcs = wcs = MockWorkingCopies(self.get_sources())
                return wcs

        self.extension = MockExtension(self.buildout)
        self.extension._config = MockConfig()

    def testPartAdded(self):
        buildout = self.buildout
        self.failIf('_mr.developer' in buildout['buildout']['parts'])
        self.extension()
        self.failUnless('_mr.developer' in buildout)
        self.failUnless('_mr.developer' in buildout['buildout']['parts'])

    def testPartExists(self):
        self.buildout._raw['_mr.developer'] = {}
        self.assertRaises(SystemExit, self.extension)

    def testArgsIgnoredIfNotBuildout(self):
        self.extension()
        self.assertEquals(self.extension.get_config().buildout_args, [])

    def testBuildoutArgsSaved(self):
        self.extension.executable = 'buildout'
        self.extension()
        self.failUnless(hasattr(self.extension.get_config(), 'buildout_args'))

    def testAutoCheckout(self):
        self.buildout['sources'].update({
            'pkg.foo': 'svn dummy://pkg.foo',
            'pkg.bar': 'svn dummy://pkg.bar',
        })
        self.buildout['buildout']['auto-checkout'] = 'pkg.foo'
        self.extension()
        wcs = self.extension.get_workingcopies()
        self.assertEquals(len(wcs._events), 1)
        self.assertEquals(wcs._events[0][0], 'checkout')
        self.assertEquals(wcs._events[0][1], ['pkg.foo'])

    def testAutoCheckoutMissingSource(self):
        self.buildout['buildout']['auto-checkout'] = 'pkg.foo'
        self.assertRaises(SystemExit, self.extension.get_auto_checkout)

    def testAutoCheckoutMissingSources(self):
        self.buildout['buildout']['auto-checkout'] = 'pkg.foo pkg.bar'
        self.assertRaises(SystemExit, self.extension.get_auto_checkout)

    def testAutoCheckoutWildcard(self):
        self.buildout['sources'].update({
            'pkg.foo': 'svn dummy://pkg.foo',
            'pkg.bar': 'svn dummy://pkg.bar',
        })
        self.buildout['buildout']['auto-checkout'] = '*'
        self.extension()
        wcs = self.extension.get_workingcopies()
        self.assertEquals(len(wcs._events), 1)
        self.assertEquals(wcs._events[0][0], 'checkout')
        self.assertEquals(wcs._events[0][1], ['pkg.bar', 'pkg.foo'])

    def testRewriteSources(self):
        self.buildout['sources'].update({
            'pkg.foo': 'svn dummy://pkg.foo',
            'pkg.bar': 'svn baz://pkg.bar',
        })
        self.extension._config.rewrites.append(('dummy://', 'ham://'))
        sources = self.extension.get_sources()
        self.assertEquals(sources['pkg.foo']['url'], 'ham://pkg.foo')
        self.assertEquals(sources['pkg.bar']['url'], 'baz://pkg.bar')

    def _testEmptySourceDefinition(self):
        # TODO handle this case
        self.buildout['sources'].update({
            'pkg.foo': '',
        })
        sources = self.extension.get_sources()

    def _testTooShortSourceDefinition(self):
        # TODO handle this case
        self.buildout['sources'].update({
            'pkg.foo': 'svn',
        })
        sources = self.extension.get_sources()


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

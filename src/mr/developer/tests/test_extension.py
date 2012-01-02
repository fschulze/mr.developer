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
        from mr.developer.extension import memoize, Extension

        self.buildout = MockBuildout(dict(
            buildout=dict(
                directory='/buildout',
                parts='',
            ),
            sources={},
        ))

        class MockExtension(Extension):
            @memoize
            def get_config(self):
                return MockConfig()

            @memoize
            def get_workingcopies(self):
                return MockWorkingCopies(self.get_sources())

        self.extension = MockExtension(self.buildout)

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
        self.extension.get_config().rewrites.append(('dummy://', 'ham://'))
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

    def testRepositoryKindChecking(self):
        self.buildout['sources'].update({
            'pkg.bar': 'dummy://foo/trunk svn',
        })
        self.assertRaises(SystemExit, self.extension.get_sources)
        self.buildout['sources'].update({
            'pkg.bar': 'foo dummy://foo/trunk',
        })
        self.assertRaises(SystemExit, self.extension.get_sources)

    def testOldSourcePathParsing(self):
        self.buildout['sources'].update({
            'pkg.bar': 'svn dummy://foo/trunk',
            'pkg.ham': 'git dummy://foo/trunk ham',
            'pkg.baz': 'git dummy://foo/trunk other/baz',
            'pkg.foo': 'git dummy://foo/trunk /foo',
        })
        sources = self.extension.get_sources()
        self.assertEqual(sources['pkg.bar']['path'],
                         os.path.join(os.sep, 'buildout', 'src', 'pkg.bar'))
        self.assertEqual(sources['pkg.ham']['path'],
                         os.path.join(os.sep, 'buildout', 'ham', 'pkg.ham'))
        self.assertEqual(sources['pkg.baz']['path'],
                         os.path.join(os.sep, 'buildout', 'other', 'baz', 'pkg.baz'))
        self.assertEqual(sources['pkg.foo']['path'],
                         os.path.join(os.sep, 'foo', 'pkg.foo'))

    def testSourcePathParsing(self):
        self.buildout['sources'].update({
            'pkg.bar': 'svn dummy://foo/trunk',
            'pkg.ham': 'git dummy://foo/trunk path=ham',
            'pkg.baz': 'git dummy://foo/trunk path=other/baz',
            'pkg.foo': 'git dummy://foo/trunk path=/foo',
        })
        sources = self.extension.get_sources()
        self.assertEqual(sources['pkg.bar']['path'],
                         os.path.join(os.sep, 'buildout', 'src', 'pkg.bar'))
        self.assertEqual(sources['pkg.ham']['path'],
                         os.path.join(os.sep, 'buildout', 'ham', 'pkg.ham'))
        self.assertEqual(sources['pkg.baz']['path'],
                         os.path.join(os.sep, 'buildout', 'other', 'baz', 'pkg.baz'))
        self.assertEqual(sources['pkg.foo']['path'],
                         os.path.join(os.sep, 'foo', 'pkg.foo'))

    def testOptionParsing(self):
        self.buildout['sources'].update({
            'pkg.bar': 'svn dummy://foo/trunk revision=456',
            'pkg.ham': 'git dummy://foo/trunk ham rev=456ad138',
            'pkg.foo': 'git dummy://foo/trunk rev=>=456ad138 branch=blubber',
        })
        sources = self.extension.get_sources()

        self.assertEqual(sorted(sources['pkg.bar'].keys()),
                         ['kind', 'name', 'path', 'revision', 'url'])
        self.assertEqual(sources['pkg.bar']['revision'], '456')

        self.assertEqual(sorted(sources['pkg.ham'].keys()),
                         ['kind', 'name', 'path', 'rev', 'url'])
        self.assertEqual(sources['pkg.ham']['path'],
                         os.path.join(os.sep, 'buildout', 'ham', 'pkg.ham'))
        self.assertEqual(sources['pkg.ham']['rev'], '456ad138')

        self.assertEqual(sorted(sources['pkg.foo'].keys()),
                         ['branch', 'kind', 'name', 'path', 'rev', 'url'])
        self.assertEqual(sources['pkg.foo']['branch'], 'blubber')
        self.assertEqual(sources['pkg.foo']['rev'], '>=456ad138')

    def testOptionParsingBeforeURL(self):
        self.buildout['sources'].update({
            'pkg.bar': 'svn revision=456 dummy://foo/trunk',
            'pkg.ham': 'git rev=456ad138 dummy://foo/trunk ham',
            'pkg.foo': 'git rev=>=456ad138 branch=blubber dummy://foo/trunk',
        })
        sources = self.extension.get_sources()

        self.assertEqual(sorted(sources['pkg.bar'].keys()),
                         ['kind', 'name', 'path', 'revision', 'url'])
        self.assertEqual(sources['pkg.bar']['revision'], '456')

        self.assertEqual(sorted(sources['pkg.ham'].keys()),
                         ['kind', 'name', 'path', 'rev', 'url'])
        self.assertEqual(sources['pkg.ham']['path'],
                         os.path.join(os.sep, 'buildout', 'ham', 'pkg.ham'))
        self.assertEqual(sources['pkg.ham']['rev'], '456ad138')

        self.assertEqual(sorted(sources['pkg.foo'].keys()),
                         ['branch', 'kind', 'name', 'path', 'rev', 'url'])
        self.assertEqual(sources['pkg.foo']['branch'], 'blubber')
        self.assertEqual(sources['pkg.foo']['rev'], '>=456ad138')

    def testDuplicateOptionParsing(self):
        self.buildout['sources'].update({
            'pkg.foo': 'git dummy://foo/trunk rev=456ad138 rev=blubber',
        })
        self.assertRaises(ValueError, self.extension.get_sources)

        self.buildout['sources'].update({
            'pkg.foo': 'git dummy://foo/trunk kind=svn',
        })
        self.assertRaises(ValueError, self.extension.get_sources)

    def testInvalidOptionParsing(self):
        self.buildout['sources'].update({
            'pkg.foo': 'git dummy://foo/trunk rev=456ad138 =foo',
        })
        self.assertRaises(ValueError, self.extension.get_sources)

    def testDevelopHonored(self):
        self.buildout['buildout']['develop'] = '/normal/develop ' \
          '/develop/with/slash/'

        (develop, develeggs, versions) = self.extension.get_develop_info()
        self.failUnless('/normal/develop' in develop)
        self.failUnless('/develop/with/slash/' in develop)
        self.failUnless('slash' in develeggs)
        self.failUnless('develop' in develeggs)
        self.assertEqual(develeggs['slash'], '/develop/with/slash/')
        self.assertEqual(develeggs['develop'], '/normal/develop')


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


class TestSourcesDir(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def test_sources_dir_created(self):
        buildout = MockBuildout(dict(
            buildout = {
                'directory': self.tempdir,
                'parts': '',
                'sources-dir': 'develop',
            },
            sources={},
        ))
        from mr.developer.extension import Extension
        self.failIf('develop' in os.listdir(self.tempdir))
        ext = Extension(buildout)
        ext()
        self.failUnless('develop' in os.listdir(self.tempdir))
        self.assertEqual(ext.get_sources_dir(),
                         os.path.join(self.tempdir, 'develop'))

from copy import deepcopy
from mock import patch
from mr.developer.extension import Extension
from mr.developer.tests.utils import MockConfig
from zc.buildout.buildout import MissingSection
import os
import pytest


class MockBuildout(object):
    def __init__(self, config=None):
        if config is None:
            config = dict()
        self._raw = deepcopy(config)

    def __contains__(self, key):
        return key in self._raw

    def __delitem__(self, key):
        del self._raw[key]

    def __getitem__(self, key):
        try:
            return self._raw[key]
        except KeyError:
            raise MissingSection(key)

    def get(self, key, default=None):
        return self._raw.get(key, default)

    def __repr__(self):
        return repr(self._raw)


class MockWorkingCopies(object):
    def __init__(self, sources):
        self.sources = sources
        self._events = []

    def checkout(self, packages, **kwargs):
        self._events.append(('checkout', packages, kwargs))
        return False


class TestExtensionClass:
    @pytest.fixture
    def buildout(self):
        return MockBuildout(dict(
            buildout=dict(
                directory='/buildout',
                parts=''),
            sources={}))

    @pytest.fixture
    def extension(self, buildout):
        from mr.developer.extension import memoize

        class MockExtension(Extension):
            @memoize
            def get_config(self):
                return MockConfig()

            @memoize
            def get_workingcopies(self):
                return MockWorkingCopies(self.get_sources())

        return MockExtension(buildout)

    def testPartAdded(self, buildout, extension):
        assert '_mr.developer' not in buildout['buildout']['parts']
        extension()
        assert '_mr.developer' in buildout
        assert '_mr.developer' in buildout['buildout']['parts']

    def testPartExists(self, buildout, extension):
        buildout._raw['_mr.developer'] = {}
        pytest.raises(SystemExit, extension)

    def testArgsIgnoredIfNotBuildout(self, extension):
        extension()
        assert extension.get_config().buildout_args == []

    def testBuildoutArgsSaved(self, extension):
        extension.executable = 'buildout'
        extension()
        assert hasattr(extension.get_config(), 'buildout_args')

    def testAutoCheckout(self, buildout, extension):
        buildout['sources'].update({
            'pkg.foo': 'svn dummy://pkg.foo',
            'pkg.bar': 'svn dummy://pkg.bar',
        })
        buildout['buildout']['auto-checkout'] = 'pkg.foo'
        extension()
        wcs = extension.get_workingcopies()
        assert len(wcs._events) == 1
        assert wcs._events[0][0] == 'checkout'
        assert wcs._events[0][1] == ['pkg.foo']

    def testAutoCheckoutMissingSource(self, buildout, extension):
        buildout['buildout']['auto-checkout'] = 'pkg.foo'
        pytest.raises(SystemExit, extension.get_auto_checkout)

    def testAutoCheckoutMissingSources(self, buildout, extension):
        buildout['buildout']['auto-checkout'] = 'pkg.foo pkg.bar'
        pytest.raises(SystemExit, extension.get_auto_checkout)

    def testAutoCheckoutWildcard(self, buildout, extension):
        buildout['sources'].update({
            'pkg.foo': 'svn dummy://pkg.foo',
            'pkg.bar': 'svn dummy://pkg.bar',
        })
        buildout['buildout']['auto-checkout'] = '*'
        extension()
        wcs = extension.get_workingcopies()
        len(wcs._events) == 1
        wcs._events[0][0] == 'checkout'
        wcs._events[0][1] == ['pkg.bar', 'pkg.foo']

    def testRewriteSources(self, buildout, extension):
        from mr.developer.common import LegacyRewrite
        buildout['sources'].update({
            'pkg.foo': 'svn dummy://pkg.foo',
            'pkg.bar': 'svn baz://pkg.bar',
        })
        extension.get_config().rewrites.append(
            LegacyRewrite('dummy://', 'ham://'))
        sources = extension.get_sources()
        assert sources['pkg.foo']['url'] == 'ham://pkg.foo'
        assert sources['pkg.bar']['url'] == 'baz://pkg.bar'

    def _testEmptySourceDefinition(self, buildout, extension):
        # TODO handle this case
        buildout['sources'].update({
            'pkg.foo': '',
        })
        extension.get_sources()

    def _testTooShortSourceDefinition(self, buildout, extension):
        # TODO handle this case
        buildout['sources'].update({
            'pkg.foo': 'svn',
        })
        extension.get_sources()

    def testRepositoryKindChecking(self, buildout, extension):
        buildout['sources'].update({
            'pkg.bar': 'dummy://foo/trunk svn',
        })
        pytest.raises(SystemExit, extension.get_sources)
        buildout['sources'].update({
            'pkg.bar': 'foo dummy://foo/trunk',
        })
        pytest.raises(SystemExit, extension.get_sources)

    def testOldSourcePathParsing(self, buildout, extension):
        buildout['sources'].update({
            'pkg.bar': 'svn dummy://foo/trunk',
            'pkg.ham': 'git dummy://foo/trunk ham',
            'pkg.baz': 'git dummy://foo/trunk other/baz',
            'pkg.foo': 'git dummy://foo/trunk /foo',
        })
        sources = extension.get_sources()
        assert sources['pkg.bar']['path'] == os.path.join(os.sep, 'buildout', 'src', 'pkg.bar')
        assert sources['pkg.ham']['path'] == os.path.join(os.sep, 'buildout', 'ham', 'pkg.ham')
        assert sources['pkg.baz']['path'] == os.path.join(os.sep, 'buildout', 'other', 'baz', 'pkg.baz')
        assert sources['pkg.foo']['path'] == os.path.join(os.sep, 'foo', 'pkg.foo')

    def testSourcePathParsing(self, buildout, extension):
        buildout['sources'].update({
            'pkg.bar': 'svn dummy://foo/trunk',
            'pkg.ham': 'git dummy://foo/trunk path=ham',
            'pkg.baz': 'git dummy://foo/trunk path=other/baz',
            'pkg.foo': 'git dummy://foo/trunk path=/foo',
        })
        sources = extension.get_sources()
        assert sources['pkg.bar']['path'] == os.path.join(os.sep, 'buildout', 'src', 'pkg.bar')
        assert sources['pkg.ham']['path'] == os.path.join(os.sep, 'buildout', 'ham', 'pkg.ham')
        assert sources['pkg.baz']['path'] == os.path.join(os.sep, 'buildout', 'other', 'baz', 'pkg.baz')
        assert sources['pkg.foo']['path'] == os.path.join(os.sep, 'foo', 'pkg.foo')

    def testOptionParsing(self, buildout, extension):
        buildout['sources'].update({
            'pkg.bar': 'svn dummy://foo/trunk revision=456',
            'pkg.ham': 'git dummy://foo/trunk ham rev=456ad138',
            'pkg.foo': 'git dummy://foo/trunk rev=>=456ad138 branch=blubber',
        })
        sources = extension.get_sources()

        assert sorted(sources['pkg.bar'].keys()) == ['kind', 'name', 'path', 'revision', 'url']
        assert sources['pkg.bar']['revision'] == '456'

        assert sorted(sources['pkg.ham'].keys()) == ['kind', 'name', 'path', 'rev', 'url']
        assert sources['pkg.ham']['path'] == os.path.join(os.sep, 'buildout', 'ham', 'pkg.ham')
        assert sources['pkg.ham']['rev'] == '456ad138'

        assert sorted(sources['pkg.foo'].keys()) == ['branch', 'kind', 'name', 'path', 'rev', 'url']
        assert sources['pkg.foo']['branch'] == 'blubber'
        assert sources['pkg.foo']['rev'] == '>=456ad138'

    def testOptionParsingBeforeURL(self, buildout, extension):
        buildout['sources'].update({
            'pkg.bar': 'svn revision=456 dummy://foo/trunk',
            'pkg.ham': 'git rev=456ad138 dummy://foo/trunk ham',
            'pkg.foo': 'git rev=>=456ad138 branch=blubber dummy://foo/trunk',
        })
        sources = extension.get_sources()

        assert sorted(sources['pkg.bar'].keys()) == ['kind', 'name', 'path', 'revision', 'url']
        assert sources['pkg.bar']['revision'] == '456'

        assert sorted(sources['pkg.ham'].keys()) == ['kind', 'name', 'path', 'rev', 'url']
        assert sources['pkg.ham']['path'] == os.path.join(os.sep, 'buildout', 'ham', 'pkg.ham')
        assert sources['pkg.ham']['rev'] == '456ad138'

        assert sorted(sources['pkg.foo'].keys()) == ['branch', 'kind', 'name', 'path', 'rev', 'url']
        assert sources['pkg.foo']['branch'] == 'blubber'
        assert sources['pkg.foo']['rev'] == '>=456ad138'

    def testDuplicateOptionParsing(self, buildout, extension):
        buildout['sources'].update({
            'pkg.foo': 'git dummy://foo/trunk rev=456ad138 rev=blubber',
        })
        pytest.raises(ValueError, extension.get_sources)

        buildout['sources'].update({
            'pkg.foo': 'git dummy://foo/trunk kind=svn',
        })
        pytest.raises(ValueError, extension.get_sources)

    def testInvalidOptionParsing(self, buildout, extension):
        buildout['sources'].update({
            'pkg.foo': 'git dummy://foo/trunk rev=456ad138 =foo',
        })
        pytest.raises(ValueError, extension.get_sources)

    def testDevelopHonored(self, buildout, extension):
        buildout['buildout']['develop'] = '/normal/develop ' \
            '/develop/with/slash/'

        (develop, develeggs, versions) = extension.get_develop_info()
        assert '/normal/develop' in develop
        assert '/develop/with/slash/' in develop
        assert 'slash' in develeggs
        assert 'develop' in develeggs
        assert develeggs['slash'] == '/develop/with/slash/'
        assert develeggs['develop'] == '/normal/develop'

    def testDevelopSafeName(self, buildout, extension):
        '''We have two source packages:
         - pkg.bar_foo
         - pkg.foo_bar
        both of them have a pinned version.

        If we auto-checkout pkg.foo_bar it gets unpinned!
        '''
        buildout['sources'].update({
            'pkg.bar_foo': 'svn dummy://pkg.bar_foo',
            'pkg.foo_bar': 'svn dummy://pkg.foo_bar',
        })
        buildout['buildout']['auto-checkout'] = 'pkg.foo_bar'
        buildout._raw['buildout']['versions'] = 'versions'
        buildout._raw['versions'] = {
            'pkg.foo-bar': '1.0',
            'pkg.bar-foo': '1.0',
        }
        _exists = patch('os.path.exists')
        exists = _exists.__enter__()
        try:
            exists().return_value = True

            (develop, develeggs, versions) = extension.get_develop_info()
        finally:
            _exists.__exit__()
        assert buildout['versions'] == {
            'pkg.foo-bar': '',
            'pkg.bar-foo': '1.0'}

    def testDevelopOrder(self, buildout, extension):
        buildout['buildout']['develop'] = '/normal/develop ' \
            '/develop/with/slash/'

        (develop, develeggs, versions) = extension.get_develop_info()
        assert develop == ['/normal/develop', '/develop/with/slash/']

    def testDevelopSourcesMix(self, buildout, extension):
        buildout['sources'].update({
            'pkg.bar': 'svn dummy://foo/trunk'})
        buildout['buildout']['auto-checkout'] = 'pkg.bar'
        buildout['buildout']['develop'] = '/normal/develop ' \
            '/develop/with/slash/'

        _exists = patch('os.path.exists')
        exists = _exists.__enter__()
        try:
            exists().return_value = True
            (develop, develeggs, versions) = extension.get_develop_info()
        finally:
            _exists.__exit__()
        assert develop == ['/normal/develop', '/develop/with/slash/', 'src/pkg.bar']

    def testMissingSourceSection(self, buildout, extension):
        del buildout['sources']
        assert extension.get_sources() == {}


class TestExtension:
    def testConfigCreated(self, tempdir):
        from mr.developer.extension import extension
        buildout = MockBuildout(dict(
            buildout=dict(
                directory=tempdir,
                parts=''),
            sources={}))
        extension(buildout)
        assert '.mr.developer.cfg' in os.listdir(tempdir)


class TestSourcesDir:
    def test_sources_dir_option_set_if_missing(self, tempdir):
        buildout = MockBuildout(dict(
            buildout={
                'directory': tempdir,
                'parts': ''},
            sources={},
        ))
        ext = Extension(buildout)
        assert 'sources-dir' not in buildout['buildout']
        ext()
        assert buildout['buildout']['sources-dir'] == os.path.join(
            tempdir, 'src')

    def test_sources_dir_created(self, tempdir):
        buildout = MockBuildout(dict(
            buildout={
                'directory': tempdir,
                'parts': '',
                'sources-dir': 'develop'},
            sources={},
        ))
        assert 'develop' not in os.listdir(tempdir)
        ext = Extension(buildout)
        ext()
        assert 'develop' in os.listdir(tempdir)
        assert ext.get_sources_dir() == tempdir['develop']

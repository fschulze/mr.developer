from mock import patch
from mr.developer.extension import Source
from mr.developer.tests.utils import Process
import os
import pytest


class TestSVN:
    @pytest.fixture(autouse=True)
    def clear_svn_caches(self):
        from mr.developer.svn import SVNWorkingCopy
        SVNWorkingCopy._clear_caches()

    def testUpdateWithoutRevisionPin(self, develop, src, tempdir):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
        process = Process()
        repository = tempdir['repository']
        process.check_call("svnadmin create %s" % repository)
        checkout = tempdir['checkout']
        process.check_call(
            "svn checkout file://%s %s" % (repository, checkout),
            echo=False)
        foo = checkout['foo']
        foo.create_file('foo')
        process.check_call("svn add %s" % foo, echo=False)
        process.check_call("svn commit %s -m foo" % foo, echo=False)
        bar = checkout['bar']
        bar.create_file('bar')
        process.check_call("svn add %s" % bar, echo=False)
        process.check_call("svn commit %s -m bar" % bar, echo=False)
        develop.sources = {
            'egg': Source(
                kind='svn',
                name='egg',
                url='file://%s' % repository,
                path=src['egg'])}
        _log = patch('mr.developer.svn.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('.svn', 'bar', 'foo'))
            CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('.svn', 'bar', 'foo'))
            assert log.method_calls == [
                ('info', ("Checked out 'egg' with subversion.",), {}),
                ('info', ("Updated 'egg' with subversion.",), {})]
        finally:
            _log.__exit__()

    def testUpdateWithRevisionPin(self, develop, src, tempdir):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
        process = Process()
        repository = tempdir['repository']
        process.check_call("svnadmin create %s" % repository)
        checkout = tempdir['checkout']
        process.check_call(
            "svn checkout file://%s %s" % (repository, checkout),
            echo=False)
        foo = checkout['foo']
        foo.create_file('foo')
        process.check_call("svn add %s" % foo, echo=False)
        process.check_call("svn commit %s -m foo" % foo, echo=False)
        bar = checkout['bar']
        bar.create_file('bar')
        process.check_call("svn add %s" % bar, echo=False)
        process.check_call("svn commit %s -m bar" % bar, echo=False)
        develop.sources = {
            'egg': Source(
                kind='svn',
                name='egg',
                url='file://%s@1' % repository,
                path=src['egg'])}
        CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
        assert set(os.listdir(src['egg'])) == set(('.svn', 'foo'))
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(src['egg'])) == set(('.svn', 'foo'))

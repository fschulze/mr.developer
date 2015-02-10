from mock import patch
from mr.developer.extension import Source
from mr.developer.tests.utils import Process, JailSetup
import argparse
import os


class MockConfig(object):
    def __init__(self):
        self.develop = {}

    def save(self):
        pass


class MockDevelop(object):
    def __init__(self):
        self.always_accept_server_certificate = True
        self.always_checkout = False
        self.update_git_submodules = 'always'
        self.config = MockConfig()
        self.parser = argparse.ArgumentParser()
        self.parsers = self.parser.add_subparsers(title="commands", metavar="")
        self.threads = 1


class SVNTests(JailSetup):
    def setUp(self):
        JailSetup.setUp(self)
        from mr.developer.svn import SVNWorkingCopy
        SVNWorkingCopy._clear_caches()

    def testUpdateWithoutRevisionPin(self):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
        process = Process()
        repository = os.path.join(self.tempdir, 'repository')
        rc, lines = process.popen(
            "svnadmin create %s" % repository)
        assert rc == 0
        checkout = os.path.join(self.tempdir, 'checkout')
        rc, lines = process.popen(
            "svn checkout file://%s %s" % (repository, checkout),
            echo=False)
        assert rc == 0
        foo = os.path.join(checkout, 'foo')
        self.mkfile(foo, 'foo')
        rc, lines = process.popen(
            "svn add %s" % foo,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "svn commit %s -m foo" % foo,
            echo=False)
        assert rc == 0
        bar = os.path.join(checkout, 'bar')
        self.mkfile(bar, 'bar')
        rc, lines = process.popen(
            "svn add %s" % bar,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "svn commit %s -m bar" % bar,
            echo=False)
        assert rc == 0
        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='svn',
                name='egg',
                url='file://%s' % repository,
                path=os.path.join(src, 'egg'))}
        _log = patch('mr.developer.svn.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.svn', 'bar', 'foo'))
            CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.svn', 'bar', 'foo'))
            assert log.method_calls == [
                ('info', ("Checked out 'egg' with subversion.",), {}),
                ('info', ("Updated 'egg' with subversion.",), {})]
        finally:
            _log.__exit__()

    def testUpdateWithRevisionPin(self):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
        process = Process()
        repository = os.path.join(self.tempdir, 'repository')
        rc, lines = process.popen(
            "svnadmin create %s" % repository)
        assert rc == 0
        checkout = os.path.join(self.tempdir, 'checkout')
        rc, lines = process.popen(
            "svn checkout file://%s %s" % (repository, checkout),
            echo=False)
        assert rc == 0
        foo = os.path.join(checkout, 'foo')
        self.mkfile(foo, 'foo')
        rc, lines = process.popen(
            "svn add %s" % foo,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "svn commit %s -m foo" % foo,
            echo=False)
        assert rc == 0
        bar = os.path.join(checkout, 'bar')
        self.mkfile(bar, 'bar')
        rc, lines = process.popen(
            "svn add %s" % bar,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "svn commit %s -m bar" % bar,
            echo=False)
        assert rc == 0
        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='svn',
                name='egg',
                url='file://%s@1' % repository,
                path=os.path.join(src, 'egg'))}
        CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.svn', 'foo'))
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.svn', 'foo'))

from mock import patch
from mr.developer.extension import Source
from mr.developer.tests.utils import Process, JailSetup
import argparse
import os
import pytest


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


class GITTests(JailSetup):
    def setUp(self):
        JailSetup.setUp(self)

    def testUpdateWithoutRevisionPin(self):
        from mr.developer.develop import CmdCheckout
        from mr.developer.develop import CmdUpdate
        repository = os.path.join(self.tempdir, 'repository')
        os.mkdir(repository)
        process = Process(cwd=repository)
        rc, lines = process.popen(
            "git init")
        assert rc == 0
        foo = os.path.join(repository, 'foo')
        self.mkfile(foo, 'foo')
        rc, lines = process.popen(
            "git add %s" % foo,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "git commit %s -m foo" % foo,
            echo=False)
        assert rc == 0
        bar = os.path.join(repository, 'bar')
        self.mkfile(bar, 'bar')
        rc, lines = process.popen(
            "git add %s" % bar,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "git commit %s -m bar" % bar,
            echo=False)
        assert rc == 0
        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='file:///%s' % repository,
                path=os.path.join(src, 'egg'))}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'bar', 'foo'))
            CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'bar', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git.",), {}),
                ('info', ("Updated 'egg' with git.",), {}),
                ('info', ("Updated all egg submodules with git.",), {})]
        finally:
            _log.__exit__()

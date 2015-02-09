import argparse
import os

import pytest
from mock import patch

from mr.developer.extension import Source
from mr.developer.tests.utils import Process, JailSetup
from mr.developer.compat import b


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


class MercurialTests(JailSetup):

    def setUp(self):
        JailSetup.setUp(self)

    def testUpdateWithoutRevisionPin(self):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
        repository = os.path.join(self.tempdir, 'repository')
        os.mkdir(repository)
        process = Process(cwd=repository)
        rc, lines = process.popen(
            "hg init %s" % repository)
        assert rc == 0

        foo = os.path.join(repository, 'foo')
        self.mkfile(foo, 'foo')
        rc, lines = process.popen(
            "hg add %s" % foo,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "hg commit %s -m foo -u test" % foo,
            echo=False)
        assert rc == 0
        bar = os.path.join(repository, 'bar')
        self.mkfile(bar, 'bar')
        rc, lines = process.popen(
            "hg add %s" % bar,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "hg commit %s -m bar -u test" % bar,
            echo=False)
        assert rc == 0
        src = os.path.join(self.tempdir, 'src')
        os.mkdir(src)
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='hg',
                name='egg',
                url='%s' % repository,
                path=os.path.join(src, 'egg'))}
        _log = patch('mr.developer.mercurial.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.hg', 'bar', 'foo'))
            CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.hg', 'bar', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with mercurial.",), {}),
                ('info', ("Updated 'egg' with mercurial.",), {}),
                ('info', ("Switched 'egg' to default.",), {})]
        finally:
            _log.__exit__()

    def testUpdateWithRevisionPin(self):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
        repository = os.path.join(self.tempdir, 'repository')
        os.mkdir(repository)
        process = Process(cwd=repository)
        rc, lines = process.popen(
            "hg init %s" % repository)
        assert rc == 0
        foo = os.path.join(repository, 'foo')
        self.mkfile(foo, 'foo')
        rc, lines = process.popen(
            "hg add %s" % foo,
            echo=False)
        assert rc == 0

        # create branch for testing
        rc, lines = process.popen(
            "hg branch test",
            echo=False)
        assert rc == 0

        rc, lines = process.popen(
            "hg commit %s -m foo -u test" % foo,
            echo=False)
        assert rc == 0

        # get comitted rev
        rc, lines = process.popen(
            "hg log %s" % foo,
            echo=False)
        assert rc == 0

        try:
            # XXX older version
            rev = lines[0].split()[1].split(b(':'))[1]
        except:
            rev = lines[0].split()[1]

        # return to default branch
        rc, lines = process.popen(
            "hg branch default",
            echo=False)
        assert rc == 0

        bar = os.path.join(repository, 'bar')
        self.mkfile(bar, 'bar')
        rc, lines = process.popen(
            "hg add %s" % bar,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "hg commit %s -m bar -u test" % bar,
            echo=False)
        assert rc == 0
        src = os.path.join(self.tempdir, 'src')
        os.mkdir(src)
        develop = MockDevelop()

        # check rev
        develop.sources = {
            'egg': Source(
                kind='hg',
                name='egg',
                rev=rev,
                url='%s' % repository,
                path=os.path.join(src, 'egg'))}
        CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.hg', 'foo'))
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.hg', 'foo'))

        # check branch
        develop.sources = {
            'egg': Source(
                kind='hg',
                name='egg',
                branch='test',
                url='%s' % repository,
                path=os.path.join(src, 'egg'))}
        CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.hg', 'foo'))
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.hg', 'foo'))

        # we can't use both rev and branch
        pytest.raises(SystemExit, """
            develop.sources = {
                'egg': Source(
                    kind='hg',
                    name='egg',
                    branch='test',
                    rev=rev,
                    url='%s' % repository,
                    path=os.path.join(src, 'egg-failed'))}
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
        """)

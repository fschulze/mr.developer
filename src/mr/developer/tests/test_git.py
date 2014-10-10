import argparse
import os
import shutil

import pytest
from mock import patch

from mr.developer.extension import Source
from mr.developer.tests.utils import Process, JailSetup


class MockConfig(object):

    def __init__(self):
        self.develop = {}

    def save(self):
        pass


class MockDevelop(object):

    def __init__(self):
        self.always_accept_server_certificate = True
        self.always_checkout = False
        self.auto_checkout = ''
        self.update_git_submodules = 'always'
        self.sources_dir = ''
        self.develeggs = ''
        self.config = MockConfig()
        self.parser = argparse.ArgumentParser()
        self.parsers = self.parser.add_subparsers(title="commands", metavar="")
        self.threads = 1


class GitTests(JailSetup):

    def setUp(self):
        JailSetup.setUp(self)

    def createRepo(self, repo):
        repository = os.path.join(self.tempdir, repo)
        os.mkdir(repository)
        process = Process(cwd=repository)
        rc, lines = process.popen("git init")
        assert rc == 0
        rc, lines = process.popen('git config user.email "florian.schulze@gmx.net"')
        assert rc == 0
        rc, lines = process.popen('git config user.name "Florian Schulze"')
        assert rc == 0
        return repository

    def testUpdateWithRevisionPin(self):
        from mr.developer.develop import CmdCheckout
        from mr.developer.develop import CmdUpdate
        from mr.developer.develop import CmdStatus
        repository = self.createRepo('repository')
        process = Process(cwd=repository)
        foo = os.path.join(repository, 'foo')
        self.mkfile(foo, 'foo')
        rc, lines = process.popen(
            "git add %s" % foo,
            echo=False)
        assert rc == 0

        rc, lines = process.popen(
            "git commit -m 'Initial'",
            echo=False)
        assert rc == 0

        # create branch for testing
        rc, lines = process.popen(
            "git checkout -b test",
            echo=False)
        assert rc == 0

        foo2 = os.path.join(repository, 'foo2')
        self.mkfile(foo2, 'foo2')
        rc, lines = process.popen(
            "git add %s" % foo2,
            echo=False)
        assert rc == 0

        rc, lines = process.popen(
            "git commit -m foo",
            echo=False)
        assert rc == 0

        # get comitted rev
        rc, lines = process.popen(
            "git log",
            echo=False)
        assert rc == 0
        rev = lines[0].split()[1]

        # return to default branch
        rc, lines = process.popen(
            "git checkout master",
            echo=False)
        assert rc == 0

        bar = os.path.join(repository, 'bar')
        self.mkfile(bar, 'bar')
        rc, lines = process.popen(
            "git add %s" % bar,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "git commit -m bar",
            echo=False)
        assert rc == 0
        src = os.path.join(self.tempdir, 'src')
        os.mkdir(src)
        develop = MockDevelop()
        develop.sources_dir = src

        # check rev
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                rev=rev,
                url='%s' % repository,
                path=os.path.join(src, 'egg'))}
        CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'foo', 'foo2'))
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'foo', 'foo2'))

        shutil.rmtree(os.path.join(src, 'egg'))

        # check branch
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                branch='test',
                url='%s' % repository,
                path=os.path.join(src, 'egg'))}
        CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'foo', 'foo2'))
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'foo', 'foo2'))

        CmdStatus(develop)(develop.parser.parse_args(['status']))

        # we can't use both rev and branch
        pytest.raises(SystemExit, """
            develop.sources = {
                'egg': Source(
                    kind='git',
                    name='egg',
                    branch='test',
                    rev=rev,
                    url='%s' % repository,
                    path=os.path.join(src, 'egg-failed'))}
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
        """)

    def testUpdateWithoutRevisionPin(self):
        from mr.developer.develop import CmdCheckout
        from mr.developer.develop import CmdUpdate
        repository = self.createRepo('repository')
        process = Process(cwd=repository)
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
                ('info', ("Updated 'egg' with git.",), {})]
        finally:
            _log.__exit__()

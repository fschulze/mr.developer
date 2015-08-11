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

    def createFile(self, name, content):
        name = os.path.join(self.tempdir, name)
        f = open(name, 'w')
        f.write('\n'.join(content))
        f.close()
        return name

    def createDefaultContent(self, repository):
        # Create default content and branches in a repository.
        # Return a revision number.
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
            "git commit -m foo2",
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

        # Return revision of one of the commits, the one that adds the
        # foo2 file.
        return rev

    def testUpdateWithRevisionPin(self):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
        from mr.developer.commands import CmdStatus
        repository = self.createRepo('repository')
        rev = self.createDefaultContent(repository)
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

        # switch implicitly to master branch
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='%s' % repository,
                path=os.path.join(src, 'egg'))}
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'bar', 'foo'))

        # Switch to specific revision, then switch back to master branch.
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                rev=rev,
                url='%s' % repository,
                path=os.path.join(src, 'egg'))}
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'foo', 'foo2'))
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='%s' % repository,
                path=os.path.join(src, 'egg'))}
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'bar', 'foo'))

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
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
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

    def testDepthOption(self):
        from mr.developer.develop import develop

        # create repository and make two commits on it
        repository = self.createRepo('repository')
        self.createDefaultContent(repository)
        process = Process(cwd=repository)

        src = os.path.join(self.tempdir, 'src')
        self.createFile(
            'buildout.cfg', [
                '[buildout]',
                'mr.developer-threads = 1',
                '[sources]',
                'egg = git file:///%s' % repository])
        self.createFile('.mr.developer.cfg', [])
        os.chdir(self.tempdir)
        develop('co', 'egg')

        # check that there are two commits in history
        process = Process(cwd=os.path.join(src, 'egg'))
        rc, lines = process.popen(
            "git log",
            echo=False)
        assert rc == 0
        commits = [msg for msg in lines
                   if msg.decode('utf-8').startswith('commit')]
        assert len(commits) == 2

        shutil.rmtree(os.path.join(src, 'egg'))

        self.createFile(
            'buildout.cfg', [
                '[buildout]',
                'mr.developer-threads = 1',
                '[sources]',
                'egg = git file:///%s depth=1' % repository])
        develop('co', 'egg')

        # check that there is only one commit in history
        process = Process(cwd=os.path.join(src, 'egg'))
        rc, lines = process.popen(
            "git log",
            echo=False)
        assert rc == 0
        commits = [msg for msg in lines
                   if msg.decode('utf-8').startswith('commit')]
        assert len(commits) == 1

        shutil.rmtree(os.path.join(src, 'egg'))

        self.createFile(
            'buildout.cfg', [
                '[buildout]',
                'mr.developer-threads = 1',
                'git-clone-depth = 1',
                '[sources]',
                'egg = git file:///%s' % repository])
        develop('co', 'egg')

        # check that there is only one commit in history
        process = Process(cwd=os.path.join(src, 'egg'))
        rc, lines = process.popen(
            "git log",
            echo=False)
        assert rc == 0
        commits = [msg for msg in lines
                   if msg.decode('utf-8').startswith('commit')]
        assert len(commits) == 1

        # You should be able to combine depth and cloning a branch.
        # Otherwise with a depth of 1 you could clone the master
        # branch and then not be able to switch to the wanted branch,
        # because this branch would not be there: the revision that it
        # points to is not in the downloaded history.
        shutil.rmtree(os.path.join(src, 'egg'))
        self.createFile(
            'buildout.cfg', [
                '[buildout]',
                'mr.developer-threads = 1',
                'git-clone-depth = 1',
                '[sources]',
                'egg = git file:///%s branch=test' % repository])
        develop('co', 'egg')

        # check that there is only one commit in history
        process = Process(cwd=os.path.join(src, 'egg'))
        rc, lines = process.popen(
            "git log",
            echo=False)
        assert rc == 0
        commits = [msg for msg in lines
                   if msg.decode('utf-8').startswith('commit')]
        assert len(commits) == 1

        # Check that the expected files from the branch are there
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.git', 'foo', 'foo2'))

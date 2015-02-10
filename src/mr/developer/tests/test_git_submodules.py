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


class GITTests(JailSetup):
    def setUp(self):
        JailSetup.setUp(self)

    # Helpers

    def addFileToRepo(self, repository, fname):
        process = Process(cwd=repository)
        repo_file = os.path.join(repository, fname)
        self.mkfile(repo_file, fname)
        rc, lines = process.popen(
            "git add %s" % repo_file,
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "git commit %s -m %s" % (repo_file, fname),
            echo=False)
        assert rc == 0

    def createRepo(self, repo):
        repository = os.path.join(self.tempdir, repo)
        os.mkdir(repository)
        process = Process(cwd=repository)
        rc, lines = process.popen("git init")
        assert rc == 0
        self.gitConfigUser(repo)
        return repository

    def gitConfigUser(self, repo):
        repository = os.path.join(self.tempdir, repo)
        process = Process(cwd=repository)
        rc, lines = process.popen('git config user.email "florian.schulze@gmx.net"')
        assert rc == 0
        rc, lines = process.popen('git config user.name "Florian Schulze"')
        assert rc == 0
        return repository

    def addSubmoduleToRepo(self, repository, submodule_path, submodule_name):
        process = Process(cwd=repository)
        rc, lines = process.popen("git submodule add file:///%s %s" % (submodule_path, submodule_name))
        assert rc == 0
        rc, lines = process.popen("git add .gitmodules")
        assert rc == 0
        rc, lines = process.popen("git add %s" % submodule_name)
        assert rc == 0
        rc, lines = process.popen("git commit -m 'Add submodule %s'" % submodule_name)
    # git subomdule tests

    def testCheckoutWithSubmodule(self):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it
        """
        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule_a = self.createRepo(submodule_name)
        self.addFileToRepo(submodule_a, 'foo')
        egg = self.createRepo('egg')
        self.addFileToRepo(egg, 'bar')
        self.addSubmoduleToRepo(egg, submodule_a, submodule_name)

        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='file:///%s' % egg,
                path=os.path.join(src, 'egg'))}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_name))) == set(('.git', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git.",), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {})]
        finally:
            _log.__exit__()

    def testCheckoutWithTwoSubmodules(self):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a'
            and a submodule 'submodule_b' in it.
        """
        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule = self.createRepo(submodule_name)
        submodule_b_name = 'submodule_b'
        submodule_b = self.createRepo(submodule_b_name)

        self.addFileToRepo(submodule, 'foo')
        self.addFileToRepo(submodule_b, 'foo_b')
        egg = self.createRepo('egg')
        self.addFileToRepo(egg, 'bar')
        self.addSubmoduleToRepo(egg, submodule, submodule_name)
        self.addSubmoduleToRepo(egg, submodule_b, submodule_b_name)

        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='file:///%s' % egg,
                path=os.path.join(src, 'egg'))}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', 'submodule_b', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_name))) == set(('.git', 'foo'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_b_name))) == set(('.git', 'foo_b'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git.",), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_b_name,), {})]
        finally:
            _log.__exit__()

    def testUpdateWithSubmodule(self):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it.
            Add a new 'submodule_b' to 'egg' and check it succesfully initializes.
        """
        from mr.developer.commands import CmdCheckout, CmdUpdate
        submodule_name = 'submodule_a'
        submodule = self.createRepo(submodule_name)
        self.addFileToRepo(submodule, 'foo')
        egg = self.createRepo('egg')
        self.addFileToRepo(egg, 'bar')
        self.addSubmoduleToRepo(egg, submodule, submodule_name)

        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='file:///%s' % egg,
                path=os.path.join(src, 'egg'))}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_name))) == set(('.git', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git.",), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {})]
        finally:
            _log.__exit__()

        submodule_b_name = 'submodule_b'
        submodule_b = self.createRepo(submodule_b_name)
        self.addFileToRepo(submodule_b, 'foo_b')
        self.addSubmoduleToRepo(egg, submodule_b, submodule_b_name)

        log = _log.__enter__()
        try:
            CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', 'submodule_b', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_b_name))) == set(('.git', 'foo_b'))
            assert log.method_calls == [
                ('info', ("Updated 'egg' with git.",), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_b_name,), {})]
        finally:
            _log.__exit__()

    def testCheckoutWithSubmodulesOptionNever(self):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it
            without initializing the submodule, restricted by global 'never'
        """

        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule_a = self.createRepo(submodule_name)
        self.addFileToRepo(submodule_a, 'foo')
        egg = self.createRepo('egg')
        self.addFileToRepo(egg, 'bar')
        self.addSubmoduleToRepo(egg, submodule_a, submodule_name)

        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.update_git_submodules = 'never'
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='file:///%s' % egg,
                path=os.path.join(src, 'egg'))}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_name))) == set()
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git.",), {})]
        finally:
            _log.__exit__()

    def testCheckoutWithSubmodulesOptionNeverSourceAlways(self):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it
            and a module 'egg2' with the same submodule, initializing only the submodule
            on egg that has the 'always' option
        """

        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule_a = self.createRepo(submodule_name)
        self.addFileToRepo(submodule_a, 'foo')
        egg = self.createRepo('egg')
        self.addFileToRepo(egg, 'bar')
        self.addSubmoduleToRepo(egg, submodule_a, submodule_name)

        egg2 = self.createRepo('egg2')
        self.addFileToRepo(egg2, 'bar')
        self.addSubmoduleToRepo(egg2, submodule_a, submodule_name)

        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.update_git_submodules = 'never'
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='file:///%s' % egg,
                path=os.path.join(src, 'egg'),
                submodules='always'),
            'egg2': Source(
                kind='git',
                name='egg2',
                url='file:///%s' % egg2,
                path=os.path.join(src, 'egg2'))}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_name))) == set(('foo', '.git'))
            assert set(os.listdir(os.path.join(src, 'egg2'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg2/%s' % submodule_name))) == set()

            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git.",), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {}),
                ('info', ("Cloned 'egg2' with git.",), {})]
        finally:
            _log.__exit__()

    def testCheckoutWithSubmodulesOptionAlwaysSourceNever(self):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it
            and a module 'egg2' with the same submodule, not initializing the submodule
            on egg2 that has the 'never' option

        """
        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule_a = self.createRepo(submodule_name)
        self.addFileToRepo(submodule_a, 'foo')
        egg = self.createRepo('egg')
        self.addFileToRepo(egg, 'bar')
        self.addSubmoduleToRepo(egg, submodule_a, submodule_name)

        egg2 = self.createRepo('egg2')
        self.addFileToRepo(egg2, 'bar')
        self.addSubmoduleToRepo(egg2, submodule_a, submodule_name)

        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='file:///%s' % egg,
                path=os.path.join(src, 'egg')),
            'egg2': Source(
                kind='git',
                name='egg2',
                url='file:///%s' % egg2,
                path=os.path.join(src, 'egg2'),
                submodules='never')}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_name))) == set(('foo', '.git'))
            assert set(os.listdir(os.path.join(src, 'egg2'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg2/%s' % submodule_name))) == set()

            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git.",), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {}),
                ('info', ("Cloned 'egg2' with git.",), {})]
        finally:
            _log.__exit__()

    def testUpdateWithSubmoduleCheckout(self):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it.
            Add a new 'submodule_b' to 'egg' and check it doesn't get initialized.
        """
        from mr.developer.commands import CmdCheckout, CmdUpdate
        submodule_name = 'submodule_a'
        submodule = self.createRepo(submodule_name)
        self.addFileToRepo(submodule, 'foo')
        egg = self.createRepo('egg')
        self.addFileToRepo(egg, 'bar')
        self.addSubmoduleToRepo(egg, submodule, submodule_name)

        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='file:///%s' % egg,
                path=os.path.join(src, 'egg'),
                submodules='checkout')}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_name))) == set(('.git', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git.",), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {})]
        finally:
            _log.__exit__()

        submodule_b_name = 'submodule_b'
        submodule_b = self.createRepo(submodule_b_name)
        self.addFileToRepo(submodule_b, 'foo_b')
        self.addSubmoduleToRepo(egg, submodule_b, submodule_b_name)

        log = _log.__enter__()
        try:
            CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', 'submodule_b', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_b_name))) == set()
            assert log.method_calls == [
                ('info', ("Updated 'egg' with git.",), {})]
        finally:
            _log.__exit__()

    def testUpdateWithSubmoduleDontUpdatePreviousSubmodules(self):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it.
            Commits changes in the detached submodule, and checks update didn't break
            the changes.
        """
        from mr.developer.commands import CmdCheckout, CmdUpdate
        submodule_name = 'submodule_a'
        submodule = self.createRepo(submodule_name)
        self.addFileToRepo(submodule, 'foo')
        egg = self.createRepo('egg')
        self.addFileToRepo(egg, 'bar')
        self.addSubmoduleToRepo(egg, submodule, submodule_name)

        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url='file:///%s' % egg,
                path=os.path.join(src, 'egg'))}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_name))) == set(('.git', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git.",), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {})]
        finally:
            _log.__exit__()

        self.gitConfigUser(os.path.join(src, 'egg/%s' % submodule_name))
        self.addFileToRepo(os.path.join(src, 'egg/%s' % submodule_name), 'newfile')

        log = _log.__enter__()
        try:
            CmdUpdate(develop)(develop.parser.parse_args(['up', '-f', 'egg']))
            assert set(os.listdir(os.path.join(src, 'egg'))) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(os.path.join(src, 'egg/%s' % submodule_name))) == set(('.git', 'foo', 'newfile'))
            assert log.method_calls == [
                ('info', ("Updated 'egg' with git.",), {})]
        finally:
            _log.__exit__()

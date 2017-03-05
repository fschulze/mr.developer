from mock import patch
from mr.developer.extension import Source
from mr.developer.tests.utils import GitRepo
import os


class TestGitSubmodules:
    def testCheckoutWithSubmodule(self, develop, mkgitrepo, src):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it
        """
        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule_a = mkgitrepo(submodule_name)
        submodule_a.add_file('foo')
        egg = mkgitrepo('egg')
        egg.add_file('bar')
        egg.add_submodule(submodule_a, submodule_name)

        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url=egg.url,
                path=src['egg'])}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_name])) == set(('.git', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git from '%s'." % egg.url,), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {})]
        finally:
            _log.__exit__()

    def testCheckoutWithTwoSubmodules(self, develop, mkgitrepo, src):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a'
            and a submodule 'submodule_b' in it.
        """
        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule = mkgitrepo(submodule_name)
        submodule_b_name = 'submodule_b'
        submodule_b = mkgitrepo(submodule_b_name)

        submodule.add_file('foo')
        submodule_b.add_file('foo_b')
        egg = mkgitrepo('egg')
        egg.add_file('bar')
        egg.add_submodule(submodule, submodule_name)
        egg.add_submodule(submodule_b, submodule_b_name)

        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url=egg.url,
                path=src['egg'])}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', 'submodule_b', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_name])) == set(('.git', 'foo'))
            assert set(os.listdir(src['egg/%s' % submodule_b_name])) == set(('.git', 'foo_b'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git from '%s'." % egg.url,), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_b_name,), {})]
        finally:
            _log.__exit__()

    def testUpdateWithSubmodule(self, develop, mkgitrepo, src):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it.
            Add a new 'submodule_b' to 'egg' and check it succesfully initializes.
        """
        from mr.developer.commands import CmdCheckout, CmdUpdate
        submodule_name = 'submodule_a'
        submodule = mkgitrepo(submodule_name)
        submodule.add_file('foo')
        egg = mkgitrepo('egg')
        egg.add_file('bar')
        egg.add_submodule(submodule, submodule_name)

        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url=egg.url,
                path=src['egg'])}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_name])) == set(('.git', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git from '%s'." % egg.url,), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {})]
        finally:
            _log.__exit__()

        submodule_b_name = 'submodule_b'
        submodule_b = mkgitrepo(submodule_b_name)
        submodule_b.add_file('foo_b')
        egg.add_submodule(submodule_b, submodule_b_name)

        log = _log.__enter__()
        try:
            CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', 'submodule_b', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_b_name])) == set(('.git', 'foo_b'))
            assert log.method_calls == [
                ('info', ("Updated 'egg' with git.",), {}),
                ('info', ("Switching to branch 'master'.",), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_b_name,), {})]
        finally:
            _log.__exit__()

    def testCheckoutWithSubmodulesOptionNever(self, develop, mkgitrepo, src):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it
            without initializing the submodule, restricted by global 'never'
        """

        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule_a = mkgitrepo(submodule_name)
        submodule_a.add_file('foo')
        egg = mkgitrepo('egg')
        egg.add_file('bar')
        egg.add_submodule(submodule_a, submodule_name)

        develop.update_git_submodules = 'never'
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url=egg.url,
                path=src['egg'])}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_name])) == set()
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git from '%s'." % egg.url,), {})]
        finally:
            _log.__exit__()

    def testCheckoutWithSubmodulesOptionNeverSourceAlways(self, develop, mkgitrepo, src):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it
            and a module 'egg2' with the same submodule, initializing only the submodule
            on egg that has the 'always' option
        """

        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule_a = mkgitrepo(submodule_name)
        submodule_a.add_file('foo')
        egg = mkgitrepo('egg')
        egg.add_file('bar')
        egg.add_submodule(submodule_a, submodule_name)

        egg2 = mkgitrepo('egg2')
        egg2.add_file('bar')
        egg2.add_submodule(submodule_a, submodule_name)

        develop.update_git_submodules = 'never'
        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url=egg.url,
                path=src['egg'],
                submodules='always'),
            'egg2': Source(
                kind='git',
                name='egg2',
                url=egg2.url,
                path=src['egg2'])}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_name])) == set(('foo', '.git'))
            assert set(os.listdir(src['egg2'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg2/%s' % submodule_name])) == set()

            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git from '%s'." % egg.url,), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {}),
                ('info', ("Cloned 'egg2' with git from '%s'." % egg2.url,), {})]
        finally:
            _log.__exit__()

    def testCheckoutWithSubmodulesOptionAlwaysSourceNever(self, develop, mkgitrepo, src):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it
            and a module 'egg2' with the same submodule, not initializing the submodule
            on egg2 that has the 'never' option

        """
        from mr.developer.commands import CmdCheckout
        submodule_name = 'submodule_a'
        submodule_a = mkgitrepo(submodule_name)
        submodule_a.add_file('foo')
        egg = mkgitrepo('egg')
        egg.add_file('bar')
        egg.add_submodule(submodule_a, submodule_name)

        egg2 = mkgitrepo('egg2')
        egg2.add_file('bar')
        egg2.add_submodule(submodule_a, submodule_name)

        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url=egg.url,
                path=src['egg']),
            'egg2': Source(
                kind='git',
                name='egg2',
                url=egg2.url,
                path=src['egg2'],
                submodules='never')}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_name])) == set(('foo', '.git'))
            assert set(os.listdir(src['egg2'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg2/%s' % submodule_name])) == set()

            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git from '%s'." % egg.url,), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {}),
                ('info', ("Cloned 'egg2' with git from '%s'." % egg2.url,), {})]
        finally:
            _log.__exit__()

    def testUpdateWithSubmoduleCheckout(self, develop, mkgitrepo, src):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it.
            Add a new 'submodule_b' to 'egg' and check it doesn't get initialized.
        """
        from mr.developer.commands import CmdCheckout, CmdUpdate
        submodule_name = 'submodule_a'
        submodule = mkgitrepo(submodule_name)
        submodule.add_file('foo')
        egg = mkgitrepo('egg')
        egg.add_file('bar')
        egg.add_submodule(submodule, submodule_name)

        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url=egg.url,
                path=src['egg'],
                submodules='checkout')}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_name])) == set(('.git', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git from '%s'." % egg.url,), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {})]
        finally:
            _log.__exit__()

        submodule_b_name = 'submodule_b'
        submodule_b = mkgitrepo(submodule_b_name)
        submodule_b.add_file('foo_b')
        egg.add_submodule(submodule_b, submodule_b_name)

        log = _log.__enter__()
        try:
            CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', 'submodule_b', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_b_name])) == set()
            assert log.method_calls == [
                ('info', ("Updated 'egg' with git.",), {}),
                ('info', ("Switching to branch 'master'.",), {})]
        finally:
            _log.__exit__()

    def testUpdateWithSubmoduleDontUpdatePreviousSubmodules(self, develop, mkgitrepo, src):
        """
            Tests the checkout of a module 'egg' with a submodule 'submodule_a' in it.
            Commits changes in the detached submodule, and checks update didn't break
            the changes.
        """
        from mr.developer.commands import CmdCheckout, CmdUpdate
        submodule_name = 'submodule_a'
        submodule = mkgitrepo(submodule_name)
        submodule.add_file('foo')
        egg = mkgitrepo('egg')
        egg.add_file('bar')
        egg.add_submodule(submodule, submodule_name)

        develop.sources = {
            'egg': Source(
                kind='git',
                name='egg',
                url=egg.url,
                path=src['egg'])}
        _log = patch('mr.developer.git.logger')
        log = _log.__enter__()
        try:
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_name])) == set(('.git', 'foo'))
            assert log.method_calls == [
                ('info', ("Cloned 'egg' with git from '%s'." % egg.url,), {}),
                ('info', ("Initialized 'egg' submodule at '%s' with git." % submodule_name,), {})]
        finally:
            _log.__exit__()

        repo = GitRepo(src['egg/%s' % submodule_name])
        repo.setup_user()
        repo.add_file('newfile')

        log = _log.__enter__()
        try:
            CmdUpdate(develop)(develop.parser.parse_args(['up', '-f', 'egg']))
            assert set(os.listdir(src['egg'])) == set(('submodule_a', '.git', 'bar', '.gitmodules'))
            assert set(os.listdir(src['egg/%s' % submodule_name])) == set(('.git', 'foo', 'newfile'))
            assert log.method_calls == [
                ('info', ("Updated 'egg' with git.",), {}),
                ('info', ("Switching to branch 'master'.",), {})]
        finally:
            _log.__exit__()

import os

import pytest
from mock import patch

from mr.developer.extension import Source
from mr.developer.tests.utils import Process
from mr.developer.compat import b


class TestMercurial:
    def testUpdateWithoutRevisionPin(self, develop, src, tempdir):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
        repository = tempdir['repository']
        os.mkdir(repository)
        process = Process(cwd=repository)
        process.check_call("hg init %s" % repository)

        foo = repository['foo']
        foo.create_file('foo')
        process.check_call("hg add %s" % foo, echo=False)
        process.check_call("hg commit %s -m foo -u test" % foo, echo=False)
        bar = repository['bar']
        bar.create_file('bar')
        process.check_call("hg add %s" % bar, echo=False)
        process.check_call("hg commit %s -m bar -u test" % bar, echo=False)
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

    def testUpdateWithRevisionPin(self, develop, src, tempdir):
        from mr.developer.commands import CmdCheckout
        from mr.developer.commands import CmdUpdate
        repository = tempdir['repository']
        os.mkdir(repository)
        process = Process(cwd=repository)
        lines = process.check_call("hg init %s" % repository)
        foo = repository['foo']
        foo.create_file('foo')
        lines = process.check_call("hg add %s" % foo, echo=False)

        # create branch for testing
        lines = process.check_call("hg branch test", echo=False)

        lines = process.check_call("hg commit %s -m foo -u test" % foo, echo=False)

        # get comitted rev
        lines = process.check_call("hg log %s" % foo, echo=False)

        try:
            # XXX older version
            rev = lines[0].split()[1].split(b(':'))[1]
        except Exception:
            rev = lines[0].split()[1]

        # return to default branch
        lines = process.check_call("hg branch default", echo=False)

        bar = repository['bar']
        bar.create_file('bar')
        lines = process.check_call("hg add %s" % bar, echo=False)
        lines = process.check_call("hg commit %s -m bar -u test" % bar, echo=False)

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
        with pytest.raises(SystemExit):
            develop.sources = {
                'egg': Source(
                    kind='hg',
                    name='egg',
                    branch='test',
                    rev=rev,
                    url='%s' % repository,
                    path=os.path.join(src, 'egg-failed'))}
            CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))

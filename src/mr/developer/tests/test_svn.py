from mr.developer.extension import Source
from jarn.mkrelease.process import Process
from jarn.mkrelease.testing import JailSetup
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
        self.config = MockConfig()
        self.parser = argparse.ArgumentParser()
        self.parsers = self.parser.add_subparsers(title="commands", metavar="")
        self.threads = 1


class SVNTests(JailSetup):
    def testUpdateWithRevisionPin(self):
        from mr.developer.develop import CmdCheckout
        from mr.developer.develop import CmdUpdate
        process = Process()
        repository = os.path.join(self.tempdir, 'repository')
        rc, lines = process.popen(
            "svnadmin create {0}".format(repository))
        assert rc == 0
        checkout = os.path.join(self.tempdir, 'checkout')
        rc, lines = process.popen(
            "svn checkout file://{0} {1}".format(repository, checkout),
            echo=False)
        assert rc == 0
        foo = os.path.join(checkout, 'foo')
        self.mkfile(foo, 'foo')
        rc, lines = process.popen(
            "svn add {0}".format(foo),
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "svn commit {0} -m foo".format(foo),
            echo=False)
        assert rc == 0
        bar = os.path.join(checkout, 'bar')
        self.mkfile(bar, 'bar')
        rc, lines = process.popen(
            "svn add {0}".format(bar),
            echo=False)
        assert rc == 0
        rc, lines = process.popen(
            "svn commit {0} -m bar".format(bar),
            echo=False)
        assert rc == 0
        src = os.path.join(self.tempdir, 'src')
        develop = MockDevelop()
        develop.sources = {
            'egg': Source(
                kind='svn',
                name='egg',
                url='file://{0}@1'.format(repository),
                path=os.path.join(src, 'egg'))}
        CmdCheckout(develop)(develop.parser.parse_args(['co', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.svn', 'foo'))
        CmdUpdate(develop)(develop.parser.parse_args(['up', 'egg']))
        assert set(os.listdir(os.path.join(src, 'egg'))) == set(('.svn', 'foo'))

from subprocess import Popen, PIPE
from mr.developer.compat import s
import os
import sys
import threading


def tee(process, filter_func):
    """Read lines from process.stdout and echo them to sys.stdout.

    Returns a list of lines read. Lines are not newline terminated.

    The 'filter_func' is a callable which is invoked for every line,
    receiving the line as argument. If the filter_func returns True, the
    line is echoed to sys.stdout.
    """
    # We simply use readline here, more fancy IPC is not warranted
    # in the context of this package.
    lines = []
    while True:
        line = process.stdout.readline()
        if line:
            stripped_line = line.rstrip()
            if filter_func(stripped_line):
                sys.stdout.write(s(line))
            lines.append(stripped_line)
        elif process.poll() is not None:
            break
    return lines


def tee2(process, filter_func):
    """Read lines from process.stderr and echo them to sys.stderr.

    The 'filter_func' is a callable which is invoked for every line,
    receiving the line as argument. If the filter_func returns True, the
    line is echoed to sys.stderr.
    """
    while True:
        line = process.stderr.readline()
        if line:
            stripped_line = line.rstrip()
            if filter_func(stripped_line):
                sys.stderr.write(s(line))
        elif process.poll() is not None:
            break


class background_thread(object):
    """Context manager to start and stop a background thread."""

    def __init__(self, target, args):
        self.target = target
        self.args = args

    def __enter__(self):
        self._t = threading.Thread(target=self.target, args=self.args)
        self._t.start()
        return self._t

    def __exit__(self, *ignored):
        self._t.join()


def popen(cmd, echo=True, echo2=True, env=None, cwd=None):
    """Run 'cmd' and return a two-tuple of exit code and lines read.

    If 'echo' is True, the stdout stream is echoed to sys.stdout.
    If 'echo2' is True, the stderr stream is echoed to sys.stderr.

    The 'echo' and 'echo2' arguments may also be callables, in which
    case they are used as tee filters.

    The 'env' argument allows to pass a dict replacing os.environ.

    if 'cwd' is not None, current directory will be changed to cwd before execution.
    """
    if not callable(echo):
        if echo:
            echo = On()
        else:
            echo = Off()

    if not callable(echo2):
        if echo2:
            echo2 = On()
        else:
            echo2 = Off()

    process = Popen(
        cmd,
        shell=True,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        cwd=cwd
    )

    bt = background_thread(tee2, (process, echo2))
    bt.__enter__()
    try:
        lines = tee(process, echo)
    finally:
        bt.__exit__()
    return process.returncode, lines


class On(object):
    """A tee filter printing all lines."""

    def __call__(self, line):
        return True


class Off(object):
    """A tee filter suppressing all lines."""

    def __call__(self, line):
        return False


class Process(object):
    """Process related functions using the tee module."""

    def __init__(self, quiet=False, env=None, cwd=None):
        self.quiet = quiet
        self.env = env
        self.cwd = cwd

    def popen(self, cmd, echo=True, echo2=True, cwd=None):
        # env *replaces* os.environ
        if self.quiet:
            echo = echo2 = False
        return popen(cmd, echo, echo2, env=self.env, cwd=self.cwd or cwd)

    def check_call(self, cmd, **kw):
        rc, lines = self.popen(cmd, **kw)
        assert rc == 0
        return lines


class MockConfig(object):
    def __init__(self):
        self.buildout_args = []
        self.develop = {}
        self.rewrites = []

    def save(self):
        pass


class MockDevelop(object):
    def __init__(self):
        from mr.developer.develop import ArgumentParser
        self.always_accept_server_certificate = True
        self.always_checkout = False
        self.auto_checkout = ''
        self.update_git_submodules = 'always'
        self.develeggs = ''
        self.config = MockConfig()
        self.parser = ArgumentParser()
        self.parsers = self.parser.add_subparsers(title="commands", metavar="")
        self.threads = 1


class GitRepo(object):
    def __init__(self, base):
        self.base = base
        self.url = 'file:///%s' % self.base
        self.process = Process(cwd=self.base)

    def __call__(self, cmd, **kw):
        return self.process.check_call(cmd, **kw)

    def init(self):
        os.mkdir(self.base)
        self("git init")

    def setup_user(self):
        self('git config user.email "florian.schulze@gmx.net"')
        self('git config user.name "Florian Schulze"')

    def add_file(self, fname, msg=None):
        repo_file = self.base[fname]
        repo_file.create_file(fname)
        self("git add %s" % repo_file, echo=False)
        if msg is None:
            msg = fname
        self("git commit %s -m %s" % (repo_file, msg), echo=False)

    def add_submodule(self, submodule, submodule_name):
        assert isinstance(submodule, GitRepo)
        self("git submodule add %s %s" % (submodule.url, submodule_name))
        self("git add .gitmodules")
        self("git add %s" % submodule_name)
        self("git commit -m 'Add submodule %s'" % submodule_name)

    def add_branch(self, bname, msg=None):
        self("git checkout -b %s" % bname)

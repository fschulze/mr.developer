from subprocess import Popen, PIPE
from mr.developer.compat import s
import os
import shutil
import sys
import tempfile
import threading
import unittest


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

    def pipe(self, cmd):
        rc, lines = self.popen(cmd, echo=False)
        if rc == 0 and lines:
            return lines[0]
        return ''

    def system(self, cmd):
        rc, lines = self.popen(cmd)
        return rc

    def os_system(self, cmd):
        # env *updates* os.environ
        if self.quiet:
            cmd = cmd + ' >%s 2>&1' % os.devnull
        if self.env:
            cmd = ''.join('export %s="%s"\n' % (k, v) for k, v in self.env.items()) + cmd
        return os.system(cmd)


class DirStack(object):
    """Stack of current working directories."""

    def __init__(self):
        self.stack = []

    def __len__(self):
        return len(self.stack)

    def push(self, dir):
        """Push cwd on stack and change to 'dir'.
        """
        self.stack.append(os.getcwd())
        os.chdir(dir)

    def pop(self):
        """Pop dir off stack and change to it.
        """
        if len(self.stack):
            os.chdir(self.stack.pop())


class JailSetup(unittest.TestCase):
    """Manage a temporary working directory."""

    dirstack = None
    tempdir = None

    def setUp(self):
        self.dirstack = DirStack()
        try:
            self.tempdir = os.path.realpath(self.mkdtemp())
            self.dirstack.push(self.tempdir)
        except:
            self.cleanUp()
            raise

    def tearDown(self):
        self.cleanUp()

    def cleanUp(self):
        if self.dirstack is not None:
            while self.dirstack:
                self.dirstack.pop()
        if self.tempdir is not None:
            if os.path.isdir(self.tempdir):
                shutil.rmtree(self.tempdir)

    def mkdtemp(self):
        return tempfile.mkdtemp()

    def mkfile(self, name, body=''):
        f = open(name, 'wt')
        try:
            f.write(body)
        finally:
            f.close()

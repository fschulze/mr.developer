# -*- coding: utf-8 -*-

from mr.developer import common
import os
import subprocess
import re
import sys


logger = common.logger

if sys.version_info < (3, 0):
    b = lambda x: x
    s = lambda x: x
else:
    b = lambda x: x.encode('ascii')
    s = lambda x: x.decode('ascii')


class GitError(common.WCError):
    pass


class GitWorkingCopy(common.BaseWorkingCopy):
    """The git working copy.

    Now supports git 1.5 and 1.6+ in a single codebase.
    """

    # TODO: make this configurable? It might not make sense however, as we
    # should make master and a lot of other conventional stuff configurable
    _upstream_name = "origin"

    def __init__(self, source):
        self.git_executable = common.which('git')
        if self.git_executable is None:
            logger.error("Cannot find git executable in PATH")
            sys.exit(1)
        if 'rev' in source and 'revision' in source:
            raise ValueError("The source definition of '%s' contains "
                             "duplicate revision options." % source['name'])
        # 'rev' is canonical
        if 'revision' in source:
            source['rev'] = source['revision']
            del source['revision']
        if 'branch' in source and 'rev' in source:
            logger.error("Cannot specify both branch (%s) and rev/revision "
                         "(%s) in source for %s",
                         source['branch'], source['rev'], source['name'])
            sys.exit(1)
        super(GitWorkingCopy, self).__init__(source)

    @common.memoize
    def git_version(self):
        cmd = self.run_git(['--version'])
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Could not determine git version")
            logger.error("'git --version' output was:\n%s\n%s" % (stdout, stderr))
            sys.exit(1)

        m = re.search(b("git version (\d+)\.(\d+)(\.\d+)?(\.\d+)?"), stdout)
        if m is None:
            logger.error("Unable to parse git version output")
            logger.error("'git --version' output was:\n%s\n%s" % (stdout, stderr))
            sys.exit(1)
        version = m.groups()

        if version[3] is not None:
            version = (
                int(version[0]),
                int(version[1]),
                int(version[2][1:]),
                int(version[3][1:])
            )
        elif version[2] is not None:
            version = (
                int(version[0]),
                int(version[1]),
                int(version[2][1:])
            )
        else:
            version = (int(version[0]), int(version[1]))
        if version < (1, 5):
            logger.error(
                "Git version %s is unsupported, please upgrade",
                ".".join([str(v) for v in version]))
            sys.exit(1)
        return version

    @property
    def _remote_branch_prefix(self):
        version = self.git_version()
        if version < (1, 6, 3):
            return self._upstream_name
        else:
            return 'remotes/%s' % self._upstream_name

    def run_git(self, commands, **kwargs):
        commands.insert(0, self.git_executable)
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE
        # This should ease things up when multiple processes are trying to send
        # back to the main one large chunks of output
        kwargs['bufsize'] = -1
        return subprocess.Popen(commands, **kwargs)

    def git_merge_rbranch(self, stdout_in, stderr_in):
        path = self.source['path']
        branch = self.source['branch']
        rbp = self._remote_branch_prefix
        cmd = self.run_git(["merge", "%s/%s" % (rbp, branch)], cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git merge of remote branch 'origin/%s' failed.\n%s" % (branch, stderr))
        return (stdout_in + stdout,
                stderr_in + stderr)

    def git_checkout(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        url = self.source['url']
        if os.path.exists(path):
            self.output((logger.info, "Skipped cloning of existing package '%s'." % name))
            return
        self.output((logger.info, "Cloned '%s' with git." % name))
        # here, but just on 1.6, if a branch was provided we could checkout it
        # directly via the -b <branchname> option instead of doing a separate
        # checkout later: I however think it outweighs the benefits
        cmd = self.run_git(["clone", "--quiet", url, path])
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git cloning of '%s' failed.\n%s" % (name, stderr))
        if 'branch' in self.source or 'rev' in self.source:
            stdout, stderr = self.git_switch_branch(stdout, stderr)
        if 'pushurl' in self.source:
            stdout, stderr = self.git_set_pushurl(stdout, stderr)

        update_git_submodules = self.source.get('submodules', kwargs['submodules'])
        if update_git_submodules in ['always', 'checkout']:
            stdout, stderr, initialized = self.git_init_submodules(stdout, stderr)
            # Update only new submodules that we just registered. this is for safety reasons
            # as git submodule update on modified subomdules may cause code loss
            for submodule in initialized:
                stdout, stderr = self.git_update_submodules(stdout, stderr, submodule=submodule)
                self.output((logger.info, "Initialized '%s' submodule at '%s' with git." % (name, submodule)))

        if kwargs.get('verbose', False):
            return stdout

    def git_switch_branch(self, stdout_in, stderr_in):
        path = self.source['path']
        branch = self.source.get('branch', 'master')
        rbp = self._remote_branch_prefix
        cmd = self.run_git(["branch", "-a"], cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("'git branch -a' failed.\n%s" % (branch, stderr))
        stdout_in += stdout
        stderr_in += stderr
        if 'rev' in self.source:
            # A tag or revision was specified instead of a branch
            argv = ["checkout", self.source['rev']]
        elif re.search(b("^(\*| ) %s$" % re.escape(branch)), stdout, re.M):
            # the branch is local, normal checkout will work
            argv = ["checkout", branch]
        elif re.search(b("^  " + re.escape(rbp) + "\/" + re.escape(branch)
                + "$"), stdout, re.M):
            # the branch is not local, normal checkout won't work here
            argv = ["checkout", "-b", branch, "%s/%s" % (rbp, branch)]
        else:
            logger.error("No such branch %r", branch)
            sys.exit(1)
        # runs the checkout with predetermined arguments
        cmd = self.run_git(argv, cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git checkout of branch '%s' failed.\n%s" % (branch, stderr))
        return (stdout_in + stdout,
                stderr_in + stderr)

    def git_update(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        self.output((logger.info, "Updated '%s' with git." % name))
        if 'rev' in self.source:
            # Specific revision, so we only fetch.  Pull is fetch plus
            # merge, which is not possible here.
            argv = ["fetch"]
        else:
            argv = ["pull"]
        cmd = self.run_git(argv, cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git pull of '%s' failed.\n%s" % (name, stderr))
        if 'rev' in self.source:
            stdout, stderr = self.git_switch_branch(stdout, stderr)
        elif 'branch' in self.source:
            stdout, stderr = self.git_switch_branch(stdout, stderr)
            stdout, stderr = self.git_merge_rbranch(stdout, stderr)

        update_git_submodules = self.source.get('submodules', kwargs['submodules'])
        if update_git_submodules in ['always']:
            stdout, stderr, initialized = self.git_init_submodules(stdout, stderr)
            # Update only new submodules that we just registered. this is for safety reasons
            # as git submodule update on modified subomdules may cause code loss
            for submodule in initialized:
                stdout, stderr = self.git_update_submodules(stdout, stderr, submodule=submodule)
                self.output((logger.info, "Initialized '%s' submodule at '%s' with git." % (name, submodule)))

        if kwargs.get('verbose', False):
            return stdout

    def checkout(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        update = self.should_update(**kwargs)
        if os.path.exists(path):
            if update:
                self.update(**kwargs)
            elif self.matches():
                self.output((logger.info, "Skipped checkout of existing package '%s'." % name))
            else:
                self.output((logger.warning, "Checkout URL for existing package '%s' differs. Expected '%s'." % (name, self.source['url'])))
        else:
            return self.git_checkout(**kwargs)

    def status(self, **kwargs):
        path = self.source['path']
        cmd = self.run_git(["status", "-s", "-b"], cwd=path)
        stdout, stderr = cmd.communicate()
        lines = stdout.strip().split(b('\n'))
        if len(lines) == 1:
            if b('ahead') in lines[0]:
                status = 'ahead'
            else:
                status = 'clean'
        else:
            status = 'dirty'
        if kwargs.get('verbose', False):
            return status, stdout
        else:
            return status

    def matches(self):
        name = self.source['name']
        path = self.source['path']
        # This is the old matching code: it does not work on 1.5 due to the
        # lack of the -v switch
        cmd = self.run_git(["remote", "show", "-n", self._upstream_name],
                           cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git remote of '%s' failed.\n%s" % (name, stderr))
        return (self.source['url'] in s(stdout).split())

    def update(self, **kwargs):
        name = self.source['name']
        if not self.matches():
            self.output((logger.warning, "Can't update package '%s' because its URL doesn't match." % name))
        if self.status() != 'clean' and not kwargs.get('force', False):
            raise GitError("Can't update package '%s' because it's dirty." % name)
        return self.git_update(**kwargs)

    def git_set_pushurl(self, stdout_in, stderr_in):
        cmd = self.run_git(
            [
                "config",
                "remote.%s.pushurl" % self._upstream_name,
                self.source['pushurl']],
            cwd=self.source['path'])
        stdout, stderr = cmd.communicate()

        if cmd.returncode != 0:
            raise GitError("git config remote.%s.pushurl %s \nfailed.\n" % (self._upstream_name, self.source['pushurl']))
        return (stdout_in + stdout, stderr_in + stderr)

    def git_init_submodules(self, stdout_in, stderr_in):
        cmd = self.run_git(
            [
                'submodule',
                'init'],
            cwd=self.source['path'])
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git submodule init failed.\n")
        initialized_submodules = re.findall(r'Submodule\s+[\'"](.*?)[\'"]\s+\(.+\)', s(stdout))
        return (stdout_in + stdout, stderr_in + stderr, initialized_submodules)

    def git_update_submodules(self, stdout_in, stderr_in, submodule='all'):
        params = ['submodule',
                  'update']
        if submodule != 'all':
            params.append(submodule)
        cmd = self.run_git(
            params,
            cwd=self.source['path'])
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git submodule update failed.\n")
        return (stdout_in + stdout, stderr_in + stderr)

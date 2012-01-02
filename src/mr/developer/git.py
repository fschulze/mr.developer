# -*- coding: utf-8 -*-

from mr.developer import common
import os
import subprocess
import re
import sys


logger = common.logger


class GitError(common.WCError):
    pass


class GitWorkingCopy(common.BaseWorkingCopy):
    """The git working copy base class, it holds methods that are not
    git-version dependant
    """

    def __init__(self, source, git_executable):
        self.git_executable = git_executable
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
        if 'branch' not in source:
            source['branch'] = 'master'
        super(GitWorkingCopy, self).__init__(source)

    def run_git(self, commands, **kwargs):
        commands.insert(0, self.git_executable)
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE
        return subprocess.Popen(commands, **kwargs)

    def git_merge_rbranch(self, stdout_in, stderr_in):
        path = self.source['path']
        branch = self.source['branch']
        cmd = self.run_git(["merge", "origin/%s" % branch], cwd=path)
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
        if 'branch' in self.source:
            stdout, stderr = self.git_switch_branch(stdout, stderr)
        if kwargs.get('verbose', False):
            return stdout

    def git_switch_branch(self, stdout_in, stderr_in):
        path = self.source['path']
        branch = self.source['branch']
        rbp = self.__class__._remote_branch_prefix
        cmd = self.run_git(["branch", "-a"], cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("'git branch -a' failed.\n%s" % (branch, stderr))
        stdout_in += stdout
        stderr_in += stderr
        if 'rev' in self.source:
            # A tag or revision was specified instead of a branch
            argv = ["checkout", self.source['rev']]
        elif re.search("^(\*| ) " + re.escape(branch) + "$", stdout, re.M):
            # the branch is local, normal checkout will work
            argv = ["checkout", branch]
        elif re.search("^  " + re.escape(rbp) + "\/" + re.escape(branch)
                + "$", stdout, re.M):
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
        cmd = self.run_git(["status"], cwd=path)
        stdout, stderr = cmd.communicate()
        lines = stdout.strip().split('\n')
        if 'nothing to commit (working directory clean)' in lines[-1]:
            status = 'clean'
        else:
            status = 'dirty'
        if kwargs.get('verbose', False):
            return status, stdout
        else:
            return status

    def update(self, **kwargs):
        name = self.source['name']
        if not self.matches():
            self.output((logger.warning, "Can't update package '%s' because its URL doesn't match." % name))
        if self.status() != 'clean' and not kwargs.get('force', False):
            raise GitError("Can't update package '%s' because it's dirty." % name)
        return self.git_update(**kwargs)


class Git15WorkingCopy(GitWorkingCopy):
    """The git 1.5 specific API
    """

    _remote_branch_prefix = "origin"

    def matches(self):
        name = self.source['name']
        path = self.source['path']
        # what we do here is first get the list of remotes, then do a
        # remote show <remotename> on each: if one matches we return true,
        # else we return false at the end (early bailout)
        cmd = self.run_git(["remote"], cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git remote of '%s' failed.\n%s" % (name, stderr))
        for remote in stdout.splitlines():
            if remote != '':
                cmd = self.run_git(["remote", "show", remote], cwd=path)
                stdout, stderr = cmd.communicate()
                if cmd.returncode != 0:
                    raise GitError("git remote show %s of '%s' failed.\n%s" % (remote, name, stderr))
                if self.source['url'] in stdout:
                    return True
        return False


class Git16WorkingCopy(GitWorkingCopy):
    """The git 1.6 specific API
    """

    _remote_branch_prefix = "remotes/origin"

    def matches(self):
        name = self.source['name']
        path = self.source['path']
        # This is the old matching code: it does not work on 1.5 due to the
        # lack of the -v switch
        cmd = self.run_git(["remote", "-v"], cwd=path)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git remote of '%s' failed.\n%s" % (name, stderr))
        return (self.source['url'] in stdout.split())


def gitWorkingCopyFactory(source):
    """This is the factory of git working copy classes: it will determine the
    version of git and load up the one with the correct API. Any returned
    instance is guaranted to pass isinstance(GitWorkingCopy)
    """
    # determines git version as API has been jumping up and down
    # this could also be ran at import time.

    git_executable = None
    for command in ['git', 'git.cmd']:
        try:
            cmd = subprocess.Popen([command],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            git_executable = command
            break
        except OSError, e:
            if getattr(e, 'errno', None) == 2:
                continue
            else:
                raise
    else:
        logger.error("Couldn't find 'git' executable on your PATH.")
        sys.exit(1)

    cmd = subprocess.Popen([git_executable, '--version'],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)

    stdout, stderr = cmd.communicate()
    if cmd.returncode != 0:
        logger.error("Could not determine git version")
        logger.error("'git --version' output was:\n%s\n%s" % (stdout, stderr))
        sys.exit(1)

    m = re.search("git version (\d+)\.(\d+)(\.\d+)?(\.\d+)?", stdout)
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
            "Git version %s is unsupported, please upgrade" % \
                ".".join([str(v) for v in version])
        )
        sys.exit(1)
    elif version > (1, 5) and version < (1, 6):
        return Git15WorkingCopy(source, git_executable)
    else:
        return Git16WorkingCopy(source, git_executable)


common.workingcopytypes['git'] = gitWorkingCopyFactory

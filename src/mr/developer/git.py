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
    
    def git_checkout(self, source, **kwargs):
        name = source['name']
        path = source['path']
        url = source['url']
        if os.path.exists(path):
            self.output((logger.info, "Skipped cloning of existing package '%s'." % name))
            return
        self.output((logger.info, "Cloning '%s' with git." % name))
        # here, but just on 1.6, if a branch was provided we could checkout it
        # directly via the -b <branchname> option instead of doing a separate
        # checkout later: I however think it outweighs the benefits
        cmd = subprocess.Popen(["git", "clone", "--quiet", url, path],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git cloning for '%s' failed.\n%s" % (name, stderr))
        if 'branch' in source:
            stdout, stderr = self.git_switch_branch(source, stdout, stderr)
        if kwargs.get('verbose', False):
            return stdout

    def git_update(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        self.output((logger.info, "Updating '%s' with git." % name))
        cmd = subprocess.Popen(["git", "pull"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git pull for '%s' failed.\n%s" % (name, stderr))
        if 'branch' in source:
            stdout, stderr = self.git_switch_branch(source, stdout, stderr)
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
                raise GitError("Checkout URL for existing package '%s' differs. Expected '%s'." % (name, self.source['url']))
        else:
            return self.git_checkout(**kwargs)

    def status(self, source, **kwargs):
        name = source['name']
        path = source['path']
        cmd = subprocess.Popen(["git", "status"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
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
        path = self.source['path']
        if not self.matches():
            raise GitError("Can't update package '%s', because it's URL doesn't match." % name)
        if self.status() != 'clean' and not kwargs.get('force', False):
            raise GitError("Can't update package '%s', because it's dirty." % name)
        return self.git_update(**kwargs)


class Git15WorkingCopy(GitWorkingCopy):
    """The git 1.5 specific API
    """

    def git_switch_branch(self, source, stdout_in, stderr_in):
        name = source['name']
        path = source['path']
        branch = source['branch']
        cmd = subprocess.Popen(["git", "branch", "-a"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("'git branch -a' failed.\n%s" % (branch, stderr))
        stdout_in += stdout
        stderr_in += stderr
        if re.search("^(\*| ) "+re.escape(branch)+"$", stdout, re.M):
            # the branch is local, normal checkout will work
            argv = ["git", "checkout", branch]
        elif re.search("^  origin\/"+re.escape(branch)+"$", stdout, re.M):
            # the branch is not local, normal checkout won't work here
            argv = ["git", "checkout", "-b", branch, "origin/%s" % branch]
        # runs the checkout with predetermined arguments
        cmd = subprocess.Popen(argv,
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git checkout of branch '%s' failed.\n%s" % (branch, stderr))
        return (stdout_in + stdout,
                stderr_in + stderr)

    def matches(self, source):
        name = source['name']
        path = source['path']
        # what we do here is first get the list of remotes, then do a
        # remote show <remotename> on each: if one matches we return true,
        # else we return false at the end (early bailout)
        cmd = subprocess.Popen(["git", "remote"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git remote for '%s' failed.\n%s" % (name, stderr))
        for remote in stdout.splitlines():
            if remote != '':
                cmd = subprocess.Popen(["git", "remote", "show", remote],
                                       cwd=path,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
                stdout, stderr = cmd.communicate()
                if cmd.returncode != 0:
                    raise GitError("git remote show %s for '%s' failed.\n%s" % (remote, name, stderr))
                if source['url'] in stdout:
                    return True
        return False


class Git16WorkingCopy(GitWorkingCopy):
    """The git 1.6 specific API
    """

    def git_switch_branch(self, source, stdout_in, stderr_in):
        name = source['name']
        path = source['path']
        branch = source['branch']
        # git 1.6, smart enough to figure out
        cmd = subprocess.Popen(["git", "checkout", branch],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git checkout of branch '%s' failed.\n%s" % (branch, stderr))
        return (stdout_in + stdout,
                stderr_in + stderr)

    def matches(self, source):
        name = source['name']
        path = source['path']
        # This is the old matching code: it does not work on 1.5 due to the
        # lack of the -v switch
        cmd = subprocess.Popen(["git", "remote", "-v"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git remote for '%s' failed.\n%s" % (name, stderr))
        return (source['url'] in stdout.split())

    
def gitWorkingCopyFactory(source):
    """This is the factory of git working copy classes: it will determine the
    version of git and load up the one with the correct API. Any returned
    instance is guaranted to pass isinstance(GitWorkingCopy)
    """
    # determines git version as API has been jumping up and down
    # this could also be ran at import time.
    try:
        cmd = subprocess.Popen(["git", "--version"],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    except OSError, e:
        if getattr(e, 'errno', None) == 2:
            logger.error("Couldn't find 'git' executable in your PATH.")
            sys.exit(1)
        raise

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

    if len(version) == 4:
        version = (
            int(version[0]),
            int(version[1]),
            int(version[2][1:]),
            int(version[3][1:])
        )
    elif len(version) == 3:
        version = (
            int(version[0]),
            int(version[1]),
            int(version[2][1:])
        )
    else:
        version = (int(version[0]), int(version[1]))
        
    if version < (1,5):
        logger.error(
            "Git version %s is unsupported, please upgrade" % \
                ".".join([str(v) for v in version])
        )
        sys.exit(1)
    elif version > (1,5) and version < (1,6):
        return Git15WorkingCopy(source)
    else:
        return Git16WorkingCopy(source)


common.workingcopytypes['git'] = gitWorkingCopyFactory

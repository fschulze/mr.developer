from mr.developer import common
import os
import subprocess
import re


logger = common.logger


class GitError(common.WCError):
    pass


class GitWorkingCopy(common.BaseWorkingCopy):
    def __init__(self, source):
        super(GitWorkingCopy, self).__init__(source)
        # determines git version as API has been jumping up and down
        cmd = subprocess.Popen(["git", "--version"],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git version failed.\n%s" % (stderr,))
        m = re.search("git version ([0-9]{1}\.[0-9]+)", stdout)
        if m is None:
            raise GitError("could not parse git output: %s" % (stdout,))
        self.git_version = m.group(1)
        
    def git_switch_branch(self, source, stdout_in, stderr_in):
        name = source['name']
        path = source['path']
        branch = source['branch']
        if self.git_version == "1.6":
            # git 1.6, smart enough to figure out
            argv = ["git", "checkout", branch]
        else:
            cmd = subprocess.Popen(["git", "branch", "-a"],
                                   cwd=path,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            stdout, stderr = cmd.communicate()
            if cmd.returncode != 0:
                raise GitError("git branch failed.\n%s" % (branch, stderr))
            stdout_in += stdout
            stderr_in += stderr
            # branch euristics start: either the branch is local already and we are
            # safe (think update) or if it's remote the handling changes from git
            # 1.5 to 1.6: with 1.6 being smart enough to figure out
            if re.search("^(\*| ) "+re.escape(branch)+"$", stdout, re.M):
                argv = ["git", "checkout", branch]
            elif re.search("^  origin\/"+re.escape(branch)+"$", stdout, re.M):
                # git 1.5: the funny -b switch is because I'm not totally sure of
                # how well parsing goes here
                argv = ["git", "checkout", "-b", branch, "origin/%s" % branch]
        cmd = subprocess.Popen(argv,
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git checkout of branch '%s' failed.\n%s" % (branch, stderr))
        return (stdout_in + stdout,
                stderr_in + stderr)

    def git_checkout(self, source, **kwargs):
        name = source['name']
        path = source['path']
        url = source['url']
        if os.path.exists(path):
            self.output((logger.info, "Skipped cloning of existing package '%s'." % name))
            return
        self.output((logger.info, "Cloning '%s' with git." % name))
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

    def git_update(self, source, **kwargs):
        name = source['name']
        path = source['path']
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

    def checkout(self, source, **kwargs):
        name = source['name']
        path = source['path']
        update = self.should_update(source, **kwargs)
        if os.path.exists(path):
            if update:
                self.update(source, **kwargs)
            elif self.matches(source):
                self.output((logger.info, "Skipped checkout of existing package '%s'." % name))
            else:
                raise GitError("Checkout URL for existing package '%s' differs. Expected '%s'." % (name, source['url']))
        else:
            return self.git_checkout(source, **kwargs)

    def matches(self, source):
        name = source['name']
        path = source['path']
        if self.git_version == "1.6":
            cmd = subprocess.Popen(["git", "remote", "-v"],
                                   cwd=path,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            stdout, stderr = cmd.communicate()
            if cmd.returncode != 0:
                raise GitError("git remote for '%s' failed.\n%s" % (name, stderr))
            return (source['url'] in stdout.split())
        else:
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

    def update(self, source, **kwargs):
        name = source['name']
        path = source['path']
        if not self.matches(source):
            raise GitError("Can't update package '%s', because it's URL doesn't match." % name)
        if self.status(source) != 'clean' and not kwargs.get('force', False):
            raise GitError("Can't update package '%s', because it's dirty." % name)
        return self.git_update(source, **kwargs)

common.workingcopytypes['git'] = GitWorkingCopy

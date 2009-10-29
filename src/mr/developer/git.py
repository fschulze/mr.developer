from mr.developer import common
import os
import subprocess


logger = common.logger


class GitError(common.WCError):
    pass


class GitWorkingCopy(common.BaseWorkingCopy):
    def git_checkout(self, source, **kwargs):
        name = source['name']
        path = source['path']
        url = source['url']
        if os.path.exists(path):
            logger.info("Skipped cloning of existing package '%s'." % name)
            return
        logger.info("Cloning '%s' with git." % name)
        cmd = subprocess.Popen(["git", "clone", "--quiet", url, path],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git cloning for '%s' failed.\n%s" % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def git_update(self, source, **kwargs):
        name = source['name']
        path = source['path']
        logger.info("Updating '%s' with git." % name)
        cmd = subprocess.Popen(["git", "pull"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git pull for '%s' failed.\n%s" % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def _gitcmd(self, name, path, gitcmd, *args):
        cmd = subprocess.Popen(["git", gitcmd]+list(args),
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git %s for '%s' failed.\n%s" % (gitcmd, name, stderr))
        return stdout


    def git_revision(self, source, **kwargs):
        name = source['name']
        path = source['path']
        revision = source['revision']
        logger.info("Checking out revision '%s' with git." % revision)
        try:
            # Assume it's a local branch/tag/SHA1
            stdout = self._gitcmd(name, path, 'checkout', revision)
        except GitError:
            # A remote branch, checkout as local branch
            stdout = self._gitcmd(name, path, 'checkout', '-b', revision, 'remotes/origin/'+revision)
            # TODO:
            # - remote tag
            # SHA1 are checked out without creating a branch
        if kwargs.get('verbose', False):
            return stdout


    def checkout(self, source, **kwargs):
        name = source['name']
        path = source['path']
        stdout = ''
        # checkout package
        if os.path.exists(path):
            if self.matches(source):
                logger.info("Skipped clone of existing package '%s'." % name)
                stdout = self.update(source, **kwargs) or ''
            else:
                raise GitError("Checkout URL for existing package '%s' differs. Expected '%s'." % (name, source['url']))
        else:
            stdout = self.git_checkout(source, **kwargs) or ''

        # get specific revision
        if source['revision']:
            stdout += self.git_revision(source, **kwargs) or ''

        return stdout


    def matches(self, source):
        name = source['name']
        path = source['path']
        cmd = subprocess.Popen(["git", "remote", "-v"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git remote for '%s' failed.\n%s" % (name, stderr))
        return (source['url'] in stdout.split())

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
        force = kwargs.get('force', False)
        if not self.matches(source):
            raise GitError("Can't update package '%s', because it's URL doesn't match." % name)
        if self.status(source) != 'clean' and not force:
            raise GitError("Can't update package '%s', because it's dirty." % name)
        return self.git_update(source, **kwargs)

wc = GitWorkingCopy('git')

from mr.developer import common
from mr.developer.svn import SVNWorkingCopy
import subprocess


logger = common.logger


class GitSVNError(common.WCError):
    pass


class GitSVNWorkingCopy(SVNWorkingCopy):

    def gitify_init(self, source, **kwargs):
        name = source['name']
        path = source['path']
        self.output((logger.info, "Gitifying '%s'." % name))
        cmd = subprocess.Popen(["gitify", "init"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitSVNError("gitify init for '%s' failed.\n%s" % (name, stdout))
        if kwargs.get('verbose', False):
            return stdout

    def svn_checkout(self, source, **kwargs):
        super(GitSVNWorkingCopy, self).svn_checkout(source, **kwargs)
        return self.gitify_init(source, **kwargs)

    def svn_switch(self, source, **kwargs):
        super(GitSVNWorkingCopy, self).svn_switch(source, **kwargs)
        return self.gitify_init(source, **kwargs)

    def svn_update(self, source, **kwargs):
        name = source['name']
        path = source['path']
        self.output((logger.info, "Updating '%s' with gitify." % name))
        cmd = subprocess.Popen(["gitify", "update"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitSVNError("gitify update for '%s' failed.\n%s" % (name, stdout))
        if kwargs.get('verbose', False):
            return stdout

    def status(self, source, **kwargs):
        svn_status = super(GitSVNWorkingCopy, self).status(source, **kwargs)
        if svn_status == 'clean':
            return common.workingcopytypes['git'](source).status(source, **kwargs)
        else:
            return svn_status

common.workingcopytypes['gitsvn'] = GitSVNWorkingCopy

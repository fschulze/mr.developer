from mr.developer import common
try:
    import xml.etree.ElementTree as etree
except ImportError:
    import elementtree.ElementTree as etree
import getpass
import os
import re
import subprocess
import sys

from mr.developer.svn import SVNWorkingCopy

logger = common.logger


class GitSVNError(common.WCError):
    pass


class GitSVNAuthorizationError(GitSVNError):
    pass


class GitSVNCertificateError(GitSVNError):
    pass


class GitSVNWorkingCopy(SVNWorkingCopy):

    def svn_checkout(self, source, **kwargs):
        result = super(GitSVNWorkingCopy, self).svn_checkout(source, **kwargs)
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

    def svn_switch(self, source, **kwargs):
        return self._svn_error_wrapper(self._svn_switch, source, **kwargs)

    def svn_update(self, source, **kwargs):
        return self._svn_error_wrapper(self._svn_update, source, **kwargs)

    def status(self, source, **kwargs):
        name = source['name']
        path = source['path']
        cmd = subprocess.Popen(["svn", "status", "--xml", path],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitSVNError("Subversion status for '%s' failed.\n%s" % (name, stderr))
        info = etree.fromstring(stdout)
        clean = True
        for target in info.findall('target'):
            for entry in target.findall('entry'):
                status = entry.find('wc-status')
                if status is not None and status.get('item') != 'external':
                    clean = False
                    break
        if clean:
            status = 'clean'
        else:
            status = 'dirty'
        if kwargs.get('verbose', False):
            cmd = subprocess.Popen(["svn", "status", path],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            stdout, stderr = cmd.communicate()
            if cmd.returncode != 0:
                raise GitSVNError("Subversion status for '%s' failed.\n%s" % (name, stderr))
            return status, stdout
        else:
            return status


common.workingcopytypes['gitsvn'] = GitSVNWorkingCopy

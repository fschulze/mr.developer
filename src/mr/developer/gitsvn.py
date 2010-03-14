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
        result = self._svn_error_wrapper(self._svn_checkout, source, **kwargs)
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

    def checkout(self, source, **kwargs):
        name = source['name']
        path = source['path']
        update = self.should_update(source, **kwargs)
        if os.path.exists(path):
            matches = self.matches(source)
            if matches:
                if update:
                    self.update(source, **kwargs)
                else:
                    self.output((logger.info, "Skipped checkout of existing package '%s'." % name))
            else:
                if self.status(source) == 'clean':
                    return self.svn_switch(source, **kwargs)
                else:
                    raise GitSVNError("Can't switch package '%s' from '%s', because it's dirty." % (name, source['url']))
        else:
            return self.svn_checkout(source, **kwargs)

    def matches(self, source):
        info = self._svn_info(source)
        url = source['url']
        rev = info.get('revision')
        match = re.search('^(.+)@(\\d+)$', url)
        if match:
            url = match.group(1)
            rev = match.group(2)
        if 'rev' in source and 'revision' in source:
            raise ValueError("The source definition of '%s' contains duplicate revision option." % source['name'])
        elif ('rev' in source or 'revision' in source) and match:
            raise ValueError("The url of '%s' contains a revision and there is an additional revision option." % source['name'])
        elif 'rev' in source:
            rev = source['rev']
        elif 'revision' in source:
            rev = source['revision']
        if url.endswith('/'):
            url = url[:-1]
        if rev.startswith('>='):
            return (info.get('url') == url) and (int(info.get('revision')) >= int(rev[2:]))
        elif rev.startswith('>'):
            return (info.get('url') == url) and (int(info.get('revision')) > int(rev[1:]))
        else:
            return (info.get('url') == url) and (info.get('revision') == rev)

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

    def update(self, source, **kwargs):
        name = source['name']
        path = source['path']
        force = kwargs.get('force', False)
        status = self.status(source)
        if not self.matches(source):
            if force or status == 'clean':
                return self.svn_switch(source, **kwargs)
            else:
                raise GitSVNError("Can't switch package '%s', because it's dirty." % name)
        if status != 'clean' and not force:
            raise GitSVNError("Can't update package '%s', because it's dirty." % name)
        return self.svn_update(source, **kwargs)

common.workingcopytypes['gitsvn'] = GitSVNWorkingCopy

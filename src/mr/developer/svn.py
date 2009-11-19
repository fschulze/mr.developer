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

logger = common.logger


class SVNError(common.WCError):
    pass


class SVNAuthorizationError(SVNError):
    pass


class SVNCertificateError(SVNError):
    pass


class SVNWorkingCopy(common.BaseWorkingCopy):
    def __init__(self, *args, **kwargs):
        self._svn_info_cache = {}
        self._svn_auth_cache = {}
        self.accept_invalid_certs = True

    def _svn_auth_get(self, url):
        for root in self._svn_auth_cache:
            if url.startswith(root):
                return self._svn_auth_cache[root]

    def _svn_error_wrapper(self, f, source, **kwargs):
        count = 4
        accept_invalid_cert = False
        while count:
            count = count - 1
            try:
                if accept_invalid_cert:
                    accept_invalid_cert = False
                    return f(source, accept_invalid_cert=True, **kwargs)
                else:
                    return f(source, **kwargs)
            except SVNAuthorizationError, e:
                lines = e.args[0].split('\n')
                root = lines[-1].split('(')[-1].strip(')')
                print "Authorization needed for '%s'" % source['url']
                user = raw_input("Username: ")
                passwd = getpass.getpass("Password: ")
                self._svn_auth_cache[root] = dict(
                    user=user,
                    passwd=passwd,
                )
            except SVNCertificateError, e:
                if self.accept_invalid_certs:
                    lines = e.args[0].split('\n')
                    root = lines[-1].split('(')[-1].strip(')')
                    accept_invalid_cert = True
                    # sadly this is not possible without pexpect
                    raise
                else:
                    raise

    def _svn_checkout(self, source, **kwargs):
        name = source['name']
        path = source['path']
        url = source['url']
        if os.path.exists(path):
            logger.info("Skipped checkout of existing package '%s'." % name)
            return
        logger.info("Checking out '%s' with subversion." % name)
        args = ["svn", "checkout", url, path]
        stdout, stderr, returncode = self._svn_communicate(args, url, **kwargs)
        if returncode != 0:
            raise SVNError("Subversion checkout for '%s' failed.\n%s" % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def _svn_communicate(self, args, url, **kwargs):
        accept_invalid_cert = kwargs.get('accept_invalid_cert', False)
        auth = self._svn_auth_get(url)
        if auth is not None:
            args[2:2] = ["--username", auth['user'],
                         "--password", auth['passwd']]
        if kwargs.get('verbose', False):
            args[2:2] = ["--no-auth-cache", "--non-interactive"]
        else:
            args[2:2] = ["--quiet", "--no-auth-cache", "--non-interactive"]
        if accept_invalid_cert:
            raise NotImplementedError
        env = dict(os.environ)
        env['LC_ALL'] = 'C'
        if accept_invalid_cert:
            cmd = subprocess.Popen(args, env=env,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            stdout, stderr = cmd.communicate('t')
        else:
            cmd = subprocess.Popen(args, env=env,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            lines = stderr.strip().split('\n')
            if 'authorization failed' in lines[-1]:
                raise SVNAuthorizationError(stderr.strip())
            if 'Server certificate verification failed: issuer is not trusted' in lines[-1]:
                raise SVNCertificateError(stderr.strip())
        return stdout, stderr, cmd.returncode

    def _svn_info(self, source):
        name = source['name']
        if name in self._svn_info_cache:
            return self._svn_info_cache[name]
        path = source['path']
        cmd = subprocess.Popen(["svn", "info", "--non-interactive", "--xml",
                                path],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise SVNError("Subversion info for '%s' failed.\n%s" % (name, stderr))
        info = etree.fromstring(stdout)
        result = {}
        entry = info.find('entry')
        if entry is not None:
            rev = entry.attrib.get('revision')
            if rev is not None:
                result['revision'] = rev
            info_url = entry.find('url')
            if info_url is not None:
                result['url'] = info_url.text
        entry = info.find('entry')
        if entry is not None:
            root = entry.find('root')
            if root is not None:
                result['root'] = root.text
        self._svn_info_cache[name] = result
        return result

    def _svn_switch(self, source, **kwargs):
        name = source['name']
        path = source['path']
        url = source['url']
        logger.info("Switching '%s' with subversion." % name)
        args = ["svn", "switch", url, path]
        rev = source.get('revision', source.get('rev'))
        if rev is not None and not rev.startswith('>'):
            args.insert(2, '-r%s' % rev)
        stdout, stderr, returncode = self._svn_communicate(args, url, **kwargs)
        if returncode != 0:
            raise SVNError("Subversion switch for '%s' failed.\n%s" % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def _svn_update(self, source, **kwargs):
        name = source['name']
        path = source['path']
        url = source['url']
        logger.info("Updating '%s' with subversion." % name)
        args = ["svn", "update", path]
        rev = source.get('revision', source.get('rev'))
        if rev is not None and not rev.startswith('>'):
            args.insert(2, '-r%s' % rev)
        stdout, stderr, returncode = self._svn_communicate(args, url, **kwargs)
        if returncode != 0:
            raise SVNError("Subversion update for '%s' failed.\n%s" % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def svn_checkout(self, source, **kwargs):
        return self._svn_error_wrapper(self._svn_checkout, source, **kwargs)

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
                    logger.info("Skipped checkout of existing package '%s'." % name)
            else:
                if self.status(source) == 'clean':
                    return self.svn_switch(source, **kwargs)
                else:
                    raise SVNError("Can't switch package '%s' from '%s', because it's dirty." % (name, source['url']))
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
            raise SVNError("Subversion status for '%s' failed.\n%s" % (name, stderr))
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
                raise SVNError("Subversion status for '%s' failed.\n%s" % (name, stderr))
            return status, stdout
        else:
            return status

    def update(self, source, **kwargs):
        name = source['name']
        path = source['path']
        force = kwargs.get('force', False)
        status = self.status(source)
        if status != 'clean' and not force:
            print >>sys.stderr, "The package '%s' is dirty." % name
            while 1:
                answer = raw_input("Do you want to update it anyway [y/N]? ")
                if answer.lower() in ('', 'n', 'no'):
                    break
                elif answer.lower() in ('y', 'yes'):
                    force = True
                    break
                else:
                    print >>sys.stderr, "You have to answer with y, yes, n or no."
        if not self.matches(source):
            if force or status == 'clean':
                return self.svn_switch(source, **kwargs)
            else:
                raise SVNError("Can't switch package '%s', because it's dirty." % name)
        if status != 'clean' and not force:
            raise SVNError("Can't update package '%s', because it's dirty." % name)
        return self.svn_update(source, **kwargs)

wc = SVNWorkingCopy('svn')

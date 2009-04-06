import elementtree.ElementTree as etree
import getpass
import logging
import os
import subprocess
import sys


logger = logging.getLogger("mr.developer")


class SVNError(Exception):
    pass


class SVNAuthorizationError(SVNError):
    pass


class SVNCertificateError(SVNError):
    pass


class GitError(Exception):
    pass


class WorkingCopies(object):
    def __init__(self, sources):
        self.sources = sources
        self._svn_info_cache = {}
        self._svn_auth_cache = {}
        self.accept_invalid_certs = True

    def _svn_auth_get(self, url):
        for root in self._svn_auth_cache:
            if url.startswith(root):
                return self._svn_auth_cache[root]

    def _svn_error_wrapper(self, f, source):
        count = 4
        accept_invalid_cert = False
        while count:
            count = count - 1
            try:
                if accept_invalid_cert:
                    accept_invalid_cert = False
                    return f(source, accept_invalid_cert=True)
                else:
                    return f(source)
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

    def _svn_checkout(self, source, accept_invalid_cert=False):
        name = source['name']
        path = source['path']
        url = source['url']
        if os.path.exists(path):
            logger.info("Skipped checkout of existing package '%s'." % name)
            return
        logger.info("Checking out '%s' with subversion." % name)
        args = ["svn", "checkout", url, path]
        stdout, stderr, returncode = self._svn_communicate(args, url, accept_invalid_cert)
        if returncode != 0:
            raise SVNError("Subversion checkout for '%s' failed.\n%s" % (name, stderr))

    def _svn_communicate(self, args, url, accept_invalid_cert):
        auth = self._svn_auth_get(url)
        if auth is not None:
            args[2:2] = ["--username", auth['user'],
                         "--password", auth['passwd']]
        args[2:2] = ["--quiet", "--no-auth-cache", "--non-interactive"]
        if accept_invalid_cert:
            raise NotImplementedError
        env = dict(os.environ)
        env['LC_ALL'] = 'C'
        if accept_invalid_cert:
            cmd = subprocess.Popen(args, env=env,
                                   stdin=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            stdout, stderr = cmd.communicate('t')
        else:
            cmd = subprocess.Popen(args, env=env,
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

    def _svn_switch(self, source, accept_invalid_cert=False):
        name = source['name']
        path = source['path']
        url = source['url']
        logger.info("Switching '%s' with subversion." % name)
        args = ["svn", "switch", url, path]
        stdout, stderr, returncode = self._svn_communicate(args, url, accept_invalid_cert)
        if returncode != 0:
            raise SVNError("Subversion switch for '%s' failed.\n%s" % (name, stderr))

    def _svn_update(self, source, accept_invalid_cert=False):
        name = source['name']
        path = source['path']
        url = source['url']
        logger.info("Updating '%s' with subversion." % name)
        args = ["svn", "update", path]
        stdout, stderr, returncode = self._svn_communicate(args, url, accept_invalid_cert)
        if returncode != 0:
            raise SVNError("Subversion update for '%s' failed.\n%s" % (name, stderr))

    def svn_checkout(self, source):
        return self._svn_error_wrapper(self._svn_checkout, source)

    def svn_matches(self, source):
        info = self._svn_info(source)
        return (info.get('url') == source['url'])

    def svn_status(self, source, verbose=False):
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
            if len(target.findall('entry')) > 0:
                clean = False
                break
        if clean:
            status = 'clean'
        else:
            status = 'dirty'
        if verbose:
            cmd = subprocess.Popen(["svn", "status", path],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            stdout, stderr = cmd.communicate()
            if cmd.returncode != 0:
                raise SVNError("Subversion status for '%s' failed.\n%s" % (name, stderr))
            return status, stdout
        else:
            return status

    def svn_switch(self, source):
        return self._svn_error_wrapper(self._svn_switch, source)

    def svn_update(self, source):
        return self._svn_error_wrapper(self._svn_update, source)

    def git_checkout(self, source):
        name = source['name']
        path = source['path']
        url = source['url']
        if os.path.exists(path):
            logger.info("Skipped cloning of existing package '%s'." % name)
            return
        logger.info("Cloning '%s' with git." % name)
        cmd = subprocess.Popen(["git", "clone", "--quiet", url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise GitError("git cloning for '%s' failed.\n%s" % (name, stderr))

    def git_matches(self, source):
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

    def git_status(self, source, verbose=False):
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
        if verbose:
            return status, stdout
        else:
            return status

    def git_update(self, source):
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

    def checkout(self, packages, skip_errors=False):
        errors = False
        for name in packages:
            if name not in self.sources:
                logger.error("Checkout failed. No source defined for '%s'." % name)
                if not skip_errors:
                    sys.exit(1)
                else:
                    errors = True
            source = self.sources[name]
            try:
                if source['kind']=='svn':
                    path = source['path']
                    if os.path.exists(path):
                        if self.svn_matches(source):
                            logger.info("Skipped checkout of existing package '%s'." % name)
                        else:
                            if self.svn_status(source) == 'clean':
                                self.svn_switch(source)
                            else:
                                logger.error("Can't switch package '%s' from '%s', because it's dirty." % (name, source['url']))
                                if not skip_errors:
                                    sys.exit(1)
                                else:
                                    errors = True
                    else:
                        self.svn_checkout(source)
                elif source['kind']=='git':
                    path = source['path']
                    if os.path.exists(path):
                        if self.git_matches(source):
                            logger.info("Skipped checkout of existing package '%s'." % name)
                        else:
                            logger.error("Checkout URL for existing package '%s' differs. Expected '%s'." % (name, source['url']))
                            if not skip_errors:
                                sys.exit(1)
                            else:
                                errors = True
                    else:
                        self.git_checkout(source)
                else:
                    logger.error("Unknown repository type '%s'." % kind)
                    if not skip_errors:
                        sys.exit(1)
                    else:
                        errors = True
            except (SVNError, GitError), e:
                for l in e.args[0].split('\n'):
                    logger.error(l)
                if not skip_errors:
                    sys.exit(1)
                else:
                    errors = True
        return errors

    def matches(self, source):
        name = source['name']
        if name not in self.sources:
            logger.error("Checkout failed. No source defined for '%s'." % name)
            sys.exit(1)
        source = self.sources[name]
        try:
            if source['kind']=='svn':
                return self.svn_matches(source)
            elif source['kind']=='git':
                return self.git_matches(source)
            else:
                logger.error("Unknown repository type '%s'." % kind)
                sys.exit(1)
        except (SVNError, GitError), e:
            for l in e.args[0].split('\n'):
                logger.error(l)
            sys.exit(1)

    def status(self, source, verbose=False):
        name = source['name']
        if name not in self.sources:
            logger.error("Status failed. No source defined for '%s'." % name)
            sys.exit(1)
        source = self.sources[name]
        try:
            if source['kind']=='svn':
                return self.svn_status(source, verbose=verbose)
            elif source['kind']=='git':
                return self.git_status(source, verbose=verbose)
            else:
                logger.error("Unknown repository type '%s'." % kind)
                sys.exit(1)
        except (SVNError, GitError), e:
            for l in e.args[0].split('\n'):
                logger.error(l)
            sys.exit(1)

    def update(self, packages):
        for name in packages:
            if name not in self.sources:
                continue
            source = self.sources[name]
            try:
                if source['kind']=='svn':
                    path = source['path']
                    if not self.svn_matches(source):
                        if self.svn_status(source) == 'clean':
                            self.svn_switch(source)
                        else:
                            logger.error("Can't switch package '%s', because it's dirty." % name)
                            continue
                    if self.svn_status(source) != 'clean':
                        logger.error("Can't update package '%s', because it's dirty." % name)
                        continue
                    self.svn_update(source)
                elif source['kind']=='git':
                    path = source['path']
                    if not self.git_matches(source):
                        logger.info("Skipped update of existing package '%s', because it's URL doesn't match." % name)
                        continue
                    if self.git_status(source) != 'clean':
                        logger.error("Can't update package '%s', because it's dirty." % name)
                        continue
                    self.git_update(source)
                else:
                    logger.error("Unknown repository type '%s'." % kind)
                    continue
            except (SVNError, GitError), e:
                for l in e.args[0].split('\n'):
                    logger.error(l)
                sys.exit(1)

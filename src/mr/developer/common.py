import elementtree.ElementTree as etree
import logging
import os
import subprocess
import sys


logger = logging.getLogger("mr.developer")


class WorkingCopies(object):
    def __init__(self, sources, sources_dir):
        self.sources = sources
        self.sources_dir = sources_dir

    def svn_checkout(self, name, url):
        path = os.path.join(self.sources_dir, name)
        if os.path.exists(path):
            logger.info("Skipped checkout of existing package '%s'." % name)
            return
        logger.info("Checking out '%s' with subversion." % name)
        cmd = subprocess.Popen(["svn", "checkout", "--quiet", url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Subversion checkout for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)

    def svn_matches(self, name, url):
        path = os.path.join(self.sources_dir, name)
        cmd = subprocess.Popen(["svn", "info", "--xml", path],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Subversion info for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)
        info = etree.fromstring(stdout)
        return (info.find('entry').find('url').text == url)

    def svn_status(self, name):
        path = os.path.join(self.sources_dir, name)
        cmd = subprocess.Popen(["svn", "status", "--xml", path],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Subversion status for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)
        info = etree.fromstring(stdout)
        clean = True
        for target in info.findall('target'):
            if len(target.findall('entry')) > 0:
                clean = False
                break
        if clean:
            return 'clean'
        else:
            return 'dirty'

    def svn_switch(self, name, url):
        path = os.path.join(self.sources_dir, name)
        logger.info("Switching '%s' with subversion." % name)
        cmd = subprocess.Popen(["svn", "switch", "--quiet", url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Subversion switch for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)

    def git_checkout(self, name, url):
        path = os.path.join(self.sources_dir, name)
        if os.path.exists(path):
            logger.info("Skipped cloning of existing package '%s'." % name)
            return
        logger.info("Cloning '%s' with git." % name)
        cmd = subprocess.Popen(["git", "clone", "--quiet", url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Git cloning for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)

    def git_matches(self, name, url):
        path = os.path.join(self.sources_dir, name)
        cmd = subprocess.Popen(["git", "remote", "-v"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Getting remote for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)
        return (url in stdout.split())

    def git_status(self, name):
        path = os.path.join(self.sources_dir, name)
        cmd = subprocess.Popen(["git", "status"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        lines = stdout.strip().split('\n')
        if 'nothing to commit (working directory clean)' in lines[-1]:
            return 'clean'
        else:
            return 'dirty'

    def checkout(self, packages, skip_errors=False):
        for name in packages:
            if name not in self.sources:
                logger.error("Checkout failed. No source defined for '%s'." % name)
                if not skip_errors:
                    sys.exit(1)
            kind, url = self.sources[name]
            if kind=='svn':
                path = os.path.join(self.sources_dir, name)
                if os.path.exists(path):
                    if self.svn_matches(name, url):
                        logger.info("Skipped checkout of existing package '%s'." % name)
                    else:
                        if self.svn_status(name) == 'clean':
                            self.svn_switch(name, url)
                        else:
                            logger.error("Can't switch package '%s', because it's dirty." % (name, url))
                            if not skip_errors:
                                sys.exit(1)
                else:
                    self.svn_checkout(name, url)
            elif kind=='git':
                path = os.path.join(self.sources_dir, name)
                if os.path.exists(path):
                    if self.git_matches(name, url):
                        logger.info("Skipped checkout of existing package '%s'." % name)
                    else:
                        logger.error("Checkout URL for existing package '%s' differs. Expected '%s'." % (name, url))
                        if not skip_errors:
                            sys.exit(1)
                else:
                    self.git_checkout(name, url)
            else:
                logger.error("Unknown repository type '%s'." % kind)
                if not skip_errors:
                    sys.exit(1)

    def matches(self, name):
        if name not in self.sources:
            logger.error("Checkout failed. No source defined for '%s'." % name)
            sys.exit(1)
        kind, url = self.sources[name]
        if kind=='svn':
            return self.svn_matches(name, url)
        elif kind=='git':
            return self.git_matches(name, url)
        else:
            logger.error("Unknown repository type '%s'." % kind)
            sys.exit(1)

    def status(self, name):
        if name not in self.sources:
            logger.error("Status failed. No source defined for '%s'." % name)
            sys.exit(1)
        kind, url = self.sources[name]
        if kind=='svn':
            return self.svn_status(name)
        elif kind=='git':
            return self.git_status(name)
        else:
            logger.error("Unknown repository type '%s'." % kind)
            sys.exit(1)

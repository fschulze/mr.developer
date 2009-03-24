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
        cmd = subprocess.Popen(["svn", "checkout", "--quiet",
                                url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Subversion checkout for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)

    def git_checkout(self, name, url):
        path = os.path.join(self.sources_dir, name)
        if os.path.exists(path):
            logger.info("Skipped cloning of existing package '%s'." % name)
            return
        logger.info("Cloning '%s' with git." % name)
        cmd = subprocess.Popen(["git", "clone", "--quiet",
                                url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Git cloning for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)

    def checkout(self, packages):
        for name in packages:
            if name not in self.sources:
                raise KeyError("Checkout failed. No source defined for '%s'." % name)
            kind, url = self.sources[name]
            if kind == 'svn':
                self.svn_checkout(name, url)
            elif kind == 'git':
                self.git_checkout(name, url)
            else:
                raise ValueError("Unknown repository type '%s'." % kind)

import logging
import os
import subprocess
import sys


logger = logging.getLogger("mr.developer")


def do_svn_checkout(packages, sources_dir):
    for name, url in packages:
        path = os.path.join(sources_dir, name)
        if os.path.exists(path):
            logger.info("Skipped checkout of existing package '%s'." % name)
            continue
        logger.info("Checking out '%s' with subversion." % name)
        cmd = subprocess.Popen(["svn", "checkout", "--quiet",
                                url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Subversion checkout for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)


def do_git_checkout(packages, sources_dir):
    for name, url in packages:
        path = os.path.join(sources_dir, name)
        if os.path.exists(path):
            logger.info("Skipped cloning of existing package '%s'." % name)
            continue
        logger.info("Cloning '%s' with git." % name)
        cmd = subprocess.Popen(["git", "clone", "--quiet",
                                url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logger.error("Git cloning for '%s' failed." % name)
            logger.error(stderr)
            sys.exit(1)


def do_checkout(packages, sources_dir):
    for kind in packages:
        if kind == 'svn':
            do_svn_checkout(sorted(packages[kind].iteritems()), sources_dir)
        elif kind == 'git':
            do_git_checkout(sorted(packages[kind].iteritems()), sources_dir)
        else:
            raise ValueError("Unknown repository type '%s'." % kind)

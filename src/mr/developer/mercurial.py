from mr.developer import common
import os
import subprocess

logger = common.logger

class MercurialError(common.WCError):
    pass

class MercurialWorkingCopy(common.BaseWorkingCopy):
    def hg_clone(self, source, verbose=False):
        name = source['name']
        path = source['path']
        url = source['url']
        if os.path.exists(path):
            logger.info('Skipped cloning of existing package %r.' % name)
            return
        logger.info('Cloning %r with mercurial.' % name)
        cmd = subprocess.Popen(
            ['hg', 'clone', '--quiet', '--noninteractive', url, path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg clone for %r failed.\n%s' % (name, stderr))
        if verbose:
            return stdout

    def hg_pull(self, source, verbose=False):
        name = source['name']
        path = source['path']
        logger.info('Updating %r with mercurial.' % name)
        cmd = subprocess.Popen(['hg', 'pull', '-u'], cwd=path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg pull for %r failed.\n%s' % (name, stderr))
        if verbose:
            return stdout

    def checkout(self, source, verbose=False):
        name = source['name']
        path = source['path']
        if os.path.exists(path):
            if self.matches(source):
                logger.info('Skipped checkout of existing package %r.' % name)
            else:
                raise MercurialError(
                    'Source URL for existing package %r differs. '
                    'Expected %r.' % (name, source['url']))
        else:
            return self.hg_clone(source, verbose=verbose)

    def matches(self, source):
        name = source['name']
        path = source['path']
        cmd = subprocess.Popen(
            ['hg', 'showconfig', 'paths.default'], cwd=path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg showconfig for %r failed.\n%s' % (name, stderr))
        return (source['url'] + '\n' == stdout)

    def status(self, source, verbose=False):
        name = source['name']
        path = source['path']
        cmd = subprocess.Popen(
            ['hg', 'status'], cwd=path, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        status = stdout and 'dirty' or 'clean'
        if verbose:
            return status, stdout
        else:
            return status

    def update(self, source, verbose=False):
        name = source['name']
        path = source['path']
        if not self.matches(source):
            raise MercurialError(
                "Can't update package %r, because it's URL doesn't match." %
                name)
        if self.status(source) != 'clean':
            raise MercurialError(
                "Can't update package %r, because it's dirty." % name)
        return self.hg_pull(source, verbose=verbose)

wc = MercurialWorkingCopy('hg')

from mr.developer import common
import os
import subprocess

logger = common.logger


class BazaarError(common.WCError):
    pass


class BazaarWorkingCopy(common.BaseWorkingCopy):

    def __init__(self, source):
        super(BazaarWorkingCopy, self).__init__(source)
        self.bzr_executable = common.which('bzr')

    def bzr_branch(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        url = self.source['url']
        if os.path.exists(path):
            self.output((logger.info,
                'Skipped branching existing package %r.' % name))
            return
        self.output((logger.info, 'Branched %r with bazaar.' % name))
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            [self.bzr_executable, 'branch', '--quiet', url, path],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise BazaarError(
                'bzr branch for %r failed.\n%s' % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def bzr_pull(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        url = self.source['url']
        self.output((logger.info, 'Updated %r with bazaar.' % name))
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen([self.bzr_executable, 'pull', url], cwd=path,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise BazaarError(
                'bzr pull for %r failed.\n%s' % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def checkout(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        update = self.should_update(**kwargs)
        if os.path.exists(path):
            if update:
                self.update(**kwargs)
            elif self.matches():
                self.output((logger.info,
                    'Skipped checkout of existing package %r.' % name))
            else:
                raise BazaarError(
                    'Source URL for existing package %r differs. '
                    'Expected %r.' % (name, self.source['url']))
        else:
            return self.bzr_branch(**kwargs)

    def matches(self):
        name = self.source['name']
        path = self.source['path']
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            [self.bzr_executable, 'info'], cwd=path,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise BazaarError(
                'bzr info for %r failed.\n%s' % (name, stderr))
        return (self.source['url'] in stdout.split())

    def status(self, **kwargs):
        path = self.source['path']
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            [self.bzr_executable, 'status'], cwd=path,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        status = stdout and 'dirty' or 'clean'
        if kwargs.get('verbose', False):
            return status, stdout
        else:
            return status

    def update(self, **kwargs):
        name = self.source['name']
        if not self.matches():
            raise BazaarError(
                "Can't update package %r because its URL doesn't match." %
                name)
        if self.status() != 'clean' and not kwargs.get('force', False):
            raise BazaarError(
                "Can't update package %r because it's dirty." % name)
        return self.bzr_pull(**kwargs)

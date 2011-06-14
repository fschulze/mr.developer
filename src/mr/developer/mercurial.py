from mr.developer import common
import os
import subprocess

logger = common.logger


class MercurialError(common.WCError):
    pass


class MercurialWorkingCopy(common.BaseWorkingCopy):
    def hg_clone(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        url = self.source['url']
        if os.path.exists(path):
            self.output((logger.info,
                'Skipped cloning of existing package %r.' % name))
            return
        self.output((logger.info, 'Cloned %r with mercurial.' % name))
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            ['hg', 'clone', '--quiet', '--noninteractive', url, path],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg clone for %r failed.\n%s' % (name, stderr))
        if 'branch' in self.source:
            stdout, stderr = self.hg_co_branch(stdout, stderr)
        if kwargs.get('verbose', False):
            return stdout

    def hg_pull(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        self.output((logger.info, 'Updated %r with mercurial.' % name))
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(['hg', 'pull', '-u'], cwd=path,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg pull for %r failed.\n%s' % (name, stderr))
        if 'branch' in self.source:
            stdout, stderr = self.hg_co_branch(stdout, stderr)
        if kwargs.get('verbose', False):
            return stdout

    def hg_get_branch(self):
        name = self.source['name']
        path = self.source['path']
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(['hg', 'branch'], cwd=path,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg branch for %r failed.\n%s' % (name, stderr))
        return stdout[:-1]

    def hg_co_branch(self, stdout_in, stderr_in):
        name = self.source['name']
        path = self.source['path']
        branch = self.source['branch']
        current_branch = self.hg_get_branch()
        if current_branch == branch:
            return stdout_in, stderr_in
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(['hg', 'co', branch], cwd=path,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg co %s for %r failed.\n%s' % (branch, name, stderr))
        return (stdout_in + stdout,
                stderr_in + stderr)

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
                raise MercurialError(
                    'Source URL for existing package %r differs. '
                    'Expected %r.' % (name, self.source['url']))
        else:
            return self.hg_clone(**kwargs)

    def matches(self):
        name = self.source['name']
        path = self.source['path']
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            ['hg', 'showconfig', 'paths.default'], cwd=path,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg showconfig for %r failed.\n%s' % (name, stderr))
        return (self.source['url'] + '\n' == stdout)

    def status(self, **kwargs):
        path = self.source['path']
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            ['hg', 'status'], cwd=path,
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
            raise MercurialError(
                "Can't update package %r because its URL doesn't match." %
                name)
        if self.status() != 'clean' and not kwargs.get('force', False):
            raise MercurialError(
                "Can't update package %r because it's dirty." % name)
        return self.hg_pull(**kwargs)

common.workingcopytypes['hg'] = MercurialWorkingCopy

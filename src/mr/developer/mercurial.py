from mr.developer import common
import os
import subprocess

logger = common.logger

class MercurialError(common.WCError):
    pass

class MercurialWorkingCopy(common.BaseWorkingCopy):

    def __init__(self, source):
        source.setdefault('branch', 'default')
        source.setdefault('rev')
        super(MercurialWorkingCopy, self).__init__(source)

    def hg_clone(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        url = self.source['url']
        branch = self.source['branch']
        rev = self.source['rev']

        if os.path.exists(path):
            self.output((logger.info, 'Skipped cloning of existing package %r.' % name))
            return
        if branch != 'default':
            if rev:
                raise ValueError("'branch' and 'rev' parameters cannot be used "
                    "simultanously")
            else:
                rev = branch
        else:
            rev = rev or 'default'


        self.output((logger.info, 'Cloned %r with mercurial.' % name))
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            ['hg', 'clone', '--update', rev, '--quiet', '--noninteractive', url, path],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg clone for %r failed.\n%s' % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def _update_to_rev(self, rev):
        path = self.source['path']
        name = self.source['name']
        env = dict(os.environ)
        cmd = subprocess.Popen(['hg', 'checkout', rev], cwd=path,
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode:
            raise MercurialError(
                'hg update for %r failed.\n%s' %(name, stderr))
        return stdout

    def hg_pull(self, **kwargs):
        # NOTE: we don't include the branch here as we just want to update
        # to the head of whatever branch the developer is working on
        # However the 'rev' parameter works differently and forces revision
        name = self.source['name']
        path = self.source['path']
        rev = self.source['rev']
        self.output((logger.info, 'Updated %r with mercurial.' % name))
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(['hg', 'pull', '-u'], cwd=path,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            # hg v2.1 pull returns non-zero return code in case of
            # no remote changes.
            if 'no changes found' not in stdout:
                raise MercurialError(
                    'hg pull for %r failed.\n%s' % (name, stderr))
        if rev:
            stdout += self._update_to_rev(rev)
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
                self.output((logger.info, 'Skipped checkout of existing package %r.' % name))
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
        # now check that the working branch is the same
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

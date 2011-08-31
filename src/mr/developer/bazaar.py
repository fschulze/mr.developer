from mr.developer import common
import os
import subprocess

logger = common.logger


def normalize_bzr_url(url):
    url = url.strip()
    if url.startswith('file://'):
        url = url[7:]   # no URI scheme-name for file URIs
    if url.startswith('/') and url.endswith('/'):
        url = url[:-1]  # no trailing slashes for file URIs
    if not url.startswith('/'):
        if not url.endswith('/'):
            url = '%s/' % url # append trailing slash to all non-file URIs
        url = url.replace('+junk', '%2Bjunk') # launchpad +junk branch URIs
    return url 


class BazaarError(common.WCError):
    pass


class BazaarWorkingCopy(common.BaseWorkingCopy):
    def bzr_branch(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        url = normalize_bzr_url(self.source['url'])
        rev = self.source.get('rev', self.source.get('revision', None))
        if os.path.exists(path):
            self.output((logger.info,
                'Skipped branching existing package %r.' % name))
            return
        self.output((logger.info, 'Branched %r with bazaar.' % name))
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        branch_spec = [url, path] 
        if rev:
            #non-empty rev: assume it conforms to `bzr help revisionspec`
            branch_spec = ['-r%s' % rev.strip()] + branch_spec
        cmd = subprocess.Popen(
            ['bzr', 'branch', '--quiet'] + branch_spec,
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
        url = normalize_bzr_url(self.source['url'])
        rev = self.source.get('rev', self.source.get('revision', None))
        self.output((logger.info, 'Updated %r with bazaar.' % name))
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        branch_spec = [url,] 
        if rev:
            if kwargs.get('force', False):
                # force means local (even committed) changes will be
                # overwritten to accommodate upstream.
                branch_spec += ['--overwrite']
            #non-empty rev: assume it conforms to `bzr help revisionspec`
            branch_spec = ['-r%s' % rev.strip()] + branch_spec
        cmd = subprocess.Popen(['bzr', 'pull',] + branch_spec, cwd=path,
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
                    'Expected %r.' % (name,
                                      normalize_bzr_url(self.source['url'])))
        else:
            return self.bzr_branch(**kwargs)

    def matches(self):
        name = self.source['name']
        path = self.source['path']
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            ['bzr', 'info'], cwd=path,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise BazaarError(
                'bzr info for %r failed.\n%s' % (name, stderr))
        return (normalize_bzr_url(self.source['url']) in stdout.split())

    def status(self, **kwargs):
        path = self.source['path']
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            ['bzr', 'status'], cwd=path,
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

common.workingcopytypes['bzr'] = BazaarWorkingCopy

from mr.developer import common
import os
import subprocess

logger = common.logger

class MercurialError(common.WCError):
    pass

class MercurialWorkingCopy(common.BaseWorkingCopy):
    def hg_clone(self, source, **kwargs):
        name = source['name']
        path = source['path']
        url = source['url']
        if os.path.exists(path):
            self.output((logger.info, 'Skipped cloning of existing package %r.' % name))
            return
        self.output((logger.info, 'Cloning %r with mercurial.' % name))
        cmd = subprocess.Popen(
            ['hg', 'clone', '--quiet', '--noninteractive', url, path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg clone for %r failed.\n%s' % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def hg_pull(self, source, **kwargs):
        name = source['name']
        path = source['path']
        self.output((logger.info, 'Updating %r with mercurial.' % name))
        cmd = subprocess.Popen(['hg', 'pull', '-u'], cwd=path,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                'hg pull for %r failed.\n%s' % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def checkout(self, source, **kwargs):
        name = source['name']
        path = source['path']
        update = self.should_update(source, **kwargs)
        if os.path.exists(path):
            if update:
                self.update(source, **kwargs)
            elif self.matches(source):
                self.output((logger.info, 'Skipped checkout of existing package %r.' % name))
            else:
                raise MercurialError(
                    'Source URL for existing package %r differs. '
                    'Expected %r.' % (name, source['url']))
        else:
            return self.hg_clone(source, **kwargs)

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

    def status(self, source, **kwargs):
        name = source['name']
        path = source['path']
        cmd = subprocess.Popen(
            ['hg', 'status'], cwd=path, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        status = stdout and 'dirty' or 'clean'
        if kwargs.get('verbose', False):
            return status, stdout
        else:
            return status

    def update(self, source, **kwargs):
        name = source['name']
        path = source['path']
        if not self.matches(source):
            raise MercurialError(
                "Can't update package %r, because its URL doesn't match." %
                name)
        if self.status(source) != 'clean' and not kwargs.get('force', False):
            raise MercurialError(
                "Can't update package %r, because it's dirty." % name)
        return self.hg_pull(source, **kwargs)

common.workingcopytypes['hg'] = MercurialWorkingCopy

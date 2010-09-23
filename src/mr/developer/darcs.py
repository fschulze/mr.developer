from mr.developer import common
import os
import subprocess


logger = common.logger


class DarcsError(common.WCError):
    pass

class DarcsWorkingCopy(common.BaseWorkingCopy):
    def darcs_checkout(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        url = self.source['url']
        if os.path.exists(path):
            self.output((logger.info, "Skipped getting of existing package '%s'." % name))
            return
        self.output((logger.info, "Getting '%s' with darcs." % name))
        cmd = subprocess.Popen(["darcs", "get", "--quiet", url, path],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise DarcsError("darcs get for '%s' failed.\n%s" % (name, stderr))
        if kwargs.get('verbose', False):
            return stdout

    def darcs_update(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        self.output((logger.info, "Updating '%s' with darcs." % name))
        cmd = subprocess.Popen(["darcs", "pull", "-a"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise DarcsError("darcs pull for '%s' failed.\n%s" % (name, stderr))
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
                self.output((logger.info, "Skipped checkout of existing package '%s'." % name))
            else:
                raise DarcsError("Checkout URL for existing package '%s' differs. Expected '%s'." % (name, self.source['url']))
        else:
            return self.darcs_checkout(**kwargs)

    def _darcs_info(self):
        name = self.source['name']
        path = self.source['path']
        cmd = subprocess.Popen(["darcs", "show", "repo"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise DarcsError("darcs info for '%s' failed.\n%s" % (name, stderr))
        lines = stdout.splitlines()
        d = {}
        for line in lines:
            k, v = line.split(': ')
            d[k.strip()] = v.strip()
        return d

    def matches(self):
        name = self.source['name']
        infos = self._darcs_info()
        return (self.source['url'] == infos.get('Default Remote', None))

    def status(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        cmd = subprocess.Popen(["darcs", "whatsnew"],
                               cwd=path,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        lines = stdout.strip().split('\n')
        if 'No changes' in lines[-1]:
            status = 'clean'
        else:
            status = 'dirty'
        if kwargs.get('verbose', False):
            return status, stdout
        else:
            return status

    def update(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        if not self.matches():
            raise DarcsError("Can't update package '%s', because it's URL doesn't match." % name)
        if self.status() != 'clean' and not kwargs.get('force', False):
            raise DarcsError("Can't update package '%s', because it's dirty." % name)
        return self.darcs_update(**kwargs)

common.workingcopytypes['darcs'] = DarcsWorkingCopy

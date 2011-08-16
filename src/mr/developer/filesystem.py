from mr.developer import common
import os

logger = common.logger

class FilesystemError(common.WCError):
    pass

class FilesystemWorkingCopy(common.BaseWorkingCopy):
    def checkout(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        if os.path.exists(path):
            if self.matches():
                self.output((logger.info, 'Filesystem package %r doesn\'t need a checkout.' % name))
            else:
                raise FilesystemError(
                    'Directory name for existing package %r differs. '
                    'Expected %r.' % (name, self.source['url']))
        else:
            raise FilesystemError(
                'Directory for package %r doesn\'t exist.' % name)
        return ''

    def matches(self):
        return os.path.split(self.source['path'])[1] == self.source['url']

    def status(self, **kwargs):
        return 'clean'

    def update(self, **kwargs):
        name = self.source['name']
        if not self.matches():
            raise FilesystemError(
                'Directory name for existing package %r differs. '
                'Expected %r.' % (name, self.source['url']))
        self.output((logger.info, 'Filesystem package %r doesn\'t need update.' % name))
        return ''

common.workingcopytypes['fs'] = FilesystemWorkingCopy

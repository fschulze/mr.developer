from mr.developer import common
import os

logger = common.logger

class FilesystemError(common.WCError):
    pass

class FilesystemWorkingCopy(common.BaseWorkingCopy):
    def checkout(self, source, **kwargs):
        name = source['name']
        path = source['path']
        if os.path.exists(path):
            if self.matches(source):
                self.output((logger.info, 'Filesystem package %r doesn\'t need a checkout.' % name))
            else:
                raise FilesystemError(
                    'Directory name for existing package %r differs. '
                    'Expected %r.' % (name, source['url']))
        else:
            raise FilesystemError(
                'Directory for package %r doesn\'t exist.' % name)
        return ''

    def matches(self, source):
        return os.path.split(source['path'])[1] == source['url']

    def status(self, source, **kwargs):
        return 'clean'

    def update(self, source, **kwargs):
        name = source['name']
        path = source['path']
        if not self.matches(source):
            raise FilesystemError(
                'Directory name for existing package %r differs. '
                'Expected %r.' % (name, source['url']))
        self.output((logger.info, 'Filesystem package %r doesn\'t need update.' % name))
        return ''

common.workingcopytypes['fs'] = FilesystemWorkingCopy

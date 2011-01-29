from mr.developer import common
import os
import sys
import re
import subprocess

logger = common.logger

class MercurialError(common.WCError):
    pass


class RepositoryInfo(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class MercurialWorkingCopy(common.BaseWorkingCopy):

    def hg_run_command(self, cmd_list, name, path, output=False):
        """Execute cmd_list for package called name in path.
        """
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        cmd = subprocess.Popen(
            cmd_list,
            cwd=path, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            raise MercurialError(
                '%s for %r failed.\n%s' % (' '.join(cmd_list), name, stderr))
        if output:
            return stdout
        return ''

    def hg_clone(self, info):
        """Run hg clone <repository url>.
        """
        if os.path.exists(info.path):
            self.output((logger.info, 'Skipped cloning of existing package %r.' % info.name))
            return
        self.output((logger.info, 'Cloned %r with mercurial.' % info.name))

        return self.hg_run_command(
            ['hg', 'clone', '--quiet', '--noninteractive', info.url, info.path],
            name=info.name, path=None, output=info.verbose)

    def hg_pull(self, run_update, info):
        """Run hg pull [-u].
        """
        self.output((logger.info, 'Updated %r with mercurial.' % info.name))
        cmd_list = ['hg', 'pull']
        if run_update:
            cmd_list.append('-u')
        return self.hg_run_command(
            cmd_list,
            name=info.name, path=info.path, output=info.verbose)

    def hg_switch_branch(self, info):
        """Run hg update <branch name>.
        """
        self.output(
            (logger.info,
             'Switch to branch %s for %r with mercurial.' % (
                    info.branch, info.name)))
        return self.hg_run_command(
            ['hg', 'update', '-r', 'branch(%r)' % info.branch],
            name=info.name, path=info.path, output=info.verbose)

    def hg_get_current_branch(self, info):
        """Return current repository selected branch: hg branch.
        """
        return self.hg_run_command(
            ['hg', 'branch'],
            name=info.name, path=info.path, output=True).strip()

    def get_info(self, **kwargs):
        name = self.source['name']
        path = self.source['path']
        url = self.source['url']
        branch = 'default'
        if '#' in url:
            url, branch = url.split('#', 1)
        url = url.rstrip('/')
        return RepositoryInfo(
            name=name, path=path, url=url, branch=branch,
            verbose=kwargs.get('verbose', False))

    def checkout(self, **kwargs):
        info = self.get_info(**kwargs)
        update = self.should_update(**kwargs)
        if os.path.exists(info.path):
            if update:
                self.update(**kwargs)
            elif self.matches(info):
                self.output(
                    (logger.info,
                     'Skipped checkout of existing package %r.' % info.name))
            else:
                raise MercurialError(
                    'Source URL for existing package %r differs. '
                    'Expected %r.' % (info.name, info.url))
        else:
            stdout = self.hg_clone(info)
            if info.branch != 'default':
                stdout += self.hg_switch_branch(info)
            return stdout

    def matches(self, **kwargs):
        info = self.get_info(**kwargs)
        current_url = self.hg_run_command(
            ['hg', 'showconfig', 'paths.default'],
            name=info.name, path=info.path, output=True).strip()
        if '#' in current_url:
            # There is a branch in the HG checkout URL.
            current_url = current_url.split('#')[0]
        return (info.url == current_url)

    def status(self, **kwargs):
        info = self.get_info(**kwargs)
        output = self.hg_run_command(
            ['hg', 'status'],
            name=info.name, path=info.path, output=True).strip()
        status = output and 'dirty' or 'clean'
        if info.verbose:
            return status, output
        else:
            return status

    def update(self, **kwargs):
        info = self.get_info(**kwargs)
        if not self.matches(**kwargs):
            raise MercurialError(
                "Can't update package %r, because its URL doesn't match." %
                info.name)
        if self.status(**kwargs) != 'clean' and not kwargs.get('force', False):
            raise MercurialError(
                "Can't update package %r, because it's dirty." % info.name)
        if info.branch != self.hg_get_current_branch(info):
            stdout = self.hg_pull(False, info)
            stdout += self.hg_switch_branch(info)
        else:
            stdout = self.hg_pull(True, info)
        return stdout


class MercurialPre17WorkingCopy(MercurialWorkingCopy):

    def hg_switch_branch(self, info):
        """Run hg update <branch name>.
        """
        self.output((logger.info, 'Switch to branch %s for %r with mercurial.' % (
                    info.branch, info.name)))
        return self.hg_run_command(
            ['hg', 'update', info.branch],
            name=info.name, path=info.path, output=info.verbose)


@apply
def mercurialVersion():
    """Determine mercurial version. If it is above 1.7, we can use the branch()
    revision notation.
    """
    try:
        cmd = subprocess.Popen(["hg", "--version"],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
    except OSError, e:
        if getattr(e, 'errno', None) == 2:
            logger.error(
                "Couldn't find Mercurial 'hg' executable in your PATH.")
            sys.exit(1)
        raise

    m = re.search("\(version (\d+)\.(\d+)(\.\d+)?(\.\d+)?\)", stdout)
    if m is None:
        logger.error("Unable to parse mercurial version output")
        logger.error("'hg --version' output was:\n%s\n%s" % (stdout, stderr))
        sys.exit(1)
    return m.groups()

def mercurialWorkingCopyFactory():
    if mercurialVersion < ('1', '7'):
        return MercurialPre17WorkingCopy
    return MercurialWorkingCopy

common.workingcopytypes['hg'] = mercurialWorkingCopyFactory()

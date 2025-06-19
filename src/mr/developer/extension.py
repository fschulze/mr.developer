from mr.developer.common import memoize, WorkingCopies, Config, get_workingcopytypes
import logging
import os
import re
import sys


FAKE_PART_ID = '_mr.developer'

logger = logging.getLogger("mr.developer")


def safe_name(name):
    """Convert an arbitrary string to a standard distribution name

    Any runs of non-alphanumeric/. characters are replaced with a single '-'.

    This is copied from pkg_resources.safe_name.
    (formerly setuptools.package_index.safe_name)
    """
    return re.sub('[^A-Za-z0-9.]+', '-', name)


class Source(dict):
    def exists(self):
        return os.path.exists(self['path'])


class Extension(object):
    def __init__(self, buildout):
        self.buildout = buildout
        self.buildout_dir = buildout['buildout']['directory']
        self.executable = sys.argv[0]

    @memoize
    def get_config(self):
        return Config(self.buildout_dir)

    def get_workingcopies(self):
        return WorkingCopies(
            self.get_sources(),
            threads=self.get_threads())

    @memoize
    def get_threads(self):
        threads = int(self.buildout['buildout'].get(
            'mr.developer-threads',
            self.get_config().threads))
        return threads

    @memoize
    def get_mrdev_verbose(self):
        return self.buildout['buildout'].get('mr.developer-verbose', '').lower() == 'true'

    @memoize
    def get_sources_dir(self):
        sources_dir = self.buildout['buildout'].get('sources-dir', 'src')
        if not os.path.isabs(sources_dir):
            sources_dir = os.path.join(self.buildout_dir, sources_dir)
        if os.path.isdir(self.buildout_dir) and not os.path.isdir(sources_dir):
            logger.info('Creating missing sources dir %s.' % sources_dir)
            os.mkdir(sources_dir)
        return sources_dir

    @memoize
    def get_sources(self):
        from zc.buildout.buildout import MissingSection
        sources_dir = self.get_sources_dir()
        sources = {}
        sources_section = self.buildout['buildout'].get('sources', 'sources')
        try:
            section = self.buildout[sources_section]
        except MissingSection:
            if sys.exc_info()[1].args[0] == sources_section:
                section = {}
            else:
                raise
        workingcopytypes = get_workingcopytypes()
        for name in section:
            info = section[name].split()
            options = []
            option_matcher = re.compile(r'[a-zA-Z0-9-]+=.*')
            for index, item in reversed(list(enumerate(info))):
                if option_matcher.match(item):
                    del info[index]
                    options.append(item)
            options.reverse()
            if len(info) < 2:
                logger.error("The source definition of '%s' needs at least the repository kind and URL." % name)
                sys.exit(1)
            kind = info[0]
            if kind not in workingcopytypes:
                logger.error("Unknown repository type '%s' for source '%s'." % (kind, name))
                sys.exit(1)
            url = info[1]

            path = None
            if len(info) > 2:
                if '=' not in info[2]:
                    logger.warning("You should use 'path=%s' to set the path." % info[2])
                    path = os.path.join(info[2], name)
                    if not os.path.isabs(path):
                        path = os.path.join(self.buildout_dir, path)
                    options[:0] = info[3:]
                else:
                    options[:0] = info[2:]

            if path is None:
                source = Source(kind=kind, name=name, url=url)
            else:
                source = Source(kind=kind, name=name, url=url, path=path)

            for option in options:
                key, value = option.split('=', 1)
                if not key:
                    raise ValueError("Option with no name '%s'." % option)
                if key in source:
                    raise ValueError("Key '%s' already in source info." % key)
                if key == 'path':
                    value = os.path.join(value, name)
                    if not os.path.isabs(value):
                        value = os.path.join(self.buildout_dir, value)
                if key == 'full-path':
                    if not os.path.isabs(value):
                        value = os.path.join(self.buildout_dir, value)
                if key == 'egg':
                    if value.lower() in ('true', 'yes', 'on'):
                        value = True
                    elif value.lower() in ('false', 'no', 'off'):
                        value = False
                if key == 'depth':
                    try:
                        not_used = int(value)  # noqa
                    except ValueError:
                        raise ValueError('depth value needs to be a number.')
                source[key] = value
            if 'path' not in source:
                if 'full-path' in source:
                    source['path'] = source['full-path']
                else:
                    source['path'] = os.path.join(sources_dir, name)

            if 'depth' not in source and \
                    self.get_git_clone_depth():
                source['depth'] = self.get_git_clone_depth()

            for rewrite in self.get_config().rewrites:
                rewrite(source)

            sources[name] = source

        return sources

    @memoize
    def get_auto_checkout(self):
        packages = set(self.get_sources().keys())

        auto_checkout = set(
            self.buildout['buildout'].get('auto-checkout', '').split()
        )
        if '*' in auto_checkout:
            auto_checkout = packages

        if not auto_checkout.issubset(packages):
            diff = list(sorted(auto_checkout.difference(packages)))
            if len(diff) > 1:
                pkgs = "%s and '%s'" % (", ".join("'%s'" % x for x in diff[:-1]), diff[-1])
                logger.error("The packages %s from auto-checkout have no source information." % pkgs)
            else:
                logger.error("The package '%s' from auto-checkout has no source information." % diff[0])
            sys.exit(1)

        return auto_checkout

    def get_always_checkout(self):
        return self.buildout['buildout'].get('always-checkout', False)

    def get_update_git_submodules(self):
        return self.buildout['buildout'].get('update-git-submodules', 'always')

    def get_git_clone_depth(self):
        value = self.buildout['buildout'].get('git-clone-depth', '')
        if value:
            try:
                not_used = int(value)  # noqa
            except ValueError:
                raise ValueError('git-clone-depth needs to be a number.')
        return value

    def get_develop_info(self):
        auto_checkout = self.get_auto_checkout()
        sources = self.get_sources()
        develop = self.buildout['buildout'].get('develop', '')
        versions_section = self.buildout['buildout'].get('versions')
        versions = self.buildout._raw.get(versions_section, {})
        develeggs = {}
        develeggs_order = []
        for path in develop.split():
            # strip / from end of path
            head, tail = os.path.split(path.rstrip('/'))
            develeggs[tail] = path
            develeggs_order.append(tail)
        config_develop = self.get_config().develop
        for name in sources:
            source = sources[name]
            if source.get('egg', True) and name not in develeggs:
                path = sources[name]['path']
                status = config_develop.get(name, name in auto_checkout)
                if os.path.exists(path) and status:
                    if name in auto_checkout:
                        config_develop.setdefault(name, 'auto')
                    else:
                        if status == 'auto':
                            if name in config_develop:
                                del config_develop[name]
                                continue
                        config_develop.setdefault(name, True)
                    develeggs[name] = path
                    develeggs_order.append(name)
                    versions[safe_name(name)] = ''
        develop = []
        for path in [develeggs[k] for k in develeggs_order]:
            if path.startswith(self.buildout_dir):
                develop.append(path[len(self.buildout_dir) + 1:])
            else:
                develop.append(path)
        return develop, develeggs, versions

    def get_always_accept_server_certificate(self):
        always_accept_server_certificate = self.buildout['buildout'].get('always-accept-server-certificate', False)
        if isinstance(always_accept_server_certificate, bool):
            pass
        elif always_accept_server_certificate.lower() in ('true', 'yes', 'on'):
            always_accept_server_certificate = True
        elif always_accept_server_certificate.lower() in ('false', 'no', 'off'):
            always_accept_server_certificate = False
        else:
            logger.error("Unknown value '%s' for always-accept-server-certificate option." % always_accept_server_certificate)
            sys.exit(1)
        return always_accept_server_certificate

    def add_fake_part(self):
        if FAKE_PART_ID in self.buildout._raw:
            logger.error("The buildout already has a '%s' section, this shouldn't happen" % FAKE_PART_ID)
            sys.exit(1)
        self.buildout._raw[FAKE_PART_ID] = dict(
            recipe='zc.recipe.egg',
            eggs='mr.developer',
        )
        # insert the fake part
        parts = self.buildout['buildout']['parts'].split()
        parts.insert(0, FAKE_PART_ID)
        self.buildout['buildout']['parts'] = " ".join(parts)

    def __call__(self):
        config = self.get_config()

        # store arguments when running from buildout
        if os.path.split(self.executable)[1] in ('buildout', 'buildout-script.py'):
            config.buildout_args = list(sys.argv)

        auto_checkout = self.get_auto_checkout()

        root_logger = logging.getLogger()
        workingcopies = self.get_workingcopies()
        always_checkout = self.get_always_checkout()
        update_git_submodules = self.get_update_git_submodules()
        always_accept_server_certificate = self.get_always_accept_server_certificate()
        (develop, develeggs, versions) = self.get_develop_info()

        packages = set(auto_checkout)
        sources = self.get_sources()
        for pkg in develeggs:
            if pkg in sources:
                if always_checkout or sources[pkg].get('update'):
                    packages.add(pkg)

        offline = self.buildout['buildout'].get('offline', '').lower() == 'true'
        verbose = root_logger.level <= 10 or self.get_mrdev_verbose()
        workingcopies.checkout(sorted(packages),
                               verbose=verbose,
                               update=always_checkout,
                               submodules=update_git_submodules,
                               always_accept_server_certificate=always_accept_server_certificate,
                               offline=offline)

        # get updated info after checkout
        (develop, develeggs, versions) = self.get_develop_info()

        if versions:
            import zc.buildout.easy_install
            zc.buildout.easy_install.default_versions(dict(versions))

        self.buildout['buildout']['develop'] = "\n".join(develop)
        self.buildout['buildout']['sources-dir'] = self.get_sources_dir()

        self.add_fake_part()

        config.save()


def extension(buildout=None):
    return Extension(buildout)()

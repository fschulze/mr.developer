from mr.developer.common import WorkingCopies, Config
import logging
import os
import sys


FAKE_PART_ID = '_mr.developer'

logger = logging.getLogger("mr.developer")


def memoize(f, _marker=[]):
    def g(*args, **kwargs):
        name = '_memoize_%s' % f.__name__
        value = getattr(args[0], name, _marker)
        if value is _marker:
            value = f(*args, **kwargs)
            setattr(args[0], name, value)
        return value
    return g


class Extension(object):
    def __init__(self, buildout):
        self.buildout = buildout
        self.buildout_dir = buildout['buildout']['directory']
        self.executable = sys.argv[0]

    @memoize
    def get_config(self):
        return Config(self.buildout_dir)

    def get_workingcopies(self):
        return WorkingCopies(self.get_sources())

    @memoize
    def get_sources(self):
        sources_dir = self.buildout['buildout'].get('sources-dir', 'src')
        if not os.path.isabs(sources_dir):
            sources_dir = os.path.join(self.buildout_dir, sources_dir)

        sources = {}
        sources_section = self.buildout['buildout'].get('sources', 'sources')
        section = self.buildout.get(sources_section, {})
        for name in section:
            info = section[name].split()
            kind = info[0]
            url = info[1]

            for rewrite in self.get_config().rewrites:
                if len(rewrite) == 2 and url.startswith(rewrite[0]):
                    url = "%s%s" % (rewrite[1], url[len(rewrite[0]):])

            if len(info) > 2:
                path = os.path.join(info[2], name)
                if not os.path.isabs(path):
                    path = os.path.join(self.buildout_dir, path)
            else:
                path = os.path.join(sources_dir, name)

            sources[name] = dict(kind=kind, name=name, url=url, path=path)

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

    def get_develop_info(self):
        auto_checkout = self.get_auto_checkout()
        sources = self.get_sources()
        develop = self.buildout['buildout'].get('develop', '')
        versions_section = self.buildout['buildout'].get('versions')
        versions = self.buildout.get(versions_section, {})
        develeggs = {}
        for path in develop.split():
            head, tail = os.path.split(path)
            develeggs[tail] = path
        config_develop = self.get_config().develop
        for name in sources:
            if name not in develeggs:
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
                    if name in versions:
                        del versions[name]
        develop = []
        for path in develeggs.itervalues():
            if path.startswith(self.buildout_dir):
                develop.append(path[len(self.buildout_dir)+1:])
            else:
                develop.append(path)
        return develop, develeggs, versions

    def add_fake_part(self):
        if FAKE_PART_ID in self.buildout._raw:
            logger.error("mr.developer: The buildout already has a '%s' section, this shouldn't happen" % FAKE_PART_ID)
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
        if os.path.split(self.executable)[1] == 'buildout':
            config.buildout_args = list(sys.argv)

        auto_checkout = self.get_auto_checkout()

        root_logger = logging.getLogger()
        workingcopies = self.get_workingcopies()
        workingcopies.checkout(sorted(auto_checkout),
                               verbose=root_logger.level <= 10)

        (develop, develeggs, versions) = self.get_develop_info()

        if versions:
            import zc.buildout.easy_install
            zc.buildout.easy_install.default_versions(dict(versions))

        self.buildout['buildout']['develop'] = "\n".join(develop)

        self.add_fake_part()

        config.save()


def extension(buildout=None):
    return Extension(buildout)()

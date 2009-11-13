from mr.developer.common import WorkingCopies, Config
from pprint import pformat
import logging
import os
import sys


FAKE_PART_ID = '_mr.developer'

logger = logging.getLogger("mr.developer")


class Extension(object):
    def __init__(self, buildout):
        self.buildout = buildout
        self.buildout_dir = buildout['buildout']['directory']
        self.executable = sys.argv[0]

    def get_config(self):
        config = getattr(self, '_config', None)
        if config is None:
            self._config = config = Config(self.buildout_dir)
        return config

    def get_workingcopies(self):
        return WorkingCopies(self.get_sources())

    def get_sources(self):
        sources = getattr(self, '_sources', None)
        if sources is not None:
            return sources
        buildout = self.buildout
        sources_dir = buildout['buildout'].get('sources-dir', 'src')
        if not os.path.isabs(sources_dir):
            sources_dir = os.path.join(self.buildout_dir, sources_dir)

        self._sources = sources = {}
        section = buildout.get(buildout['buildout'].get('sources', 'sources'), {})
        for name, info in section.iteritems():
            info = info.split()
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

    def get_auto_checkout(self):
        auto_checkout = getattr(self, '_auto_checkout', None)
        if auto_checkout is not None:
            return auto_checkout
        buildout = self.buildout
        sources = self.get_sources()

        auto_checkout = set(
            buildout['buildout'].get('auto-checkout', '').split()
        )
        if '*' in auto_checkout:
            auto_checkout = set(sources.keys())
        self._auto_checkout = auto_checkout

        if not auto_checkout.issubset(set(sources.keys())):
            diff = list(sorted(auto_checkout.difference(set(sources.keys()))))
            if len(diff) > 1:
                pkgs = "%s and '%s'" % (", ".join("'%s'" % x for x in diff[:-1]), diff[-1])
                logger.error("The packages %s from auto-checkout have no source information." % pkgs)
            else:
                logger.error("The package '%s' from auto-checkout has no source information." % diff[0])
            sys.exit(1)

        return auto_checkout

    def get_develop_info(self):
        buildout = self.buildout
        config = self.get_config()
        auto_checkout = self.get_auto_checkout()
        sources = self.get_sources()
        develop = buildout['buildout'].get('develop', '')
        versions = buildout.get(buildout['buildout'].get('versions'), {})
        develeggs = {}
        for path in develop.split():
            head, tail = os.path.split(path)
            develeggs[tail] = path
        for name in sources:
            if name not in develeggs:
                path = sources[name]['path']
                status = config.develop.get(name, name in auto_checkout)
                if os.path.exists(path) and status:
                    if name in auto_checkout:
                        config.develop.setdefault(name, 'auto')
                    else:
                        if status == 'auto':
                            if name in config.develop:
                                del config.develop[name]
                                continue
                        config.develop.setdefault(name, True)
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

    def add_fake_part(self, **kwargs):
        buildout = self.buildout
        if FAKE_PART_ID in buildout._raw:
            logger.error("mr.developer: The buildout already has a '%s' section, this shouldn't happen" % FAKE_PART_ID)
            sys.exit(1)
        buildout._raw[FAKE_PART_ID] = dict(
            recipe='zc.recipe.egg',
            eggs='mr.developer',
            arguments=',\n'.join("=".join(x) for x in kwargs.items()),
        )
        # insert the fake part
        parts = buildout['buildout']['parts'].split()
        parts.insert(0, FAKE_PART_ID)
        buildout['buildout']['parts'] = " ".join(parts)

    def __call__(self):
        buildout = self.buildout
        buildout_dir = self.buildout_dir
        config = self.get_config()

        # store arguments when running from buildout
        if os.path.split(self.executable)[1] == 'buildout':
            config.buildout_args = list(sys.argv)

        sources = self.get_sources()

        auto_checkout = self.get_auto_checkout()

        root_logger = logging.getLogger()
        workingcopies = self.get_workingcopies()
        workingcopies.checkout(sorted(auto_checkout),
                               verbose=root_logger.level <= 10)

        develop, develeggs, versions = self.get_develop_info()
        if versions:
            import zc.buildout.easy_install
            zc.buildout.easy_install.default_versions(dict(versions))
        buildout['buildout']['develop'] = "\n".join(develop)

        self.add_fake_part(
            sources = pformat(sources),
            auto_checkout = pformat(auto_checkout),
            buildout_dir = '%r' % buildout_dir,
            develeggs = pformat(develeggs),
        )

        config.save()


def extension(buildout=None):
    return Extension(buildout)()

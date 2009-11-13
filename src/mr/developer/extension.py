from mr.developer.common import WorkingCopies, Config
from pprint import pformat
import logging
import os
import re
import sys


FAKE_PART_ID = '_mr.developer'

logger = logging.getLogger("mr.developer")


def report_error():
    logger.error("*"*40)
    logger.error("There have been errors during checkout, check the output above or use 'develop status'.")
    logger.error("*"*40)


def sourcefromcfgline(config, name, info):
    """Factory for sources defined by info

    info format:
        <name> = <kind> <repo_url> [path] \
            [rev[ision]=<revision] [pkgbasedir=<pkgbasedir>]

        >>> config = UserDict()
        >>> config.namedrepos = {}
        >>> config.rewrites = dict(
        ...         local = [[]],
        ...         defaultcfg = [[]],
        ...         )
        >>> config.sources_dir = 'src'
        >>> config.buildout_dir = '/buildout/dir'

    A generic repo using the default sources_dir:

        >>> info = "kind repo://url/example"
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['name'] == 'name'
        True
        >>> src['kind'] == 'kind'
        True
        >>> src['url'] == 'repo://url/example'
        True
        >>> src['path'] == 'src/name'
        True
        >>> src['pkgbasedir'] is None
        True

    Alternative sources_dir:

        >>> info = "kind repo://url/example othersrc"
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['path'] == 'othersrc/name'
        True

    Named repository:

        >>> config.namedrepos['repo1'] = (
        ...     'repo1:', 'xyz://repo1.url/', 'kind1')
        >>> info = "repo1:rel/path"
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['kind']
        'kind1'
        >>> src['url']
        'xyz://repo1.url/rel/path'

    Overruling kind for a named repository:

        >>> info = "mykind repo1:rel/path"
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['kind']
        'mykind'
        >>> src['url']
        'xyz://repo1.url/rel/path'

    Defaultcfg rewrite performed after one round of named repo rewrite:

        >>> config.rewrites['defaultcfg'].append(
        ...     ('xyz://repo1.url/', 'user@repo1.url:'))
        >>> info = "repo1:rel/path"
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['url']
        'user@repo1.url:rel/path'

    Local rewrites overruling defaultcfg:

        >>> config.rewrites['local'].append(
        ...     ('xyz://repo1.url/', 'otheruser@repo1.url:'))
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['url']
        'otheruser@repo1.url:rel/path'

    Rewriting with regular expression

        >>> config.rewrites['local'].append(
        ...     ('re.sub', 'other(.*)/path', r'\\1'))
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['url']
        'user@repo1.url:rel'

        >>> config.rewrites['local'].append(
        ...     ('re.sub', ':rel$'))
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['url']
        'user@repo1.url'

    Revision:

        >>> info = "repo1:rel/path rev=rev/spec1"
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['revision']
        'rev/spec1'

        >>> info = "repo1:rel/path revision=rev/spec1"
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['revision']
        'rev/spec1'

    Revision and path:

        >>> info = "repo1:rel/path othersrc rev=rev/spec1"
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['path']
        'othersrc/name'
        >>> src['revision']
        'rev/spec1'

    Project repositories:

        >>> info = "repo1:rel/path rev=rev/spec1 pkgbasedir="
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['path']
        'src/name'
        >>> src['pkgbasedir']
        ''
        >>> src['revision']
        'rev/spec1'

        >>> info = "repo1:rel/path rev=rev/spec1 pkgbasedir=subdir"
        >>> src = sourcefromcfgline(config, 'name', info)
        >>> src['path']
        'src/name'
        >>> src['pkgbasedir']
        'subdir'
    """
    info = info.split()

    # figure out what arguments we got
    arg0 = info.pop(0)
    if ':' in arg0:
        # kind of hackish, named repos eventually shouldnt be rewrites
        reponame = arg0.split(':',1)[0]
        kind = config.namedrepos[reponame][2]
        url = arg0
    else:
        kind = arg0
        url = info.pop(0)

    # perform url rewrites
    for rewrite in filter(None, config.namedrepos.values() + \
                config.rewrites['local'] + \
                config.rewrites['defaultcfg']):
        # regex substitution
        if rewrite[0] == 're.sub':
            pattern = rewrite[1]
            try:
                repl = rewrite[2]
            except IndexError:
                repl = ''
            url = re.sub(pattern, repl, url)
            continue
        # replacement at beginning of url
        if url.startswith(rewrite[0]):
            url = "%s%s" % (rewrite[1], url[len(rewrite[0]):])

    # derive relative path to package
    if len(info) and not '=' in info[0]:
        path = os.path.join(info.pop(0), name)
        # XXX:
        #if not os.path.isabs(path):
        #    path = os.path.join(config.buildout_dir, path)
    else:
        path = os.path.join(config.sources_dir, name)

    revision = None
    pkgbasedir = None
    while len(info):
        if not '=' in info[0]:
            #XXX: Make this nice
            raise RuntimeError('Only keyword arguments allowed')
        if info[0].startswith('rev'):
            revision = info.pop(0).split('=')[1]
            continue
        if info[0].startswith('pkgbasedir'):
            pkgbasedir = info.pop(0).split('=')[1]
            continue
        #XXX: Make this nice
        raise NotImplemented
    source = dict(kind=kind, name=name, url=url, path=path,
            revision=revision, pkgbasedir=pkgbasedir)
    return source


def extension(buildout=None):
    import zc.buildout.easy_install

    buildout_dir = buildout['buildout']['directory']
    sources_dir = buildout['buildout'].get('sources-dir', 'src')
    if not os.path.isabs(sources_dir):
        sources_dir = os.path.join(buildout_dir, sources_dir)

    config = Config(buildout_dir, sources_dir)
    if os.path.split(sys.argv[0])[1] == 'buildout':
        config.buildout_args = list(sys.argv)

    sources = {}
    section = buildout.get(buildout['buildout'].get('sources', 'sources'), {})
    for name, info in section.iteritems():
        sources[name] = sourcefromcfgline(config, name, info)

    # do automatic checkout of specified packages
    auto_checkout = set(buildout['buildout'].get('auto-checkout', '').split())
    if '*' in auto_checkout:
        auto_checkout = set(sources.keys())
    workingcopies = WorkingCopies(sources)
    if not auto_checkout.issubset(set(sources.keys())):
        diff = list(sorted(auto_checkout.difference(set(sources.keys()))))
        if len(diff) > 1:
            pkgs = "%s and '%s'" % (", ".join("'%s'" % x for x in diff[:-1]), diff[-1])
            logger.error("The packages %s from auto-checkout have no source information." % pkgs)
        else:
            logger.error("The package '%s' from auto-checkout has no source information." % diff[0])
        sys.exit(1)
    root_logger = logging.getLogger()
    workingcopies.checkout(sorted(auto_checkout),
                           verbose=root_logger.level <= 10)

    # make the develop eggs if the package is checked out and fixup versions
    develop = buildout['buildout'].get('develop', '')
    versions = buildout.get(buildout['buildout'].get('versions'), {})
    develeggs = {}
    for path in develop.split():
        head, tail = os.path.split(path)
        develeggs[tail] = path
    for name in sources:
        if name not in develeggs:
            path = sources[name]['path']
            if os.path.exists(path) and config.develop.get(name, name in auto_checkout):
                config.develop.setdefault(name, True)
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
                pkgbasedir = sources[name]['pkgbasedir']
                if pkgbasedir is not None:
                    path = os.path.join(path, pkgbasedir, name)
                develeggs[name] = path
                if name in versions:
                    del versions[name]
    if versions:
        zc.buildout.easy_install.default_versions(dict(versions))
    develop = []
    for path in develeggs.itervalues():
        if path.startswith(buildout_dir):
            develop.append(path[len(buildout_dir)+1:])
        else:
            develop.append(path)
    buildout['buildout']['develop'] = "\n".join(develop)

    # build the fake part to install the checkout script
    if FAKE_PART_ID in buildout._raw:
        logger.error("mr.developer: The buildout already has a '%s' section, this shouldn't happen" % FAKE_PART_ID)
        sys.exit(1)
    args = dict(
        sources = pformat(sources),
        auto_checkout = pformat(auto_checkout),
        buildout_dir = '%r' % buildout_dir,
        develeggs = pformat(develeggs),
    )
    buildout._raw[FAKE_PART_ID] = dict(
        recipe='zc.recipe.egg',
        eggs='mr.developer',
        arguments=',\n'.join("=".join(x) for x in args.items()),
    )
    # insert the fake part
    parts = buildout['buildout']['parts'].split()
    parts.insert(0, FAKE_PART_ID)
    buildout['buildout']['parts'] = " ".join(parts)

    config.save()

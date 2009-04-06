from mr.developer.common import WorkingCopies
from pprint import pformat
import atexit
import logging
import os
import sys


FAKE_PART_ID = '_mr.developer'

logger = logging.getLogger("mr.developer")


def report_error():
    logger.error("*"*40)
    logger.error("There have been errors during checkout, check the output above or use 'develop status'.")
    logger.error("*"*40)

def extension(buildout=None):
    import zc.buildout.easy_install

    buildout_dir = buildout['buildout']['directory']

    sources_dir = buildout['buildout'].get('sources-dir', 'src')
    if not os.path.isabs(sources_dir):
        sources_dir = os.path.join(buildout_dir, sources_dir)

    sources = {}
    section = buildout.get(buildout['buildout'].get('sources'), {})
    for name, info in section.iteritems():
        info = info.split()
        kind = info[0]
        url = info[1]
        if len(info) > 2:
            path = os.path.join(info[2], name)
            if not os.path.isabs(path):
                path = os.path.join(buildout_dir, path)
        else:
            path = os.path.join(sources_dir, name)
        sources[name] = dict(kind=kind, name=name, url=url, path=path)

    # deprecated way of specifing sources
    if 'sources-svn' in buildout['buildout']:
        logger.warn("'sources-svn' is deprecated, use 'sources' instead (see README for usage).")
    section = buildout.get(buildout['buildout'].get('sources-svn'), {})
    for name, url in section.iteritems():
        if name in sources:
            logger.error("The source for '%s' is already set." % name)
            sys.exit(1)
        sources[name] = dict(
            kind='svn',
            name=name,
            url=url,
            path=os.path.join(sources_dir, name))
    if 'sources-git' in buildout['buildout']:
        logger.warn("'sources-git' is deprecated, use 'sources' instead (see README for usage).")
    section = buildout.get(buildout['buildout'].get('sources-git'), {})
    for name, url in section.iteritems():
        if name in sources:
            logger.error("The source for '%s' is already set." % name)
            sys.exit(1)
        sources[name] = dict(
            kind='git',
            name=name,
            url=url,
            path=os.path.join(sources_dir, name))

    # do automatic checkout of specified packages
    auto_checkout = buildout['buildout'].get('auto-checkout', '').split()
    workingcopies = WorkingCopies(sources)
    if workingcopies.checkout(auto_checkout, skip_errors=True):
        atexit.register(report_error)

    # build the fake part to install the checkout script
    if FAKE_PART_ID in buildout._raw:
        logger.error("mr.developer: The buildout already has a '%s' section, this shouldn't happen" % FAKE_PART_ID)
        sys.exit(1)
    buildout._raw[FAKE_PART_ID] = dict(
        recipe='zc.recipe.egg',
        eggs='mr.developer',
        arguments='\nsources=%s,\nauto_checkout=%s' % (
            pformat(sources), auto_checkout),
    )
    # insert the fake part
    parts = buildout['buildout']['parts'].split()
    parts.insert(0, FAKE_PART_ID)
    buildout['buildout']['parts'] = " ".join(parts)

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
            if os.path.exists(path):
                develeggs[name] = path
                if name in versions:
                    del versions[name]
    if versions:
        zc.buildout.easy_install.default_versions(dict(versions))
    buildout['buildout']['develop'] = "\n".join(develeggs.itervalues())

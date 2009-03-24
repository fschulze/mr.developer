from mr.developer.common import WorkingCopies
from pprint import pformat
import os
import sys
import zc.buildout.easy_install


FAKE_PART_ID = '_mr.developer'


def extension(buildout=None):
    buildout_dir = buildout['buildout']['directory']

    sources_dir = buildout['buildout'].get('sources-dir', 'src')
    if not os.path.isabs(sources_dir):
        sources_dir = os.path.join(buildout_dir, sources_dir)

    sources = {}
    section = buildout.get(buildout['buildout'].get('sources-svn'), {})
    for name, url in section.iteritems():
        if name in sources:
            logger.error("The source for '%s' is already set." % name)
            sys.exit(1)
        sources[name] = ('svn', url)
    section = buildout.get(buildout['buildout'].get('sources-git'), {})
    for name, url in section.iteritems():
        if name in sources:
            logger.error("The source for '%s' is already set." % name)
            sys.exit(1)
        sources[name] = ('git', url)

    # do automatic checkout of specified packages
    auto_checkout = buildout['buildout'].get('auto-checkout', '').split()
    workingcopies = WorkingCopies(sources, sources_dir)
    workingcopies.checkout(auto_checkout)

    # build the fake part to install the checkout script
    if FAKE_PART_ID in buildout._raw:
        logger.error("mr.developer: The buildout already has a '%s' section, this shouldn't happen" % FAKE_PART_ID)
        sys.exit(1)
    buildout._raw[FAKE_PART_ID] = dict(
        recipe='zc.recipe.egg',
        eggs='mr.developer',
        arguments='\n%s,\n"%s",\n%s' % (pformat(sources), sources_dir, auto_checkout),
    )
    # append the fake part
    parts = buildout['buildout']['parts'].split()
    parts.append(FAKE_PART_ID)
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
            path = os.path.join(sources_dir, name)
            if os.path.exists(path):
                develeggs[name] = path
                if name in versions:
                    del versions[name]
    if versions:
        zc.buildout.easy_install.default_versions(dict(versions))
    buildout['buildout']['develop'] = "\n".join(develeggs.itervalues())

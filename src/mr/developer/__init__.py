import os, sys
import logging
import subprocess
from optparse import OptionParser
from pprint import pformat, pprint


def extension(buildout=None):
    buildout_dir = buildout['buildout']['directory']
    sources_dir = buildout['buildout'].get('sources-dir', 'src')
    if not os.path.isabs(sources_dir):
        sources_dir = os.path.join(buildout_dir, sources_dir)
    sources = {}
    svn_sources = buildout['buildout'].get('sources-svn')
    if svn_sources is not None:
        section = buildout[svn_sources]
        for name, url in section.iteritems():
            sources[name] = ('svn', url)
    if '_mr.developer' in buildout._raw:
        raise ValueError("mr.developer: The buildout already has a '_mr.developer' section, this shouldn't happen")
    buildout._raw['_mr.developer'] = dict(
        recipe='zc.recipe.egg',
        eggs='mr.developer',
        arguments='sources=%s,\nsources_dir="%s"' % (pformat(sources), sources_dir),
    )
    parts = buildout['buildout']['parts'].split()
    parts.append('_mr.developer')
    buildout['buildout']['parts'] = " ".join(parts)
    develop = buildout['buildout'].get('develop', '')
    versions = buildout['buildout'].get('versions')
    if versions is None:
        versions = {}
    else:
        versions = buildout[versions]
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
                    versions[name] = ''
    buildout['buildout']['develop'] = "\n".join(develeggs.itervalues())


def checkout(sources, sources_dir):
    parser=OptionParser(
            usage="%s [<packages>]" % sys.argv[0],
            description="Make a checkout of the given packages.")
    (options, args)=parser.parse_args()

    if not args:
        parser.print_help()
        sys.exit(0)

    for name in args:
        if name in sources:
            kind, url = sources[name]
            if kind == 'svn':
                logging.info("Checking out '%s'" % name)
                cmd = subprocess.Popen(["svn", "checkout", "--quiet",
                                        url, sources_dir],
                                       stderr=subprocess.PIPE)
                stdout, stderr = cmd.communicate()
                if cmd.returncode != 0:
                    logging.error("Subversion checkout for '%s' failed" % name)
                    logging.error(stderr)
                    sys.exit(1)
            else:
                raise ValueError("Unknown repository type '%s'." % kind)

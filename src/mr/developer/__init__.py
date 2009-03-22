import os, sys, re
import logging
import subprocess
from optparse import OptionParser
from pprint import pformat, pprint


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
            raise ValueError("The source for '%s' is already set." % name)
        sources[name] = ('svn', url)
    section = buildout.get(buildout['buildout'].get('sources-git'), {})
    for name, url in section.iteritems():
        if name in sources:
            raise ValueError("The source for '%s' is already set." % name)
        sources[name] = ('git', url)

    # do automatic checkout of specified packages
    packages = {}
    for name in buildout['buildout'].get('auto-checkout', '').split():
        if name in sources:
            kind, url = sources[name]
            packages.setdefault(kind, {})[name] = url
        else:
            raise ValueError("Automatic checkout failed. No source defined for '%s'." % name)
    do_checkout(packages, sources_dir)

    # build the fake part to install the checkout script
    if FAKE_PART_ID in buildout._raw:
        raise ValueError("mr.developer: The buildout already has a '%s' section, this shouldn't happen" % FAKE_PART_ID)
    buildout._raw[FAKE_PART_ID] = dict(
        recipe='zc.recipe.egg',
        eggs='mr.developer',
        arguments='sources=%s,\nsources_dir="%s"' % (pformat(sources), sources_dir),
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
    buildout['buildout']['develop'] = "\n".join(develeggs.itervalues())


def do_svn_checkout(packages, sources_dir):
    for name, url in packages:
        path = os.path.join(sources_dir, name)
        if os.path.exists(path):
            logging.info("Skipped checkout of existing package '%s'." % name)
            continue
        logging.info("Checking out '%s' with subversion." % name)
        cmd = subprocess.Popen(["svn", "checkout", "--quiet",
                                url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logging.error("Subversion checkout for '%s' failed." % name)
            logging.error(stderr)
            sys.exit(1)


def do_git_checkout(packages, sources_dir):
    for name, url in packages:
        path = os.path.join(sources_dir, name)
        if os.path.exists(path):
            logging.info("Skipped cloning of existing package '%s'." % name)
            continue
        logging.info("Cloning '%s' with git." % name)
        cmd = subprocess.Popen(["git", "clone", "--quiet",
                                url, path],
                               stderr=subprocess.PIPE)
        stdout, stderr = cmd.communicate()
        if cmd.returncode != 0:
            logging.error("Git cloning for '%s' failed." % name)
            logging.error(stderr)
            sys.exit(1)


def do_checkout(packages, sources_dir):
    for kind in packages:
        if kind == 'svn':
            do_svn_checkout(sorted(packages[kind].iteritems()), sources_dir)
        elif kind == 'git':
            do_git_checkout(sorted(packages[kind].iteritems()), sources_dir)
        else:
            raise ValueError("Unknown repository type '%s'." % kind)


def checkout(sources, sources_dir):
    parser=OptionParser(
            usage="%s <options> [<packages>]" % sys.argv[0],
            description="Make a checkout of the given packages or show info about packages.")
    parser.add_option("-e", "--regexp", dest="regexp",
                      action="store_true",
                      help="Use regular expression to check for package matches.")
    parser.add_option("-l", "--list", dest="list",
                      action="store_true",
                      help="List info about package(s), all packages will be listed if none are specified.")
    options, args = parser.parse_args()

    if options.regexp:
        if len(args) > 1:
            logging.error("When using regular expression matching, then you can only specifiy one argument.")
            sys.exit(1)
        regexp = re.compile(args[0])

    if options.list:
        for name in sorted(sources):
            if args:
                if options.regexp:
                    if not regexp.search(name):
                        continue
                elif name not in args:
                    continue
            kind, url = sources[name]
            print name, url, "(%s)" % kind
        sys.exit(0)

    if not args:
        parser.print_help()
        sys.exit(0)

    packages = {}
    if options.regexp:
        for name in sorted(sources):
            if not regexp.search(name):
                continue
            kind, url = sources[name]
            packages.setdefault(kind, {})[name] = url
        if len(packages) == 0:
            logging.error("No package matched '%s'." % args[0])
            sys.exit(1)
    else:
        for name in args:
            if name in sources:
                kind, url = sources[name]
                packages.setdefault(kind, {})[name] = url
            else:
                logging.error("There is no package named '%s'." % name)
                sys.exit(1)

    try:
        do_checkout(packages, sources_dir)
    except ValueError, e:
        logging.error(e)
        sys.exit(1)

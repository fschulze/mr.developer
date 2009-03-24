from mr.developer.common import logger, do_checkout
from optparse import OptionParser
import logging
import re
import sys


def checkout(sources, sources_dir):
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(ch)
    parser=OptionParser(
            usage="%s <options> [<package-regexps>]" % sys.argv[0],
            description="Make a checkout of the packages matching the regular expressions or show info about them.")
    parser.add_option("-l", "--list", dest="list",
                      action="store_true",
                      help="List info about package(s), all packages will be listed if none are specified.")
    options, args = parser.parse_args()

    regexp = re.compile("|".join("(%s)" % x for x in args))

    if options.list:
        for name in sorted(sources):
            if args:
                if not regexp.search(name):
                    continue
            kind, url = sources[name]
            print name, url, "(%s)" % kind
        sys.exit(0)

    if not args:
        parser.print_help()
        sys.exit(0)

    packages = {}
    for name in sorted(sources):
        if not regexp.search(name):
            continue
        kind, url = sources[name]
        packages.setdefault(kind, {})[name] = url
    if len(packages) == 0:
        if len(args) > 1:
            regexps = "%s or '%s'" % (", ".join("'%s'" % x for x in args[:-1]), args[-1])
        else:
            regexps = "'%s'" % args[0]
        logger.error("No package matched %s." % regexps)
        sys.exit(1)

    try:
        do_checkout(packages, sources_dir)
        logger.warn("Don't forget to run buildout again, so the checked out packages are used as develop eggs.")
    except ValueError, e:
        logger.error(e)
        sys.exit(1)

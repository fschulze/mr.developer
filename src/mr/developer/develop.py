from mr.developer.common import logger, do_checkout
from optparse import OptionParser
import logging
import os
import re
import sys


class Command(object):
    def __init__(self, develop):
        self.develop = develop


class CmdCheckout(Command):
    def __init__(self, develop):
        super(CmdCheckout, self).__init__(develop)
        self.parser=OptionParser(
            usage="%prog <options> [<package-regexps>]",
            description="Make a checkout of the packages matching the regular expressions.",
            add_help_option=False)

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])

        regexp = re.compile("|".join("(%s)" % x for x in args))
        packages = {}
        for name in sorted(self.develop.sources):
            if not regexp.search(name):
                continue
            kind, url = self.develop.sources[name]
            packages.setdefault(kind, {})[name] = url
        if len(packages) == 0:
            if len(args) > 1:
                regexps = "%s or '%s'" % (", ".join("'%s'" % x for x in args[:-1]), args[-1])
            else:
                regexps = "'%s'" % args[0]
            logger.error("No package matched %s." % regexps)
            sys.exit(1)

        try:
            do_checkout(packages, self.sources_dir)
            logger.warn("Don't forget to run buildout again, so the checked out packages are used as develop eggs.")
        except ValueError, e:
            logger.error(e)
            sys.exit(1)

class CmdHelp(Command):
    def __init__(self, develop):
        super(CmdHelp, self).__init__(develop)
        self.parser = OptionParser(
            usage="%prog help [<command>]",
            description="Show help on the given command or about the whole script if none given.",
            add_help_option=False)

    def __call__(self):
        develop = self.develop
        if len(sys.argv) != 3 or sys.argv[2] not in develop.commands:
            print("usage: %s <command> [options] [args]" % os.path.basename(sys.argv[0]))
            print("\nType '%s help <command>' for help on a specific command." % os.path.basename(sys.argv[0]))
            print("\nAvailable commands:")
            f_to_name = {}
            for name, f in develop.commands.iteritems():
                f_to_name.setdefault(f, []).append(name)
            for cmd in sorted(x for x in dir(develop) if x.startswith('cmd_')):
                name = cmd[4:]
                f = getattr(develop, cmd)
                aliases = [x for x in f_to_name[f] if x != name]
                if len(aliases):
                    print("    %s (%s)" % (name, ", ".join(aliases)))
                else:
                    print("    %s" % name)
        else:
            print develop.commands[sys.argv[2]].parser.format_help()


class CmdList(Command):
    def __init__(self, develop):
        super(CmdList, self).__init__(develop)
        self.parser = OptionParser(
            usage="%prog list [<package-regexps>]",
            description="List the available packages, filtered if <package-regexps> is given.",
            add_help_option=False)

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])

        regexp = re.compile("|".join("(%s)" % x for x in args))
        for name in sorted(self.develop.sources):
            if args:
                if not regexp.search(name):
                    continue
            kind, url = self.develop.sources[name]
            print name, url, "(%s)" % kind


class Develop(object):
    def __call__(self, sources, sources_dir):
        self.sources = sources
        self.sources_dir = sources_dir

        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(ch)

        self.cmd_checkout = CmdCheckout(self)
        self.cmd_help = CmdHelp(self)
        self.cmd_list = CmdList(self)

        self.commands = dict(
            help=self.cmd_help,
            checkout=self.cmd_checkout,
            co=self.cmd_checkout,
            list=self.cmd_list,
            ls=self.cmd_list,
        )

        if len(sys.argv) < 2:
            logger.info("Type '%s help' for usage." % os.path.basename(sys.argv[0]))
        else:
            self.commands.get(sys.argv[1], self.unknown)()

    def unknown(self):
        logger.error("Unknown command '%s'." % sys.argv[1])
        logger.info("Type '%s help' for usage." % os.path.basename(sys.argv[0]))
        sys.exit(1)

develop = Develop()

from mr.developer.common import logger, WorkingCopies
from optparse import OptionParser
import logging
import os
import re
import sys


class Command(object):
    def __init__(self, develop):
        self.develop = develop

    def get_packages(self, args):
        packages = getattr(self, '_packages', None)
        if packages is not None:
            return packages
        packages = self._packages = []
        if not args:
            return packages
        regexp = re.compile("|".join("(%s)" % x for x in args))
        for name in sorted(self.develop.sources):
            if not regexp.search(name):
                continue
            packages.append(name)
        return packages


class CmdCheckout(Command):
    def __init__(self, develop):
        super(CmdCheckout, self).__init__(develop)
        self.parser=OptionParser(
            usage="%prog <options> <package-regexps>",
            description="Make a checkout of the packages matching the regular expressions.",
            add_help_option=False)
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        if len(args) == 0:
            if options.auto_checkout:
                packages = self.develop.auto_checkout
            else:
                print self.parser.format_help()
                sys.exit(0)
        else:
            packages = self.get_packages(args)
            if options.auto_checkout:
                packages = [x for x in packages
                            if x in self.develop.auto_checkout]
        if len(packages) == 0:
            if len(args) > 1:
                regexps = "%s or '%s'" % (", ".join("'%s'" % x for x in args[:-1]), args[-1])
            else:
                regexps = "'%s'" % args[0]
            logger.error("No package matched %s." % regexps)
            sys.exit(1)

        try:
            workingcopies = WorkingCopies(self.develop.sources,
                                          self.develop.sources_dir)
            workingcopies.checkout(packages)
            logger.warn("Don't forget to run buildout again, so the checked out packages are used as develop eggs.")
        except (ValueError, KeyError), e:
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
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only show packages in auto-checkout list.""")
        self.parser.add_option("-l", "--long", dest="long",
                               action="store_true", default=False,
                               help="""Show URL and kind of package.""")
        self.parser.add_option("-s", "--status", dest="status",
                               action="store_true", default=False,
                               help="""Show checkout status.
                                       The first column in the output shows the checkout status:
                                       ' ' available for checkout
                                       'A' in auto-checkout list and checked out
                                       'C' not in auto-checkout list, but checked out
                                       '!' in auto-checkout list, but not checked out
                                       '~' the repository URL doesn't match""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        sources_dir = self.develop.sources_dir
        auto_checkout = self.develop.auto_checkout
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources, sources_dir)
        for name in sorted(sources):
            if args and name not in packages:
                continue
            if options.auto_checkout and name not in auto_checkout:
                continue
            kind, url = sources[name]
            if options.status:
                if os.path.exists(os.path.join(sources_dir, name)):
                    if not workingcopies.matches(name):
                        print "~",
                    else:
                        if name in auto_checkout:
                            print "A",
                        else:
                            print "C",
                else:
                    if name in auto_checkout:
                        print "!",
                    else:
                        print " ",
            if options.long:
                print "(%s)" % kind, name, url
            else:
                print name


class CmdStatus(Command):
    def __init__(self, develop):
        super(CmdStatus, self).__init__(develop)
        self.parser = OptionParser(
            usage="%prog status",
            description="""Shows the status of the sources directory. Only directories are checked, files are skipped.

                           The first column in the output shows the checkout status:
                               ' ' in auto-checkout list
                               'C' not in auto-checkout list
                               '?' directory which is not in sources list
                               '~' the repository URL doesn't match
                           The second column shows the working copy status:
                               ' ' no changes
                               'M' local modifications or untracked files""",
            add_help_option=False)

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        sources_dir = self.develop.sources_dir
        auto_checkout = self.develop.auto_checkout
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources, sources_dir)
        for name in os.listdir(sources_dir):
            path = os.path.join(sources_dir, name)
            if os.path.isfile(path):
                continue
            if name not in sources:
                print "?", " ", name
                continue
            kind, url = sources[name]
            if not workingcopies.matches(name):
                print "~",
            else:
                if name in auto_checkout:
                    print " ",
                else:
                    print "C",
            if workingcopies.status(name) == 'clean':
                print " ",
            else:
                print "M",
            print name


class CmdUpdate(Command):
    def __init__(self, develop):
        super(CmdUpdate, self).__init__(develop)
        self.parser = OptionParser(
            usage="%prog update",
            description="Updates all known packages currently checked out.",
            add_help_option=False)

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        sources_dir = self.develop.sources_dir
        auto_checkout = self.develop.auto_checkout
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources, sources_dir)
        workingcopies.update(os.listdir(sources_dir))


class Develop(object):
    def __call__(self, sources, sources_dir, auto_checkout):
        self.sources = sources
        self.sources_dir = sources_dir
        self.auto_checkout = set(auto_checkout)

        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(ch)

        self.cmd_checkout = CmdCheckout(self)
        self.cmd_help = CmdHelp(self)
        self.cmd_list = CmdList(self)
        self.cmd_status = CmdStatus(self)
        self.cmd_update = CmdUpdate(self)

        self.commands = dict(
            help=self.cmd_help,
            h=self.cmd_help,
            checkout=self.cmd_checkout,
            co=self.cmd_checkout,
            list=self.cmd_list,
            ls=self.cmd_list,
            status=self.cmd_status,
            stat=self.cmd_status,
            st=self.cmd_status,
            update=self.cmd_update,
            up=self.cmd_update,
        )

        if len(sys.argv) < 2:
            print "Type '%s help' for usage." % os.path.basename(sys.argv[0])
        else:
            self.commands.get(sys.argv[1], self.unknown)()

    def unknown(self):
        logger.error("Unknown command '%s'." % sys.argv[1])
        logger.info("Type '%s help' for usage." % os.path.basename(sys.argv[0]))
        sys.exit(1)

develop = Develop()

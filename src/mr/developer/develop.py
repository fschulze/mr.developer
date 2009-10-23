from mr.developer.common import logger, WorkingCopies, Config
from mr.developer.extension import FAKE_PART_ID
import ConfigParser
import logging
import optparse
import os
import re
import subprocess
import sys
import textwrap


def load_installed_cfg(path=None):
    if path is None:
        path = os.getcwd()
        while path:
            if os.path.exists(os.path.join(path, '.installed.cfg')):
                break
            old_path = path
            path = os.path.dirname(path)
            if old_path == path:
                path = None
                break
    if path is None:
        raise IOError(".installed.cfg not found")

    config = ConfigParser.RawConfigParser()
    config.optionxform = lambda s: s
    config.read(os.path.join(path, '.installed.cfg'))

    return config


class HelpFormatter(optparse.IndentedHelpFormatter):
    def _lineswrap(self, text, width, indent=0):
        result = []
        for line in text.split("\n"):
            for line2 in textwrap.fill(line, width).split("\n"):
                result.append("%*s%s" % (indent, "", line2))
        return "\n".join(result)

    def format_description(self, description):
        if not description:
            return ""
        desc_width = self.width - self.current_indent
        return self._lineswrap(description, desc_width,
                               indent=self.current_indent)

    def format_option(self, option):
        # The help for each option consists of two parts:
        #   * the opt strings and metavars
        #     eg. ("-x", or "-fFILENAME, --file=FILENAME")
        #   * the user-supplied help string
        #     eg. ("turn on expert mode", "read data from FILENAME")
        #
        # If possible, we write both of these on the same line:
        #   -x      turn on expert mode
        #
        # But if the opt string list is too long, we put the help
        # string on a second line, indented to the same column it would
        # start in if it fit on the first line.
        #   -fFILENAME, --file=FILENAME
        #           read data from FILENAME
        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "", opts)
            indent_first = self.help_position
        else:                       # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width, opts)
            indent_first = 0
        result.append(opts)
        if option.help:
            help_text = self.expand_default(option)
            help_lines = self._lineswrap(help_text, self.help_width).split('\n')
            result.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            result.extend(["%*s%s\n" % (self.help_position, "", line)
                           for line in help_lines[1:]])
        elif opts[-1] != "\n":
            result.append("\n")
        return "".join(result)

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


class CmdActivate(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=optparse.OptionParser(
            usage="%prog <package-regexps>",
            description="Add package to the list of development packages.",
            formatter=HelpFormatter(),
            add_help_option=False)
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        auto_checkout = self.develop.auto_checkout
        config = self.develop.config
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources)
        changed = False
        for name in sorted(sources):
            if options.auto_checkout and name not in auto_checkout:
                continue
            source = sources[name]
            if args and name not in packages:
                continue
            if not os.path.exists(source['path']):
                logger.warning("The package '%s' matched, but isn't checked out." % name)
                continue
            config.develop[name] = True
            logger.info("Activated '%s'." % name)
            changed = True
        if changed:
            logger.warn("Don't forget to run buildout again, so the actived packages are actually used.")
        config.save()


class CmdCheckout(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=optparse.OptionParser(
            usage="%prog <options> <package-regexps>",
            description="Make a checkout of the packages matching the regular expressions and add them to the list of development packages.",
            formatter=HelpFormatter(),
            add_help_option=False)
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-v", "--verbose", dest="verbose",
                               action="store_true", default=False,
                               help="""Show output of VCS command.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        config = self.develop.config
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
            workingcopies = WorkingCopies(self.develop.sources)
            workingcopies.checkout(packages, verbose=options.verbose)
            for name in packages:
                config.develop[name] = True
                logger.info("Activated '%s'." % name)
            logger.warn("Don't forget to run buildout again, so the checked out packages are used as develop eggs.")
            config.save()
        except (ValueError, KeyError), e:
            logger.error(e)
            sys.exit(1)


class CmdDeactivate(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=optparse.OptionParser(
            usage="%prog <package-regexps>",
            description="Remove package from the list of development packages.",
            formatter=HelpFormatter(),
            add_help_option=False)

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        config = self.develop.config
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources)
        changed = False
        for name in sorted(sources):
            source = sources[name]
            if args and name not in packages:
                continue
            if not os.path.exists(source['path']):
                logger.warning("The package '%s' matched, but isn't checked out." % name)
                continue
            if config.develop.get(name) != False:
                config.develop[name] = False
                logger.info("Deactivated '%s'." % name)
                changed = True
        if changed:
            logger.warn("Don't forget to run buildout again, so the deactived packages are actually not used anymore.")
        config.save()


class CmdHelp(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser = optparse.OptionParser(
            usage="%prog help [<command>]",
            description="Show help on the given command or about the whole script if none given.",
            formatter=HelpFormatter(),
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
                if name == 'pony':
                    continue
                f = getattr(develop, cmd)
                aliases = [x for x in f_to_name[f] if x != name]
                if len(aliases):
                    print("    %s (%s)" % (name, ", ".join(aliases)))
                else:
                    print("    %s" % name)
        else:
            print develop.commands[sys.argv[2]].parser.format_help()


class CmdInfo(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser = optparse.OptionParser(
            usage="%prog info [<package-regexps>]",
            description="Lists informations about packages, filtered if <package-regexps> is given.",
            formatter=HelpFormatter(),
            add_help_option=False)
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all declared packages are processed.""")
        info_opts = optparse.OptionGroup(self.parser, "Output options",
                                         """The following options are used to print just the info you want, the order they are specified reflects the order in which the information will be printed.""")
        info_opts.add_option("--name", dest="info",
                             action="callback", callback=self.store_info,
                             help="""Prints the name of the package.""")
        info_opts.add_option("-p", "--path", dest="info",
                             action="callback", callback=self.store_info,
                             help="""Prints the absolute path of the package.""")
        info_opts.add_option("--type", dest="info",
                             action="callback", callback=self.store_info,
                             help="""Prints the repository type of the package.""")
        info_opts.add_option("--url", dest="info",
                             action="callback", callback=self.store_info,
                             help="""Prints the URL of the package.""")
        self.parser.add_option_group(info_opts)

    def store_info(self, option, opt_str, value, parser):
        info = getattr(parser.values, option.dest)
        if info is None:
            info = []
            setattr(parser.values, option.dest, info)
        info.append(option._long_opts[0][2:])

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        auto_checkout = self.develop.auto_checkout
        develeggs = self.develop.develeggs
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources)
        for name in sorted(sources):
            source = sources[name]
            if args and name not in packages:
                continue
            if options.auto_checkout and name not in auto_checkout:
                continue
            if options.checked_out and not os.path.exists(source['path']):
                continue
            if options.develop and name not in develeggs:
                continue
            if options.info:
                for key in options.info:
                    if key=='name':
                        print name,
                    elif key=='path':
                        print source['path'],
                    elif key=='type':
                        print source['kind'],
                    elif key=='url':
                        print source['url'],
                print
            else:
                print "Name:", name
                print "Path:", source['path']
                print "Type:", source['kind']
                print "URL:", source['url']
                print

class CmdList(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser = optparse.OptionParser(
            usage="%prog list [<package-regexps>]",
            description="Lists tracked packages, filtered if <package-regexps> is given.",
            formatter=HelpFormatter(),
            add_help_option=False)
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only show packages in auto-checkout list.""")
        self.parser.add_option("-l", "--long", dest="long",
                               action="store_true", default=False,
                               help="""Show URL and kind of package.""")
        self.parser.add_option("-s", "--status", dest="status",
                               action="store_true", default=False,
                               help=textwrap.dedent("""\
                                   Show checkout status.
                                   The first column in the output shows the checkout status:
                                       ' ' available for checkout
                                       'A' in auto-checkout list and checked out
                                       'C' not in auto-checkout list, but checked out
                                       '!' in auto-checkout list, but not checked out
                                       '~' the repository URL doesn't match"""))

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        auto_checkout = self.develop.auto_checkout
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources)
        for name in sorted(sources):
            if args and name not in packages:
                continue
            if options.auto_checkout and name not in auto_checkout:
                continue
            source = sources[name]
            if options.status:
                if os.path.exists(source['path']):
                    if not workingcopies.matches(source):
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
                print "(%s)" % source['kind'], name, source['url']
            else:
                print name


class CmdPony(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser = optparse.OptionParser(
            usage="%prog pony",
            description="It should be easy to develop a pony!",
            formatter=HelpFormatter(),
            add_help_option=False)

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        pony = '''
            .,,.
         ,;;*;;;;,
        .-'``;-');;.
       /'  .-.  /*;;
     .'    \d    \;;               .;;;,
    / o      `    \;    ,__.     ,;*;;;*;,
    \__, _.__,'   \_.-') __)--.;;;;;*;;;;,
     `""`;;;\       /-')_) __)  `\' ';;;;;;
        ;*;;;        -') `)_)  |\ |  ;;;;*;
        ;;;;|        `---`    O | | ;;*;;;
        *;*;\|                 O  / ;;;;;*
       ;;;;;/|    .-------\      / ;*;;;;;
      ;;;*;/ \    |        '.   (`. ;;;*;;;
      ;;;;;'. ;   |          )   \ | ;;;;;;
      ,;*;;;;\/   |.        /   /` | ';;;*;
       ;;;;;;/    |/       /   /__/   ';;;
       '*jgs/     |       /    |      ;*;
            `""""`        `""""`     ;'
'''
        import time
        logger.info("Starting to develop a pony.")
        for line in pony.split("\n"):
            time.sleep(0.25)
            print line
        logger.info("Done.")


class CmdRebuild(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=optparse.OptionParser(
            usage="%prog",
            description="Run buildout with the last used arguments.",
            formatter=HelpFormatter(),
            add_help_option=False)
        self.parser.add_option("-n", "--dry-run", dest="dry_run",
                               action="store_true", default=False,
                               help="""Don't actually run buildout, just show the last used arguments.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        buildout_dir = self.develop.buildout_dir
        buildout_args = self.develop.config.buildout_args
        print "Last used buildout arguments:",
        print " ".join(buildout_args[1:])
        if options.dry_run:
            logger.warning("Dry run, buildout not invoked.")
            return
        else:
            logger.info("Running buildout.")
        os.chdir(buildout_dir)
        subprocess.call(buildout_args)


class CmdReset(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=optparse.OptionParser(
            usage="%prog <package-regexps>",
            description="Resets the packages develop status. This is useful when switching to a new buildout configuration.",
            formatter=HelpFormatter(),
            add_help_option=False)

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        config = self.develop.config
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources)
        changed = False
        for name in sorted(sources):
            source = sources[name]
            if args and name not in packages:
                continue
            if not os.path.exists(source['path']):
                continue
            if name in config.develop:
                del config.develop[name]
                logger.info("Reset develop state of '%s'." % name)
                changed = True
        if changed:
            logger.warn("Don't forget to run buildout again, so the deactived packages are actually not used anymore.")
        config.save()


class CmdStatus(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser = optparse.OptionParser(
            usage="%prog status [<package-regexps>]",
            description=textwrap.dedent("""\
                Shows the status of tracked packages, filtered if <package-regexps> is given.
                The first column in the output shows the checkout status:
                    ' ' in auto-checkout list
                    '~' not in auto-checkout list
                    '!' in auto-checkout list, but not checked out
                    'C' the repository URL doesn't match
                The second column shows the working copy status:
                    ' ' no changes
                    'M' local modifications or untracked files
                The third column shows the development status:
                    ' ' activated
                    '-' deactivated
                    '!' deactivated, but the package is in the auto-checkout list
                    'A' activated, but not in list of development packages (run buildout)
                    'D' deactivated, but still in list of development packages (run buildout)"""),
            formatter=HelpFormatter(),
            add_help_option=False)
        self.parser.add_option("-v", "--verbose", dest="verbose",
                               action="store_true", default=False,
                               help="""Show output of VCS command.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        auto_checkout = self.develop.auto_checkout
        develeggs = self.develop.develeggs
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources)
        for name in sorted(sources):
            if args and name not in packages:
                continue
            source = sources[name]
            path = source['path']
            if not os.path.exists(path):
                if name in auto_checkout:
                    print "!", " ", name
                continue
            if not workingcopies.matches(source):
                print "C",
            else:
                if name in auto_checkout:
                    print " ",
                else:
                    print "~",
            if options.verbose:
                status, output = workingcopies.status(source, verbose=True)
            else:
                status = workingcopies.status(source)
            if status == 'clean':
                print " ",
            else:
                print "M",
            if self.develop.config.develop.get(name, name in auto_checkout):
                if name in develeggs:
                    print " ",
                else:
                    print "A",
            else:
                if name not in develeggs:
                    if name in auto_checkout:
                        print "!",
                    else:
                        print "-",
                else:
                    print "D",
            print name
            if options.verbose:
                output = output.strip()
                if output:
                    for line in output.split('\n'):
                        print "   ", line
                    print


class CmdUpdate(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser = optparse.OptionParser(
            usage="%prog update [<package-regexps>]",
            description="Updates all known packages currently checked out. If <package-regexps> are given, then the set is limited to the matching packages.",
            formatter=HelpFormatter(),
            add_help_option=False)
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-f", "--force", dest="force",
                               action="store_true", default=False,
                               help="""Force update even if the working copy is dirty.""")
        self.parser.add_option("-v", "--verbose", dest="verbose",
                               action="store_true", default=False,
                               help="""Show output of VCS command.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        auto_checkout = self.develop.auto_checkout
        packages = set(self.get_packages(args))
        workingcopies = WorkingCopies(sources)
        toupdate = []
        for name in sorted(sources):
            if options.auto_checkout and name not in auto_checkout:
                continue
            source = sources[name]
            if args and name not in packages:
                continue
            if not os.path.exists(source['path']):
                continue
            toupdate.append(name)
        workingcopies.update(toupdate,
                             force=options.force,
                             verbose=options.verbose)


class Develop(object):
    def __call__(self, **kwargs):
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(ch)

        self.cmd_activate = self.alias_a = CmdActivate(self)
        self.cmd_checkout = self.alias_co = CmdCheckout(self)
        self.cmd_deactivate = self.alias_d = CmdDeactivate(self)
        self.cmd_help = self.alias_h = CmdHelp(self)
        self.cmd_info = CmdInfo(self)
        self.cmd_list = self.alias_ls = CmdList(self)
        self.cmd_pony = CmdPony(self)
        self.cmd_rebuild = self.alias_rb = CmdRebuild(self)
        self.cmd_reset = CmdReset(self)
        self.cmd_status = self.alias_stat = self.alias_st = CmdStatus(self)
        self.cmd_update = self.alias_up = CmdUpdate(self)

        if len(kwargs) == 0:
            try:
                installed = load_installed_cfg()
            except IOError, e:
                logger.error("You are not in a path which has mr.developer installed (%s)." % e)
                return
            if not installed.has_option(FAKE_PART_ID, '__buildout_installed__'):
                logger.error("You are not in a path which has mr.developer installed (mr.developer not in buildout).")
                return
            develop = installed.get(FAKE_PART_ID, '__buildout_installed__')
            subprocess.call([develop] + sys.argv[1:])
            return

        self.sources = kwargs['sources']
        self.auto_checkout = set(kwargs['auto_checkout'])
        self.buildout_dir = kwargs['buildout_dir']
        self.config = Config(self.buildout_dir)
        self.develeggs = kwargs['develeggs']

        if len(sys.argv) < 2:
            print "Type '%s help' for usage." % os.path.basename(sys.argv[0])
        else:
            self.commands.get(sys.argv[1], self.unknown)()

    @property
    def commands(self):
        commands = getattr(self, '_commands', None)
        if commands is not None:
            return commands
        self._commands = commands = dict()
        for key in dir(self):
            if key.startswith('cmd_'):
                commands[key[4:]] = getattr(self, key)
            if key.startswith('alias_'):
                commands[key[6:]] = getattr(self, key)
        return commands

    def unknown(self):
        logger.error("Unknown command '%s'." % sys.argv[1])
        logger.info("Type '%s help' for usage." % os.path.basename(sys.argv[0]))
        sys.exit(1)

develop = Develop()

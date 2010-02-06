from mr.developer.common import logger, memoize, WorkingCopies, Config
from mr.developer.extension import Extension
from zc.buildout.buildout import Buildout
import atexit
import errno
import logging
import optparse
import os
import re
import shutil
import stat
import subprocess
import sys
import textwrap


def find_base():
    path = os.getcwd()
    while path:
        if os.path.exists(os.path.join(path, '.mr.developer.cfg')):
            break
        old_path = path
        path = os.path.dirname(path)
        if old_path == path:
            path = None
            break
    if path is None:
        raise IOError(".mr.developer.cfg not found")

    return path


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

    @memoize
    def get_packages(self, args, auto_checkout=False,
                     develop=False, checked_out=False):
        if auto_checkout:
            packages = set(self.develop.auto_checkout)
        else:
            packages = set(self.develop.sources)
        if develop:
            packages = packages.intersection(set(self.develop.develeggs))
        if checked_out:
            for name in set(packages):
                if not self.develop.sources[name].exists():
                    packages.remove(name)
        if not args:
            return packages
        result = set()
        regexp = re.compile("|".join("(%s)" % x for x in args))
        for name in packages:
            if not regexp.search(name):
                continue
            result.add(name)

        if len(result) == 0:
            if len(args) > 1:
                regexps = "%s or '%s'" % (", ".join("'%s'" % x for x in args[:-1]), args[-1])
            else:
                regexps = "'%s'" % args[0]
            logger.error("No package matched %s." % regexps)
            sys.exit(1)

        return result


class CmdActivate(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=optparse.OptionParser(
            usage="%prog activate [options] [<package-regexps>]",
            description="Add package to the list of development packages.",
            formatter=HelpFormatter())
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_option("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        config = self.develop.config
        packages = self.get_packages(args,
                                     auto_checkout=options.auto_checkout,
                                     checked_out=options.checked_out,
                                     develop=options.develop)
        changed = False
        for name in sorted(packages):
            source = self.develop.sources[name]
            if not source.exists():
                logger.warning("The package '%s' matched, but isn't checked out." % name)
                continue
            if not source.get('egg', True):
                logger.warning("The package '%s' isn't an egg." % name)
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
            usage="%prog checkout [options] <package-regexps>",
            description="Make a checkout of the packages matching the regular expressions and add them to the list of development packages.",
            formatter=HelpFormatter())
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-v", "--verbose", dest="verbose",
                               action="store_true", default=False,
                               help="""Show output of VCS command.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        config = self.develop.config
        if len(args) == 0 and not options.auto_checkout:
            print self.parser.format_help()
            sys.exit(0)
        packages = self.get_packages(args,
                                     auto_checkout=options.auto_checkout)
        try:
            workingcopies = WorkingCopies(self.develop.sources)
            workingcopies.checkout(sorted(packages), verbose=options.verbose)
            for name in sorted(packages):
                source = self.develop.sources[name]
                if not source.get('egg', True):
                    continue
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
            usage="%prog deactivate [options] <package-regexps>",
            description="Remove package from the list of development packages.",
            formatter=HelpFormatter())
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_option("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        config = self.develop.config
        packages = self.get_packages(args,
                                     auto_checkout=options.auto_checkout,
                                     checked_out=options.checked_out,
                                     develop=options.develop)
        changed = False
        for name in sorted(packages):
            source = self.develop.sources[name]
            if not source.exists():
                logger.warning("The package '%s' matched, but isn't checked out." % name)
                continue
            if not source.get('egg', True):
                logger.warning("The package '%s' isn't an egg." % name)
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
            usage="%prog help [options] [<command>]",
            description="Show help on the given command or about the whole script if none given.",
            formatter=HelpFormatter())
        self.parser.add_option("", "--rst", dest="rst",
                               action="store_true", default=False,
                               help="""Print help for all commands in reStructuredText format.""")

    def __call__(self):
        develop = self.develop
        options, args = self.parser.parse_args(sys.argv[2:])
        if len(args) and args[0] in develop.commands:
            print develop.commands[args[0]].parser.format_help()
            return
        f_to_name = {}
        for name, f in develop.commands.iteritems():
            f_to_name.setdefault(f, []).append(name)
        cmds = {}
        for cmd in (x for x in dir(develop) if x.startswith('cmd_')):
            name = cmd[4:]
            if name == 'pony':
                continue
            f = getattr(develop, cmd)
            aliases = [x for x in f_to_name[f] if x != name]
            cmds[name] = dict(
                aliases=aliases,
                cmd=f,
            )
        if options.rst:
            print "Commands"
            print "========"
            print
            print "The following is a list of all commands and their options."
            print
            for name in sorted(cmds):
                cmd = cmds[name]
                if len(cmd['aliases']):
                    header = "%s (%s)" % (name, ", ".join(cmd['aliases']))
                else:
                    header = name
                print header
                print "-"*len(header)
                print
                print "::"
                print
                for line in cmd['cmd'].parser.format_help().split('\n'):
                    print "    %s" % line
                print
        else:
            print self.parser.format_help()
            print("Available commands:")
            for name in sorted(cmds):
                cmd = cmds[name]
                if len(cmd['aliases']):
                    print("    %s (%s)" % (name, ", ".join(cmd['aliases'])))
                else:
                    print("    %s" % name)


class CmdInfo(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser = optparse.OptionParser(
            usage="%prog info [options] [<package-regexps>]",
            description="Lists informations about packages, filtered if <package-regexps> is given.",
            formatter=HelpFormatter())
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
        packages = self.get_packages(args,
                                     auto_checkout=options.auto_checkout,
                                     develop=options.develop,
                                     checked_out=options.checked_out)
        for name in sorted(packages):
            source = self.develop.sources[name]
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
            usage="%prog list [options] [<package-regexps>]",
            description="Lists tracked packages, filtered if <package-regexps> is given.",
            formatter=HelpFormatter())
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only show packages in auto-checkout list.""")
        self.parser.add_option("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_option("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")
        self.parser.add_option("-l", "--long", dest="long",
                               action="store_true", default=False,
                               help="""Show URL and kind of package.""")
        self.parser.add_option("-s", "--status", dest="status",
                               action="store_true", default=False,
                               help=textwrap.dedent("""\
                                   Show checkout status.
                                   The first column in the output shows the checkout status:
                                       '#' available for checkout
                                       ' ' in auto-checkout list and checked out
                                       '~' not in auto-checkout list, but checked out
                                       '!' in auto-checkout list, but not checked out
                                       'C' the repository URL doesn't match"""))

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        sources = self.develop.sources
        auto_checkout = self.develop.auto_checkout
        packages = self.get_packages(args,
                                     auto_checkout=options.auto_checkout,
                                     checked_out=options.checked_out,
                                     develop=options.develop)
        workingcopies = WorkingCopies(sources)
        for name in sorted(packages):
            source = sources[name]
            if options.status:
                if source.exists():
                    if not workingcopies.matches(source):
                        print "C",
                    else:
                        if name in auto_checkout:
                            print " ",
                        else:
                            print "~",
                else:
                    if name in auto_checkout:
                        print "!",
                    else:
                        print "#",
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
            formatter=HelpFormatter())

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


class CmdPurge(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=optparse.OptionParser(
            usage="%prog purge [options] [<package-regexps>]",
            description=textwrap.dedent("""\
                Remove checked out packages which aren't active anymore.

                Only 'svn' packages can be purged, because other repositories may contain unrecoverable files even when not marked as 'dirty'."""),
            formatter=HelpFormatter())
        self.parser.add_option("-n", "--dry-run", dest="dry_run",
                               action="store_true", default=False,
                               help="""Don't actually remove anything, just print the paths which would be removed.""")

    def handle_remove_readonly(self, func, path, exc):
        excvalue = exc[1]
        if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO) # 0777
            func(path)
        else:
            raise

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        buildout_dir = self.develop.buildout_dir
        packages = self.get_packages(args, checked_out=True)
        packages = packages - self.develop.auto_checkout
        packages = packages - set(self.develop.develeggs)
        workingcopies = WorkingCopies(self.develop.sources)
        if options.dry_run:
            logger.info("Dry run, nothing will be removed.")
        for name in packages:
            source = self.develop.sources[name]
            path = source['path']
            if path.startswith(buildout_dir):
                path = path[len(buildout_dir)+1:]
            if source['kind'] != 'svn':
                logger.warn("The directory of package '%s' at '%s' might contain unrecoverable files and will not be removed." % (name, path))
                continue
            if workingcopies.status(source) != 'clean':
                logger.warn("The package '%s' is dirty and will not be removed." % name)
                continue
            logger.info("Removing package '%s' at '%s'." % (name, path))
            if not options.dry_run:
                shutil.rmtree(source['path'],
                              ignore_errors=False,
                              onerror=self.handle_remove_readonly)


class CmdRebuild(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=optparse.OptionParser(
            usage="%prog rebuild [options]",
            description="Run buildout with the last used arguments.",
            formatter=HelpFormatter())
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
            usage="%prog reset [options] [<package-regexps>]",
            description="Resets the packages develop status. This is useful when switching to a new buildout configuration.",
            formatter=HelpFormatter())
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_option("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        config = self.develop.config
        packages = self.get_packages(args,
                                     auto_checkout=options.auto_checkout,
                                     checked_out=options.checked_out,
                                     develop=options.develop)
        changed = False
        for name in sorted(packages):
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
            usage="%prog status [options] [<package-regexps>]",
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
            formatter=HelpFormatter())
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_option("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")
        self.parser.add_option("-v", "--verbose", dest="verbose",
                               action="store_true", default=False,
                               help="""Show output of VCS command.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        auto_checkout = self.develop.auto_checkout
        develeggs = self.develop.develeggs
        packages = self.get_packages(args,
                                     auto_checkout=options.auto_checkout,
                                     checked_out=options.checked_out,
                                     develop=options.develop)
        workingcopies = WorkingCopies(self.develop.sources)
        for name in sorted(packages):
            source = self.develop.sources[name]
            if not source.exists():
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
                    if source.get('egg', True):
                        print "A",
                    else:
                        print " ",
            else:
                if name not in develeggs:
                    if not source.get('egg', True):
                        print " ",
                    elif name in auto_checkout:
                        print "!",
                    else:
                        print "-",
                else:
                    if source.get('egg', True):
                        print "D",
                    else:
                        print " ",
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
            usage="%prog update [options] [<package-regexps>]",
            description="Updates all known packages currently checked out. If <package-regexps> are given, then the set is limited to the matching packages.",
            formatter=HelpFormatter())
        self.parser.add_option("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_option("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")
        self.parser.add_option("-f", "--force", dest="force",
                               action="store_true", default=False,
                               help="""Force update even if the working copy is dirty.""")
        self.parser.add_option("-v", "--verbose", dest="verbose",
                               action="store_true", default=False,
                               help="""Show output of VCS command.""")

    def __call__(self):
        options, args = self.parser.parse_args(sys.argv[2:])
        packages = self.get_packages(args,
                                     auto_checkout=options.auto_checkout,
                                     checked_out=True,
                                     develop=options.develop)
        workingcopies = WorkingCopies(self.develop.sources)
        workingcopies.update(sorted(packages),
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
        self.cmd_purge = CmdPurge(self)
        self.cmd_rebuild = self.alias_rb = CmdRebuild(self)
        self.cmd_reset = CmdReset(self)
        self.cmd_status = self.alias_stat = self.alias_st = CmdStatus(self)
        self.cmd_update = self.alias_up = CmdUpdate(self)

        try:
            self.buildout_dir = find_base()
        except IOError, e:
            self.cmd_help()
            print
            logger.error("You are not in a path which has mr.developer installed (%s)." % e)
            return

        self.config = Config(self.buildout_dir)
        self.original_dir = os.getcwd()
        atexit.register(self.restore_original_dir)
        os.chdir(self.buildout_dir)
        buildout = Buildout(self.config.buildout_settings['config_file'],
                            self.config.buildout_options,
                            self.config.buildout_settings['user_defaults'],
                            self.config.buildout_settings['windows_restart'])
        root_logger = logging.getLogger()
        root_logger.handlers = []
        root_logger.setLevel(logging.INFO)
        extension = Extension(buildout)
        self.sources = extension.get_sources()
        self.auto_checkout = extension.get_auto_checkout()
        develop, self.develeggs, versions = extension.get_develop_info()

        if len(sys.argv) < 2:
            print "Type '%s help' for usage." % os.path.basename(sys.argv[0])
        else:
            self.commands.get(sys.argv[1], self.unknown)()

    def restore_original_dir(self):
        os.chdir(self.original_dir)

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

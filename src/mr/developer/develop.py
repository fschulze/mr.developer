from mr.developer.common import logger, memoize, WorkingCopies, Config, yesno
from mr.developer.extension import Extension
from zc.buildout.buildout import Buildout
import argparse
import atexit
import pkg_resources
import errno
import logging
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


class ChoicesPseudoAction(argparse.Action):

    def __init__(self, *args, **kwargs):
        sup = super(ChoicesPseudoAction, self)
        sup.__init__(dest=args[0], option_strings=list(args), help=kwargs.get('help'), nargs=0)


class ArgumentParser(argparse.ArgumentParser):
    def _check_value(self, action, value):
        # converted value must be one of the choices (if specified)
        if action.choices is not None and value not in action.choices:
            tup = value, ', '.join([repr(x) for x in sorted(action.choices) if x != 'pony'])
            msg = argparse._('invalid choice: %r (choose from %s)') % tup
            raise argparse.ArgumentError(action, msg)


class HelpFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        return self._fill_text(text, width, "").split("\n")

    def _fill_text(self, text, width, indent):
        result = []
        for line in text.split("\n"):
            for line2 in textwrap.fill(line, width).split("\n"):
                result.append("%s%s" % (indent, line2))
        return "\n".join(result)


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
        description="Add packages to the list of development packages."
        self.parser=self.develop.parsers.add_parser(
            "activate",
            description=description)
        self.develop.parsers._name_parser_map["a"] = self.develop.parsers._name_parser_map["activate"]
        self.develop.parsers._choices_actions.append(ChoicesPseudoAction(
            "activate", "a", help=description))
        self.parser.add_argument("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_argument("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_argument("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")
        self.parser.add_argument("package-regexp", nargs="+",
                                 help="A regular expression to match package names.")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        config = self.develop.config
        packages = self.get_packages(getattr(args, 'package-regexp'),
                                     auto_checkout=args.auto_checkout,
                                     checked_out=args.checked_out,
                                     develop=args.develop)
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
        self.parser=self.develop.parsers.add_parser(
            "checkout",
            description="Make a checkout of the packages matching the regular expressions and add them to the list of development packages.")
        self.develop.parsers._name_parser_map["co"] = self.develop.parsers._name_parser_map["checkout"]
        self.develop.parsers._choices_actions.append(ChoicesPseudoAction(
            "checkout", "co", help="Checkout packages"))
        self.parser.add_argument("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_argument("-v", "--verbose", dest="verbose",
                               action="store_true", default=False,
                               help="""Show output of VCS command.""")
        self.parser.add_argument("package-regexp", nargs="+",
                                 help="A regular expression to match package names.")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        config = self.develop.config
        packages = self.get_packages(getattr(args, 'package-regexp'),
                                     auto_checkout=args.auto_checkout)
        try:
            workingcopies = WorkingCopies(self.develop.sources)
            workingcopies.checkout(sorted(packages),
                                   verbose=args.verbose,
                                   always_accept_server_certificate=self.develop.always_accept_server_certificate)
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
        description="Remove packages from the list of development packages."
        self.parser=self.develop.parsers.add_parser(
            "deactivate",
            description=description)
        self.develop.parsers._name_parser_map["d"] = self.develop.parsers._name_parser_map["deactivate"]
        self.develop.parsers._choices_actions.append(ChoicesPseudoAction(
            "deactivate", "d", help=description))
        self.parser.add_argument("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_argument("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_argument("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")
        self.parser.add_argument("package-regexp", nargs="+",
                                 help="A regular expression to match package names.")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        config = self.develop.config
        packages = self.get_packages(getattr(args, 'package-regexp'),
                                     auto_checkout=args.auto_checkout,
                                     checked_out=args.checked_out,
                                     develop=args.develop)
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
        self.parser=self.develop.parsers.add_parser(
            "help",
            description="Show help on the given command or about the whole script if none given.")
        self.develop.parsers._name_parser_map["h"] = self.develop.parsers._name_parser_map["help"]
        self.develop.parsers._choices_actions.append(ChoicesPseudoAction(
            "help", "h", help="Show help"))
        self.parser.add_argument("--rst", dest="rst",
                               action="store_true", default=False,
                               help="""Print help for all commands in reStructuredText format.""")
        self.parser.add_argument("command", nargs="?", help="The command you want to see the help of.")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        develop = self.develop
        choices = develop.parsers.choices
        if args.command in choices:
            print choices[args.command].format_help()
            return
        cmds = {}
        for name in choices:
            if name == 'pony':
                continue
            cmds.setdefault(choices[name], set()).add(name)
        for cmd, names in cmds.items():
            names = list(reversed(sorted(names, key=len)))
            cmds[names[0]] = dict(
                aliases=names[1:],
                cmd=cmd,
            )
            del cmds[cmd]
        if args.rst:
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
                for line in cmd['cmd'].format_help().split('\n'):
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
        description="Lists informations about packages."
        self.parser=self.develop.parsers.add_parser(
            "info",
            help=description,
            description=description)
        self.parser.add_argument("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_argument("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_argument("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all declared packages are processed.""")
        info_opts = self.parser.add_argument_group("Output options",
                                              """The following options are used to print just the info you want, the order they are specified reflects the order in which the information will be printed.""")
        info_opts.add_argument("--name", dest="info",
                             action="append_const", const="name",
                             help="""Prints the name of the package.""")
        info_opts.add_argument("-p", "--path", dest="info",
                             action="append_const", const="path",
                             help="""Prints the absolute path of the package.""")
        info_opts.add_argument("--type", dest="info",
                             action="append_const", const="type",
                             help="""Prints the repository type of the package.""")
        info_opts.add_argument("--url", dest="info",
                             action="append_const", const="url",
                             help="""Prints the URL of the package.""")
        self.parser.add_argument_group(info_opts)
        self.parser.add_argument("package-regexp", nargs="*",
                                 help="A regular expression to match package names.")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        packages = self.get_packages(getattr(args, 'package-regexp'),
                                     auto_checkout=args.auto_checkout,
                                     develop=args.develop,
                                     checked_out=args.checked_out)
        for name in sorted(packages):
            source = self.develop.sources[name]
            if args.info:
                for key in args.info:
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
        description="Lists tracked packages."
        self.parser=self.develop.parsers.add_parser(
            "list",
            formatter_class=HelpFormatter,
            description=description)
        self.develop.parsers._name_parser_map["ls"] = self.develop.parsers._name_parser_map["list"]
        self.develop.parsers._choices_actions.append(ChoicesPseudoAction(
            "list", "ls", help=description))
        self.parser.add_argument("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only show packages in auto-checkout list.""")
        self.parser.add_argument("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_argument("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")
        self.parser.add_argument("-l", "--long", dest="long",
                               action="store_true", default=False,
                               help="""Show URL and kind of package.""")
        self.parser.add_argument("-s", "--status", dest="status",
                               action="store_true", default=False,
                               help=textwrap.dedent("""\
                                   Show checkout status.
                                   The first column in the output shows the checkout status:
                                       '#' available for checkout
                                       ' ' in auto-checkout list and checked out
                                       '~' not in auto-checkout list, but checked out
                                       '!' in auto-checkout list, but not checked out
                                       'C' the repository URL doesn't match"""))
        self.parser.add_argument("package-regexp", nargs="*",
                                 help="A regular expression to match package names.")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        sources = self.develop.sources
        auto_checkout = self.develop.auto_checkout
        packages = self.get_packages(getattr(args, 'package-regexp'),
                                     auto_checkout=args.auto_checkout,
                                     checked_out=args.checked_out,
                                     develop=args.develop)
        workingcopies = WorkingCopies(sources)
        for name in sorted(packages):
            source = sources[name]
            if args.status:
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
            if args.long:
                print "(%s)" % source['kind'], name, source['url']
            else:
                print name


class CmdPony(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=self.develop.parsers.add_parser(
            "pony",
            description="It should be easy to develop a pony!")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
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
        self.parser=self.develop.parsers.add_parser(
            "purge",
            formatter_class=HelpFormatter,
            description=textwrap.dedent("""\
                Remove checked out packages which aren't active anymore.

                Only 'svn' packages can be purged, because other repositories may contain unrecoverable files even when not marked as 'dirty'."""))
        self.parser.add_argument("-n", "--dry-run", dest="dry_run",
                               action="store_true", default=False,
                               help="""Don't actually remove anything, just print the paths which would be removed.""")
        self.parser.add_argument("-f", "--force", dest="force",
                               action="store_true", default=False,
                               help="""Force purge even if the working copy is dirty or unknown (non-svn).""")
        self.parser.add_argument("package-regexp", nargs="*",
                                 help="A regular expression to match package names.")
        self.parser.set_defaults(func=self)

    def handle_remove_readonly(self, func, path, exc):
        excvalue = exc[1]
        if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO) # 0777
            func(path)
        else:
            raise

    def __call__(self, args):
        buildout_dir = self.develop.buildout_dir
        packages = self.get_packages(getattr(args, 'package-regexp'),
                                     checked_out=True)
        packages = packages - self.develop.auto_checkout
        packages = packages - set(self.develop.develeggs)
        force = args.force
        force_all = False
        workingcopies = WorkingCopies(self.develop.sources)
        if args.dry_run:
            logger.info("Dry run, nothing will be removed.")
        for name in packages:
            source = self.develop.sources[name]
            path = source['path']
            if path.startswith(buildout_dir):
                path = path[len(buildout_dir)+1:]
            need_force = False
            if source['kind'] != 'svn':
                need_force = True
                logger.warn("The directory of package '%s' at '%s' might contain unrecoverable files and will not be removed without --force." % (name, path))
            if workingcopies.status(source) != 'clean':
                need_force = True
                logger.warn("The package '%s' is dirty and will not be removed without --force." % name)
            if need_force:
                if not force:
                    continue
                # We only get here when a --force is needed and we
                # have actually added the --force argument on the
                # command line.
                if not force_all:
                    answer = yesno("Do you want to purge it anyway?", default=False, all=True)
                    if not answer:
                        logger.info("Skipped purge of '%s'." % name)
                        continue
                    if answer == 'all':
                        force_all = True

            logger.info("Removing package '%s' at '%s'." % (name, path))
            if not args.dry_run:
                shutil.rmtree(source['path'],
                              ignore_errors=False,
                              onerror=self.handle_remove_readonly)


class CmdRebuild(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        description="Run buildout with the last used arguments."
        self.parser=self.develop.parsers.add_parser(
            "rebuild",
            description=description)
        self.develop.parsers._name_parser_map["rb"] = self.develop.parsers._name_parser_map["rebuild"]
        self.develop.parsers._choices_actions.append(ChoicesPseudoAction(
            "rebuild", "rb", help=description))
        self.parser.add_argument("-n", "--dry-run", dest="dry_run",
                               action="store_true", default=False,
                               help="""Don't actually run buildout, just show the last used arguments.""")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        buildout_dir = self.develop.buildout_dir
        buildout_args = self.develop.config.buildout_args
        print "Last used buildout arguments:",
        print " ".join(buildout_args[1:])
        if args.dry_run:
            logger.warning("Dry run, buildout not invoked.")
            return
        else:
            logger.info("Running buildout.")
        os.chdir(buildout_dir)
        subprocess.call(buildout_args)


class CmdReset(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        self.parser=self.develop.parsers.add_parser(
            "reset",
            help="Resets the packages develop status.",
            description="Resets the packages develop status. This is useful when switching to a new buildout configuration.")
        self.parser.add_argument("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_argument("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_argument("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")
        self.parser.add_argument("package-regexp", nargs="*",
                                 help="A regular expression to match package names.")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        config = self.develop.config
        packages = self.get_packages(getattr(args, 'package-regexp'),
                                     auto_checkout=args.auto_checkout,
                                     checked_out=args.checked_out,
                                     develop=args.develop)
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
        self.parser=self.develop.parsers.add_parser(
            "status",
            formatter_class=HelpFormatter,
            description=textwrap.dedent("""\
                Shows the status of tracked packages, filtered if <package-regexps> is given.
                The first column in the output shows the checkout status:
                    ' ' in auto-checkout list
                    '~' not in auto-checkout list
                    '!' in auto-checkout list, but not checked out
                    'C' the repository URL doesn't match
                    '?' unknown package (only reported when package-regexp is not specified)
                The second column shows the working copy status:
                    ' ' no changes
                    'M' local modifications or untracked files
                The third column shows the development status:
                    ' ' activated
                    '-' deactivated
                    '!' deactivated, but the package is in the auto-checkout list
                    'A' activated, but not in list of development packages (run buildout)
                    'D' deactivated, but still in list of development packages (run buildout)"""))
        self.develop.parsers._name_parser_map["stat"] = self.develop.parsers._name_parser_map["status"]
        self.develop.parsers._name_parser_map["st"] = self.develop.parsers._name_parser_map["status"]
        self.develop.parsers._choices_actions.append(ChoicesPseudoAction(
            "status", "stat", "st", help="Shows the status of tracked packages."))
        self.parser.add_argument("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_argument("-c", "--checked-out", dest="checked_out",
                               action="store_true", default=False,
                               help="""Only considers packages currently checked out. If you don't specify a <package-regexps> then all checked out packages are processed.""")
        self.parser.add_argument("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")
        self.parser.add_argument("-v", "--verbose", dest="verbose",
                               action="store_true", default=False,
                               help="""Show output of VCS command.""")
        self.parser.add_argument("package-regexp", nargs="*",
                                 help="A regular expression to match package names.")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        auto_checkout = self.develop.auto_checkout
        sources_dir = self.develop.sources_dir
        develeggs = self.develop.develeggs
        package_regexp = getattr(args, 'package-regexp')
        packages = self.get_packages(package_regexp,
                                     auto_checkout=args.auto_checkout,
                                     checked_out=args.checked_out,
                                     develop=args.develop)
        workingcopies = WorkingCopies(self.develop.sources)
        paths = []
        for name in sorted(packages):
            source = self.develop.sources[name]
            if not source.exists():
                if name in auto_checkout:
                    print "!", " ", name
                continue
            paths.append(source['path'])
            if not workingcopies.matches(source):
                print "C",
            else:
                if name in auto_checkout:
                    print " ",
                else:
                    print "~",
            if args.verbose:
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
            if args.verbose:
                output = output.strip()
                if output:
                    for line in output.split('\n'):
                        print "   ", line
                    print

        # Only report on unknown entries when we have no package regexp.
        if not package_regexp:
            for entry in os.listdir(sources_dir):
                if not os.path.join(sources_dir, entry) in paths:
                    print '?', ' ', entry


class CmdUpdate(Command):
    def __init__(self, develop):
        Command.__init__(self, develop)
        description="Updates all known packages currently checked out."
        self.parser=self.develop.parsers.add_parser(
            "update",
            description=description)
        self.develop.parsers._name_parser_map["up"] = self.develop.parsers._name_parser_map["update"]
        self.develop.parsers._choices_actions.append(ChoicesPseudoAction(
            "update", "up", help=description))
        self.parser.add_argument("-a", "--auto-checkout", dest="auto_checkout",
                               action="store_true", default=False,
                               help="""Only considers packages declared by auto-checkout. If you don't specify a <package-regexps> then all declared packages are processed.""")
        self.parser.add_argument("-d", "--develop", dest="develop",
                               action="store_true", default=False,
                               help="""Only considers packages currently in development mode. If you don't specify a <package-regexps> then all develop packages are processed.""")
        self.parser.add_argument("-f", "--force", dest="force",
                               action="store_true", default=False,
                               help="""Force update even if the working copy is dirty.""")
        self.parser.add_argument("-v", "--verbose", dest="verbose",
                               action="store_true", default=False,
                               help="""Show output of VCS command.""")
        self.parser.add_argument("package-regexp", nargs="*",
                                 help="A regular expression to match package names.")
        self.parser.set_defaults(func=self)

    def __call__(self, args):
        packages = self.get_packages(getattr(args, 'package-regexp'),
                                     auto_checkout=args.auto_checkout,
                                     checked_out=True,
                                     develop=args.develop)
        workingcopies = WorkingCopies(self.develop.sources)
        force = args.force or self.develop.always_checkout
        workingcopies.update(sorted(packages),
                             force=force,
                             verbose=args.verbose,
                             always_accept_server_certificate=self.develop.always_accept_server_certificate)


class Develop(object):
    def __call__(self, **kwargs):
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(ch)
        self.parser = ArgumentParser()
        version = pkg_resources.get_distribution("mr.developer").version
        self.parser.add_argument('-v', '--version',
                                 action='version',
                                 version='mr.developer %s' % version)
        self.parsers = self.parser.add_subparsers(title="commands", metavar="")
        CmdActivate(self)
        CmdCheckout(self)
        CmdDeactivate(self)
        CmdHelp(self)
        CmdInfo(self)
        CmdList(self)
        CmdPony(self)
        CmdPurge(self)
        CmdRebuild(self)
        CmdReset(self)
        CmdStatus(self)
        CmdUpdate(self)
        args = self.parser.parse_args()

        try:
            self.buildout_dir = find_base()
        except IOError, e:
            self.parser.print_help()
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
        self.sources_dir = extension.get_sources_dir()
        self.auto_checkout = extension.get_auto_checkout()
        self.always_checkout = extension.get_always_checkout()
        self.always_accept_server_certificate = extension.get_always_accept_server_certificate()
        develop, self.develeggs, versions = extension.get_develop_info()

        args.func(args)

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

from mr.developer.common import logger, Config, get_commands
from mr.developer.commands import CmdHelp
from mr.developer.extension import Extension
from zc.buildout.buildout import Buildout
import argparse
import atexit
import pkg_resources
import logging
import os
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


class Develop(object):
    def __call__(self, *args, **kwargs):
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

        for command in get_commands():
            command(self)

        if not args:
            args = None
        args = self.parser.parse_args(args)

        try:
            self.buildout_dir = find_base()
        except IOError:
            if isinstance(args.func, CmdHelp):
                args.func(args)
                return
            self.parser.print_help()
            print
            logger.error("You are not in a path which has mr.developer installed (%s)." % sys.exc_info()[1])
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
        self.update_git_submodules = extension.get_update_git_submodules()
        self.always_accept_server_certificate = extension.get_always_accept_server_certificate()
        develop, self.develeggs, versions = extension.get_develop_info()
        self.threads = extension.get_threads()

        args.func(args)

    def restore_original_dir(self):
        if os.path.exists(self.original_dir):
            os.chdir(self.original_dir)

develop = Develop()

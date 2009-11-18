from ConfigParser import RawConfigParser
import logging
import os
import sys


logger = logging.getLogger("mr.developer")


def memoize(f, _marker=[]):
    def g(*args, **kwargs):
        name = '_memoize_%s' % f.__name__
        value = getattr(args[0], name, _marker)
        if value is _marker:
            value = f(*args, **kwargs)
            setattr(args[0], name, value)
        return value
    return g


class WCError(Exception):
    """ A working copy error. """


workingcopytypes = {}

class BaseWorkingCopy(object):
    def __new__(cls, kind):
        wc = object.__new__(cls)
        workingcopytypes[kind] = wc
        return wc


class WorkingCopies(object):
    def __init__(self, sources):
        self.sources = sources

    def checkout(self, packages, **kwargs):
        errors = False
        for name in packages:
            if name not in self.sources:
                logger.error("Checkout failed. No source defined for '%s'." % name)
                sys.exit(1)
            source = self.sources[name]
            try:
                kind = source['kind']
                wc = workingcopytypes.get(kind)
                if wc is None:
                    logger.error("Unknown repository type '%s'." % kind)
                    sys.exit(1)
                output = wc.checkout(source, **kwargs)
                if kwargs.get('verbose', False) and output is not None and output.strip():
                    print output
            except WCError, e:
                for l in e.args[0].split('\n'):
                    logger.error(l)
                sys.exit(1)
        return errors

    def matches(self, source):
        name = source['name']
        if name not in self.sources:
            logger.error("Checkout failed. No source defined for '%s'." % name)
            sys.exit(1)
        source = self.sources[name]
        try:
            kind = source['kind']
            wc = workingcopytypes.get(kind)
            if wc is None:
                logger.error("Unknown repository type '%s'." % kind)
                sys.exit(1)
            return wc.matches(source)
        except WCError, e:
            for l in e.args[0].split('\n'):
                logger.error(l)
            sys.exit(1)

    def status(self, source, **kwargs):
        name = source['name']
        if name not in self.sources:
            logger.error("Status failed. No source defined for '%s'." % name)
            sys.exit(1)
        source = self.sources[name]
        try:
            kind = source['kind']
            wc = workingcopytypes.get(kind)
            if wc is None:
                logger.error("Unknown repository type '%s'." % kind)
                sys.exit(1)
            return wc.status(source, **kwargs)
        except WCError, e:
            for l in e.args[0].split('\n'):
                logger.error(l)
            sys.exit(1)

    def update(self, packages, **kwargs):
        for name in packages:
            if name not in self.sources:
                continue
            source = self.sources[name]
            try:
                kind = source['kind']
                wc = workingcopytypes.get(kind)
                if wc is None:
                    logger.error("Unknown repository type '%s'." % kind)
                    sys.exit(1)
                output = wc.update(source, **kwargs)
                if kwargs.get('verbose', False) and output is not None and output.strip():
                    print output
            except WCError, e:
                for l in e.args[0].split('\n'):
                    logger.error(l)
                sys.exit(1)


def parse_buildout_args(args):
    settings = dict(
        config_file = 'buildout.cfg',
        verbosity = 0,
        options = [],
        windows_restart = False,
        user_defaults = True,
        debug = False,
    )
    options = []
    while args:
        if args[0][0] == '-':
            op = orig_op = args.pop(0)
            op = op[1:]
            while op and op[0] in 'vqhWUoOnNDA':
                if op[0] == 'v':
                    settings['verbosity'] = settings['verbosity'] + 10
                elif op[0] == 'q':
                    settings['verbosity'] = settings['verbosity'] - 10
                elif op[0] == 'W':
                    settings['windows_restart'] = True
                elif op[0] == 'U':
                    settings['user_defaults'] = False
                elif op[0] == 'o':
                    options.append(('buildout', 'offline', 'true'))
                elif op[0] == 'O':
                    options.append(('buildout', 'offline', 'false'))
                elif op[0] == 'n':
                    options.append(('buildout', 'newest', 'true'))
                elif op[0] == 'N':
                    options.append(('buildout', 'newest', 'false'))
                elif op[0] == 'D':
                    settings['debug'] = True
                else:
                    raise ValueError("Unkown option '%s'." % op[0])
                op = op[1:]

            if op[:1] in  ('c', 't'):
                op_ = op[:1]
                op = op[1:]

                if op_ == 'c':
                    if op:
                        settings['config_file'] = op
                    else:
                        if args:
                            settings['config_file'] = args.pop(0)
                        else:
                            raise ValueError("No file name specified for option", orig_op)
                elif op_ == 't':
                    try:
                        timeout = int(args.pop(0))
                    except IndexError:
                        raise ValueError("No timeout value specified for option", orig_op)
                    except ValueError:
                        raise ValueError("No timeout value must be numeric", orig_op)
                    settings['socket_timeout'] = op
            elif op:
                if orig_op == '--help':
                    return 'help'
                raise ValueError("Invalid option", '-'+op[0])
        elif '=' in args[0]:
            option, value = args.pop(0).split('=', 1)
            if len(option.split(':')) != 2:
                raise ValueError('Invalid option:', option)
            section, option = option.split(':')
            options.append((section.strip(), option.strip(), value.strip()))
        else:
            # We've run out of command-line options and option assignnemnts
            # The rest should be commands, so we'll stop here
            break
    return options, settings


class Config(object):
    def __init__(self, buildout_dir):
        self.cfg_path = os.path.join(buildout_dir, '.mr.developer.cfg')
        self._config = RawConfigParser()
        self._config.optionxform = lambda s: s
        self._config.read(self.cfg_path)
        self.develop = {}
        self.buildout_args = []
        self.rewrites = []
        if self._config.has_section('develop'):
            for package, value in self._config.items('develop'):
                value = value.lower()
                if value == 'true':
                    self.develop[package] = True
                elif value == 'false':
                    self.develop[package] = False
                elif value == 'auto':
                    self.develop[package] = 'auto'
                else:
                    raise ValueError("Invalid value in 'develop' section of '%s'" % self.cfg_path)
        if self._config.has_option('buildout', 'args'):
            args = self._config.get('buildout', 'args').split("\n")
            for arg in args:
                arg = arg.strip()
                if arg.startswith("'") and arg.endswith("'"):
                    arg = arg[1:-1].replace("\\'", "'")
                elif arg.startswith('"') and arg.endswith('"'):
                    arg = arg[1:-1].replace('\\"', '"')
                self.buildout_args.append(arg)
        (self.buildout_options, self.buildout_settings) = \
            parse_buildout_args(self.buildout_args[1:])
        if self._config.has_option('mr.developer', 'rewrites'):
            for rewrite in self._config.get('mr.developer', 'rewrites').split('\n'):
                self.rewrites.append(rewrite.split())

    def save(self):
        self._config.remove_section('develop')
        self._config.add_section('develop')
        for package in sorted(self.develop):
            state = self.develop[package]
            if state is 'auto':
                self._config.set('develop', package, 'auto')
            elif state is True:
                self._config.set('develop', package, 'true')
            elif state is False:
                self._config.set('develop', package, 'false')

        if not self._config.has_section('buildout'):
            self._config.add_section('buildout')
        self._config.set('buildout', 'args', "\n".join(repr(x) for x in self.buildout_args))

        if not self._config.has_section('mr.developer'):
            self._config.add_section('mr.developer')
        self._config.set('mr.developer', 'rewrites', "\n".join(" ".join(x) for x in self.rewrites))

        self._config.write(open(self.cfg_path, "w"))

from ConfigParser import RawConfigParser
import logging
import os
import pkg_resources
import Queue
import subprocess
import sys
import threading


logger = logging.getLogger("mr.developer")


# shameless copy from
# http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
def which(*names):
    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    for name in names:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, name)
            if is_exe(exe_file):
                return exe_file

    return None


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
    def __init__(self, source):
        self._output = []
        self.output = self._output.append
        self.source = source

    def should_update(self, **kwargs):
        offline = kwargs.get('offline', False)
        if offline:
            return False
        update = self.source.get('update', kwargs.get('update', False))
        if not isinstance(update, bool):
            if update.lower() in ('true', 'yes'):
                update = True
            elif update.lower() in ('false', 'no'):
                update = False
            else:
                raise ValueError("Unknown value for 'update': %s" % update)
        return update


def yesno(question, default=True, all=True):
    if default:
        question = "%s [Yes/no" % question
        answers = {
            False: ('n', 'no'),
            True: ('', 'y', 'yes'),
        }
    else:
        question = "%s [yes/No" % question
        answers = {
            False: ('', 'n', 'no'),
            True: ('y', 'yes'),
        }
    if all:
        answers['all'] = ('a', 'all')
        question = "%s/all] " % question
    else:
        question = "%s] " % question
    while 1:
        answer = raw_input(question).lower()
        for option in answers:
            if answer in answers[option]:
                return option
        if all:
            print >>sys.stderr, "You have to answer with y, yes, n, no, a or all."
        else:
            print >>sys.stderr, "You have to answer with y, yes, n or no."


main_lock = input_lock = output_lock = threading.RLock()


def worker(working_copies, queue):
    while True:
        if working_copies.errors:
            return
        try:
            wc, action, kwargs = queue.get_nowait()
        except Queue.Empty:
            return
        try:
            output = action(**kwargs)
        except WCError, e:
            output_lock.acquire()
            for lvl, msg in wc._output:
                lvl(msg)
            for l in e.args[0].split('\n'):
                logger.error(l)
            working_copies.errors = True
            output_lock.release()
        else:
            output_lock.acquire()
            for lvl, msg in wc._output:
                lvl(msg)
            if kwargs.get('verbose', False) and output is not None and output.strip():
                print output
            output_lock.release()


class WorkingCopies(object):
    def __init__(self, sources):
        self.sources = sources
        self.threads = 5
        self.errors = False

    def process(self, queue):
        threads = []
        if sys.version_info < (2, 6):
            # work around a race condition in subprocess
            _old_subprocess_cleanup = subprocess._cleanup
            def _cleanup():
                pass
            subprocess._cleanup = _cleanup
        for i in range(self.threads):
            thread = threading.Thread(target=worker, args=(self, queue))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
        if sys.version_info < (2, 6):
            subprocess._cleanup = _old_subprocess_cleanup
            subprocess._cleanup()
        if self.errors:
            logger.error("There have been errors, see messages above.")
            sys.exit(1)

    def checkout(self, packages, **kwargs):
        queue = Queue.Queue()
        if 'update' in kwargs:
            if isinstance(kwargs['update'], bool):
                pass
            elif kwargs['update'].lower() in ('true', 'yes', 'on', 'force'):
                if kwargs['update'].lower() == 'force':
                    kwargs['force'] = True
                kwargs['update'] = True
            elif kwargs['update'].lower() in ('false', 'no', 'off'):
                kwargs['update'] = False
            else:
                logger.error("Unknown value '%s' for always-checkout option." % kwargs['update'])
                sys.exit(1)
        for name in packages:
            kw = kwargs.copy()
            if name not in self.sources:
                logger.error("Checkout failed. No source defined for '%s'." % name)
                sys.exit(1)
            source = self.sources[name]
            kind = source['kind']
            wc = workingcopytypes.get(kind)(source)
            if wc is None:
                logger.error("Unknown repository type '%s'." % kind)
                sys.exit(1)
            update = wc.should_update(**kwargs)
            if not source.exists():
                pass
            elif update and wc.status() != 'clean' and not kw.get('force', False):
                print >>sys.stderr, "The package '%s' is dirty." % name
                answer = yesno("Do you want to update it anyway?", default=False, all=True)
                if answer:
                    kw['force'] = True
                    if answer == 'all':
                        kwargs['force'] = True
                else:
                    logger.info("Skipped update of '%s'." % name)
                    continue
            logger.info("Queued '%s' for checkout.", name)
            queue.put_nowait((wc, wc.checkout, kw))
        self.process(queue)

    def matches(self, source):
        name = source['name']
        if name not in self.sources:
            logger.error("Checkout failed. No source defined for '%s'." % name)
            sys.exit(1)
        source = self.sources[name]
        try:
            kind = source['kind']
            wc = workingcopytypes.get(kind)(source)
            if wc is None:
                logger.error("Unknown repository type '%s'." % kind)
                sys.exit(1)
            return wc.matches()
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
            wc = workingcopytypes.get(kind)(source)
            if wc is None:
                logger.error("Unknown repository type '%s'." % kind)
                sys.exit(1)
            return wc.status(**kwargs)
        except WCError, e:
            for l in e.args[0].split('\n'):
                logger.error(l)
            sys.exit(1)

    def update(self, packages, **kwargs):
        queue = Queue.Queue()
        for name in packages:
            kw = kwargs.copy()
            if name not in self.sources:
                continue
            source = self.sources[name]
            kind = source['kind']
            wc = workingcopytypes.get(kind)(source)
            if wc is None:
                logger.error("Unknown repository type '%s'." % kind)
                sys.exit(1)
            if wc.status() != 'clean' and not kw.get('force', False):
                print >>sys.stderr, "The package '%s' is dirty." % name
                answer = yesno("Do you want to update it anyway?", default=False, all=True)
                if answer:
                    kw['force'] = True
                    if answer == 'all':
                        kwargs['force'] = True
                else:
                    logger.info("Skipped update of '%s'." % name)
                    continue
            logger.info("Queued '%s' for update.", name)
            queue.put_nowait((wc, wc.update, kw))
        self.process(queue)


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
    version = pkg_resources.get_distribution("zc.buildout").version
    if tuple(version.split('.')[:2]) <= ('1', '4'):
        option_str = 'vqhWUoOnNDA'
    else:
        option_str = 'vqhWUoOnNDAs'
    while args:
        if args[0][0] == '-':
            op = orig_op = args.pop(0)
            op = op[1:]
            while op and op[0] in option_str:
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
                elif op[0] == 's':
                    settings['ignore_broken_dash_s'] = True
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
                        int(args.pop(0))
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
    return options, settings, args


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
        (self.buildout_options, self.buildout_settings, _) = \
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
        options, settings, args = parse_buildout_args(self.buildout_args[1:])
        # don't store the options when a command was in there
        if not len(args):
            self._config.set('buildout', 'args', "\n".join(repr(x) for x in self.buildout_args))

        if not self._config.has_section('mr.developer'):
            self._config.add_section('mr.developer')
        self._config.set('mr.developer', 'rewrites', "\n".join(" ".join(x) for x in self.rewrites))

        self._config.write(open(self.cfg_path, "w"))

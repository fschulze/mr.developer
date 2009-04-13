import logging
import sys


logger = logging.getLogger("mr.developer")


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

    def checkout(self, packages, skip_errors=False, verbose=False):
        errors = False
        for name in packages:
            if name not in self.sources:
                logger.error("Checkout failed. No source defined for '%s'." % name)
                if not skip_errors:
                    sys.exit(1)
                else:
                    errors = True
            source = self.sources[name]
            try:
                kind = source['kind']
                wc = workingcopytypes.get(kind)
                if wc is None:
                    logger.error("Unknown repository type '%s'." % kind)
                    if not skip_errors:
                        sys.exit(1)
                    else:
                        errors = True
                wc.checkout(source, verbose=False)
            except WCError, e:
                for l in e.args[0].split('\n'):
                    logger.error(l)
                if not skip_errors:
                    sys.exit(1)
                else:
                    errors = True
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

    def status(self, source, verbose=False):
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
            return wc.status(source, verbose=verbose)
        except WCError, e:
            for l in e.args[0].split('\n'):
                logger.error(l)
            sys.exit(1)

    def update(self, packages, verbose=False):
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
                output = wc.update(source, verbose=verbose)
                if verbose:
                    print output
            except WCError, e:
                for l in e.args[0].split('\n'):
                    logger.error(l)
                sys.exit(1)

.. contents:: :depth: 1

Introduction
============

.. figure:: http://fschulze.github.io/mr.developer/xkcd-buildout.png
    :figwidth: image

    Let Mr. Developer help you win the everlasting buildout battle!

    (Remixed by Matt Hamilton, original from http://xkcd.com/303)

**mr.developer** is a `zc.buildout`_ extension that makes it easy to work with
buildouts containing lots of packages, of which you only want to develop some.
The basic idea comes from Wichert Akkerman's plonenext_ effort.

.. image:: https://secure.travis-ci.org/fschulze/mr.developer.png

.. _`zc.buildout`: http://pypi.python.org/pypi/zc.buildout
.. _plonenext: http://svn.plone.org/svn/plone/plonenext/3.3/README.txt

Usage
=====

Add ``mr.developer`` to the ``extensions`` entry in your ``[buildout]``
section::

  [buildout]
  extensions = mr.developer

This enables additional ``[buildout]`` options:

``sources``
  This specifies the name of a section which lists the repository
  information for your packages. Defaults to ``sources``.

``sources-dir``
  This specifies the default directory where your development packages will
  be placed. Defaults to ``src``.

``auto-checkout``
  This specifies the names of packages which should be checked out during
  buildout. Packages already checked out are skipped. You can use ``*`` as
  a wildcard for all packages in ``sources``.

``always-checkout``
  This defaults to ``false``. If it's ``true``, then all packages specified
  by ``auto-checkout`` and currently in develop mode are updated during each
  buildout run. If set to ``force``, then packages are updated even when
  they are dirty instead of asking interactively.

``update-git-submodules``
  This defaults to ``always``. If it's ``always``, then submodules present
  in each package in develompent will be registered and updated on checkout and
  new ones on updates via the develop command. If you don't want to initialize any submodule,
  set value to ``never``. If you set the value to ``checkout``,
  code inside submodules will be pulled only the first time, so the ``develop up`` command
  will leave the submodule empty. Note that update only initializes
  new submodules, it doesn't pull newest code from original submodule repo.

``always-accept-server-certificate``
  This defaults to ``false``. If it's ``true``, invalid server
  certificates are accepted without asking (for subversion repositories).

``mr.developer-threads``
  This sets the number of threads used for parallel checkouts. See
  `Lockups during checkouts and updates`_ why you might need this.

``git-clone-depth``
  This sets the git clone history size (git clone --depth parameter).
  Not really useful for development, but really useful on CI environments.
  The other big benefit is the speedup on cloning,
  as only few revisions are downloaded.
  Default is to get the full history.

The format of entries in the ``[sources]`` section is::

  [sources]
  name = kind url [key=value ...]

Where individual parts are:

``name``
  The package name.

``kind``
  The kind of repository. Currently supported are ``svn``,
  ``hg``, ``git``, ``bzr``, ``darcs``, ``cvs``, or ``fs``.

``url``
  The location of the repository. This value is specific to the version
  control system used.

``key=value``
  You can add options for each individual package with this. No whitespace is
  allowed in ``key``, ``value``, and around the equal sign. For a
  description of the options see below. (*Note*: don't surround your ``key=value``
  with square brackets: we only use ``[ ]`` here to indicate that it
  is optional to add options.)


The per-package options are:

Common options
  The ``path`` option allows you to set the base directory where the
  package will be checked out. The name of the package will be appended to
  the base path. If ``path`` is not set, ``sources-dir`` is used.

  With ``full-path`` you can set the directory where the package will be
  checked out. This is the actual destination, nothing will be added. As 
  an example::
  
    [sources]
    pkg = fs pkg full-path=/path/to/pkg

  The ``update`` option allows you to specify whether a package will be
  updated during buildout or not. If it's ``true``, then it will always be
  updated. If it's ``false``, then it will never be updated, even if the
  global ``always-checkout`` option is set.

  The ``egg`` option makes it possible to manage packages which are not
  eggs with ``egg=false``. All commands like ``update`` work as expected,
  but the package isn't added to the ``develop`` buildout option and the
  ``activate`` and ``deactivate`` commands skip the package.

  The ``newest_tag`` option allows you to checkout/update to the newest tag.
  Possible values of the option are "true" and "false".
  The ``newest_tag_prefix`` option allows you to limit the selection of tags to
  those which start with the prefix.
  These two options currently only work for ``cvs`` and ``hg``.

``svn``
  The ``url`` is one of the urls supported by subversion.

  You can specify a url with a revision pin, like
  ``http://example.com/trunk@123``.

  You can also set the ``rev`` or ``revision`` option, which is either a pin
  like with ``rev=123`` or a minimum revision like ``rev=>123`` or
  ``rev=>=123``. When you set a minimum revision, the repository is updated
  when the current revision is lower.

``git``
  The ``branch`` option allows you to use a specific branch instead of
  master.

  The ``rev`` option allows you to use a specific revision (usually a
  tag) instead of the HEAD.

  The ``pushurl`` options allows you to explicitly separate push url from pull
  url, configured by git config.

  The ``submodules`` option allows you to initialize existing submodules.
  Default value is controled by the buildout option ``update-git-submodules``.
  Possible values are the same described before in ``update-git-submodules`` option,

  The ``depth`` option allows to specify how much history you want to clone.
  This is the so called *shallow clones*.
  Note that this is mostly not useful at all for regular clones,
  on the other hand for one time usages (continuous integration for example) it makes clones much faster.
  This option overrides a general ``git-clone-depth`` value,
  so per-source depth can be specified.

  Note that the ``branch`` and ``rev`` option are mutually exclusive.

``hg``
  The ``branch`` option allows you to use a specific branch instead of
  default.

  The ``rev`` option allows you to force a specific revision
  (hash, tag, branch) to be checked out after buildout

``bzr``
  Currently no additional options.

``darcs``
  Currently no additional options.

``cvs``
  The ``cvs_root`` option can be used to override the setting of the $CVSROOT
  environment variable.
  The ``tag`` option forces checkout/update of the given tag instead of CVS
  HEAD.

  The ``tag_file`` option defines from which file tags will be read (in case of
  using ``newest_tag``).  Default value is "setup.py".

``fs``
  This allows you to add packages on the filesystem without a version
  control system, or with an unsupported one. You can activate and
  deactivate packages, but you don't get status info and can't update etc.

  The ``url`` needs to be the same as the ``name`` of the package.

Here's an example of how your ``buildout.cfg`` may look like::

  [buildout]
  extensions = mr.developer
  auto-checkout = my.package

  [sources]
  my.package = svn http://example.com/svn/my.package/trunk update=true
  some.other.package = git git://example.com/git/some.other.package.git

When you run buildout, the script ``bin/develop`` is created in your
buildout directory. With this script you can perform various actions on
packages, like checking out their source code, without the need to know where
the repositories are located.

For help on what the script can do, run ``bin/develop help``.

If you checked out the source code of a package, you must run buildout again.
The new package will then be marked as a development egg and have its version
pin cleared (if any). You can control the list of development eggs explicitely
with the ``activate`` and ``deactivate`` commands.

Any source where the path is a symlink is skipped during updates, as it is
assumed, that the developer handles it manually. It is basically treated like
a filesystem source.

Configuration
=============

You can add options to your global ``~/.buildout/mr.developer.cfg`` or local
``.mr.developer-options.cfg`` in your buildout. Don't ever edit
``.mr.developer.cfg`` in your buildout though, it's generated automatically.

In the ``[mr.developer]`` section you have the following options.

``threads``
  This sets the number of threads used for parallel checkouts. See
  `Lockups during checkouts and updates`_ why you might need this.

In the ``[rewrites]`` section you can setup rewrite rules for sources. This is
useful if you want to provide a buildout with sources to repositories which have
different URLs for repositories which are read only for anonymous users. In that
case developers can add a URL rewrite which automatically changes the URL to a
writable repository.

The rewrite rules can have multiple operators:

``=``
  Matches the exact string. Useful to only operated on sources of a certain kind
  and similar things. This doesn't rewrite anything, but limits the rule.

``~=``
  Matches with a regular expression. This doesn't rewrite anything, but limits
  the rule.

``~``
  This runs a regular expression substitution. The substitute is read from the
  next line. You can use groups in the expression and the backslash syntax in
  the substitute. See `re.sub`_ documentation.

.. _`re.sub`: http://docs.python.org/2/library/re.html#re.sub

The following are useful examples::

  [rewrites]

  plone_svn =
    url ~ ^http://svn.plone.org/svn/
    https://svn.plone.org/svn/

  github =
    url ~ ^https://github.com/
    git@github.com:
    kind = git

  my_mrdeveloper_fork =
    url ~ fschulze(/mr.developer.git)
    me\1

  my_mrdeveloper_fork_alternate =
    url ~= fschulze/mr.developer.git
    url ~ fschulze/
    me/

Extending
=========

You can extend mr.developer to teach it new types of Working Copies
and to add or modify existing commands.

Mr.developer uses entrypoints for this. TO see examples on how to create entry
points in detail, you can have a look at the existing entry points.

Adding support for a new working copy type
------------------------------------------
Add en entry to the entry point group ``mr.developer.workingcopytypes``.
They key of the entry is going to be used in the sources section of your
buildout file. The value should be a class.
The referenced class must implement the following methods::

    - __init__(self, source)
    - matches(self)
    - checkout(self, **kwargs)
    - status(self, verbose=False, **kwargs)
    - update(self, **kwargs)

The source is a dictionary like object. The source object provides the
attributes::

    - name
    - url
    - path

In addition it contains all key value pairs one can define on the source line
in buildout, and a methods ``exists`` that returns, whether the ``path``
already exists.

The matches method must return, if the checkout at the ``path`` matches the
repository at ``url``

The commands map to the commands mr.developer provides. To see the list of
potential arguments, check the documentation of the commands.
The commands ``checkout`` and update only return what they want to have printed
out on stdout, the ``status`` command must check the verbose flag. If the
verbose flag is set, it must return a tuple with what it wants to print out and
what the VCS commands generated as output.

All objects must have list ``_output`` which contains logging information.
Please refer to existing implementations for how to fill this information.

If your working copy Handler needs to throw an error, throw errors with
``mr.developer.common.WCError`` as a base clase.

If you need to add new functionality for new commands or change behavior of
something, try not to write a new working copy handler. Try your best your
changes generically useful and get them into mr.developer.

Adding a new command
--------------------
Add an entry to the entry point group ``mr.developer.commands``.
The key will be the name of the command itself.

The referenced class must implement the following methods::

    - __init__(self, develop)
    - __call__(self, args)

An inversion of control happens here. On initalization, you receive a develop
object that represents the class handling invocation of ``./bin/develop``
It is now your job to modify the attributes of the ``develop`` object to handle
argument parsing.
Create an ArgumentParser and add it to ``develop.parsers``.

Upon calling, you can perform your actions. It is a good idea to subclass from
``mr.developer.commands.Command``. It provides convenient helper methods::

    - get_workingcopies(self, sources)
    - get_packages(args, auto_checkout, develop, checked_out)

``get_workingcopies`` gives you a WorkingCopies object that will delegate all
your working copy actions to the right working copy handler.

``get_packages`` is a little helper to get sources filterd by the rules.
``args`` can be one or more regular expression filtr on source names, the other
attributes are boolean flags that by default are ``False``. False means _not_
to filter. Calling the method only with the ``arg`` '.' would thus return all
packges. THe returned object is a set containing only the names of the sources.

To perform an action, you get the package names via get_packages. then you get
the WorkingCopies object and call the action you want to perform on this
object. THe WorkingCopies object checks, which working copy is responsible for
the given package and delegates the action to this object. The WorkingCopies
object is also handling threading functionality.

The ``develop`` object has a ``config`` property. This object can be used to
store configuration of your actions. under ``config.develop`` a dictionary
resides which stores, whether the source with the given key is going to be used
from source checkout.


Troubleshooting
===============

Dirty SVN
---------

You get an error like::

  ERROR: Can't switch package 'foo' to 'https://example.com/svn/foo/trunk/' because it's dirty.

If you have not modified the package files under src/foo, then you can check
what's going on with ``status -v``. One common cause is a ``*.egg-info`` folder
which gets generated every time you run buildout and this shows up as an
untracked item in svn status.

You should add .egg-info to your global Subversion ignores in
``~/.subversion/config``, like this::

  global-ignores = *.o *.lo *.la *.al .libs *.so *.so.[0-9]* *.a *.pyc *.pyo *.rej *~ #*# .#* .*.swp .DS_Store *.egg-info

HTTPS Certificates
------------------

The best way to handle https certificates at the moment, is to accept them
permanently when checking out the source manually.

Mercurial reports mismatching URL
---------------------------------

This happens if you use lp:// URLs from launchpad. The problem is, that hg
reports the actual URL, not the lp shortcut.

Lockups during checkouts and updates
------------------------------------

Especially on multicore machines, there is an issue that you can get lockups
because of the parallel checkouts. You can configure the number of threads used
for this in ``.mr.developer.cfg`` in the buildout root of your project or
globally in ``~/.buildout/mr.developer.cfg`` through the ``threads`` option
in the ``[mr.developer]`` section or in your buildout in the ``buildout``
section with the ``mr.developer-threads`` option. Setting it to ``1`` should
fix these issues, but this disables parallel checkouts and makes the process a
bit slower.

Also, if you have `ControlPersist` in your local ssh config, and you
have a source checkout that uses ssh (for example
``git@github.com:...``) the checkout or update may work fine, but the
ssh connection may stay open and ``mr.developer`` cannot exit because
it waits for the ssh process to finish.

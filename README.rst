.. contents:: :depth: 1

Introduction
============

.. figure:: http://fschulze.github.com/mr.developer/xkcd-buildout.png
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
  description of the options see below.

The per-package options are:

Common options
  The ``path`` option allows you to set the base directory where the
  package will be checked out. The name of the package will be appended to
  the base path. If ``path`` is not set, ``sources-dir`` is used.

  With ``full-path`` you can set the directory where the package will be
  checked out. This is the actual destination, nothing will be added.

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

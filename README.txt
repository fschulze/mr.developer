.. contents:: :depth: 1

Introduction
============

.. figure:: http://www.netsight.co.uk/junk/xkcd-buildout.png
    :figwidth: image

    Let Mr. Developer help you win the everlasting buildout battle!

    (Remixed by Matt Hamilton, original from http://xkcd.com/303)

``mr.developer`` is a ``zc.buildout`` extension which makes it easier to work with
buildouts containing lots of packages of which you only want to develop some.
The basic idea for this comes from Wichert Akkerman's ``plonenext`` effort.


Usage
=====

You add ``mr.developer`` to the ``extensions`` option of your ``[buildout]``
section. Then you can add the following options to your ``[buildout]``
section:

  ``sources-dir``
    This specifies the default directory where your development packages will
    be placed. Defaults to ``src``.

  ``sources``
    This specifies the name of a section which lists the repository
    information of your packages. Defaults to ``sources``.

  ``auto-checkout``
    This specifies the names of packages which should be checked out during
    buildout, packages already checked out are skipped. You can use ``*`` as
    a wild card for all packages in ``sources``.

  ``always-checkout``
    This defaults to ``false``. If it's ``true``, then all packages specified
    by ``auto-checkout`` and currently in develop mode are updated during the
    buildout run. If set to ``force``, then packages are updated even when
    they are dirty instead of asking interactively.

  ``always-accept-server-certificate``
    This defaults to ``false``. If it's ``true``, then invalid server
    certificates are accepted without asking for subversion repositories.

The format of the section with the repository information is::

  <name> = <kind> [key=value] <url> [path] [key=value]

The different parts have the following meaning:

  ``<name>``
    This is the package name.

  ``<kind>``
    The kind of repository. Currently supported are one of ``svn`` (>= 1.5),
    ``hg``, ``git``, ``bzr``, ``cvs`` or ``fs``.

  ``<url>``
    The location of the repository. This value is specific to the version
    control system used.

  ``[path]``
    .. important::
       This is replaced by ``path=PATH`` syntax.

    The (optional) base directory where the package will be checked out.

    The name of the package will be appended.

    If it's not set, then ``sources-dir`` will be used.

  ``[key=value]``
    You can add options for each individual package with this. There are is no
    whitespace allowed in ``key``, ``value`` and around the equal sign. For a
    description of the options see below.

The different repository kinds accept some specific options.

  Common options
    The ``path`` option allows you to set the base directory where the
    package will be checked out. The name of the package will be appended to
    the base path.

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

  ``svn``
    The ``<url>`` is one of the urls supported by subversion.

    You can specify a url with a revision pin, like
    ``http://example.com/trunk@123``.

    You can also set the ``rev`` or ``revision`` option, which is either a pin
    like with ``rev=123`` or a minimum revision like ``rev=>123`` or
    ``rev=>=123``. When you set a minimum revision, the repository is updated
    when the current revision is lower.

  ``git``
    The ``branch`` option allows you to use a specific branch instead of
    master.

  ``hg``
    Currently no additional options.

  ``bzr``
    Currently no additional options.

  ``cvs``
    ``cvs_root`` option can be used to override the setting of the $CVSROOT
    environment variable.
    ``tag`` option force checkout/update of given tag instead of CVS HEAD.
    
  ``fs``
    This allows you to add packages on the filesystem without a version
    control system, or with an unsupported one. You can activate and
    deactivate packages, but you don't get status info and can't update etc.

    The ``<url>`` needs to be the same as the ``<name>`` of the package.

The following is an example of how your ``buildout.cfg`` may look like::

  [buildout]
  ...
  extensions = mr.developer
  sources = sources
  auto-checkout = my.package

  [sources]
  my.package = svn http://example.com/svn/my.package/trunk
  some.other.package = git git://example.com/git/some.other.package.git

When you run buildout, you will get a script at ``bin/develop`` in your
buildout directory. With that script you can perform various actions on the
packages, like checking out the source code, without the need to know where
the repository is located.

For help on what the script can do, run ``bin/develop help``.

If you checked out the source code of a package, you need run buildout again.
The package will automatically be marked as an develop egg and, if it's listed
in the section specified by the ``versions`` option in the ``[buildout]``
section, the version will be cleared, so the develop egg will actually be
used. You can control the list of develop eggs explicitely with the
``activate`` and ``deactivate`` commands of ``bin/develop``.

Troubleshooting
===============

Dirty SVN
---------

You get an error like::

  ERROR: Can't switch package 'foo' from 'https://example.com/svn/foo/trunk/', because it's dirty.

If you have not modified the package files under src/foo, then you can check
what's going on with `status -v`. One common cause is a `*.egg-info` folder
which gets generated every time you run buildout and this shows up as an
untracked item in svn status.

You should add .egg-info to your global Subversion ignores in
`~/.subversion/config`, like this::
  
  global-ignores = *.o *.lo *.la *.al .libs *.so *.so.[0-9]* *.a *.pyc *.pyo *.rej *~ #*# .#* .*.swp .DS_Store *.egg-info

HTTPS certificates
------------------

The best way to handle https certificates at the moment, is to accept them
permanently when checking out the source manually.

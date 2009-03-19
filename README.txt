Introduction
============


``mr.developer`` is a ``zc.buildout`` extension which makes it easier to work with
buildouts containing lots of packages of which you only want to develop some.
The basic idea for this comes from Wichert Akkerman's ``plonenext`` effort.


Usage
-----

You add ``mr.developer`` to the ``extensions`` option of your ``[buildout]``
section. Then you can add the following options to your ``[buildout]``
section:

  ``sources-dir``
    This specifies where your development packages should be placed. Defaults
    to ``src``.

  ``sources-svn``
    This specifies a section which list the subversion repository URLs of
    your packages.

The following is an example of how your ``buildout.cfg`` may look like::

  [buildout]
  ...
  extensions = mr.developer
  sources-svn = sources-svn

  [sources-svn]
  my.package = http://example.com/svn/my.package/trunk

When you run buildout, you will get a script at ``bin/checkout`` in your
buildout directory. With that script you can checkout the source from the
specified repository, without the need to know where the repository is
located.

Now if you run buildout again, the package is automatically marked as an
develop egg and, if it's listed in the section specified by the ``versions``
option in the ``[buildout]`` section, the version will be set to an empty
string, so the develop egg will actually be used.


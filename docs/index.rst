======
Fabric
======

Work in progress!
=================

This website and its documentation are still being written and updated during
Fabric 0.9's alpha and beta periods. We are providing them to you now because
any documentation is better than no documentation, but please keep in mind that
many things here are subject to change or may need fleshing out.


About
=====

.. include:: ../README


Download/Installation
=====================

Latest stable version
---------------------

The most recent stable version of Fabric is |release|. The recommended
installation method is to use ``easy_install`` or ``pip``; or you may download
TGZ or ZIP source archives from a couple of official locations.  Detailed
instructions and links may be found on the :doc:`installation` page.

Development version
-------------------

We recommend using the stable version of Fabric; releases are made often to
prevent any large gaps in functionality between the latest stable release and
the development version.

However, if you want to live on the edge, you can pull down the latest source
code from our Git repository, or fork us on Github. Please see the
:doc:`development` page for details.


Getting help
============

Mailing list
------------

The best way to get help with using Fabric is via the `fab-user mailing list
<http://lists.nongnu.org/mailman/listinfo/fab-user>`_ (currently hosted at
``nongnu.org``.) The Fabric developers do their best to reply promptly, and the
list contains an active community of other Fabric users and contributors as
well.

Bugs
----

Fabric has no official bug tracker at this point in time, but getting one is
very high on our priority list, so keep an eye out! For the time being, please
submit bug reports via the mailing list (see above) or e-mail the development
team directly at ``developers [at] fabfile [dot] org``.

.. note:: Using the mailing list is preferred -- it increases your chances of
    getting prompt feedback, and also allows other users to confirm your bug
    report and thus give it a higher priority.

Wiki
----

There is an official Fabric wiki reachable at `wiki.fabfile.org
<http://wiki.fabfile.org>`_, although as of this writing its usage patterns are
still being worked out. There is a `TodoList page
<http://wiki.fabfile.org/TodoList>`_ which may also be used to submit bug
reports, as an alternative to sending email.


Documentation
=============

.. toctree::
    :maxdepth: 2

    installation
    development
    usage
    compatibility


API
===

.. toctree::
    :maxdepth: 2
    :glob:

    api/*


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

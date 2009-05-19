"""
Fabric's own fabfile.
"""

from __future__ import with_statement

import inspect

from fabric.api import *
from fabric.contrib.project import rsync_project
import fabric.version

import os.path



def test():
    """
    Run all unit tests
    """
    # Need show_stderr=True because the interesting output of nosetests is
    # actually sent to stderr, not stdout.
    print(local('nosetests -sv', capture=False))


def build_docs():
    """
    Generate the Sphinx documentation.
    """
    local('cd docs && make clean html', capture=False)


@hosts('jforcier@fabfile.org')
def push_docs():
    """
    Build and push the Sphinx docs to docs.fabfile.org
    """
    build_docs()
    rsync_project('/var/www/docs.fabfile/', 'docs/_build/html/', delete=True)


def tag():
    """
    Tag a new release of the software
    """
    with settings(warn_only=True):
        # Get current version string
        version = fabric.version.get_version()
        # Does that tag already exist?
        exists = local("git tag | grep %s" % version)
        if exists:
            # If no work has been done since, what's the point?
            if not local("git log %s.." % version):
                abort("No work done since last tag!")
            # If work *has* been done since, we need to make a new tag. To the
            # editor for version update!
            raw_input("Work has been done since last tag, version update is needed. Hit Enter to load version info in your editor: ")
            local("$EDITOR fabric/version.py", capture=False)
            # Reload version module to get new version
            reload(fabric.version)
        # If the tag doesn't exist, the user has already updated version info
        # and we can just move on.
        else:
            print("Version has already been updated, no need to edit...")
        # Get version strings
        verbose_version = fabric.version.get_version(verbose=True)
        short_version = fabric.version.get_version()
        # Commit the version update
        local("git add fabric/version.py")
        local("git commit -m \"Cut %s\"" % verbose_version)
        # And tag it
        local("git tag -m \"Fabric %s\" %s" % (
            verbose_version,
            short_version
        ))

"""
Context managers for use with the ``with`` statement.
"""

from contextlib import contextmanager
from state import env
from utils import indent,args2str
import sys

@contextmanager
def setenv(**kwargs):
    """
    Context manager which temporarily sets a variable list of environment variables.
    
    `setenv` will preserve and then reinstate the previous value of
    the keyword arguments provided in the context_manager, so it will 
    not affect the global state of those variables, outside of its nested scope.

    The use of the below example will result in debug statments being printed out
    regardless of the command line usage::
    
        def my_task():
            with setenv(debug=True):
                run('ls')

    The use of the below example will result in quiet mode being disabled in the 
    scope of the with statement::
    
        def my_task():
            with setenv(quiet=False):
                run('ls')

    The use of the below example will result in the run statement getting executed 
    using the cmd.exe shell for windows::
    
        def my_task():
            with setenv(shell='cmd.exe /c', debug=True):
                run('dir')
    
    .. note:: `setenv` must always be called with parentheses (``with
        setenv():``) as it is actually a simple context manager factory,
        and not a context manager itself.

    .. note:: Remember that on Python 2.5, you will need to start your fabfile
        with ``from __future__ import with_statement`` in order to make use of
        this feature.

    """
    global env
    _pre_env = env
    _pre_env_mod = {}
    [_pre_env_mod.setdefault(k,env.setdefault(k,None)) for k in kwargs] 
    if env.debug:
        print >> sys.stdout, indent("settings environment variables %s" % args2str(**kwargs))
    env.update(kwargs)
    
    yield

    env = _pre_env
    if env.debug:
        print >> sys.stdout, indent("resettings environment variables %s" % args2str(**_pre_env_mod))
    

@contextmanager
def warnings_only():
    """
    Context manager which temporarily sets ``env.abort_on_failure`` to False.

    `warnings_only` will preserve and then reinstate the previous value of
    ``env.abort_on_failure``, so it will not affect the global state of that
    variable, outside of its nested scope.

    Use of this context manager is recommended over manually toggling
    ``env.abort_on_failure``.

    The below regular, unwrapped call to `run` will result in an immediate halt
    of execution (assuming the user hasn't globally changed the value of
    ``env.abort_on_failure``)::

        def my_task():
            run('/not/gonna/happen')
    
    However, with the use of `warnings_only`, the same call is guaranteed to
    warn only, and will never halt execution of the program:: 

        def my_task():
            with warnings_only():
                run('/not/gonna/happen')
                
    .. note:: `warnings_only` must always be called with parentheses (``with
        warnings_only():``) as it is actually a simple context manager factory,
        and not a context manager itself.

    .. note:: Remember that on Python 2.5, you will need to start your fabfile
        with ``from __future__ import with_statement`` in order to make use of
        this feature.

    """
    previous = env.abort_on_failure
    env.abort_on_failure = False
    yield
    env.abort_on_failure = previous

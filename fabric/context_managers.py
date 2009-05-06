"""
Context managers for use with the ``with`` statement.
"""

from contextlib import contextmanager

from state import env

@contextmanager
def shell( interpreter ):
    """
    Context manager which temporarily sets ``env.shell`` to the value
    supplied by the ``interpreter`` argument.
    
    Example uses:
        with shell('python -c'):
            print run('import socket;print "hello from python on %s" % socket.gethostname();')
        with shell('perl -e'):
            print run('use Sys::Hostname;print "hello from perl on ".hostname;');

    .. note:: `shell` must always be called with parentheses (``with
        shell(interpreter):``) as it is actually a simple context manager factory,
        and not a context manager itself.

    .. note:: Remember that on Python 2.5, you will need to start your fabfile
        with ``from __future__ import with_statement`` in order to make use of
        this feature.
    """
    _prev_interpreter = env.shell
    env.shell = interpreter 
    
    # yield now so that commands in this context run with the supplied arugments.
    yield 

    env.shell = _prev_interpreter
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

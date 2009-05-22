"""
Internal subroutines for e.g. aborting execution with an error message,
or performing indenting on multiline output.
"""

import os
import sys
import textwrap
from string import Template


def abort(msg):
    """
    Abort execution, printing given message and exiting with error status.
    When not invoked as the ``fab`` command line tool, raise an exception
    instead.
    """
    from state import output
    if output.aborts:
        print >>sys.stderr, "\nFatal error: " + str(msg)
        print >>sys.stderr, "\nAborting."
    sys.exit(1)

    
def warn(msg):
    """
    Print warning message, but do not abort execution.
    """
    from state import output
    if output.warnings:
        print >>sys.stderr, "\nWarning: %s\n" % msg


def indent(text, spaces=4, strip=False):
    """
    Returns text indented by the given number of spaces.

    If text is not a string, it is assumed to be a list of lines and will be
    joined by ``\\n`` prior to indenting.

    When ``strip`` is ``True``, a minimum amount of whitespace is removed from
    the left-hand side of the given string (so that relative indents are
    preserved, but otherwise things are left-stripped). This allows you to
    effectively "normalize" any previous indentation for some inputs.
    """
    # Normalize list of strings into a string for dedenting. "list" here means
    # "not a string" meaning "doesn't have splitlines". Meh.
    if not hasattr(text, 'splitlines'):
        text = '\n'.join(text)
    # Dedent if requested
    if strip:
        text = textwrap.dedent(text)
    prefix = ' ' * spaces
    output = '\n'.join(prefix + line for line in text.splitlines())
    # Strip out empty lines before/aft
    output = output.strip()
    # Reintroduce first indent (which just got stripped out)
    output = prefix + output
    return output

def args2str(*args,**kwargs):
    _listtostr = lambda args:",".join(["'%s'"%k for k in args]) if args else None
    _dicttostr = lambda kwargs:",".join(["%s='%s'"%(k,kwargs[k]) for k in kwargs]) \
                 if kwargs else None
    str = ""
    l,d=_listtostr(args),_dicttostr(kwargs)
    
    return l+","+d if (d and l) else d or l




def eval_str_template ( s, lookups = []):
    """
    return a string evaluated from one that that is in template style, 
    with the keywords defined in the dictionaries listed in `lookups`.
    
    Example::
        reduced = eval_str_template("${user} is the user", \
                                    lookups = [{"user":"fabuser"}])
    .. note::
        the function defaults to `state.env` as the lookup dictionary,
        however `lookup` can be a list of dictionaries which will all 
        be used for the template resolution (if multiple
        dictionaries are passed in - there is no guarantee towards which
        key will be used in the substitution if multiple dictionaries
        contain the same key).
        
    """ 
    def eval_str_template_sub( s, lookups = [] ):
        _dict = {}
        [_dict.update(k) for k in lookups]
        return Template(s).safe_substitute( _dict ) if _dict else s

    from state import env
    return eval_str_template_sub( s, lookups = [env] if not lookups \
                                  else lookups )


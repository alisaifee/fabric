"""
Functions to be used in fabfiles and other non-core code, such as run()/sudo().
"""

from __future__ import with_statement

from glob import glob
import os
import os.path
import re
import stat
import subprocess

from context_managers import warnings_only
from contextlib import closing
from network import output_thread, needs_host
from state import env, connections
from utils import abort, indent, warn


def _handle_failure(message, exception=None):
    """
    Call `abort` or `warn` with the given message.

    The value of ``env.abort_on_failure`` determines which method is called.

    If ``exception`` is given, it is inspected to get a string message, which
    is printed alongside the user-generated ``message``.
    """
    func = env.abort_on_failure and abort or warn
    if exception is not None:
        # Figure out how to get a string out of the exception; EnvironmentError
        # subclasses, for example, "are" integers and .strerror is the string.
        # Others "are" strings themselves. May have to expand this further for
        # other error types.
        if hasattr(exception, 'strerror'):
            underlying_msg = exception.strerror
        else:
            underlying_msg = exception
        func("%s\n\nUnderlying exception message:\n%s" % (
            message,
            indent(underlying_msg)
        ))
    else:
        func(message)


class _AttributeString(str):
    """
    Simple string subclass to allow arbitrary attribute access.
    """
    pass



# Can't wait till Python versions supporting 'def func(*args, foo=bar)' become
# widespread :(
def require(*keys, **kwargs):
    """
    Check for given keys in the shared environment dict and abort if not found.

    Positional arguments should be strings signifying what env vars should be
    checked for. If any of the given arguments do not exist, Fabric will abort
    execution and print the names of the missing keys.

    The optional keyword argument ``used_for`` may be a string, which will be
    printed in the error output to inform users why this requirement is in
    place. ``used_for`` is printed as part of a string similar to::
    
        "Th(is|ese) variable(s) (are|is) used for %s"
        
    so format it appropriately.

    The optional keyword argument ``provided_by`` may be a list of functions or
    function names which the user should be able to execute in order to set the
    key or keys; it will be included in the error output if requirements are
    not met.

    Note: it is assumed that the keyword arguments apply to all given keys as a
    group. If you feel the need to specify more than one ``used_for``, for
    example, you should break your logic into multiple calls to ``require()``.
    """
    # If all keys exist, we're good, so keep going.
    missing_keys = filter(lambda x: x not in env, keys)
    if not missing_keys:
        return
    # Pluralization
    if len(missing_keys) > 1:
        variable = "variables were"
        used = "These variables are"
    else:
        variable = "variable was"
        used = "This variable is"
    # Regardless of kwargs, print what was missing. (Be graceful if used outside
    # of a command.)
    if 'command' in env:
        prefix = "The command '%s' failed because the " % env.command
    else:
        prefix = "The "
    msg = "%sfollowing required environment %s not defined:\n%s" % (
        prefix, variable, indent(missing_keys)
    )
    # Print used_for if given
    if 'used_for' in kwargs:
        msg += "\n\n%s used for %s" % (used, kwargs['used_for'])
    # And print provided_by if given
    if 'provided_by' in kwargs:
        funcs = kwargs['provided_by']
        # Pluralize this too
        if len(funcs) > 1:
            command = "one of the following commands"
        else:
            command = "the following command"
        to_s = lambda obj: getattr(obj, '__name__', str(obj))
        provided_by = [to_s(obj) for obj in funcs]
        msg += "\n\nTry running %s prior to this one, to fix the problem:\n%s"\
            % (command, indent(provided_by))
    abort(msg)


def prompt(name, text, default=None, validate=None):
    """
    Prompt user with ``text`` asking for the value of ``name`` env variable.

    If ``name`` is already present in the environment dict, it will be
    overwritten, and a warning printed to the user alerting them to this fact.

    If ``default`` is given, it is displayed in square brackets and used if the
    user enters nothing (i.e. presses Enter without entering any text).

    The optional keyword argument ``validate`` may be a callable or a string:
    
    * If a callable, it is called with the user's input, and should return the
      value to be stored on success. On failure, it should raise an exception
      with an exception message, which will be printed to the user.
    * If a string, the value passed to ``validate`` is used as a regular
      expression. It is thus recommended to use raw strings in this case. Note
      that the regular expression, if it is not fully matching (bounded by
      ``^`` and ``$``) it will be made so. In other words, the input must fully
      match the regex.

    Either way, `prompt` will re-prompt until validation passes (or the user
    hits ``Ctrl-C``).

    Finally, note that `prompt` will return the obtained value as well as
    setting it in the environment dict.
    
    Examples::
    
        # Simplest form:
        prompt('environment', 'Please specify target environment')
        
        # With default:
        prompt('dish', 'Specify favorite dish', default='spam & eggs')
        
        # With validation, i.e. require integer input:
        prompt('nice', 'Please specify process nice level', validate=int)
        
        # With validation against a regular expression:
        prompt('release', 'Please supply a release name',
                validate=r'^\w+-\d+(\.\d+)?$')
    
    """
    # Get default value or None
    previous_value = env.get(name)
    # Set up default display
    default_str = ""
    if default:
        default_str = " [%s] " % str(default).strip()
    # Construct full prompt string
    prompt_str = text.strip() + default_str
    # Loop until we get valid input or KeyboardInterrupt
    value = None
    while not value:
        # Get input
        value = raw_input(prompt_str) or default
        # Handle validation
        if validate:
            # Callable
            if callable(validate):
                # Callable validate() must raise an exception if validation
                # fails.
                try:
                    value = validate(value)
                except Exception, e:
                    value = None
                    print("Validation failed for the following reason:")
                    print(indent(e.message) + "\n")
            # String / regex must match and will be empty if validation fails.
            else:
                # Need to transform regex into full-matching one if it's not.
                if not validate.startswith('^'):
                    validate = r'^' + validate
                if not validate.endswith('$'):
                    validate += r'$'
                result = re.findall(validate, value)
                if not result:
                    print("Regular expression validation failed: '%s' does not match '%s'\n" % (value, validate))
                    value = None
        # Implicit continuation of loop if raw_input returned empty string, and
        # default was also unspecified. In other words, empty values are not OK!
    # At this point, value must be non-empty, so update env
    env[name] = value
    # Print warning if we overwrote some other value
    if previous_value is not None and previous_value != value:
        warn("overwrote previous value of '%s'; used to be '%s', is now '%s'." % (name, previous_value, value))
    # And return the value, too, just in case someone finds that useful.
    return value


@needs_host
def put(local_path, remote_path, mode=None):
    """
    Upload one or more files to a remote host.
    
    ``local_path`` may be a relative or absolute local file path, and may
    contain shell-style wildcards, as understood by the Python ``glob`` module.
    Tilde expansion (as implemented by ``os.path.expanduser``) is also
    performed.

    ``remote_path`` may also be a relative or absolute location, but applied to
    the remote host. Relative paths are relative to the remote user's home
    directory.

    Fabric will attempt to discern the remote user's home directory in order to
    perform tilde expansion for ``remote_path``, so you may specify remote paths
    such as ``~/.ssh/``.

    By default, the file mode is preserved by put when uploading. But you can
    also set the mode explicitly by specifying an additional ``mode`` keyword
    argument which sets the numeric mode of the remote file. See the
    ``os.chmod`` documentation or ``man chmod`` for the format of this argument.
    
    Examples::
    
        put('bin/project.zip', '/tmp/project.zip')
        put('*.py', 'cgi-bin/')
        put('index.html', 'index.html', mode=0755)
    
    """
    ftp = connections[env.host_string].open_sftp()
    with closing(ftp) as  ftp:
        # Do jury-rigged tilde expansion, but only if we can do it nicely.
        # TODO: tie into global output controls -- as a user! (i.e. hide all output
        # from this chunk below if possible)
        with warnings_only():
            cwd = run('pwd')
        if not cwd.failed:
            remote_path = remote_path.replace('~', cwd)
    
        try:
            rmode = ftp.lstat(remote_path).st_mode
        except:
            # sadly, I see no better way of doing this
            rmode = None
    
        # Expand local tildes and get globs
        globs = glob(os.path.expanduser(local_path))
    
        # Deal with bad local_path
        if not globs:
            raise ValueError, "'%s' is not a valid local path or glob." % local_path
    
        for lpath in globs:
            # first, figure out the real, absolute, remote path
            _remote_path = remote_path
            if rmode is not None and stat.S_ISDIR(rmode):
                _remote_path = os.path.join(remote_path, os.path.basename(lpath))
            
            # TODO: tie this into global output controls
            print("[%s] put: %s -> %s" % (env.host_string, lpath, _remote_path))
            # Try to catch raised exceptions (which is the only way to tell if
            # this operation had problems; there's no return code) during upload
            try:
                # Actually do the upload
                rattrs = ftp.put(lpath, _remote_path)
                # and finally set the file mode
                lmode = mode or os.stat(lpath).st_mode
                if lmode != rattrs.st_mode:
                    ftp.chmod(_remote_path, lmode)
            except Exception, e:
                msg = "put() encountered an exception while uploading '%s'"
                _handle_failure(message=msg % lpath, exception=e)


@needs_host
def get(remote_path, local_path):
    """
    Download a file from a remote host.
    
    The ``remote_path`` parameter is the relative or absolute path to the files
    to download from the remote hosts. In order to play well with multiple-host
    invocation, the local filename will be suffixed with the current hostname.
     
    Example::
   
        @hosts('host1', 'host2')
        def my_download_task():
            get('/var/log/server.log', 'server.log')
    
    The above code will produce two files on your local system, called
    ``server.log.host1`` and ``server.log.host2`` respectively.
    """
    ftp = connections[env.host_string].open_sftp()
    local_path = local_path + '.' + env.host
    remote_path = remote_path
    # TODO: tie this into global output controls
    print("[%s] download: %s <- %s" % (env.host_string, local_path, remote_path))
    # Handle any raised exceptions (no return code to inspect here)
    try:
        ftp.get(remote_path, local_path)
    except Exception, e:
        msg = "get() encountered an exception while downloading '%s'" 
        _handle_failure(message=msg % remote_path, exception=e)
    finally:
        ftp.close()


@needs_host
def run(command, shell=True, interpreter=env.shell):
    """
    Run a shell command on a remote host.

    If ``shell`` is True (the default), ``run()`` will execute the given
    command string via a shell interpreter, the value of which may be
    controlled by setting ``env.shell`` (defaulting to something similar to
    ``/bin/bash -l -c "<command>"``.) Any double-quote (``"``) characters in
    ``command`` will be automatically escaped when ``shell`` is True.
    
    If ``interpreter`` is specified with the call, the default shell interpreter
    will be overridden when executing the command string. This can be useful for
    calling commands with different interpreters in the same fabfile.
    Example use: 
    1) run(command,interpreter='cmd.exe /c') for windows
    2) run('import os;print os.environ;',interpreter='python -c') for executing a python string.

    `run` will return the result of the remote program's stdout as a
    single (likely multiline) string. This string will exhibit a ``failed``
    boolean attribute specifying whether the command failed or succeeded, and
    will also include the return code as the ``return_code`` attribute.

    Examples::
    
        run("ls /var/www/")
        run("ls /home/myuser", shell=False)
        output = run('ls /var/www/site1')
    
    """
    real_command = command
    if shell:
        real_command = '%s "%s"' % (interpreter, command.replace('"', '\\"'))
    # TODO: possibly put back in previously undocumented 'confirm_proceed'
    # functionality, i.e. users may set an option to be prompted before each
    # execution. Pretty sure this should be a global option applying to ALL
    # remote operations! And, of course -- documented.
    # TODO: tie this into global output controls
    # TODO: also, for this and sudo(), allow output of real_command too
    # (possibly as part of a 'debug' flag?)
    print("[%s] run: %s" % (env.host_string, command))
    channel = connections[env.host_string]._transport.open_session()
    channel.exec_command(real_command)
    capture = []

    # TODO: tie into global output controls
    out_thread = output_thread("[%s] out" % env.host_string, channel, capture=capture)
    err_thread = output_thread("[%s] err" % env.host_string, channel, stderr=True)
    
    # Close when done
    status = channel.recv_exit_status()
    channel.close()
    
    # Wait for threads to exit so we aren't left with stale threads
    out_thread.join()
    err_thread.join()

    # Assemble output string
    output = _AttributeString("".join(capture).strip())

    # Error handling
    output.failed = False
    if status != 0:
        output.failed = True
        msg = "run() encountered an error (return code %s) while executing '%s'" % (status, command)
        _handle_failure(message=msg)

    # Attach return code to output string so users who have set things to warn
    # only, can inspect the error code.
    output.return_code = status
    return output


@needs_host
def sudo(command, shell=True, user=None):
    """
    Run a shell command on a remote host, with superuser privileges.
    
    As with ``run()``, ``sudo()`` executes within a shell command defaulting to
    the value of ``env.shell``, although it goes one step further and wraps the
    command with ``sudo`` as well. Also similar to ``run()``, the shell

    You may specify a ``user`` keyword argument, which is passed to ``sudo``
    and allows you to run as some user other than root (which is the default).
    On most systems, the ``sudo`` program can take a string username or an
    integer userid (uid); ``user`` may likewise be a string or an int.
       
    `sudo` will return the result of the remote program's stdout as a
    single (likely multiline) string. This string will exhibit a ``failed``
    boolean attribute specifying whether the command failed or succeeded, and
    will also include the return code as the ``return_code`` attribute.

    Examples::
    
        sudo("~/install_script.py")
        sudo("mkdir /var/www/new_docroot", user="www-data")
        sudo("ls /home/jdoe", user=1001)
        result = sudo("ls /tmp/")
    
    """
    # Construct sudo command, with user if necessary
    if user is not None:
        if str(user).isint():
            user = "#%s" % user
        sudo_prefix = "sudo -S -p '%%s' -u \"%s\" " % user
    else:
        sudo_prefix = "sudo -S -p '%s' "
    # Put in explicit sudo prompt string (so we know what to look for when
    # detecting prompts)
    sudo_prefix = sudo_prefix % env.sudo_prompt
    # Without using a shell, we just do 'sudo -u blah my_command'
    if (not env.use_shell) or (not shell):
        real_command = "%s %s" % (sudo_prefix, command.replace('"', r'\"'))
    # With a shell, we do 'sudo -u blah /bin/bash -l -c "my_command"'
    else:
        real_command = '%s %s "%s"' % (sudo_prefix, env.shell,
            command.replace('"', r'\"'))
    # TODO: tie this into global output controls; both in terms of showing the
    # shell itself, AND showing the sudo prefix. Not 100% sure it's worth being
    # so granular as to allow one on and one off, but think about it.
    # TODO: handle confirm_proceed behavior, as in run()
    print("[%s] sudo: %s" % (env.host_string, command))
    channel = connections[env.host_string]._transport.open_session()
    channel.exec_command(real_command)
    capture = []

    out_thread = output_thread("[%s] out" % env.host_string, channel, capture=capture)
    err_thread = output_thread("[%s] err" % env.host_string, channel, stderr=True)

    # Close channel when done
    status = channel.recv_exit_status()
    channel.close()

    # Wait for threads to exit before returning (otherwise we will occasionally
    # end up returning before the threads have fully wrapped up)
    out_thread.join()
    err_thread.join()

    # Assemble stdout string
    output = _AttributeString("".join(capture).strip())

    # Error handling
    output.failed = False
    if status != 0:
        output.failed = True
        msg = "sudo() encountered an error (return code %s) while executing '%s'" % (status, command)
        _handle_failure(message=msg)

    # Attach return code for convenience
    output.return_code = status
    return output


def local(command, show_stderr=True, capture=True):
    """
    Run a command on the local system.

    `local` is simply a convenience wrapper around the use of the builtin
    Python ``subprocess`` module with ``shell=True`` activated. If you need to
    do anything special, consider using the ``subprocess`` module directly.

    `local` will return the contents of the command's stdout as a string.
    Standard error will be printed to your terminal by default, but you may
    specify ``show_stderr=False`` in order to discard stderr.

    If you need full interactivity with the command being run (and are willing
    to accept the loss of captured stdout) you may specify ``capture=False`` so
    that the subprocess' stdout and stderr pipes are connected to your terminal
    instead of captured and read by Fabric.
    """
    # TODO: tie this into global output controls
    print("[localhost] run: " + command)
    PIPE = subprocess.PIPE
    # User wants to interact with whatever was called, instead of capturing
    if not capture:
        p = subprocess.Popen([command], shell=True)
    # User wants stdout captured but wants stderr printed to terminal instead
    # of discarded
    elif show_stderr:
        p = subprocess.Popen([command], shell=True, stdout=PIPE)
    # Capture both and discard stderr
    else:
        p = subprocess.Popen([command], shell=True, stdout=PIPE, stderr=PIPE)
    (stdout, stderr) = p.communicate()
    # Handle error condition
    if p.returncode != 0:
        msg = "local() encountered an error (return code %s) while executing '%s'" % (p.returncode, command)
        _handle_failure(message=msg)
    return stdout

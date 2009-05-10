"""
Module for providing shutil / os type methods that work on remote systems.
(yashutil = YetAnotherShellUtil)
"""
from fabric.state import env, connections
from fabric.operations import get, put
from fabric.network import needs_host
from fabric.decorators import fabricop
from fabric.context_managers import setenv
from contextlib import closing
import stat, os, shutil, sys

# necessary to keep the lifetime of the SFTPClient object in sync with the 
# SFTPFile object. Otherwise passing the object around will require manual
# management of the sftp connection.
class _RemoteFile():
    def __init__(self, con , name , mode , buffering):
        self._con = con
        self._inst = con.open(name, mode, buffering)
    def __getattr__(self, attr):
        return self._inst.__getattribute__(attr)

def _unixifypath(path):
    return path.replace("\\", "/")

def _normalizepath(path):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return path.replace('~', ftp.normalize('.'))

def _remote_copy_tree (src , dst, ignore , is_src_local):
    with setenv(quiet=True):
        names = os.listdir(src) if is_src_local else r_listdir(_unixifypath(src))
     
        if ignore is not None:
            ignored_names = ignore(src, names)
        else:
            ignored_names = set()
        if is_src_local:
            r_makedirs(_unixifypath(dst))
        else:
            os.makedirs(_unixifypath(dst) + "/")
        errors = []
        for name in names:
            if name in ignored_names:
                continue
            srcname = _unixifypath(os.path.join(src, name))
            dstname = _unixifypath(os.path.join(dst, name))
            try:
                if os.path.isdir(srcname) if is_src_local else r_isdir(_unixifypath(srcname)):
                    _remote_copy_tree(srcname, dstname, ignore, is_src_local)
                else:
                    put(srcname, _unixifypath(dstname)) if is_src_local else get(srcname, _unixifypath(dstname))
                # XXX What about devices, sockets etc.?
            except (IOError, os.error), why:
                errors.append((srcname, dstname, str(why)))
            # catch the Error from the recursive copytree so that we can
            # continue with other files
            except shutil.Error, err:
                errors.extend(err.args[0])
        if errors:
            raise Exception, errors 
@needs_host
@fabricop
def r_rmtree(path, ignore_errors=False, onerror=None):
    """Recursively delete a directory tree.

    If ignore_errors is set, errors are ignored; otherwise, if onerror
    is set, it is called to handle the error with arguments (func,
    path, exc_info) where func is os.listdir, os.remove, or os.rmdir;
    path is the argument to that function that caused it to fail; and
    exc_info is a tuple returned by sys.exc_info().  If ignore_errors
    is false and onerror is None, an exception is raised.

    """
    with setenv(quiet=True):
        if ignore_errors:
            def onerror(*args):
                pass
        elif onerror is None:
            def onerror(*args):
                raise
        try:
            if r_islink(_unixifypath(path)):
                # symlinks to directories are forbidden, see bug #1669
                raise OSError("Cannot call rmtree on a symbolic link")
        except OSError:
            onerror(os.path.islink, _unixifypath(path), sys.exc_info())
            # can't continue even if onerror hook returns
            return
        names = []
        try:
            names = r_listdir(_unixifypath(path).replace("~", r_getcwd()))
        except os.error, err:
            onerror(r_listdir, _unixifypath(path), sys.exc_info())
        for name in names:
            fullname = _unixifypath(os.path.join(_normalizepath(_unixifypath(path)), name))
            try:
                mode = r_stat(fullname).st_mode
            except os.error:
                mode = 0
            if stat.S_ISDIR(mode):
                r_rmtree(fullname, ignore_errors, onerror)
            else:
                try:
                    r_remove(fullname)
                except os.error, err:
                    onerror(os.remove, fullname, sys.exc_info())
        try:
            r_rmdir(_normalizepath(_unixifypath(path)))
        except os.error:
            onerror(os.rmdir, path, sys.exc_info())
@needs_host
@fabricop
def r_makedirs(name, mode=0777):
    """makedirs(path [, mode=0777])

    Super-mkdir; create a leaf directory and all intermediate ones.
    Works like mkdir, except that any intermediate path segment (not
    just the rightmost) will be created if it does not exist.  This is
    recursive.

    """
    with setenv(quiet=True):
        _name = _normalizepath(_unixifypath (name))
        head, tail = os.path.split(_name)
        if not tail:
            head, tail = os.path.split(head)
        if head and tail and not r_exists(head):
            try:
                r_makedirs(head, mode)
            except OSError, e:
                # be happy if someone already created the path
                if e.errno != errno.EEXIST:
                    raise
            if tail == os.curdir:           # xxx/newdir/. exists if xxx/newdir exists
                return
        r_mkdir(_name, mode)


@needs_host
@fabricop
def r_open(name, mode='r', buffering=False):
    con = connections[env.host_string].open_sftp()
    return _RemoteFile (con, _normalizepath(_unixifypath(name)), mode, buffering)

@needs_host
@fabricop
def put_copytree (src, dst , ignore=None):
    return _remote_copy_tree (src, _normalizepath(_unixifypath(dst)), ignore, True)

@fabricop
@needs_host
def get_copytree (src, dst , ignore=None):
    return _remote_copy_tree (_normalizepath(_unixifypath(src)), dst, ignore, False)

@fabricop
@needs_host
def r_rmdir(path):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.rmdir(path.replace("~", r_getcwd()))
@fabricop
@needs_host
def r_stat (path):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.stat(path.replace("~", r_getcwd()))
@fabricop
@needs_host
def r_isfile (path):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            st = ftp.stat(path.replace("~", r_getcwd()))
        except Exception, e:
            return False
        return stat.S_ISREG(st.st_mode)
@needs_host
@fabricop
def r_isdir (path):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            st = ftp.stat(path.replace("~", r_getcwd()))
        except Exception, e:
            return False
        return stat.S_ISDIR(st.st_mode)
@needs_host
@fabricop
def r_islink(path):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            st = ftp.stat(path.replace("~", r_getcwd()))
        except Exception, e:
            return False
        return stat.S_ISLNK(st.st_mode)
@needs_host
@fabricop
def r_mkdir (path , mode=0777):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            return ftp.mkdir(path.replace("~", r_getcwd()) , mode)
        except IOError, e:
            return False
@needs_host
@fabricop
def r_rename(old, new):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.rename (old.replace("~", r_getcwd()), new.replace("~", r_getcwd()))

@needs_host
@fabricop
def r_listdir(path):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.listdir(path.replace("~", r_getcwd()))
@needs_host
@fabricop
def r_remove(path):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.remove(path.replace("~", r_getcwd()))

@needs_host
@fabricop
def r_exists(path):
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            ftp.stat(path.replace("~", r_getcwd()))
        except:
            return False
        return True
    
@needs_host
@fabricop
def r_getcwd():
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.normalize('.')
 

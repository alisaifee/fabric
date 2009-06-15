"""
Module for providing shutil / os type methods that work on remote systems.

All the operations provided in this namespace are decorated by the 
:func:`fabricop<fabric.decorators.fabricop>` & :func:`needs_host<fabric.network.needs_host>` 
decorators.

"""

from __future__ import with_statement
from fabric.decorators import fabricop
from fabric.network import needs_host
from fabric.state import env, connections,win32
from fabric.operations import get, put, run
from fabric.context_managers import hide
from contextlib import closing
import os
from stat import S_ISREG,S_ISDIR,S_ISLNK
import stat, shutil, sys

class _RemoteFile:
    """
    Delegate class for a remote file object. 
    
    Necessary to keep the lifetime of the SFTPClient object in sync with the 
    SFTPFile object - otherwise, using SFTPFile object directly will require 
    manual management of the sftp connection.
    
    .. note::
        This class is *not* meant to be used directly. It is simply a helper 
        class for the :func:``r_open`` method.
    
    """
    def __init__(self, connection , name , mode , buffering):
        """
        Simply stores the ``connection`` in the ``self._connection`` private
        member and saves an SFTPFile object (created with the remaining args)
        to ``self._inst``.
        """
        self._con = connection
        self._inst = connection.open(name, mode, buffering)
    def __del__(self):
        """
        closes the SFTPClient object.
        """
        self._con.close()
    def __getattr__(self, attr):
        """
        Delegates all method calls to `self._inst` member.
        """
        return self._inst.__getattribute__(attr)

def _unixpath(path):
    """
    Replace backslashes with forward slashes
    
    For win32 systems only - ensures forward slashes after performing
    `os.path` operations (which by default return back-slashes.
    """
    
    _drive_less = os.path.splitdrive( path )[1]
    _forward_slashed  = _drive_less .replace ( "\\", "/" )
    return _forward_slashed if win32 else path

def _r_normalizepath(path):
    """
    Replace '~' with the current directory on the target system.
    """
    return path.replace('~', r_getcwd() )

def _remote_copy_tree (src , dst, ignore , is_src_local , is_dst_local ):
    """
    Private method to perform a copytree operation 
    
    The implementation of this method is moreover a rip-off of shutils::
    copytree method.
    
    ..note::
        `src_dst_mode` can take the values 0,1,2 where 0: dst is local, 1:
        src is local, and 2 both src & dst are remote.
    
    """
    with hide('running'):
        names = os.listdir(src) if is_src_local \
                else r_listdir(_unixpath(src))
        if ignore is not None:
            ignored_names = ignore(src, names)
        else:
            ignored_names = set()
        if not is_dst_local:
            r_makedirs(_unixpath ( dst) )
        else:
            os.makedirs(_unixpath(dst) )
        errors = []
        for name in names:
            if name in ignored_names:
                continue
            srcname = os.path.join(src, name) 
            dstname = os.path.join(dst, name)
            try:
                if (os.path.isdir(srcname) if is_src_local \
                        else r_isdir(_unixpath(srcname))):
                    _remote_copy_tree(srcname, dstname, ignore, is_src_local,is_dst_local)
                else:
                    if not is_src_local and not is_dst_local:
                        r_copy2(srcname, dstname)
                    else:
                        put(srcname, _unixpath(dstname)) if is_src_local \
                            else get(srcname, _unixpath(dstname))
                # XXX What about devices, sockets etc.?
            except (IOError, os.error), why:
                errors.append((srcname, dstname, str(why)))
            # catch the Error from the recursive copytree so that we can
            # continue with other files
            except shutil.Error, err:
                errors.extend(err.args[0])
        if errors:
            raise Exception, errors 

def allow_patterns(*patterns):
    """Function that can be used as a reverse copytree() ignore parameter.

 
    Patterns is a sequence of glob-style patterns
    that are used to include files""" 
    def _allow_patterns(path, names):
        ignored_names = []
        for pattern in patterns:
            ignored_names.extend([k for k in names if k not in shutil.fnmatch.filter(names, pattern)])
        return set(ignored_names)
    return _allow_patterns

def ignore_patterns(*patterns):
    """Function that can be used as copytree() ignore parameter.

    Patterns is a sequence of glob-style patterns
    that are used to exclude files
    
    .. note::
        This implementation is copied from Python 2.6 shutil library and
        is provided as is for the benefit of Python 2.5 users.
    
    """
    def _ignore_patterns(path, names):
        ignored_names = []
        for pattern in patterns:
            ignored_names.extend(shutil.fnmatch.filter(names, pattern))
        return set(ignored_names)
    return _ignore_patterns


@needs_host
@fabricop
def r_rmtree(path, ignore_errors=False, onerror=None):
    """
    Recursively delete a remote directory tree.

    If ignore_errors is set, errors are ignored; otherwise, if onerror
    is set, it is called to handle the error with arguments (func,
    path, exc_info) where func is :func:`r_listdir`, :func:`r_remove`,
    or :func:`r_rmdir`; path is the argument to that function that caused 
    it to fail; and `exc_info` is a tuple returned by `sys.exc_info()`.  If 
    ignore_errors is false and `onerror` is None, an exception is raised.

    """
    with hide('running'):
        if ignore_errors:
            def onerror(*args):
                pass
        elif onerror is None:
            def onerror(*args):
                raise
        try:
            if r_islink(_unixpath(path)):
                # symlinks to directories are forbidden, see bug #1669
                raise OSError("Cannot call rmtree on a symbolic link")
        except OSError:
            onerror(r_islink, _unixpath(path), sys.exc_info())
            # can't continue even if onerror hook returns
            return
        names = []
        try:
            names = r_listdir(_r_normalizepath(path))
        except os.error, err:
            onerror(r_listdir, _unixpath(path), sys.exc_info())
        for name in names:
            fullname = _unixpath(os.path.join(_r_normalizepath(path), name))
            try:
                mode = r_stat(fullname).st_mode
            except os.error:
                mode = 0
            if stat.S_ISDIR(mode):
                r_rmtree(fullname, ignore_errors, onerror)
            else:
                try:
                    r_remove(fullname)
                except OSError, err:
                    onerror(remove, fullname, sys.exc_info())
        try:
            r_rmdir(_r_normalizepath(_unixpath(path)))
        except os.error:
            onerror(rmdir, path, sys.exc_info())

@needs_host
@fabricop
def r_makedirs(path, mode=0777):
    """ 
    Recursively create a directory structure remotely.
    
    Super-r_mkdir; create a leaf directory and all intermediate ones.
    Works like :func:`r_mkdir`, except that any intermediate path segment
    (not just the rightmost) will be created if it does not exist.  This 
    is recursive.

    """
    with hide('running'):
        head, tail = os.path.split(_r_normalizepath(path))
        if not tail:
            head, tail =  os.path.split(head)
        if head and tail and not r_exists(head):
            try:
                r_makedirs(head, mode)
            except OSError, e:
                # be happy if someone already created the path
                if e.errno != errno.EEXIST:
                    raise
            # xxx/newdir/. exists if xxx/newdir exists
            if tail == os.curdir:           
                return
        r_mkdir(_r_normalizepath(path), mode)


@needs_host
@fabricop
def r_open(name, mode='r', buffering=False):
    """
    Creates a file object on the remote host. 
    
    Treat it as you would treat a file object returned by `open` for instance::
    
        infile = r_open ( "~/input.txt","r")
        if infile:
            contents = infile.read()
            infile.close()
        
        with warnings_only():
            outfile = r_open("~/output.txt","w")
            outfile.write("output text")
    
    """
    con = connections[env.host_string].open_sftp()
    return _RemoteFile (con, _unixpath(_r_normalizepath(name)), mode, buffering)

@needs_host
@fabricop
def put_copytree (src, dst , ignore=None):
    """
    Perform a copytree operation where `src` is local and `dst` is remote.
    
    The implementation of this method is moreover a rip-off of the shutils
    implementation of the copytree method.
    
    """
    
    return _remote_copy_tree (src, _r_normalizepath(dst), ignore, True, False)

@needs_host
@fabricop
def get_copytree (src, dst , ignore=None):
    """
    Perform a copytree operation where `src` is remote and `dst` is local.
    
    The implementation of this method is moreover a rip-off of the shutils
    implementation of the copytree method.
    
    """

    return _remote_copy_tree (_r_normalizepath(src), dst, ignore, False, True)

@needs_host
@fabricop
def r_copytree ( src, dst, ignore=None):
    return _remote_copy_tree(_r_normalizepath(src), _r_normalizepath(dst) , ignore, False, False)

@needs_host
@fabricop
def r_rmdir(path):
    """
    Remove a remote directory.
    
    .. note::
        This is not a recursive method. For that, use :func:`r_rmtree`
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.rmdir(_r_normalizepath( path ) )

@needs_host
@fabricop
def r_stat (path):
    """
    State a path on the remote host.
    
    The tuple returned by this method should be inspected the same
    way as that returned by the python standard libaray ``os.stat``
    method.
        
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.stat(_r_normalizepath( path ) )

@needs_host
@fabricop
def r_isfile (path):
    """
    Test to see if *path* is a file.
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            st = ftp.stat(_r_normalizepath( path ) )
        except Exception, e:
            return False
        return S_ISREG(st.st_mode)

@needs_host
@fabricop
def r_isdir (path):
    """
    Test to see if *path* is a directory.
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            st = ftp.stat(_r_normalizepath( path ) )
        except Exception, e:
            return False
        return S_ISDIR(st.st_mode)

@needs_host
@fabricop
def r_islink(path):
    """
    Test to see if *path* is a symlink.
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            st = ftp.stat(_r_normalizepath ( path ))
        except Exception, e:
            return False
        return S_ISLNK(st.st_mode)

@needs_host
@fabricop
def r_mkdir (path , mode=0777):
    """
    Create a directory given by *path* with the mode specified by *mode*.
    Returns False on error.
    
    .. note::
        This is not a recursive method. If that is what you need,
        use :func:`r_makedirs`.
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            return ftp.mkdir(_r_normalizepath( path ) , mode)
        except IOError, e:
            return False

@needs_host
@fabricop
def r_rename(old, new):
    """
    Renames a file or directory.
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.rename (_r_normalizepath( old ), _r_normalizepath( new ))
    

@needs_host
@fabricop
def r_listdir(path):
    """
    Returns a list containing the entries in the directory given by 
    *path*. The list is in arbitrary order and the special entries '.' and '..'
    are not included
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.listdir(_unixpath ( _r_normalizepath( path ) )) 

@needs_host
@fabricop
def r_remove(path):
    """
    Removes a file on the remote system.
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.remove(_r_normalizepath( path )) 

@needs_host
@fabricop
def r_exists(path):
    """
    Test to see if a path exists on the remote system.
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        try:
            ftp.stat(_r_normalizepath( path ))
        except:
            return False
        return True
    
@needs_host
@fabricop
def r_getcwd():
    """
    Returns a string representing the current working directory on the remote
    system.
    """
    with closing(connections[env.host_string].open_sftp()) as ftp:
        return ftp.normalize('.')


@needs_host
@fabricop
def r_copy2(src,dst):
    """
    Essentially does the same thing as r_copy except it uses the shell 'cp' command.
    """
    try:
        run ( 'cp "%s" "%s"' % (src,dst))
    except Exception,e:
        raise
@needs_host
@fabricop
def r_copy(src,dst):
    """
    Copy file obeject *src* to *dst*. 
    
    .. note::
        This actually opens up a filehandle for both *src* and *dst* and copies 
        byte by byte.
    """
    fsrc = None
    fdst = None
    try:
        fsrc = r_open(src, 'rb')
        fdst = r_open(dst, 'wb')
        shutil.copyfileobj(fsrc, fdst)
    finally:
        if fdst:
            fdst.close()
        if fsrc:
            fsrc.close()


============================
Remote FileSystem utilities
============================
.. automodule:: fabric.contrib.rfsutil
    :members:
    :exclude-members: get_copytree,put_copytree,r_copy,r_copy2,r_copytree,r_exists,r_getcwd,r_isdir,r_isfile,r_islink,r_listdir,r_makedirs,r_mkdir,r_open,r_remove,r_rename,r_rmdir,r_rmtree,r_stat

       .. autofunction:: get_copytree (src, dst, ignore=None)
       .. autofunction:: put_copytree (src, dst, ignore=None)
       .. autofunction:: r_copytree (src, dst, ignore=None)
       .. autofunction:: r_copy (src, dst)
       .. autofunction:: r_copy2 (src, dst)
       .. autofunction:: r_exists (path)
       .. autofunction:: r_isdir (path)
       .. autofunction:: r_isfile (path)
       .. autofunction:: r_islink (path)
       .. autofunction:: r_listdir (path)
       .. autofunction:: r_mkdir (path, mode=511)
       .. autofunction:: r_makedirs (path, mode=511)
       .. autofunction:: r_open (name, mode='r', buffering=False)
       .. autofunction:: r_remove (path)
       .. autofunction:: r_rename (old, new)
       .. autofunction:: r_rmdir (path)
       .. autofunction:: r_rmtree (path, ignore_errors=False, onerror=None)
       .. autofunction:: r_stat (path)
       .. autofunction:: r_getcwd ()

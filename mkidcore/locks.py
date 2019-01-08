import fasteners
import tempfile
import os
import re


def interprocess_lock(name, tempdir=None):
    """Get a fasteners.InterProcessLock """
    if not tempdir:
        tempdir = tempfile.gettempdir()

    lockname = re.sub('[^\w\-_\. ]', '_', name)

    return fasteners.InterProcessLock(os.path.join(tempdir, '{}.lck'.format(lockname)))

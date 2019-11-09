import os
import posixpath
import re


def xisabs(filename):
    """ Cross-platform version of `os.path.isabs()`
        Returns True if `filename` is absolute on
        Linux, OS X or Windows.
    """
    if filename.startswith(b'/'):     # Linux/Unix
        return True
    elif filename.startswith(b'\\'):  # Windows
        return True
    elif re.match(b'\\w:[\\\\/]', filename):  # Windows
        return True
    return False


def xnormpath(path):
    """ Cross-platform version of os.path.normpath """
    # replace escapes and Windows slashes
    normalized = posixpath.normpath(path).replace(b'\\', b'/')
    # fold the result
    return posixpath.normpath(normalized)


def xstrip(filename):
    """ Make relative path out of absolute by stripping
        prefixes used on Linux, OS X and Windows.

        This function is critical for security.
    """
    while xisabs(filename):
        # strip windows drive with all slashes
        if re.match(b'\\w:[\\\\/]', filename):
            filename = re.sub(b'^\\w+:[\\\\/]+', b'', filename)
        # strip all slashes
        elif re.match(b'[\\\\/]', filename):
            filename = re.sub(b'^[\\\\/]+', b'', filename)
    return filename


# [ ] reuse more universal pathsplit()
def pathstrip(path, n):
    """ Strip n leading components from the given path """
    pathlist = [path]
    while os.path.dirname(pathlist[0]) != b'':
        pathlist[0:1] = os.path.split(pathlist[0])
    return b'/'.join(pathlist[n:])

from __future__ import print_function

from pkg_resources import get_distribution, DistributionNotFound

from io import BytesIO
from urllib import request

import logging

from filepatch.patchset import PatchSet

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass

logger = logging.getLogger('filepatch')
logger.addHandler(logging.NullHandler())


def fromurl(url):
    """ Parse patch from an URL, return False
        if an error occured. Note that this also
        can throw urlopen() exceptions.
    """
    ps = PatchSet(request.urlopen(url))
    if ps.errors == 0:
        return ps
    return False


def fromfile(filename):
    """ Parse patch file. If successful, returns
        PatchSet() object. Otherwise returns False.
    """
    patchset = PatchSet()
    logger.debug("reading %s" % filename)
    fp = open(filename, "rb")
    res = patchset.parse(fp)
    fp.close()
    if res is True:
        return patchset
    return False


def fromstring(s):
    """ Parse text string and return PatchSet()
        object (or False if parsing fails)
    """
    ps = PatchSet(BytesIO(s))
    if ps.errors == 0:
        return ps
    return False

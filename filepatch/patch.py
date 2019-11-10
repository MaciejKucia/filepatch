class Patch(object):
    """ Patch for a single file.
        If used as an iterable, returns hunks.
    """
    def __init__(self):
        self.source = None
        self.target = None
        self.hunks = []
        self.hunkends = []
        self.header = []

        self.type = None

class WrapEnumerate(enumerate):
    """Enumerate wrapper that uses boolean end of stream status instead
    of StopIteration exception, and properties to access line
    information.
    """

    def __init__(self, *args, **kwargs):
        # we don't call parent, it is magically created by
        # __new__ method

        self._exhausted = False
        # after end of stream equal to the num of lines
        self._lineno = False
        # will be reset to False after end of stream
        self._line = False

    def next(self):
        """Try to read the next line and return True if it is available
           False if end of stream is reached."""
        if self._exhausted:
            return False

        try:
            self._lineno, self._line = super(WrapEnumerate, self).__next__()
        except StopIteration:
            self._exhausted = True
            self._line = False
            return False
        return True

    @property
    def is_empty(self):
        return self._exhausted

    @property
    def line(self):
        return self._line

    @property
    def lineno(self):
        return self._lineno

class Hunk(object):
    """ Parsed hunk data container (hunk starts with @@ -R +R @@) """

    def __init__(self):
        self.startsrc = None  #: line count starts with 1
        self.linessrc = None
        self.starttgt = None
        self.linestgt = None
        self.invalid = False
        self.desc = ''
        self.text = []

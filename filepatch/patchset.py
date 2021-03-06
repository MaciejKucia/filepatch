import copy
import logging
import re
from enum import Enum

from os.path import exists, isfile, abspath
import os
import shutil

from filepatch.hunk import Hunk
from filepatch.patch import Patch
from filepatch.utils import pathstrip, xnormpath, xisabs, xstrip
from filepatch.wrap_enumerate import WrapEnumerate

HUNKHEAD_REGEX = re.compile(
    b"^@@ -(\\d+)(,(\\d+))? \\+(\\d+)(,(\\d+))? @@(.*)")
# regexp to match start of hunk, used groups - 1,3,4,6
HUNK_REGEX = re.compile(
    b"^@@ -(\\d+)(,(\\d+))? \\+(\\d+)(,(\\d+))? @@")

logger = logging.getLogger('filepatch')
debug = logger.debug
info = logger.info
warning = logger.warning


class PatchSetTypes(Enum):
    GIT = "git"
    HG = "mercurial"
    MIXED = "mixed"
    PLAIN = "plain"
    SVN = "svn"


class PatchSet(object):
    """ PatchSet is a patch parser and container.
        When used as an iterable, returns patches.
    """

    def __init__(self, stream=None):
        # patch set type - one of constants
        self.type = None

        # list of Patch objects
        self.items = []

        self.errors = 0    # fatal parsing errors
        self.warnings = 0  # non-critical warnings
        # --- /API ---

        if stream:
            self.parse(stream)

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        for i in self.items:
            yield i

    def parse(self, stream):
        """ parse unified diff
            return True on success
        """
        lineends = dict(lf=0, crlf=0, cr=0)
        #: even if index starts with 0 user messages number hunks from 1
        nexthunkno = 0

        p = None
        hunk = None
        # hunkactual variable is used to calculate hunk lines for comparison
        hunkactual = dict(linessrc=None, linestgt=None)

        # define states (possible file regions) that direct parse flow
        headscan = True  # start with scanning header
        filenames = False  # lines starting with --- and +++

        hunkhead = False  # @@ -R +R @@ sequence
        hunkbody = False  #
        hunkskip = False  # skipping invalid hunk mode

        hunkparsed = False  # state after successfully parsed hunk

        re_hunk_start = HUNK_REGEX

        self.errors = 0
        # temp buffers for header and filenames info
        header = []
        srcname = None
        tgtname = None

        # start of main cycle
        # each parsing block already has line available in fe.line
        fe = WrapEnumerate(stream)
        while fe.next():

            # -- deciders: these only switch state to decide who should process
            # --           line fetched at the start of this cycle
            if hunkparsed:
                hunkparsed = False
                if re_hunk_start.match(fe.line):
                    hunkhead = True
                elif fe.line.startswith(b"--- "):
                    filenames = True
                else:
                    headscan = True
            # -- ------------------------------------

            # read out header
            if headscan:
                while not fe.is_empty and not fe.line.startswith(b"--- "):
                    header.append(fe.line)
                    fe.next()
                if fe.is_empty:
                    if p is None:
                        debug("no patch data found")  # error is shown later
                        self.errors += 1
                    else:
                        info("%d unparsed bytes left at the end of stream"
                             % len(b''.join(header)))
                        self.warnings += 1
                        # TODO check for \No new line at the end..
                        # TODO test for unparsed bytes
                        # otherwise error += 1
                    # this is actually a loop exit
                    continue

                headscan = False
                # switch to filenames state
                filenames = True

            line = fe.line
            lineno = fe.lineno

            # hunkskip and hunkbody code skipped until definition of hunkhead
            # is parsed
            if hunkbody:
                # [x] treat empty lines inside hunks as containing single space
                #    (this happens when diff is saved by copy/pasting to editor
                #     that strips trailing whitespace)
                if line.strip(b"\r\n") == b"":
                    debug("expanding empty line in a middle of hunk body")
                    self.warnings += 1
                    line = b' ' + line

                # process line first
                if re.match(b"^[- \\+\\\\]", line):
                    # gather stats about line endings
                    if line.endswith(b"\r\n"):
                        p.hunkends["crlf"] += 1
                    elif line.endswith(b"\n"):
                        p.hunkends["lf"] += 1
                    elif line.endswith(b"\r"):
                        p.hunkends["cr"] += 1

                    if line.startswith(b"-"):
                        hunkactual["linessrc"] += 1
                    elif line.startswith(b"+"):
                        hunkactual["linestgt"] += 1
                    elif not line.startswith(b"\\"):
                        hunkactual["linessrc"] += 1
                        hunkactual["linestgt"] += 1
                    hunk.text.append(line)
                    # todo: handle \ No newline cases
                else:
                    warning("invalid hunk no.%d at %d for target file %s"
                            % (nexthunkno, lineno+1, p.target))
                    # add hunk status node
                    hunk.invalid = True
                    p.hunks.append(hunk)
                    self.errors += 1
                    # switch to hunkskip state
                    hunkbody = False
                    hunkskip = True

                # check exit conditions
                if hunkactual["linessrc"] > hunk.linessrc or \
                        hunkactual["linestgt"] > hunk.linestgt:
                    warning("extra lines for hunk no.%d at %d for target %s"
                            % (nexthunkno, lineno+1, p.target))
                    # add hunk status node
                    hunk.invalid = True
                    p.hunks.append(hunk)
                    self.errors += 1
                    # switch to hunkskip state
                    hunkbody = False
                    hunkskip = True
                elif hunk.linessrc == hunkactual["linessrc"] and \
                        hunk.linestgt == hunkactual["linestgt"]:
                    # hunk parsed successfully
                    p.hunks.append(hunk)
                    # switch to hunkparsed state
                    hunkbody = False
                    hunkparsed = True

                    # detect mixed window/unix line ends
                    ends = p.hunkends
                    line_ends_types = (
                            (ends["cr"] != 0) +
                            (ends["crlf"] != 0) +
                            (ends["lf"] != 0))
                    if line_ends_types > 1:
                        warning("inconsistent line ends in patch hunks for %s"
                                % p.source)
                        self.warnings += 1
                    # fetch next line
                    continue

            if hunkskip:
                if re_hunk_start.match(line):
                    # switch to hunkhead state
                    hunkskip = False
                    hunkhead = True
                elif line.startswith(b"--- "):
                    # switch to filenames state
                    hunkskip = False
                    filenames = True

            if filenames:
                if line.startswith(b"--- "):
                    if srcname is not None:
                        # XXX testcase
                        warning("skipping false patch for %s" % srcname)
                        srcname = None
                        # XXX header += srcname
                        # double source filename line is encountered
                        # attempt to restart from this second line
                    re_filename = b"^--- ([^\t]+)"
                    match = re.match(re_filename, line)
                    # todo: support spaces in filenames
                    if match:
                        srcname = match.group(1).strip()
                    else:
                        warning("skipping invalid filename at line %d"
                                % (lineno+1))
                        self.errors += 1
                        # XXX p.header += line
                        # switch back to headscan state
                        filenames = False
                        headscan = True
                elif not line.startswith(b"+++ "):
                    if srcname is not None:
                        warning("skipping invalid patch with no target for %s"
                                % srcname)
                        self.errors += 1
                        srcname = None
                        # XXX header += srcname
                        # XXX header += line
                    else:
                        # this should be unreachable
                        warning("skipping invalid target patch")
                    filenames = False
                    headscan = True
                else:
                    if tgtname is not None:
                        # XXX seems to be a dead branch
                        warning("skipping invalid patch - double target at "
                                "line %d" % (lineno+1))
                        self.errors += 1
                        srcname = None
                        tgtname = None
                        # XXX header += srcname
                        # XXX header += tgtname
                        # XXX header += line
                        # double target filename line is encountered
                        # switch back to headscan state
                        filenames = False
                        headscan = True
                    else:
                        re_filename = b"^\\+\\+\\+ ([^\\t]+)"
                        match = re.match(re_filename, line)
                        if not match:
                            warning("skipping invalid patch - no target"
                                    " filename at line %d" % (lineno+1))
                            self.errors += 1
                            srcname = None
                            # switch back to headscan state
                            filenames = False
                            headscan = True
                        else:
                            if p:  # for the first run p is None
                                self.items.append(p)
                            p = Patch()
                            p.source = srcname
                            srcname = None
                            p.target = match.group(1).strip()
                            p.header = header
                            header = []
                            # switch to hunkhead state
                            filenames = False
                            hunkhead = True
                            nexthunkno = 0
                            p.hunkends = lineends.copy()
                            continue

            if hunkhead:
                match = HUNKHEAD_REGEX.match(line)
                if not match:
                    if not p.hunks:
                        warning("skipping invalid patch with no hunks for file"
                                " %s" % p.source)
                        self.errors += 1
                        # XXX review switch
                        # switch to headscan state
                        hunkhead = False
                        headscan = True
                        continue
                    else:
                        # TODO review condition case
                        # switch to headscan state
                        hunkhead = False
                        headscan = True
                else:
                    hunk = Hunk()
                    hunk.startsrc = int(match.group(1))
                    hunk.linessrc = 1
                    if match.group(3):
                        hunk.linessrc = int(match.group(3))
                    hunk.starttgt = int(match.group(4))
                    hunk.linestgt = 1
                    if match.group(6):
                        hunk.linestgt = int(match.group(6))
                    hunk.invalid = False
                    hunk.desc = match.group(7)[1:].rstrip()
                    hunk.text = []

                    hunkactual["linessrc"] = hunkactual["linestgt"] = 0

                    # switch to hunkbody state
                    hunkhead = False
                    hunkbody = True
                    nexthunkno += 1
                    continue

        if p:
            self.items.append(p)

        if not hunkparsed:
            if hunkskip:
                warning("warning: finished with errors, "
                        "some hunks may be invalid")
            elif headscan:
                if len(self.items) == 0:
                    warning("error: no patch data found!")
                    return False
                else:  # extra data at the end of file
                    pass
            else:
                warning("error: patch stream is incomplete!")
                self.errors += 1
                if len(self.items) == 0:
                    return False

        # XXX fix total hunks calculation
        debug("total files: %d  total hunks: %d",
              len(self.items), sum(len(p.hunks) for p in self.items))

        # ---- detect patch and patchset types ----
        for idx, p in enumerate(self.items):
            self.items[idx].type = self._detect_type(p)

        types = set([p.type for p in self.items])
        if len(types) > 1:
            self.type = PatchSetTypes.MIXED
        else:
            self.type = types.pop()
        # --------

        self._normalize_filenames()

        return self.errors == 0

    def _detect_type(self, p):
        """ detect and return type for the specified Patch object
            analyzes header and filenames info

            NOTE: must be run before filenames are normalized
        """

        # check for SVN
        #  - header starts with Index:
        #  - next line is ===... delimiter
        #  - filename is followed by revision number
        # TODO add SVN revision
        if (len(p.header) > 1 and p.header[-2].startswith(b"Index: ") and
                p.header[-1].startswith(b"="*67)):
            return PatchSetTypes.SVN

        # common checks for both HG and GIT
        DVCS = ((p.source.startswith(b'a/') or p.source == b'/dev/null')
                and (p.target.startswith(b'b/') or p.target == b'/dev/null'))

        # GIT type check
        #  - header[-2] is like "diff --git a/oldname b/newname"
        #  - header[-1] is like "index <hash>..<hash> <mode>"
        # TODO add git rename diffs and add/remove diffs
        #      add git diff with spaced filename
        # TODO http://www.kernel.org/pub/software/scm/git/docs/git-diff.html

        # Git patch header len is 2 min
        if len(p.header) > 1:
            # detect the start of diff header -
            # there might be some comments before
            for idx in reversed(range(len(p.header))):
                if p.header[idx].startswith(b"diff --git"):
                    break
            if p.header[idx].startswith(b'diff --git a/'):
                if (idx+1 < len(p.header)
                        and re.match(b'index \\w{7}..\\w{7} \\d{6}',
                                     p.header[idx+1])):
                    if DVCS:
                        return PatchSetTypes.GIT

        # HG check
        #
        #  - for plain HG format header is like "diff -r b2d9961ff1f5 filename"
        #  - for Git-style HG patches it is "diff --git a/oldname b/newname"
        #  - filename starts with a/, b/ or is equal to /dev/null
        #  - exported changesets also contain the header
        #    # HG changeset patch
        #    # User name@example.com
        #    ...
        # TODO add MQ
        # TODO add revision info
        if len(p.header) > 0:
            if DVCS and re.match(b'diff -r \\w{12} .*', p.header[-1]):
                return PatchSetTypes.HG
            if DVCS and p.header[-1].startswith(b'diff --git a/'):
                if len(p.header) == 1:  # native Git patch header len is 2
                    return PatchSetTypes.HG
                elif p.header[0].startswith(b'# HG changeset patch'):
                    return PatchSetTypes.HG

        return PatchSetTypes.PLAIN

    def _normalize_filenames(self):
        """ sanitize filenames, normalizing paths, i.e.:
            1. strip a/ and b/ prefixes from GIT and HG style patches
            2. remove all references to parent directories (with warning)
            3. translate any absolute paths to relative (with warning)

            [x] always use forward slashes to be crossplatform
                (diff/patch were born as a unix utility after all)

            return None
        """
        for i, p in enumerate(self.items):
            if p.type in (PatchSetTypes.HG, PatchSetTypes.GIT):
                # TODO: figure out how to deal with /dev/null entries
                debug("stripping a/ and b/ prefixes")
                if p.source != '/dev/null':
                    if not p.source.startswith(b"a/"):
                        warning("invalid source filename")
                    else:
                        p.source = p.source[2:]
                if p.target != '/dev/null':
                    if not p.target.startswith(b"b/"):
                        warning("invalid target filename")
                    else:
                        p.target = p.target[2:]

            p.source = xnormpath(p.source)
            p.target = xnormpath(p.target)

            sep = b'/'

            # references to parent are not allowed
            if p.source.startswith(b".." + sep):
                warning("error: stripping parent path for source file patch "
                        "no.%d" % (i+1))
                self.warnings += 1
                while p.source.startswith(b".." + sep):
                    p.source = p.source.partition(sep)[2]
            if p.target.startswith(b".." + sep):
                warning("error: stripping parent path for target file patch "
                        "no.%d" % (i+1))
                self.warnings += 1
                while p.target.startswith(b".." + sep):
                    p.target = p.target.partition(sep)[2]
            # absolute paths are not allowed
            if xisabs(p.source) or xisabs(p.target):
                warning("error: absolute paths are not allowed - file no.%d"
                        % (i+1))
                self.warnings += 1
                if xisabs(p.source):
                    warning("stripping absolute path from source name '%s'"
                            % p.source)
                    p.source = xstrip(p.source)
                if xisabs(p.target):
                    warning("stripping absolute path from target name '%s'"
                            % p.target)
                    p.target = xstrip(p.target)

            self.items[i].source = p.source
            self.items[i].target = p.target

    def diffstat(self):
        """ calculate diffstat and return as a string
            Notes:
              - original diffstat ouputs target filename
              - single + or - shouldn't escape histogram
        """
        names = []
        insert = []
        delete = []
        delta = 0    # size change in bytes
        namelen = 0
        maxdiff = 0  # max number of changes for single file
        # (for histogram width calculation)
        for patch in self.items:
            i, d = 0, 0
            for hunk in patch.hunks:
                for line in hunk.text:
                    if line.startswith(b'+'):
                        i += 1
                        delta += len(line)-1
                    elif line.startswith(b'-'):
                        d += 1
                        delta -= len(line)-1
            names.append(patch.target)
            insert.append(i)
            delete.append(d)
            namelen = max(namelen, len(patch.target))
            maxdiff = max(maxdiff, i+d)
        output = ''
        statlen = len(str(maxdiff))  # stats column width
        for i, n in enumerate(names):
            format = " %-" + str(namelen) + "s | %" + str(statlen) + "s %s\n"
            # -- calculating histogram --
            width = len(format % ('', '', ''))
            histwidth = max(2, 80 - width)
            if maxdiff < histwidth:
                hist = "+"*insert[i] + "-"*delete[i]
            else:
                iratio = (float(insert[i]) / maxdiff) * histwidth
                dratio = (float(delete[i]) / maxdiff) * histwidth

                # make sure every entry gets at least one + or -
                iwidth = 1 if 0 < iratio < 1 else int(iratio)
                dwidth = 1 if 0 < dratio < 1 else int(dratio)
                hist = "+"*int(iwidth) + "-"*int(dwidth)
            # -- /calculating +- histogram --
            output += (format % (
                names[i].decode('utf-8'), str(insert[i] + delete[i]), hist))

        output += (" %d files changed, %d insertions(+), %d deletions(-), %+d "
                   "bytes" % (len(names), sum(insert), sum(delete), delta))
        return output

    def findfile(self, old, new):
        """ return name of file to be patched or None """
        if exists(old):
            return old
        elif exists(new):
            return new
        else:
            # [w] Google Code generates broken patches with its online editor
            debug("broken patch from Google Code, stripping prefixes..")
            if old.startswith(b'a/') and new.startswith(b'b/'):
                old, new = old[2:], new[2:]
                debug("   %s" % old)
                debug("   %s" % new)
                if exists(old):
                    return old
                elif exists(new):
                    return new
            return None

    def apply(self, strip=0, root=None):
        """ Apply parsed patch, optionally stripping leading components
            from file paths. `root` parameter specifies working dir.
            return True on success
        """
        if root:
            prevdir = os.getcwd()
            os.chdir(root)

        total = len(self.items)
        errors = 0
        if strip:
            # [ ] test strip level exceeds nesting level
            #   [ ] test the same only for selected files
            #     [ ] test if files end up being on the same level
            try:
                strip = int(strip)
            except ValueError:
                errors += 1
                warning("error: strip parameter '%s' must be an integer"
                        % strip)
                strip = 0

        for i, p in enumerate(self.items):
            if strip:
                debug("stripping %s leading component(s) from:" % strip)
                debug("   %s" % p.source)
                debug("   %s" % p.target)
                old = pathstrip(p.source, strip)
                new = pathstrip(p.target, strip)
            else:
                old, new = p.source, p.target

            filename = self.findfile(old, new)

            if not filename:
                warning("source/target file does not exist:\n  --- %s\n"
                        "  +++ %s" % (old, new))
                errors += 1
                continue
            if not isfile(filename):
                warning("not a file - %s" % filename)
                errors += 1
                continue

            # [ ] check absolute paths security here
            debug("processing %d/%d:\t %s" % (i+1, total, filename))

            # validate before patching
            f2fp = open(filename, 'rb')
            hunkno = 0
            hunk = p.hunks[hunkno]
            hunkfind = []
            validhunks = 0
            canpatch = False
            for lineno, line in enumerate(f2fp):
                if lineno+1 < hunk.startsrc:
                    continue
                elif lineno+1 == hunk.startsrc:
                    hunkfind = [x[1:].rstrip(b"\r\n") for x in hunk.text if
                                x[0] in b" -"]
                    hunklineno = 0

                    # todo \ No newline at end of file

                # check hunks in source file
                if lineno+1 < hunk.startsrc+len(hunkfind)-1:
                    if line.rstrip(b"\r\n") == hunkfind[hunklineno]:
                        hunklineno += 1
                    else:
                        errors += 1
                        info("file %d/%d:\t %s" % (i+1, total, filename))
                        info(" hunk no.%d doesn't match source file at line %d"
                             % (hunkno+1, lineno+1))
                        info("  expected: %s" % hunkfind[hunklineno])
                        info("  actual  : %s" % line.rstrip(b"\r\n"))
                        # not counting this as error, because file may already
                        # be patched. check if file is already patched is done
                        # after the number of invalid hunks if found
                        # TODO: check hunks against source/target file in one
                        # pass
                        #   API - check(stream, srchunks, tgthunks)
                        #           return tuple (srcerrs, tgterrs)

                        # continue to check other hunks for completeness
                        hunkno += 1
                        if hunkno < len(p.hunks):
                            hunk = p.hunks[hunkno]
                            continue
                        else:
                            break

                # check if processed line is the last line
                if lineno+1 == hunk.startsrc+len(hunkfind)-1:
                    debug(" hunk no.%d for file %s  -- is ready to be patched"
                          % (hunkno+1, filename))
                    hunkno += 1
                    validhunks += 1
                    if hunkno < len(p.hunks):
                        hunk = p.hunks[hunkno]
                    else:
                        if validhunks == len(p.hunks):
                            # patch file
                            canpatch = True
                            break
            else:
                if hunkno < len(p.hunks):
                    warning("premature end of source file %s at hunk %d"
                            % (filename, hunkno+1))
                    errors += 1

            f2fp.close()

            if validhunks < len(p.hunks):
                if self._match_file_hunks(filename, p.hunks):
                    warning("already patched  %s" % filename)
                else:
                    warning("source file is different - %s" % filename)
                    errors += 1
            if canpatch:
                backupname = filename+b".orig"
                if exists(backupname):
                    warning("can't backup original file to %s - aborting"
                            % backupname)
                else:
                    import shutil
                    shutil.move(filename, backupname)
                    if self.write_hunks(backupname, filename, p.hunks):
                        info("successfully patched %d/%d:\t %s"
                             % (i+1, total, filename))
                        os.unlink(backupname)
                    else:
                        errors += 1
                        warning("error patching file %s" % filename)
                        shutil.copy(filename, filename+".invalid")
                        warning("invalid version is saved to %s"
                                % filename+".invalid")
                        # todo: proper rejects
                        shutil.move(backupname, filename)

        if root:
            os.chdir(prevdir)

        # todo: check for premature eof
        return errors == 0

    def _reverse(self):
        """ reverse patch direction (this doesn't touch filenames) """
        for p in self.items:
            for h in p.hunks:
                h.startsrc, h.starttgt = h.starttgt, h.startsrc
                h.linessrc, h.linestgt = h.linestgt, h.linessrc
                for i, line in enumerate(h.text):
                    # need to use line[0:1] here, because line[0]
                    # returns int instead of bytes on Python 3
                    if line[0:1] == b'+':
                        h.text[i] = b'-' + line[1:]
                    elif line[0:1] == b'-':
                        h.text[i] = b'+' + line[1:]

    def revert(self, strip=0, root=None):
        """ apply patch in reverse order """
        reverted = copy.deepcopy(self)
        reverted._reverse()
        return reverted.apply(strip, root)

    def can_patch(self, filename):
        """ Check if specified filename can be patched. Returns None if file
        can not be found among source filenames. False if patch can not be
        applied clearly. True otherwise.

        :returns: True, False or None
        """
        filename = abspath(filename)
        for p in self.items:
            if filename == abspath(p.source):
                return self._match_file_hunks(filename, p.hunks)
        return None

    def _match_file_hunks(self, filepath, hunks):
        matched = True
        fp = open(abspath(filepath), 'rb')

        class NoMatch(Exception):
            pass

        lineno = 1
        line = fp.readline()
        try:
            for hno, h in enumerate(hunks):
                # skip to first line of the hunk
                while lineno < h.starttgt:
                    if not len(line):  # eof
                        debug("check failed - premature eof before hunk: %d"
                              % (hno+1))
                        raise NoMatch
                    line = fp.readline()
                    lineno += 1
                for hline in h.text:
                    if hline.startswith(b"-"):
                        continue
                    if not len(line):
                        debug("check failed - premature eof on hunk: %d"
                              % (hno+1))
                        # todo: \ No newline at the end of file
                        raise NoMatch
                    if line.rstrip(b"\r\n") != hline[1:].rstrip(b"\r\n"):
                        debug("file is not patched - failed hunk: %d"
                              % (hno+1))
                        raise NoMatch
                    line = fp.readline()
                    lineno += 1

        except NoMatch:
            matched = False
            # todo: display failed hunk, i.e. expected/found

        fp.close()
        return matched

    def patch_stream(self, instream, hunks):
        """ Generator that yields stream patched with hunks iterable

            Converts lineends in hunk lines to the best suitable format
            autodetected from input
        """

        # todo: At the moment substituted lineends may not be the same
        #       at the start and at the end of patching. Also issue a
        #       warning/throw about mixed lineends (is it really needed?)

        hunks = iter(hunks)

        srclineno = 1

        lineends = {b'\n': 0, b'\r\n': 0, b'\r': 0}

        def get_line():
            """
            local utility function - return line from source stream
            collecting line end statistics on the way
            """
            line = instream.readline()
            # 'U' mode works only with text files
            if line.endswith(b"\r\n"):
                lineends[b"\r\n"] += 1
            elif line.endswith(b"\n"):
                lineends[b"\n"] += 1
            elif line.endswith(b"\r"):
                lineends[b"\r"] += 1
            return line

        for hno, h in enumerate(hunks):
            debug("hunk %d" % (hno+1))
            # skip to line just before hunk starts
            while srclineno < h.startsrc:
                yield get_line()
                srclineno += 1

            for hline in h.text:
                # todo: check \ No newline at the end of file
                if hline.startswith(b"-") or hline.startswith(b"\\"):
                    get_line()
                    srclineno += 1
                    continue
                else:
                    if not hline.startswith(b"+"):
                        get_line()
                        srclineno += 1
                    line2write = hline[1:]
                    # detect if line ends are consistent in source file
                    if sum([bool(lineends[x]) for x in lineends]) == 1:
                        newline = [x for x in lineends if lineends[x] != 0][0]
                        yield line2write.rstrip(b"\r\n")+newline
                    else:  # newlines are mixed
                        yield line2write

        for line in instream:
            yield line

    def write_hunks(self, srcname, tgtname, hunks):
        src = open(srcname, "rb")
        tgt = open(tgtname, "wb")

        debug("processing target file %s" % tgtname)

        tgt.writelines(self.patch_stream(src, hunks))

        tgt.close()
        src.close()
        # [ ] TODO: add test for permission copy
        shutil.copymode(srcname, tgtname)
        return True

import logging
from os.path import isfile

from filepatch import __version__, logger, streamhandler, setdebug, PatchSet, \
    fromurl, fromfile


def main():
    from optparse import OptionParser
    from os.path import exists
    import sys

    opt = OptionParser(usage="1. %prog [options] unified.diff\n"
                             "       2. %prog [options] http://host/patch\n"
                             "       3. %prog [options] -- < unified.diff",
                       version="python-patch %s" % __version__)
    opt.add_option("-q", "--quiet", action="store_const", dest="verbosity",
                   const=0, help="print only warnings and errors", default=1)
    opt.add_option("-v", "--verbose", action="store_const", dest="verbosity",
                   const=2, help="be verbose")
    opt.add_option("--debug", action="store_true", dest="debugmode",
                   help="debug mode")
    opt.add_option("--diffstat", action="store_true", dest="diffstat",
                   help="print diffstat and exit")
    opt.add_option("-d", "--directory", metavar='DIR',
                   help="specify root directory for applying patch")
    opt.add_option("-p", "--strip", type="int", metavar='N', default=0,
                   help="strip N path components from filenames")
    opt.add_option("--revert", action="store_true",
                   help="apply patch in reverse order (unpatch)")
    (options, args) = opt.parse_args()

    if not args and sys.argv[-1:] != ['--']:
        opt.print_version()
        opt.print_help()
        sys.exit()
    readstdin = (sys.argv[-1:] == ['--'] and not args)

    verbosity_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    loglevel = verbosity_levels[options.verbosity]
    logformat = "%(message)s"
    logger.setLevel(loglevel)
    streamhandler.setFormatter(logging.Formatter(logformat))

    if options.debugmode:
        setdebug()  # this sets global debugmode variable

    if readstdin:
        patch = PatchSet(sys.stdin)
    else:
        patchfile = args[0]
        urltest = patchfile.split(':')[0]
        if ':' in patchfile and urltest.isalpha() and len(urltest) > 1:
            # one char before : is a windows drive letter
            patch = fromurl(patchfile)
        else:
            if not exists(patchfile) or not isfile(patchfile):
                sys.exit("patch file does not exist - %s" % patchfile)
            patch = fromfile(patchfile)

    if options.diffstat:
        print(patch.diffstat())
        sys.exit(0)

    if options.revert:
        patch.revert(options.strip, root=options.directory) or sys.exit(-1)
    else:
        patch.apply(options.strip, root=options.directory) or sys.exit(-1)

    # todo: document and test line ends handling logic - patch.py detects
    # proper line-endings for inserted hunks and issues a warning if patched
    # file has incosistent line ends


if __name__ == "__main__":
    main()

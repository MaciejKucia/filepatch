import unittest
from os.path import join, dirname, abspath

from filepatch import fromstring, fromfile, PatchSet

TESTS = dirname(abspath(__file__))
TESTDATA = join(TESTS, 'data')


def testfile(name):
    return join(TESTDATA, name)


class TestPatchParse(unittest.TestCase):
    def test_fromstring(self):
        try:
            f = open(join(TESTS, "01uni_multi/01uni_multi.patch"), "rb")
            readstr = f.read()
        finally:
            f.close()
        pst = fromstring(readstr)
        self.assertEqual(len(pst), 5)

    def test_fromfile(self):
        pst = fromfile(join(TESTS, "01uni_multi/01uni_multi.patch"))
        self.assertNotEqual(pst, False)
        self.assertEqual(len(pst), 5)
        ps2 = fromfile(testfile("failing/not-a-patch.log"))
        self.assertFalse(ps2)

    def test_no_header_for_plain_diff_with_single_file(self):
        pto = fromfile(join(TESTS, "03trail_fname.patch"))
        self.assertEqual(pto.items[0].header, [])

    def test_header_for_second_file_in_svn_diff(self):
        pto = fromfile(join(TESTS, "01uni_multi/01uni_multi.patch"))
        self.assertEqual(pto.items[1].header[0], b'Index: updatedlg.h\r\n')
        self.assertTrue(pto.items[1].header[1].startswith(b'====='))

    def test_hunk_desc(self):
        pto = fromfile(testfile('git-changed-file.diff'))
        self.assertEqual(pto.items[0].hunks[0].desc,
                         b'class JSONPluginMgr(object):')

    def test_autofixed_absolute_path(self):
        pto = fromfile(join(TESTS, "data/autofix/absolute-path.diff"))
        self.assertEqual(pto.errors, 0)
        self.assertEqual(pto.warnings, 2)
        self.assertEqual(pto.items[0].source, b"winnt/tests/run_tests.py")

    def test_autofixed_parent_path(self):
        # [ ] exception vs return codes for error recovery
        #  [x] separate return code when patch lib compensated the error
        #      (implemented as warning count)
        pto = fromfile(join(TESTS, "data/autofix/parent-path.diff"))
        self.assertEqual(pto.errors, 0)
        self.assertEqual(pto.warnings, 2)
        self.assertEqual(pto.items[0].source, b"patch.py")

    def test_autofixed_stripped_trailing_whitespace(self):
        pto = fromfile(join(TESTS,
                            "data/autofix/stripped-trailing-whitespace.diff"))
        self.assertEqual(pto.errors, 0)
        self.assertEqual(pto.warnings, 4)

    def test_fail_missing_hunk_line(self):
        fp = open(join(TESTS, "data/failing/missing-hunk-line.diff"), 'rb')
        pto = PatchSet()
        self.assertNotEqual(pto.parse(fp), True)
        fp.close()

    def test_fail_context_format(self):
        fp = open(join(TESTS, "data/failing/context-format.diff"), 'rb')
        res = PatchSet().parse(fp)
        self.assertFalse(res)
        fp.close()

    def test_fail_not_a_patch(self):
        fp = open(join(TESTS, "data/failing/not-a-patch.log"), 'rb')
        res = PatchSet().parse(fp)
        self.assertFalse(res)
        fp.close()

    def test_diffstat(self):
        output = """\
 updatedlg.cpp | 20 ++++++++++++++++++--
 updatedlg.h   |  1 +
 manifest.xml  | 15 ++++++++-------
 conf.cpp      | 23 +++++++++++++++++------
 conf.h        |  7 ++++---
 5 files changed, 48 insertions(+), 18 deletions(-), +1203 bytes"""
        pto = fromfile(join(TESTS, "01uni_multi/01uni_multi.patch"))
        self.assertEqual(pto.diffstat(), output, "Output doesn't match")

import unittest
from os import listdir
from os.path import join, dirname, abspath, isdir

from filepatch import fromfile
from filepatch.patchset import PatchSetTypes


verbose = False
TESTS = dirname(abspath(__file__))
TESTDATA = join(TESTS, 'data')


class TestPatchSetDetection(unittest.TestCase):
    def test_svn_detected(self):
        pto = fromfile(join(TESTS, "01uni_multi/01uni_multi.patch"))
        self.assertEqual(pto.type, PatchSetTypes.SVN)


# generate tests methods for TestPatchSetDetection - one for each patch file
def generate_detection_test(file_name, patchtype):
    # saving variable in local scope to prevent test()
    # from fetching it from global
    patchtype = difftype

    def test(self):
        pto = fromfile(join(TESTDATA, file_name))
        self.assertEqual(pto.type, patchtype)
    return test


for filename in listdir(TESTDATA):
    if isdir(join(TESTDATA, filename)):
        continue

    difftype = PatchSetTypes.PLAIN
    if filename.startswith('git-'):
        difftype = PatchSetTypes.GIT
    if filename.startswith('hg-'):
        difftype = PatchSetTypes.HG
    if filename.startswith('svn-'):
        difftype = PatchSetTypes.SVN

    name = 'test_'+filename
    test = generate_detection_test(filename, difftype)
    setattr(TestPatchSetDetection, name, test)
    if verbose:
        print("added test method %s to %s" % (name, 'TestPatchSetDetection'))

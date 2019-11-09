import os
import shutil
import unittest
from os import getcwd
from os.path import dirname, abspath, join
from tempfile import mkdtemp

from filepatch import fromfile


TESTS = dirname(abspath(__file__))


class TestPatchApply(unittest.TestCase):
    def setUp(self):
        self.save_cwd = getcwd()
        self.tmpdir = mkdtemp(prefix=self.__class__.__name__)
        os.chdir(self.tmpdir)

    def tearDown(self):
        os.chdir(self.save_cwd)
        shutil.rmtree(self.tmpdir)

    def tmpcopy(self, filenames):
        """copy file(s) from test_dir to self.tmpdir"""
        for f in filenames:
            shutil.copy(join(TESTS, f), self.tmpdir)

    def test_apply_returns_false_on_failure(self):
        self.tmpcopy(['data/failing/non-empty-patch-for-empty-file.diff',
                      'data/failing/upload.py'])
        pto = fromfile('non-empty-patch-for-empty-file.diff')
        self.assertFalse(pto.apply())

    def test_apply_returns_true_on_success(self):
        self.tmpcopy(['03trail_fname.patch',
                      '03trail_fname.from'])
        pto = fromfile('03trail_fname.patch')
        self.assertTrue(pto.apply())

    def test_revert(self):
        def get_file_content(filename):
            with open(filename, 'rb') as f:
                return f.read()

        self.tmpcopy(['03trail_fname.patch',
                      '03trail_fname.from'])
        pto = fromfile('03trail_fname.patch')
        self.assertTrue(pto.apply())
        self.assertNotEqual(
            get_file_content(self.tmpdir + '/03trail_fname.from'),
            get_file_content(TESTS + '/03trail_fname.from'))
        self.assertTrue(pto.revert())
        self.assertEqual(
            get_file_content(self.tmpdir + '/03trail_fname.from'),
            get_file_content(TESTS + '/03trail_fname.from'))

    def test_apply_root(self):
        treeroot = join(self.tmpdir, 'rootparent')
        shutil.copytree(join(TESTS, '06nested'), treeroot)
        pto = fromfile(join(TESTS, '06nested/06nested.patch'))
        self.assertTrue(pto.apply(root=treeroot))

    def test_apply_strip(self):
        treeroot = join(self.tmpdir, 'rootparent')
        shutil.copytree(join(TESTS, '06nested'), treeroot)
        pto = fromfile(join(TESTS, '06nested/06nested.patch'))
        for p in pto:
            p.source = b'nasty/prefix/' + p.source
            p.target = b'nasty/prefix/' + p.target
        self.assertTrue(pto.apply(strip=2, root=treeroot))

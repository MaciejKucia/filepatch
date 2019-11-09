import os
import unittest
from os import getcwd
from os.path import join, dirname, abspath

from filepatch import fromfile


TESTS = dirname(abspath(__file__))


class TestCheckPatched(unittest.TestCase):
    def setUp(self):
        self.save_cwd = getcwd()
        os.chdir(TESTS)

    def tearDown(self):
        os.chdir(self.save_cwd)

    def test_patched_multipatch(self):
        pto = fromfile("01uni_multi/01uni_multi.patch")
        os.chdir(join(TESTS, "01uni_multi", "[result]"))
        self.assertTrue(pto.can_patch(b"updatedlg.cpp"))

    def test_can_patch_single_source(self):
        pto2 = fromfile("02uni_newline.patch")
        self.assertTrue(pto2.can_patch(b"02uni_newline.from"))

    def test_can_patch_fails_on_target_file(self):
        pto3 = fromfile("03trail_fname.patch")
        self.assertEqual(None, pto3.can_patch(b"03trail_fname.to"))
        self.assertEqual(None, pto3.can_patch(b"not_in_source.also"))

    def test_multiline_false_on_other_file(self):
        pto = fromfile("01uni_multi/01uni_multi.patch")
        os.chdir(join(TESTS, "01uni_multi"))
        self.assertFalse(pto.can_patch(b"updatedlg.cpp"))

    def test_single_false_on_other_file(self):
        pto3 = fromfile("03trail_fname.patch")
        self.assertFalse(pto3.can_patch("03trail_fname.from"))

    def test_can_patch_checks_source_filename_even_if_target_can_be_patched(
            self):
        pto2 = fromfile("04can_patch.patch")
        self.assertFalse(pto2.can_patch("04can_patch.to"))

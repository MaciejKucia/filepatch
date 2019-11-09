import unittest

from filepatch.utils import xisabs, xnormpath, pathstrip, xstrip


class TestHelpers(unittest.TestCase):
    longMessage = True

    absolute = [b'/', b'c:\\', b'c:/', b'\\', b'/path', b'c:\\path']
    relative = [b'path', b'path:\\', b'path:/', b'path\\', b'path/',
                b'path\\path']

    def test_xisabs(self):
        for path in self.absolute:
            self.assertTrue(xisabs(path), 'Target path: ' + repr(path))
        for path in self.relative:
            self.assertFalse(xisabs(path), 'Target path: ' + repr(path))

    def test_xnormpath(self):
        path = b"../something/..\\..\\file.to.patch"
        self.assertEqual(xnormpath(path), b'../../file.to.patch')

    def test_xstrip(self):
        for path in self.absolute[:4]:
            self.assertEqual(xstrip(path), b'')
        for path in self.absolute[4:6]:
            self.assertEqual(xstrip(path), b'path')
        # test relative paths are not affected
        for path in self.relative:
            self.assertEqual(xstrip(path), path)

    def test_pathstrip(self):
        self.assertEqual(
            pathstrip(b'path/to/test/name.diff', 2), b'test/name.diff')
        self.assertEqual(pathstrip(b'path/name.diff', 1), b'name.diff')
        self.assertEqual(pathstrip(b'path/name.diff', 0), b'path/name.diff')

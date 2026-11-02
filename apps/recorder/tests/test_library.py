import stat
import tempfile
import unittest
from wysun_recorder.library import Library


class LibraryTests(unittest.TestCase):
    def test_new_directories_are_private_unique_and_inside_the_root(self):
        with tempfile.TemporaryDirectory() as folder:
            library = Library(folder)
            first, second = library.new_directory(), library.new_directory()
            self.assertNotEqual(first, second)
            self.assertEqual((first.parent, stat.S_IMODE(first.stat().st_mode)), (library.root, 0o700))


if __name__ == '__main__':
    unittest.main()

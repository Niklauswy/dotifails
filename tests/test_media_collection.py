"""Collections: explicit order, natural folder order, skipping vanished files, no wrap-around."""
import tempfile
import unittest
from pathlib import Path

import media_support as support

support.app()
from wysun_media.collection import Collection, scan  # noqa: E402


class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = support.fixtures()

    def folder(self, names):
        directory = tempfile.TemporaryDirectory(prefix='wysun-collection-')
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for name in names:
            (root / name).write_bytes((self.files / ('plain.png' if name.endswith('.png') else 'tone.mp3')).read_bytes())
        return root

    def test_scan_keeps_one_group_in_natural_order(self):
        root = self.folder(['img10.png', 'img2.png', 'a.mp3', 'img1.png', 'notes.txt'])
        self.assertEqual([Path(p).name for p in scan(root, 'image')], ['img1.png', 'img2.png', 'img10.png'])
        self.assertEqual([Path(p).name for p in scan(root, 'av')], ['a.mp3'])

    def test_explicit_order_is_kept(self):
        root = self.folder(['b.png', 'a.png', 'c.png'])
        collection = Collection()
        collection.set_explicit([root / 'c.png', root / 'a.png', root / 'b.png'], current=1)
        self.assertEqual([Path(p).name for p in collection.paths], ['c.png', 'a.png', 'b.png'])
        self.assertEqual(Path(collection.current).name, 'a.png')
        self.assertEqual(collection.position(), (2, 3))

    def test_follow_folder_arrives_asynchronously_and_keeps_current(self):
        root = self.folder(['img3.png', 'img1.png', 'img2.png'])
        collection = Collection()
        collection.follow_folder(root / 'img2.png', 'image')
        self.assertEqual(len(collection), 1)                      # immediately: just the file itself
        self.assertTrue(support.pump(lambda: len(collection) == 3))
        self.assertEqual([Path(p).name for p in collection.paths], ['img1.png', 'img2.png', 'img3.png'])
        self.assertEqual(Path(collection.current).name, 'img2.png')

    def test_ends_do_not_wrap_and_missing_files_are_skipped(self):
        root = self.folder(['a.png', 'b.png', 'c.png'])
        collection = Collection()
        collection.set_explicit([root / 'a.png', root / 'b.png', root / 'c.png'], current=0)
        self.assertIsNone(collection.move(-1))
        (root / 'b.png').unlink()
        self.assertEqual(Path(collection.move(1)).name, 'c.png')   # b vanished: skipped
        self.assertIsNone(collection.move(1))
        self.assertEqual(Path(collection.current).name, 'c.png')

    def test_remove_current_shows_the_next_one(self):
        root = self.folder(['a.png', 'b.png'])
        collection = Collection()
        collection.set_explicit([root / 'a.png', root / 'b.png'], current=1)
        self.assertEqual(Path(collection.remove_current()).name, 'a.png')
        self.assertEqual(collection.remove_current(), None)

    def test_a_late_scan_of_an_older_folder_is_ignored(self):
        first, second = self.folder(['x1.png', 'x2.png']), self.folder(['y1.png', 'y2.png', 'y3.png'])
        collection = Collection()
        collection.follow_folder(first / 'x1.png', 'image')
        collection.follow_folder(second / 'y1.png', 'image')
        self.assertTrue(support.pump(lambda: len(collection) == 3))
        support.settle(.2)
        self.assertEqual([Path(p).name for p in collection.paths], ['y1.png', 'y2.png', 'y3.png'])


if __name__ == '__main__':
    unittest.main()

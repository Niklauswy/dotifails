"""wysun_lanshare.media: the phone-compatible copies stay under a size cap, least recently watched out first."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))

from wysun_lanshare import media  # noqa: E402


class TrimTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, rel, size, used):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.truncate(size)
        os.utime(path, (used, used))
        return path

    def test_drops_least_recently_used_until_it_fits(self):
        old = self.make('aa/old.mp4', 400, 100)
        mid = self.make('bb/mid.mp4', 400, 200)
        new = self.make('cc/new.mp4', 400, 300)
        media.trim(self.dir, 900)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(mid))
        self.assertTrue(os.path.exists(new))

    def test_keeps_the_copy_being_served_even_if_alone_it_is_too_big(self):
        big = self.make('aa/big.mp4', 2000, 100)
        other = self.make('bb/other.mp4', 10, 300)
        media.trim(self.dir, 1000, keep=big)
        self.assertTrue(os.path.exists(big))
        self.assertFalse(os.path.exists(other))

    def test_leaves_unfinished_copies_and_failure_marks(self):
        part = self.make('aa/.x.123.tmp.mp4', 5000, 1)
        fail = self.make('aa/y.mp4.fail', 0, 1)
        media.trim(self.dir, 10)
        self.assertTrue(os.path.exists(part))
        self.assertTrue(os.path.exists(fail))

    def test_missing_folder_is_fine(self):
        media.trim(os.path.join(self.dir, 'nope'), 10)


class PlayableTests(unittest.TestCase):
    def test_a_cached_copy_is_marked_as_used_and_the_cache_trimmed(self):
        with tempfile.TemporaryDirectory() as home:
            source = os.path.join(home, 'clip.mp4')
            Path(source).write_bytes(b'x')
            originals = media.cache_dir, media.probe
            media.cache_dir = lambda: home
            media.probe = lambda path: {'vcodec': 'h264', 'level': 62, 'width': 1920, 'height': 1080, 'fps': 60}
            try:
                key = media.file_key(source, 'compat-4.2')
                cached = os.path.join(home, 'compat', key[:2], key + '.mp4')
                os.makedirs(os.path.dirname(cached))
                Path(cached).write_bytes(b'copy')
                os.utime(cached, (1, 1))
                stale = os.path.join(home, 'compat', 'zz', 'stale.mp4')
                os.makedirs(os.path.dirname(stale))
                with open(stale, 'wb') as f:
                    f.truncate(media.COMPAT_LIMIT)
                os.utime(stale, (2, 2))
                self.assertEqual(media.playable(source), cached)
                self.assertGreater(os.stat(cached).st_mtime, 2)
                self.assertFalse(os.path.exists(stale))
            finally:
                media.cache_dir, media.probe = originals


if __name__ == '__main__':
    unittest.main()

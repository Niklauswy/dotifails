"""wysun_core.h264: the H.264 level a video really needs (phones refuse anything declared above 5.2)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))

from wysun_core import h264  # noqa: E402


class LevelTests(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(h264.level_for(1024, 768, 30), '3.1')
        self.assertEqual(h264.level_for(1920, 1080, 30), '4.0')
        self.assertEqual(h264.level_for(1920, 1080, 60), '4.2')
        self.assertEqual(h264.level_for(1670, 404, 30), '3.1')
        self.assertEqual(h264.level_for(2560, 1440, 60), '5.1')
        self.assertEqual(h264.level_for(3840, 2160, 60), '5.2')
        self.assertIsNone(h264.level_for(7680, 4320, 60), 'beyond what phones decode: leave it')

    def test_too_high_for_phones(self):
        self.assertTrue(h264.too_high({'vcodec': 'h264', 'level': 62}))
        self.assertFalse(h264.too_high({'vcodec': 'h264', 'level': 42}))
        self.assertFalse(h264.too_high({'vcodec': 'hevc', 'level': 153}))
        self.assertFalse(h264.too_high({}))


if __name__ == '__main__':
    unittest.main()

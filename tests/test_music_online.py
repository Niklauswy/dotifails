"""«Para ti»: cross-list hits and artists you play rank first; songs you have or just heard are left out."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_music.online import CHARTS, recommend  # noqa: E402

ARTIST = {'a1': 'x', 'a2': 'x', 'a3': 'x', 'b': 'y', 'c': 'z', 'd': 'fav', 'mine': 'w', 'heard': 'w'}


class RecommendTests(unittest.TestCase):
    def test_ranks_cross_list_and_known_artists_first(self):
        charts = [['c', 'b', 'a1', 'd'], ['b', 'a2']]
        got = recommend(charts, {'fav': 1.0}, set(), set(), ARTIST.get)
        self.assertEqual(got[0], 'd', 'an artist you play a lot wins')
        self.assertEqual(got[1], 'b', 'then what is in several lists')

    def test_excludes_local_and_recent_and_caps_artists(self):
        charts = [['mine', 'heard', 'a1', 'a2', 'a3', 'b']]
        got = recommend(charts, {}, {'mine'}, {'heard'}, ARTIST.get)
        self.assertNotIn('mine', got)
        self.assertNotIn('heard', got)
        self.assertEqual([k for k in got if ARTIST[k] == 'x'], ['a1', 'a2'])
        self.assertEqual(len(recommend([list(ARTIST)], {}, set(), set(), lambda k: k, limit=3)), 3)

    def test_chart_ids_are_unique(self):
        self.assertEqual(len({c[0] for c in CHARTS}), len(CHARTS))
        self.assertTrue(all(len(c[2]) == 22 for c in CHARTS))


if __name__ == '__main__':
    unittest.main()

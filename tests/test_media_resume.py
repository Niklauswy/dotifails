"""Remembered positions: only long files, never near the ends, bounded, private, tolerant of damage."""
import json
import stat
import tempfile
import unittest
from pathlib import Path

import media_support as support

support.app()
from wysun_media import resume  # noqa: E402
from wysun_media.source import MediaSource  # noqa: E402


def source(name='movie.mkv', size=10, mtime=1):
    return MediaSource(Path('/media') / name, 'video', size, mtime)


class ResumeTests(unittest.TestCase):
    def positions(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        return resume.Positions(Path(root.name) / 'state/positions.json')

    def test_long_files_are_remembered(self):
        positions = self.positions()
        positions.put(source(), 1234.5, 3600)
        self.assertEqual(positions.get(source()), 1234.5)

    def test_short_files_and_edges_are_forgotten(self):
        positions = self.positions()
        positions.put(source('short.mp4'), 100, 200)
        self.assertIsNone(positions.get(source('short.mp4')))
        positions.put(source(), 1000, 3600)
        positions.put(source(), 3, 3600)                  # barely started: start over
        self.assertIsNone(positions.get(source()))
        positions.put(source(), 1000, 3600)
        positions.put(source(), 3595, 3600)               # finished
        self.assertIsNone(positions.get(source()))

    def test_a_replaced_file_does_not_inherit_the_position(self):
        positions = self.positions()
        positions.put(source(size=10), 1000, 3600)
        self.assertIsNone(positions.get(source(size=11)))
        self.assertIsNone(positions.get(source(mtime=2)))

    def test_survives_a_new_instance_and_is_private(self):
        positions = self.positions()
        positions.put(source(), 1000, 3600)
        again = resume.Positions(positions.path)
        self.assertEqual(again.get(source()), 1000)
        self.assertEqual(stat.S_IMODE(positions.path.stat().st_mode), 0o600)
        self.assertNotIn('/media', positions.path.read_text())     # keyed by hash, no paths on disk

    def test_entries_are_bounded(self):
        positions = self.positions()
        for number in range(resume.MAX_ENTRIES + 25):
            positions.put(source(f'm{number}.mkv'), 1000, 3600)
        self.assertLessEqual(len(json.loads(positions.path.read_text())), resume.MAX_ENTRIES)

    def test_damaged_or_hostile_state_is_ignored(self):
        positions = self.positions()
        positions.path.parent.mkdir(parents=True)
        for content in ('{not json', '[]', '"x"', json.dumps({resume.key(source()): 'bad'}), 'x' * (resume.LIMIT + 1)):
            positions.path.write_text(content)
            fresh = resume.Positions(positions.path)
            self.assertIsNone(fresh.get(source()), content[:20])
            fresh.put(source(), 1000, 3600)                         # and it can be repaired
            self.assertEqual(resume.Positions(positions.path).get(source()), 1000)


if __name__ == '__main__':
    unittest.main()

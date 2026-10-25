"""wysun_core.jsonio writes atomically with private defaults and reads defensively."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wysun'))
from wysun_core import jsonio


class JsonIOTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_rewrite_keeps_mode_and_new_file_is_private(self):
        shared = self.root / 'shared.lua'
        shared.write_text('old')
        shared.chmod(0o644)
        jsonio.atomic_write_text(shared, 'new')
        self.assertEqual((shared.read_text(), shared.stat().st_mode & 0o777), ('new', 0o644))
        fresh = self.root / 'state' / 'fresh.json'
        jsonio.atomic_write_text(fresh, '{}')
        self.assertEqual(fresh.stat().st_mode & 0o777, 0o600)
        self.assertEqual(fresh.parent.stat().st_mode & 0o777, 0o700)
        jsonio.atomic_write_bytes(fresh, b'1', mode=0o640)
        self.assertEqual(fresh.stat().st_mode & 0o777, 0o640)

    def test_failure_leaves_target_and_no_temporary(self):
        target = self.root / 'data.json'
        target.write_text('keep')
        with self.assertRaises(RuntimeError):
            with jsonio.atomic_path(target) as temporary:
                temporary.write_text('partial')
                raise RuntimeError('boom')
        self.assertEqual(target.read_text(), 'keep')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['data.json'])

    def test_json_round_trip_is_utf8_with_newline(self):
        target = self.root / 'song.json'
        data = {'nombre': 'canción', 'n': [1, 2]}
        jsonio.atomic_write_json(target, data)
        self.assertTrue(target.read_bytes().endswith(b'}\n'))
        self.assertIn('canción', target.read_text(encoding='utf-8'))
        self.assertEqual(jsonio.read_json(target), data)

    def test_invalid_json_returns_default_unless_strict(self):
        broken = self.root / 'broken.json'
        broken.write_text('{')
        default = {'a': 1}
        result = jsonio.read_json(broken, default)
        self.assertEqual(result, default)
        self.assertIsNot(result, default)
        with self.assertRaises(ValueError) as caught:
            jsonio.read_json(broken, strict=True)
        self.assertIn(str(broken), str(caught.exception))
        broken.write_bytes(b'\xff\xfe')
        self.assertIsNone(jsonio.read_json(broken))

    def test_missing_file_returns_copy_of_default(self):
        default = {'k': []}
        result = jsonio.read_json(self.root / 'missing.json', default)
        result['k'].append(1)
        self.assertEqual(default, {'k': []})
        self.assertIsNone(jsonio.read_json(self.root / 'missing.json'))

    def test_nan_is_rejected(self):
        target = self.root / 'nan.json'
        with self.assertRaises(ValueError):
            jsonio.atomic_write_json(target, {'x': float('nan')})
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()

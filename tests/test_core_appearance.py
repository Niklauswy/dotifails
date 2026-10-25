"""wysun_core.appearance: opacity and reduced motion, shared by every Wysun program."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wysun'))
from wysun_core import appearance  # noqa: E402


class AppearanceTests(unittest.TestCase):
    def test_defaults_clamp_and_keep_unknown_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.config/orbit/appearance.json'
            self.assertEqual(appearance.read_appearance(tmp), appearance.DEFAULTS)
            path.parent.mkdir(parents=True)
            path.write_text('{"custom": "keep"}')
            appearance.save_appearance(dict(opacity=2, reduced_motion=True), tmp)
            self.assertEqual(appearance.read_appearance(tmp), {'opacity': 65, 'reduced_motion': True})
            self.assertEqual(json.loads(path.read_text())['custom'], 'keep')
            path.write_text('[]')
            with self.assertRaises(ValueError):
                appearance.save_appearance(dict(opacity=90, reduced_motion=False), tmp)

    def test_reduced_motion_from_environment_or_preference(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'ORBIT_REDUCED_MOTION': ''}):
            self.assertFalse(appearance.reduced_motion(tmp))
            os.environ['ORBIT_REDUCED_MOTION'] = 'true'
            self.assertTrue(appearance.reduced_motion(tmp))
            os.environ['ORBIT_REDUCED_MOTION'] = ''
            appearance.save_appearance(dict(opacity=80, reduced_motion=True), tmp)
            self.assertTrue(appearance.reduced_motion(tmp))


if __name__ == '__main__':
    unittest.main()

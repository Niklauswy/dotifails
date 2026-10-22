"""Native Colors preserves the existing store and serializes rapid edits."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'apps/shell/modules/colors/backend.py'


class ColorsBridgeTests(unittest.TestCase):
    def test_shortcut_picks_and_panel_has_its_own_binding(self):
        config = (ROOT / 'config/.config/wysun/hyprland.lua').read_text()
        self.assertIn('hl.bind("SUPER + SHIFT + C", hl.dsp.exec_cmd("wysun color-pick")', config)
        self.assertIn('hl.bind("SUPER + ALT + C", hl.dsp.exec_cmd("wysun colors")', config)

    def test_existing_palette_parse_save_and_toggle(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = home / '.local/share/orbit/colors.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'favorites': ['#123456'], 'recent': ['#ABCDEF']}))
            requests = [
                {'action': 'read'},
                {'action': 'parse', 'color': 'rgb(255, 0, 0)', 'revision': 7},
                {'action': 'parse', 'color': 'hsl(120, 100%, 50%)', 'revision': 8},
                {'action': 'parse', 'color': 'not a color', 'revision': 9},
                {'action': 'save', 'color': '#FF0000'},
                {'action': 'favorite', 'color': '#FF0000'},
                {'action': 'favorite', 'color': '#123456'},
            ]
            run = subprocess.run(['/usr/bin/python3', str(BACKEND)], input=''.join(json.dumps(r)+'\n' for r in requests),
                                 text=True, capture_output=True, env=dict(os.environ, HOME=directory), check=True)
            rows = [json.loads(line) for line in run.stdout.splitlines()]
            self.assertEqual(rows[0]['data']['favorites'], ['#123456'])
            self.assertEqual(rows[1]['color'], '#FF0000')
            self.assertEqual(rows[1]['revision'], 7)
            self.assertEqual(rows[2]['color'], '#00FF00')
            self.assertIn('error', rows[3])
            self.assertEqual(rows[3]['revision'], 9)
            self.assertEqual(rows[4]['data']['recent'], ['#FF0000', '#ABCDEF'])
            self.assertEqual(rows[6]['data']['favorites'], ['#FF0000'])
            self.assertEqual(json.loads(path.read_text()), rows[6]['data'])

    def test_bad_request_does_not_kill_service(self):
        with tempfile.TemporaryDirectory() as directory:
            run = subprocess.run(['/usr/bin/python3', str(BACKEND)], input='invalid\n[]\n{"action":"read"}\n',
                                 text=True, capture_output=True, env=dict(os.environ, HOME=directory), check=True)
            rows = [json.loads(line) for line in run.stdout.splitlines()]
            self.assertIn('error', rows[0]); self.assertIn('error', rows[1]); self.assertIn('data', rows[2])

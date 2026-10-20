"""Wysun picker for xdg-desktop-portal-hyprland: one-shot Recorder requests."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class SharePickerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wysun-picker-')
        self.addCleanup(self.tmp.cleanup)
        self.runtime = Path(self.tmp.name)
        self.module = runpy.run_path(str(ROOT / 'bin/wysun-share-picker'))
        self.path = self.runtime / 'loomrec-share-request.json'

    def write(self, **data):
        self.path.write_text(json.dumps(data))

    def run_picker(self):
        out = io.StringIO()
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(self.runtime)}), \
             patch('os.execvp', side_effect=SystemExit('fallback')) as fallback, \
             contextlib.redirect_stdout(out):
            try:
                self.module['main']()
            except SystemExit as stop:
                self.assertEqual(str(stop), 'fallback')
        return out.getvalue(), fallback.called

    def test_fresh_request_answers_once_with_restore_flag(self):
        self.write(output='DP-1', time=time.time())
        self.assertEqual(self.run_picker(), ('[SELECTION]r/screen:DP-1\n', False))
        self.assertFalse(self.path.exists())
        self.assertEqual(list(self.runtime.iterdir()), [])
        # One shot: the next client (for example a browser) gets the real picker.
        self.assertEqual(self.run_picker(), ('', True))

    def test_stale_invalid_or_linked_requests_fall_back(self):
        self.write(output='DP-1', time=time.time() - 60)
        self.assertEqual(self.run_picker(), ('', True))
        self.write(output='DP-1/../x', time=time.time())
        self.assertEqual(self.run_picker(), ('', True))
        self.write(output='DP-1', time=time.time() + 60)
        self.assertEqual(self.run_picker(), ('', True))
        target = self.runtime / 'elsewhere.json'
        target.write_text(json.dumps({'output': 'DP-1', 'time': time.time()}))
        self.path.symlink_to(target)
        self.assertEqual(self.run_picker(), ('', True))
        self.assertTrue(target.exists())

    def test_xdph_config_keeps_shared_memory_frames(self):
        import sys
        sys.path.insert(0, str(ROOT / 'installer'))
        from wayland import xdph_config
        text = xdph_config('/home/fixture')
        self.assertIn('force_shm = true', text)
        self.assertIn('allow_token_by_default = true', text)
        self.assertIn('custom_picker_binary = /home/fixture/.local/bin/wysun-share-picker', text)

    def test_installer_publishes_picker(self):
        text = (ROOT / 'installer/wayland.py').read_text()
        self.assertEqual(text.count("'wysun-share-picker'"), 2)


if __name__ == '__main__':
    unittest.main()

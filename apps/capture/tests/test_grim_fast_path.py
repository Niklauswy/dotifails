"""Whole-desktop still frames from grim on Hyprland, with portal fallback."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
QApplication.instance() or QApplication([])
from loomrec import portal_image

HYPR = {'HYPRLAND_INSTANCE_SIGNATURE': 'fixture', 'WAYLAND_DISPLAY': 'fixture'}
PPM = b'P6\n3 2\n255\n' + bytes([10, 20, 30]) * 6  # synthetic pixels only


class GrimFastPathTests(unittest.TestCase):
    def test_raw_ppm_from_stdout_becomes_image_without_files(self):
        done = subprocess.CompletedProcess([], 0, PPM, b'')
        with patch.dict(os.environ, HYPR), patch('shutil.which', return_value='/usr/bin/grim'), \
             patch('subprocess.run', return_value=done) as run:
            image = portal_image.grim_image()
        self.assertEqual((image.width(), image.height()), (3, 2))
        self.assertEqual(run.call_args.args[0], ['/usr/bin/grim', '-t', 'ppm', '-'])

    def test_failures_fall_back_to_the_screenshot_portal(self):
        with patch.dict(os.environ, HYPR), patch('shutil.which', return_value='/usr/bin/grim'), \
             patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'grim')):
            self.assertIsNone(portal_image.grim_image())
        with patch.dict(os.environ, HYPR), patch('shutil.which', return_value='/usr/bin/grim'), \
             patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, b'not an image', b'')):
            self.assertIsNone(portal_image.grim_image())
        with patch.dict(os.environ, {'HYPRLAND_INSTANCE_SIGNATURE': ''}), patch('subprocess.run') as run:
            self.assertIsNone(portal_image.grim_image())
            run.assert_not_called()

    def test_desktop_image_prefers_grim_and_skips_portal(self):
        sentinel = object()
        with patch.object(portal_image, 'grim_image', return_value=sentinel), \
             patch('loomrec.portal.Portal', side_effect=AssertionError('portal used')):
            self.assertIs(portal_image.desktop_image(), sentinel)


if __name__ == '__main__':
    unittest.main()

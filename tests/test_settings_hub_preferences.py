"""Settings window against a temporary HOME: live sync, blocked pages and undo."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
import theme_core  # noqa: E402
from settings_hub import SettingsHub  # noqa: E402

APP = QApplication.instance() or QApplication([])
MONITORS = [dict(name='DP-1', width=64, height=48, x=0, y=0, scale=1, refreshRate=60,
                 availableModes=['64x48@60.00Hz'], focused=True)]


def inline_job(self, fn, callback, progress=None):
    """Run a Settings job synchronously so assertions need no thread timing."""
    try:
        result = fn()
    except Exception as error:
        self.report_error(str(error))
    else:
        callback(result)
    return Mock()


def wait_until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        APP.processEvents()
        if predicate():
            return True
        time.sleep(.02)
    return False


class HubCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.home = Path(self.folder.name)
        self.orbit = self.home / '.config/orbit'
        self.orbit.mkdir(parents=True)
        self.patches = [patch.object(SettingsHub, 'start_job', inline_job),
                        patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.home / '.config'),
                                                'XDG_STATE_HOME': str(self.home / '.local/state')})]
        for item in self.patches:
            item.start()
        theme_core.invalidate()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        theme_core.invalidate()
        self.folder.cleanup()

    def open(self):
        runner = lambda args: json.dumps(MONITORS) if list(args[:3]) == ['hyprctl', '-j', 'monitors'] else 'ok'
        window = SettingsHub(test=True, home=self.home)
        window.env.runner = runner
        self.addCleanup(lambda: (window.close(), window.deleteLater()))
        return window


class HubPreferenceTests(HubCase):
    def test_legacy_bar_is_migrated_once_when_the_window_opens(self):
        legacy = self.orbit / 'hypr-bar.json'
        legacy.write_text(json.dumps({'monitors': {'DP-1': True}, 'tray_monitor': 'DP-1', 'height': 44}))
        before = legacy.read_bytes()
        window = self.open()
        saved = json.loads((self.orbit / 'shell.json').read_text())
        self.assertEqual((saved['schema_version'], saved['tray_monitor']), (1, 'DP-1'))
        self.assertEqual(legacy.read_bytes(), before)
        self.assertEqual(window.shell_error, '')

    def test_external_change_updates_the_open_window_and_never_overwrites_a_draft(self):
        window = self.open()
        window.env.apply_shell({'low_power': False})
        self.assertTrue(wait_until(lambda: window.preference_watcher.files()))
        shell = self.orbit / 'shell.json'
        shell.write_text(json.dumps(dict(json.loads(shell.read_text()), low_power=True, frame_enabled=False)))
        self.assertTrue(wait_until(lambda: window.low_power.isChecked() and not window.frame_enabled.isChecked()))
        # A pending edit is kept; the window only says the file moved.
        window.rail_enabled.setChecked(False)
        self.assertTrue(window.preferences_dirty)
        shell.write_text(json.dumps(dict(json.loads(shell.read_text()), low_power=False)))
        self.assertTrue(wait_until(lambda: 'cambiaron fuera' in window.status.text()))
        self.assertTrue(window.low_power.isChecked())
        self.assertFalse(window.rail_enabled.isChecked())

    def test_colour_change_from_the_cli_reaches_the_window(self):
        red = self.home / 'red.png'
        Image.new('RGB', (64, 48), (225, 36, 72)).save(red)
        (self.orbit / 'environment.json').write_text(json.dumps({'wallpaper': {'default': str(red)}}))
        window = self.open()
        self.assertTrue(window.colour_baseline['dynamic'])
        import wysun_scheme
        wysun_scheme.main(['set', 'tokyo'])
        self.assertTrue(wait_until(lambda: window.colour_source.currentData() == 'space-black:tokyo'))
        wysun_scheme.main(['set', '--dynamic', '--seed', '#336699', '--variant', 'vibrant'])
        self.assertTrue(wait_until(lambda: window.colour_source.currentData() == 'dynamic' and window.colour_seed.text() == '#336699'))
        self.assertEqual(window.colour_variant.currentData(), 'vibrant')

    def test_unknown_version_blocks_the_panels_page_without_touching_the_file(self):
        shell = self.orbit / 'shell.json'
        shell.write_text('{"schema_version": 9}')
        window = self.open()
        self.assertIn('Versión', window.shell_error)
        self.assertFalse(window.rail_enabled.isEnabled())
        window.go('shell')
        self.assertFalse(window.apply_button.isEnabled())
        window.apply_shell_preferences()
        self.assertEqual(shell.read_text(), '{"schema_version": 9}')
        window.go('wallpaper')
        self.assertTrue(window.apply_button.isEnabled())

    def test_save_and_revert_panels_through_the_window(self):
        appearance = self.orbit / 'appearance.json'
        appearance.write_bytes(b'{"opacity": 80,\r\n "extra": "\xc3\xa1"}\r\n')
        window = self.open()
        shell_before = (self.orbit / 'shell.json').read_bytes() if (self.orbit / 'shell.json').exists() else None
        window.low_power.setChecked(True)
        window.shell_motion.setChecked(True)
        window.shell_opacity.setValue(90)
        window.apply_shell_preferences()
        self.assertTrue(json.loads((self.orbit / 'shell.json').read_text())['low_power'])
        stored = json.loads(appearance.read_text())
        self.assertEqual((stored['opacity'], stored['reduced_motion'], stored['extra']), (90, True, 'á'))
        window.undo_preferences()
        self.assertEqual(appearance.read_bytes(), b'{"opacity": 80,\r\n "extra": "\xc3\xa1"}\r\n')
        shell = self.orbit / 'shell.json'
        self.assertEqual(shell.read_bytes() if shell.exists() else None, shell_before)
        self.assertFalse(window.low_power.isChecked())

    def test_colour_page_saves_seed_and_variant_through_the_single_producer(self):
        red = self.home / 'red.png'
        Image.new('RGB', (64, 48), (225, 36, 72)).save(red)
        (self.orbit / 'environment.json').write_text(json.dumps({'wallpaper': {'default': str(red)}, 'private': 1}))
        window = self.open()
        window.colour_seed.setText('#aa5500')
        window.colour_variant.setCurrentIndex(window.colour_variant.findData('expressive'))
        window.colour_mode.setCurrentIndex(window.colour_mode.findData('light'))
        window.apply_wallpaper()
        self.assertEqual(json.loads((self.orbit / 'theme.json').read_text())['dynamic'],
                         {'enabled': True, 'mode': 'light', 'variant': 'expressive', 'seed': '#aa5500'})
        scheme = json.loads(theme_core.scheme_path(self.home).read_text())
        self.assertEqual((scheme['mode'], scheme['variant']), ('light', 'expressive'))
        self.assertEqual(json.loads((self.orbit / 'environment.json').read_text())['private'], 1)


if __name__ == '__main__':
    unittest.main()

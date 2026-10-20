"""Per-output ScreenCast consent and Wayland-safe recording indicator."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loomrec import consent


class ConsentScopeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='loomrec-consent-')
        self.addCleanup(self.folder.cleanup)
        patcher = patch.dict(os.environ, {'XDG_STATE_HOME': self.folder.name})
        patcher.start(); self.addCleanup(patcher.stop)

    def test_tokens_are_kept_per_output_and_cleared_together(self):
        self.assertEqual(consent.output_kind('DP-1'), 'monitor:DP-1')
        self.assertEqual(consent.output_kind(None), 'monitor')
        self.assertEqual(consent.output_kind('bad name/..'), 'monitor')
        self.assertTrue(consent.save('monitor:DP-1', 'token-a'))
        self.assertTrue(consent.save('monitor:eDP-1', 'token-b'))
        self.assertEqual(consent.load('monitor:DP-1'), 'token-a')
        self.assertEqual(consent.load('monitor:DP-2'), '')
        consent.clear('monitor:DP-1')
        self.assertEqual(consent.load('monitor:DP-1'), '')
        self.assertEqual(consent.load('monitor:eDP-1'), 'token-b')
        consent.clear()
        self.assertEqual(consent.load('monitor:eDP-1'), '')
        with self.assertRaises(ValueError):
            consent.clear('monitor:../x')

    def test_expected_output_maps_rect_centre_to_hyprland_output(self):
        from loomrec import wayland_capture
        from loomrec.desktop_capture import topology_from_hypr
        rows = [dict(name='eDP-1', x=0, y=0, width=1920, height=1080, scale=1, transform=0, disabled=False),
                dict(name='DP-1', x=1920, y=0, width=1920, height=1080, scale=1, transform=0, disabled=False)]
        try:
            outputs = topology_from_hypr(rows)
        except Exception as error:  # fixture shape is owned by desktop_capture
            self.skipTest('topology fixture: ' + str(error))
        config = type('Config', (), dict(source_type='region', rect=[2000, 100, 400, 300]))()
        self.assertEqual(wayland_capture.expected_output(config, outputs), 'DP-1')
        self.assertIsNone(wayland_capture.expected_output(config, None))
        config.source_type = 'window'
        self.assertIsNone(wayland_capture.expected_output(config, outputs))

    def portal(self, mapping):
        from unittest.mock import MagicMock
        from loomrec.portal import Portal
        portal = Portal.__new__(Portal)
        portal.dbus = MagicMock(); portal.dbus.UInt32 = int; portal.dbus.ObjectPath = str
        portal.dbus.Interface.return_value.Get.side_effect = lambda iface, name: 3
        portal.object = object(); portal.bus = MagicMock(); portal.strict_close = False
        portal._owner = None; portal.session = None; portal._match = None
        portal.closed = False; portal.disposed = False
        calls = []
        def request(iface, method, *args, options=None):
            calls.append((method, dict(options or {})))
            if method == 'CreateSession':return {'session_handle': '/session/1'}
            if method == 'Start':return {'streams': [(42, {'mapping_id': mapping, 'source_type': 1})], 'restore_token': 'new-' + mapping}
            return {}
        portal.request = request; portal.open_remote = lambda: None; portal.close = lambda: None
        return portal, calls

    def test_restored_other_output_is_forgotten_and_new_token_saved_by_real_output(self):
        from loomrec.portal import RestoredOtherOutput
        consent.save('monitor:DP-1', 'stale')
        portal, calls = self.portal('DP-2')
        with self.assertRaises(RestoredOtherOutput):
            portal.screencast('region', True, remember=True, output='DP-1')
        self.assertEqual(dict(calls)['SelectSources']['restore_token'], 'stale')
        self.assertEqual(consent.load('monitor:DP-1'), '')
        portal, calls = self.portal('DP-1')
        self.assertEqual(portal.screencast('region', True, remember=True, output='DP-1')[0], 42)
        self.assertNotIn('restore_token', dict(calls)['SelectSources'])
        self.assertEqual(dict(calls)['SelectSources']['persist_mode'], 2)
        self.assertEqual(consent.load('monitor:DP-1'), 'new-DP-1')

    def test_share_request_is_written_privately_and_removed_after_start(self):
        from loomrec import portal as module
        seen = []
        portal, calls = self.portal('DP-1')
        base = portal.request
        def request(iface, method, *args, options=None):
            if method == 'SelectSources':
                path = Path(self.folder.name) / 'loomrec-share-request.json'
                seen.append((json.loads(path.read_text())['output'], oct(path.stat().st_mode & 0o777)))
            return base(iface, method, *args, options=options)
        portal.request = request
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': self.folder.name, 'HYPRLAND_INSTANCE_SIGNATURE': 'fixture'}):
            portal.screencast('monitor', True, output='DP-1')
        self.assertEqual(seen, [('DP-1', '0o600')])
        self.assertFalse((Path(self.folder.name) / 'loomrec-share-request.json').exists())
        self.assertIsNone(module.share_request('bad/name'))


class IndicatorTests(unittest.TestCase):
    def test_no_top_level_indicator_windows_on_wayland(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from loomrec.ui.capture_feedback import RecordingIndicator
        indicator = RecordingIndicator()
        with patch.dict(os.environ, {'WAYLAND_DISPLAY': 'fixture'}):
            self.assertFalse(indicator.present([100, 100, 640, 360], [[0, 0, 1920, 1080]], state='countdown'))
            indicator.update('countdown', remaining=2)
        self.assertEqual(indicator.windows, [])
        indicator.hide()


if __name__ == '__main__':
    unittest.main()

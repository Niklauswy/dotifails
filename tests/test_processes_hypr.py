"""Wysun Processes: Hyprland windows and the shell IPC client (core/hypr.py) with fake runners."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_processes.core import hypr  # noqa: E402

CLIENTS = [
    {'address': '0xaa', 'pid': 3011, 'class': 'firefox', 'title': 'GitHub', 'workspace': {'id': 1, 'name': '1'},
     'focusHistoryID': 1, 'monitor': 0, 'mapped': True, 'hidden': False, 'size': [1600, 900]},
    {'address': '0xbb', 'pid': 22010, 'class': 'kitty', 'title': 'btop', 'workspace': {'id': 2, 'name': '2'},
     'focusHistoryID': 0, 'monitor': 0, 'mapped': True, 'hidden': False, 'size': [700, 1200]},
    {'address': '0xcc', 'pid': 1, 'class': '', 'title': '', 'workspace': {'id': -1, 'name': ''},
     'focusHistoryID': 5, 'monitor': -1, 'mapped': False, 'hidden': True},
]

MONITORS = [
    {'id': 1, 'name': 'DP-1', 'make': 'LG Electronics', 'model': 'LG ULTRAGEAR', 'x': 1920, 'y': 0,
     'activeWorkspace': {'id': 7, 'name': '7'}, 'disabled': False},
    {'id': 2, 'name': 'DP-2', 'make': 'Philips Consumer Electronics Company', 'model': 'PHL 271E1', 'x': 0, 'y': 0,
     'activeWorkspace': {'id': 3, 'name': '3'}, 'disabled': False},
    {'id': 3, 'name': 'HDMI-A-1', 'make': 'Unknown', 'model': 'Unknown', 'x': 3840, 'y': 0,
     'activeWorkspace': {'id': 1, 'name': '1'}, 'disabled': True},
]


class Runner:
    def __init__(self, fail=()):
        self.calls, self.fail = [], fail

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[0] in self.fail:
            raise FileNotFoundError(cmd[0])
        if cmd[:2] == ['hyprctl', '-j'] and cmd[2] == 'clients':
            return subprocess.CompletedProcess(cmd, 0, json.dumps(CLIENTS), '')
        if cmd[:2] == ['hyprctl', '-j'] and cmd[2] == 'monitors':
            return subprocess.CompletedProcess(cmd, 0, json.dumps(MONITORS), '')
        if cmd[:2] == ['hyprctl', '-j'] and cmd[2] == 'activeworkspace':
            return subprocess.CompletedProcess(cmd, 0, '{"id": 2}', '')
        if cmd[:2] == ['wysun-shell', 'thumbs']:
            return subprocess.CompletedProcess(cmd, 0, '{"0xaa": "/run/x/0xaa.png"}\n', '')
        if cmd[:2] == ['wysun-shell', 'locate']:
            return subprocess.CompletedProcess(cmd, 0, 'true\n', '')
        return subprocess.CompletedProcess(cmd, 0, 'ok\n', '')


class HyprTests(unittest.TestCase):
    def test_windows(self):
        windows = hypr.Hypr(run=Runner()).windows()
        self.assertEqual([w['address'] for w in windows], ['0xaa', '0xbb'])
        self.assertEqual(windows[1], dict(address='0xbb', pid=22010, app_id='kitty', title='btop', workspace=2,
                                          active=True, monitor=0, size=[700, 1200]))

    def test_monitors(self):
        monitors = hypr.Hypr(run=Runner()).monitors()
        self.assertEqual([m['id'] for m in monitors], [1, 2])        # disabled outputs are not columns
        self.assertEqual(monitors[1], dict(id=2, name='DP-2', make='Philips Consumer Electronics Company',
                                           model='PHL 271E1', x=0, y=0, activeWorkspace=3, dpms=True))

    def test_monitors_without_hyprctl(self):
        self.assertEqual(hypr.Hypr(run=Runner(fail=('hyprctl',))).monitors(), [])

    def test_monitors_report_dpms(self):
        class Off(Runner):
            def __call__(self, cmd, **kw):
                if cmd[:3] == ['hyprctl', '-j', 'monitors']:
                    self.calls.append(cmd)
                    return subprocess.CompletedProcess(cmd, 0, json.dumps([dict(MONITORS[0], dpmsStatus=False)]), '')
                return super().__call__(cmd, **kw)
        self.assertEqual([m['dpms'] for m in hypr.Hypr(run=Off()).monitors()], [False])

    def test_active_workspace(self):
        self.assertEqual(hypr.Hypr(run=Runner()).active_workspace(), 2)

    def test_focus_and_close_dispatch(self):
        runner = Runner()
        h = hypr.Hypr(run=runner)
        h.focus('0xaa')
        h.close('0xaa')
        self.assertEqual(runner.calls[-2], ['hyprctl', 'dispatch', 'hl.dsp.focus({window="address:0xaa"})'])
        self.assertEqual(runner.calls[-1], ['hyprctl', 'dispatch', 'hl.dsp.window.close({window="address:0xaa"})'])

    def test_classic_config_falls_back_to_dispatcher_words(self):
        class Classic(Runner):
            def __call__(self, cmd, **kw):
                self.calls.append(cmd)
                ok = cmd[:2] == ['hyprctl', 'dispatch'] and not cmd[2].startswith('hl.')
                return subprocess.CompletedProcess(cmd, 0, 'ok\n' if ok else 'error\n', '')
        runner = Classic()
        self.assertTrue(hypr.Hypr(run=runner).focus('0xaa'))
        self.assertEqual(runner.calls[-1], ['hyprctl', 'dispatch', 'focuswindow', 'address:0xaa'])

    def test_rejects_bad_address(self):
        with self.assertRaises(ValueError):
            hypr.Hypr(run=Runner()).focus('0xaa; rm -rf')

    def test_shell_ipc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / '0xaa.png')
            Path(path).write_bytes(b'png')

            class Existing(Runner):
                def __call__(self, cmd, **kw):
                    if cmd[:2] == ['wysun-shell', 'thumbs']:
                        self.calls.append(cmd)
                        return subprocess.CompletedProcess(cmd, 0, json.dumps({'0xaa': path}), '')
                    return super().__call__(cmd, **kw)
            runner = Existing()
            h = hypr.Hypr(run=runner)
            self.assertEqual(h.thumbnails(['0xaa', '0xbb']), {'0xaa': path})
            self.assertEqual(runner.calls[-1], ['wysun-shell', 'thumbs', '0xaa,0xbb'])   # the old 480 px request
            h.thumbnails(['0xaa'], 900)
            self.assertEqual(runner.calls[-1], ['wysun-shell', 'thumbs', '0xaa', '900'])
            self.assertTrue(h.locate('0xaa'))

    def test_capture_width_is_clamped_or_omitted(self):
        self.assertIsNone(hypr.capture_width(None))          # the shell's default stays 480 px
        self.assertIsNone(hypr.capture_width('nope'))
        self.assertEqual(hypr.capture_width(900), 900)
        self.assertEqual(hypr.capture_width('832.4'), 832)
        self.assertEqual(hypr.capture_width(20), 160)
        self.assertEqual(hypr.capture_width(9999), 1920)

    def test_stale_thumbnail_paths_are_not_returned(self):
        # The shell remembers what it wrote; a file removed since then must not be handed to QML.
        self.assertEqual(hypr.Hypr(run=Runner()).thumbnails(['0xaa']), {})

    def test_shell_unavailable(self):
        h = hypr.Hypr(run=Runner(fail=('wysun-shell', 'hyprctl')))
        self.assertEqual(h.thumbnails(['0xaa']), {})
        self.assertFalse(h.locate('0xaa'))
        self.assertEqual(h.windows(), [])

    def test_windows_by_app(self):
        rows = [dict(pid=3011, ppid=1500, app='firefox'), dict(pid=22010, ppid=1500, app='kitty'),
                dict(pid=22050, ppid=22010, app='kitty'), dict(pid=1500, ppid=1, app='Hyprland')]
        windows = hypr.Hypr(run=Runner()).windows()
        grouped = hypr.windows_by_app(windows, rows)
        self.assertEqual({k: [w['address'] for w in v] for k, v in grouped.items()}, {'firefox': ['0xaa'], 'kitty': ['0xbb']})


if __name__ == '__main__':
    unittest.main()

"""Wysun Processes: Hyprland windows and the shell IPC client (core/hypr.py) with fake runners."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_processes.core import hypr  # noqa: E402

CLIENTS = [
    {'address': '0xaa', 'pid': 3011, 'class': 'firefox', 'title': 'GitHub', 'workspace': {'id': 1, 'name': '1'},
     'focusHistoryID': 1, 'monitor': 0, 'mapped': True, 'hidden': False},
    {'address': '0xbb', 'pid': 22010, 'class': 'kitty', 'title': 'btop', 'workspace': {'id': 2, 'name': '2'},
     'focusHistoryID': 0, 'monitor': 0, 'mapped': True, 'hidden': False},
    {'address': '0xcc', 'pid': 1, 'class': '', 'title': '', 'workspace': {'id': -1, 'name': ''},
     'focusHistoryID': 5, 'monitor': -1, 'mapped': False, 'hidden': True},
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
                                          active=True, monitor=0))

    def test_active_workspace(self):
        self.assertEqual(hypr.Hypr(run=Runner()).active_workspace(), 2)

    def test_focus_and_close_dispatch(self):
        runner = Runner()
        h = hypr.Hypr(run=runner)
        h.focus('0xaa')
        h.close('0xaa')
        self.assertEqual(runner.calls[-2], ['hyprctl', 'dispatch', 'focuswindow', 'address:0xaa'])
        self.assertEqual(runner.calls[-1], ['hyprctl', 'dispatch', 'closewindow', 'address:0xaa'])

    def test_rejects_bad_address(self):
        with self.assertRaises(ValueError):
            hypr.Hypr(run=Runner()).focus('0xaa; rm -rf')

    def test_shell_ipc(self):
        h = hypr.Hypr(run=Runner())
        self.assertEqual(h.thumbnails(['0xaa', '0xbb']), {'0xaa': '/run/x/0xaa.png'})
        self.assertTrue(h.locate('0xaa'))

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

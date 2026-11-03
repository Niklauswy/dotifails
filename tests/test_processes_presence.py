"""Wysun Processes: the pure decision that pauses sampling while nothing can be seen (core/presence.py)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_processes.core import presence  # noqa: E402


def monitor(number, workspace, dpms=True):
    return dict(id=number, name=f'DP-{number}', activeWorkspace=workspace, dpms=dpms)


def window(address, workspace, app_id='wysun-processes'):
    return dict(address=address, pid=10, app_id=app_id, title='Wysun Processes', workspace=workspace,
                active=False, monitor=0)


class PresenceTests(unittest.TestCase):
    def test_a_lit_monitor_showing_the_window_is_visible(self):
        self.assertEqual(presence.suspend_reason([monitor(1, 3), monitor(2, 7)], [window('0xaa', 3)]), '')

    def test_every_output_off_pauses(self):
        self.assertEqual(presence.suspend_reason([monitor(1, 3, False), monitor(2, 7, False)], [window('0xaa', 3)]),
                         'dpms')

    def test_another_workspace_of_a_lit_monitor_pauses(self):
        self.assertEqual(presence.suspend_reason([monitor(1, 3), monitor(2, 7)], [window('0xaa', 9)]), 'workspace')

    def test_the_workspace_of_an_off_output_pauses(self):
        self.assertEqual(presence.suspend_reason([monitor(1, 3), monitor(2, 7, False)], [window('0xaa', 7)]),
                         'workspace')

    def test_an_unmapped_window_pauses(self):
        self.assertEqual(presence.suspend_reason([monitor(1, 3)], []), 'window')

    def test_other_windows_do_not_count(self):
        self.assertEqual(presence.suspend_reason([monitor(1, 3)], [window('0xbb', 3, app_id='kitty')]), 'window')

    def test_without_monitor_data_nothing_is_decided(self):
        # `hyprctl` unavailable: the window's own visibility is the only signal and sampling keeps running.
        self.assertEqual(presence.suspend_reason([], []), '')
        self.assertEqual(presence.suspend_reason([], [window('0xaa', 3)]), '')

    def test_an_output_without_dpms_is_assumed_on(self):
        self.assertEqual(presence.suspend_reason([dict(id=1, activeWorkspace=3)], [window('0xaa', 3)]), '')


if __name__ == '__main__':
    unittest.main()

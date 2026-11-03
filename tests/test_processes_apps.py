"""Pure logic of Wysun Processes' Apps section: monitors ordered left to right with friendly names and sides, their
windows grouped by workspace, the windowless apps split from the session plumbing, and the name a window takes from
the desktop entry of its class (Brave, Wysun Processes) before the process' app (chromium, python3)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))

from wysun_processes.core import apps  # noqa: E402


def monitor(number, name, make='', model='', x=0, y=0, active=1):
    return dict(id=number, name=name, make=make, model=model, x=x, y=y, activeWorkspace=active)


def window(address, app, title='', workspace=1, monitor=0):
    return dict(address=address, app=app, app_id=app, title=title, workspace=workspace, monitor=monitor,
                active=False)


class MonitorTests(unittest.TestCase):
    def test_friendly_name_shortens_make_then_model_then_connector(self):
        self.assertEqual(apps.monitor_name('Philips Consumer Electronics Company', 'PHL 271E1', 'DP-2'), 'Philips')
        self.assertEqual(apps.monitor_name('LG Electronics', 'LG ULTRAGEAR', 'DP-1'), 'LG')
        self.assertEqual(apps.monitor_name('', 'PHL 271E1', 'DP-2'), 'PHL')
        self.assertEqual(apps.monitor_name('Unknown', '', 'DP-3'), 'DP-3')
        self.assertEqual(apps.monitor_name('', '', ''), 'Pantalla')

    def test_side_only_with_more_than_one_monitor(self):
        self.assertEqual(apps.monitor_side(0, 1), '')
        self.assertEqual(apps.monitor_side(0, 2), 'izquierda')
        self.assertEqual(apps.monitor_side(1, 2), 'derecha')
        self.assertEqual(apps.monitor_side(0, 3), 'izquierda')
        self.assertEqual(apps.monitor_side(1, 3), 'centro')
        self.assertEqual(apps.monitor_side(2, 3), 'derecha')


class GroupingTests(unittest.TestCase):
    def setUp(self):
        # hyprctl does not promise an order: the Philips panel is first in physical space even though it is id 2.
        self.monitors = [monitor(1, 'DP-1', 'LG Electronics', 'LG ULTRAGEAR', x=1920, active=7),
                         monitor(2, 'DP-2', 'Philips Consumer Electronics Company', 'PHL 271E1', x=0, active=3)]
        self.windows = [window('0xaa', 'brave-browser', 'Docs', workspace=9, monitor=1),
                        window('0xbb', 'com.mitchellh.ghostty', 'opencode', workspace=8, monitor=1),
                        window('0xcc', 'orca', 'Orca', workspace=1, monitor=2),
                        window('0xdd', 'brave-browser', 'Kick', workspace=3, monitor=2),
                        window('0xee', 'microsoft-edge', 'Superpowers', workspace=3, monitor=2)]

    def test_columns_follow_the_physical_x_position(self):
        columns = apps.group_windows(self.monitors, self.windows)
        self.assertEqual([c['connector'] for c in columns], ['DP-2', 'DP-1'])
        self.assertEqual([c['label'] for c in columns], ['Philips', 'LG'])
        self.assertEqual([c['side'] for c in columns], ['izquierda', 'derecha'])
        self.assertEqual([c['x'] for c in columns], [0, 1920])
        self.assertEqual([c['count'] for c in columns], [3, 2])

    def test_windows_group_by_workspace_and_only_the_active_one_is_marked(self):
        columns = apps.group_windows(self.monitors, self.windows)
        left, right = columns
        self.assertEqual([s['id'] for s in left['workspaces']], [1, 3])
        self.assertEqual([s['current'] for s in left['workspaces']], [False, True])
        self.assertEqual([w['address'] for w in left['workspaces'][1]['windows']], ['0xdd', '0xee'])
        self.assertEqual([s['id'] for s in right['workspaces']], [8, 9])
        self.assertEqual([s['current'] for s in right['workspaces']], [False, False])   # its workspace 7 has no window
        self.assertEqual(right['activeWorkspace'], 7)

    def test_empty_workspaces_do_not_appear(self):
        windows = [window('0xaa', 'orca', workspace=1, monitor=2)]          # workspace 3 is gone from Hypr
        columns = apps.group_windows(self.monitors, windows)
        self.assertEqual([s['id'] for s in columns[0]['workspaces']], [1])
        self.assertEqual(columns[0]['count'], 1)
        self.assertEqual(columns[1]['workspaces'], [])

    def test_a_window_of_an_unknown_monitor_lands_in_the_first_column(self):
        windows = self.windows + [window('0xff', 'orca', 'Lost', workspace=6, monitor=99)]
        columns = apps.group_windows(self.monitors, windows)
        self.assertEqual([s['id'] for s in columns[0]['workspaces']], [1, 3, 6])
        self.assertEqual(columns[0]['count'], 4)

    def test_without_monitors_windows_still_get_one_column(self):
        columns = apps.group_windows([], [window('0xaa', 'orca', workspace=1, monitor=0)])
        self.assertEqual(len(columns), 1)
        self.assertEqual(columns[0]['label'], 'Pantalla')
        self.assertEqual(columns[0]['side'], '')
        self.assertEqual(columns[0]['count'], 1)


class SystemTests(unittest.TestCase):
    def test_session_plumbing_is_system(self):
        for name in ('dbus-daemon', 'dbus-broker', 'pipewire', 'pipewire-pulse', 'wireplumber',
                     'xdg-desktop-portal-gtk', 'xdg-desktop-portal-hyprland', 'gvfsd', 'gvfsd-trash',
                     'at-spi-bus-launcher', 'gnome-keyring-daemon', 'polkitd', 'dconf-service', 'swayidle',
                     'Xwayland', 'systemd', 'systemd-journald', '(sd-pam)', 'start-hyprland', 'mpris-proxy',
                     'wl-paste', 'journalctl', 'timeout', 'cat', 'sh', 'zsh', 'bash', 'Hyprland',
                     'chrome_crashpad', 'msedge_crashpad', 'brave-browser-s', 'nmcli', 'MainThread',
                     'memfd:dwarfs', 'node_repl', '2.1.317', 'head', 'sleep', 'grep',
                     'wysun-services.wayland-clipboard'):
            self.assertTrue(apps.is_system(name), name)

    def test_desktop_apps_and_user_tools_are_not_system(self):
        # No desktop entry is not a reason to hide an app the user is running: only the plumbing list folds.
        for name in ('firefox', 'brave-browser', 'wysun-processes', 'quickshell', 'org.gnome.Nautilus', 'Code',
                     'brave', 'msedge', 'hermes', 'opencode', 'claude', 'orca.AppImage', 'local-tool',
                     'wysun-services.daemon', 'wysun-files.service'):
            self.assertFalse(apps.is_system(name), name)

    def test_an_empty_name_is_system(self):
        self.assertTrue(apps.is_system(''))


class WindowlessTests(unittest.TestCase):
    def test_groups_by_app_sorted_by_memory_and_keeps_system_apart(self):
        rows = [dict(app='brave', cpu=4, mem=300),
                dict(app='brave', cpu=1, mem=100),
                dict(app='firefox', cpu=9, mem=50),                 # it has a window: not in this column
                dict(app='wysun-processes', cpu=2, mem=50),
                dict(app='dbus-daemon', cpu=0.5, mem=10),
                dict(app='pipewire', cpu=0, mem=5)]
        user, system = apps.windowless_groups(rows, {'firefox'})
        self.assertEqual([g['app'] for g in user], ['brave', 'wysun-processes'])
        self.assertEqual(user[0], dict(app='brave', cpu=5, mem=400, count=2))
        self.assertEqual([g['app'] for g in system], ['dbus-daemon', 'pipewire'])
        summary = apps.system_summary(system)
        self.assertEqual(summary['count'], 2)
        self.assertEqual(summary['mem'], 15)
        self.assertEqual(summary['cpu'], 0.5)
        self.assertEqual([g['app'] for g in summary['apps']], ['dbus-daemon', 'pipewire'])

    def test_an_app_with_a_window_is_never_windowless(self):
        rows = [dict(app='brave', cpu=1, mem=10)]
        user, system = apps.windowless_groups(rows, {'brave'})
        self.assertEqual((user, system), ([], []))

    def test_a_background_group_of_a_windowed_app_is_still_listed(self):
        # The window's process app is Chromium; Brave's background scope is a different app key but the same program.
        rows = [dict(app='brave', cpu=1, mem=2500), dict(app='org.chromium.Chromium', cpu=3, mem=500)]
        user, system = apps.windowless_groups(rows, {'org.chromium.Chromium'})
        self.assertEqual([g['app'] for g in user], ['brave'])
        self.assertEqual(system, [])

    def test_wysun_daemon_and_service_stay_user_while_the_clipboard_helper_is_system(self):
        rows = [dict(app='wysun-services.daemon', cpu=0, mem=60),
                dict(app='wysun-files.service', cpu=0, mem=50),
                dict(app='wysun-services.wayland-clipboard', cpu=0, mem=1)]
        user, system = apps.windowless_groups(rows, set())
        self.assertEqual([g['app'] for g in user], ['wysun-services.daemon', 'wysun-files.service'])
        self.assertEqual([g['app'] for g in system], ['wysun-services.wayland-clipboard'])


class NameTests(unittest.TestCase):
    entries = {'brave-browser': {'name': 'Brave', 'desktop': 'brave-browser'},
               'wysun-processes': {'name': 'Wysun Processes', 'desktop': 'wysun-processes'},
               'ghostty': {'name': 'Ghostty', 'desktop': 'ghostty'},
               'microsoft-edge': {'name': 'Microsoft Edge', 'desktop': 'microsoft-edge'}}
    # A Brave PWA registers the browser's Exec name as an alias: it must not name the browser windows.
    pwa = dict(entries, **{'brave-browser': {'name': 'TikTok Coins', 'desktop': 'brave-nddj-pwa'}})

    def test_the_window_class_names_the_window_first(self):
        self.assertEqual(apps.preferred_app('brave-browser', 'chromium', self.entries.get), 'brave-browser')
        self.assertEqual(apps.preferred_app('wysun-processes', 'python3', self.entries.get), 'wysun-processes')
        self.assertEqual(apps.app_label('brave-browser', 'chromium', self.entries.get), 'Brave')
        self.assertEqual(apps.app_label('wysun-processes', 'python3', self.entries.get), 'Wysun Processes')

    def test_the_process_app_is_the_fallback(self):
        self.assertEqual(apps.preferred_app('code', 'code', self.entries.get), 'code')
        self.assertEqual(apps.preferred_app('', 'python3', self.entries.get), 'python3')
        self.assertEqual(apps.preferred_app('unknown-class', 'kitty', self.entries.get), 'kitty')

    def test_an_app_shortcut_does_not_steal_the_class(self):
        self.assertEqual(apps.preferred_app('brave-browser', 'org.chromium.Chromium', self.pwa.get),
                         'org.chromium.Chromium')
        self.assertEqual(apps.app_label('brave-browser', 'org.chromium.Chromium', self.pwa.get), 'Brave')
        self.assertEqual(apps.app_label('com.mitchellh.ghostty', 'ghostty', self.entries.get), 'Ghostty')
        self.assertEqual(apps.app_label('microsoft-edge', 'org.chromium.Chromium', self.entries.get),
                         'Microsoft Edge')
        self.assertEqual(apps.app_label('orca.AppImage', 'orca.AppImage', {}.get), 'Orca')

    def test_wysun_modules_keep_a_readable_name(self):
        # `python -m wysun_services.daemon` reaches the list as `wysun-services.daemon`; the last component alone
        # would read "Daemon", "Service" or "Wayland".
        self.assertEqual(apps.wysun_name('wysun-services.daemon'), 'Wysun daemon')
        self.assertEqual(apps.wysun_name('wysun-files.service'), 'Wysun Files')
        self.assertEqual(apps.wysun_name('wysun-services.wayland-clipboard'), 'Wysun clipboard')
        self.assertEqual(apps.wysun_name('wysun-processes'), '')
        self.assertEqual(apps.brand_name('wysun-services.daemon'), 'Wysun daemon')
        self.assertEqual(apps.app_label('wysun-services.daemon', 'python3', {}.get), 'Wysun daemon')
        self.assertEqual(apps.app_label('wysun-files.service', 'python3', {}.get), 'Wysun Files')


if __name__ == '__main__':
    unittest.main()

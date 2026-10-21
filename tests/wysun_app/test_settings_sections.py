"""Native settings links use the existing resident IPC and preserve draft pages."""
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/wysun'))
from PySide6.QtWidgets import QApplication
import settings_app
from settings_hub import SettingsHub
from environment_settings import EnvironmentSettings
from hypr_settings import HyprDesktopSettings, HyprShortcutFile
import theme_core

APP = QApplication.instance() or QApplication([])
CATALOGUE = ROOT / 'apps/shell/modules/nexus/pages/DesktopSections.js'


def sections():
    source = CATALOGUE.read_text()
    return re.findall(r'\{route: "([^"]+)"', source)


def inline_job(window, fn, callback, progress=None):
    try:
        callback(fn())
    except Exception as error:
        window.report_error(str(error))
    return Mock()


def runner(args):
    if list(args[:3]) == ['hyprctl', '-j', 'monitors']:
        return json.dumps([dict(name='SYNTHETIC', width=800, height=600, x=0, y=0, scale=1,
                               refreshRate=60, availableModes=['800x600@60.00Hz'], focused=True)])
    if args[-1] in ('binds', 'clients', 'workspaces'):
        return '[]'
    if len(args) > 2 and args[2] == 'getoption':
        return '{"int": 1}'
    return 'ok'


class SettingsSectionTests(unittest.TestCase):
    def test_catalogue_matches_all_actual_hub_routes(self):
        tree = ast.parse((ROOT / 'apps/wysun/settings_hub.py').read_text())
        builders = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'builders' for t in node.targets))
        routes = [entry.elts[0].value for entry in builders.elts]
        self.assertEqual(sections(), routes)
        self.assertEqual(len(set(sections())), 11)
        # Both registry lists append the desktop page; all existing indices stay stable.
        registry = (ROOT / 'apps/shell/modules/nexus/PageRegistry.qml').read_text()
        components = (ROOT / 'apps/shell/modules/nexus/PageCompRegistry.qml').read_text()
        self.assertLess(registry.index('label: Tr.tr("About")'), registry.index('category: "desktop"'))
        self.assertLess(components.index('AboutPage {}'), components.index('DesktopPage {}'))
        desktop = (ROOT / 'config/.local/share/applications/orbit-settings.desktop').read_text()
        self.assertIn('Name=Wysun Settings', desktop)
        self.assertIn('Exec=wysun settings', desktop)

    def test_native_commands_target_only_existing_sections(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node JavaScript engine unavailable')
        source = CATALOGUE.read_text().replace('.pragma library', '')
        result = subprocess.run([node], input=source + '\nconsole.log(JSON.stringify([sections.map(s => command(s.route)), command("unknown")]));',
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands, invalid = json.loads(result.stdout)
        self.assertEqual(commands, [['wysun', 'settings', route] for route in sections()])
        self.assertEqual(invalid, [])

    def test_every_link_reuses_one_live_settings_window_and_keeps_unsaved_drafts(self):
        for theme in ('space-black', 'tokyo', 'severance', 'fluent:light', 'fluent:dark'):
            with self.subTest(theme=theme):
                self.check_routes(theme)

    def check_routes(self, theme):
        with tempfile.TemporaryDirectory(prefix='wysun-sections-') as folder:
            home = Path(folder)
            env = dict(os.environ, HOME=folder, XDG_CONFIG_HOME=str(home / '.config'),
                       XDG_STATE_HOME=str(home / '.local/state'), XDG_RUNTIME_DIR=folder,
                       QT_QPA_PLATFORM='offscreen')
            for name in ('ORBIT_THEME', 'WYSUN_THEME'):
                env.pop(name, None)
            env['WYSUN_THEME'] = theme
            with patch.dict(os.environ, env, clear=True), \
                    patch.object(SettingsHub, 'start_job', inline_job), \
                    patch.object(SettingsHub, 'present', lambda win: None), \
                    patch('settings_hub.EnvironmentSettings', side_effect=lambda h: EnvironmentSettings(h, runner)), \
                    patch('settings_hub.DesktopSettings', side_effect=lambda h: HyprDesktopSettings(h, runner)), \
                    patch('settings_hub.ShortcutFile', side_effect=lambda h: HyprShortcutFile(h, runner)), \
                    patch('settings_hub.application_shortcuts', return_value=[]):
                theme_core.invalidate()
                window = SettingsHub(test=True, home=home)
                server = None
                try:
                    window.colour_seed.setText('#123abc')
                    window.shell_opacity.setValue(91)
                    pages = [window.pages.widget(i) for i in range(window.pages.count())]
                    endpoint = home / f'orbit-settings-{os.getuid()}.sock'
                    try:
                        server = settings_app.LocalSettingsServer(endpoint)
                    except PermissionError:
                        self.skipTest('Sandbox blocks Unix sockets; run with local socket access')
                    received = []
                    def present(route):
                        received.append(route)
                        settings_app.present_route(window, route)
                    server.requested.connect(present)
                    for route in sections() + ['displays', 'displays']:
                        before = len(received)
                        result = subprocess.run([sys.executable, str(ROOT / 'apps/wysun/orbit-client'), 'settings', route],
                                                env=env, capture_output=True, text=True, timeout=5)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        deadline = time.monotonic() + 2
                        while len(received) == before and time.monotonic() < deadline:
                            APP.processEvents()
                            time.sleep(.005)
                        self.assertEqual(received[-1:], [route])
                        self.assertEqual(window.section(), route)
                        self.assertEqual([window.pages.widget(i) for i in range(window.pages.count())], pages)
                        self.assertEqual(window.colour_seed.text(), '#123abc')
                        self.assertEqual(window.shell_opacity.value(), 91)
                    self.assertFalse((home / '.local/state/orbit-settings.log').exists(), 'client spawned another Settings')
                    self.assertEqual(window.windowTitle(), 'Wysun Settings')
                finally:
                    if server:
                        server.close()
                    window.deleteLater()
                    APP.processEvents()
                    theme_core.invalidate()


if __name__ == '__main__':
    unittest.main()

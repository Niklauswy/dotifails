"""Nexus exposes display settings directly and rejects retired routes."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
NEXUS = ROOT / 'apps/shell/modules/nexus'
CATALOGUE = NEXUS / 'pages/SettingsRoutes.js'
REMOVED = ('settings_hub', 'settings_window', 'settings_app', 'shortcut_capture', 'connections_window',
           'connections_data', 'connection_details')


def page_keys():
    return re.findall(r'key: "([a-z]+)"', (NEXUS / 'PageRegistry.qml').read_text())


class NativePagesTests(unittest.TestCase):
    def sections(self):
        return []

    def test_qt_settings_connections_and_processes_windows_are_removed(self):
        for name in REMOVED:
            self.assertFalse((ROOT / 'apps/wysun' / (name + '.py')).exists(), name)
        sources = ' '.join(p.read_text(errors='ignore') for p in (ROOT / 'apps/wysun').glob('*.py')
                           if p.name not in ('desktop_bridge.py',))
        for name in REMOVED:
            self.assertNotRegex(sources, r'(from|import)\s+' + name + r'\b', name)

    def test_page_registry_and_components_stay_aligned(self):
        keys = page_keys()
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys[:4], ['wallpaper', 'network', 'bluetooth', 'audio'])  # bar deep links
        components = (NEXUS / 'PageCompRegistry.qml').read_text()
        self.assertEqual(len(re.findall(r'^        Component \{', components, re.M)), len(keys))
        self.assertIn('displays', keys)
        self.assertIn('workspaces', keys)
        for retired in ('desktop', 'processes', 'ssh'):
            self.assertNotIn(retired, keys)

    def test_retired_pages_and_bridge_are_absent(self):
        for name in ('DesktopPage', 'ShortcutsPage', 'ShortcutEditPage', 'WindowsPage',
                     'RuleEditPage', 'ComponentPage', 'StartupPage', 'BackupsPage'):
            self.assertFalse((NEXUS / 'pages' / (name + '.qml')).exists())
        self.assertFalse((ROOT / 'apps/shell/wysun/desktop_bridge.py').exists())
        self.assertFalse((NEXUS / 'pages/processes').exists())
        self.assertFalse((NEXUS / 'pages/ssh').exists())

    def test_page_routes_target_registered_pages(self):
        source = CATALOGUE.read_text()
        targets = set(re.findall(r':\s*"([a-z]+)"', source[source.index('var pageRoutes'):]))
        self.assertLessEqual(targets, set(page_keys()))

    def test_shell_links_use_only_known_routes(self):
        known = {r for r, _ in self.sections()} | set(re.findall(r'^\s+(\w+): "[a-z]+",?$', CATALOGUE.read_text()[CATALOGUE.read_text().index('var pageRoutes'):], re.M))
        for path in list((ROOT / 'apps/shell').rglob('*.qml')) + list((ROOT / 'apps/shell').rglob('*.js')):
            if 'modules/nexus' in str(path):
                continue
            for match in re.finditer(r'\[?["\']wysun["\'],\s*["\']settings["\'],\s*["\'](\w+)["\']', path.read_text(errors='ignore')):
                self.assertIn(match.group(1), known, f'{path.name}: {match.group(1)}')

    def test_desktop_entry_opens_settings_through_wysun(self):
        desktop = (ROOT / 'config/.local/share/applications/orbit-settings.desktop').read_text()
        self.assertIn('Name=Wysun Settings', desktop)
        self.assertIn('Exec=wysun settings', desktop)

    def test_catalogue_is_valid_javascript(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node JavaScript engine unavailable')
        source = CATALOGUE.read_text().replace('.pragma library', '')
        result = subprocess.run([node], input=source + '\nconsole.log(JSON.stringify(pageRoutes));',
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        routes = json.loads(result.stdout)
        self.assertEqual(routes['displays'], 'displays')
        self.assertEqual(routes['workspaces'], 'workspaces')
        for retired in ('desktop', 'effects', 'shortcuts', 'ssh', 'processes', 'terminal', 'startup', 'files', 'notifications', 'rules'):
            self.assertNotIn(retired, routes)



if __name__ == '__main__':
    unittest.main()

"""Settings, connections and processes are shell (Nexus) pages; Qt windows are gone."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
NEXUS = ROOT / 'apps/shell/modules/nexus'
CATALOGUE = NEXUS / 'pages/DesktopSections.js'
REMOVED = ('settings_hub', 'settings_window', 'settings_app', 'shortcut_capture', 'connections_window',
           'connections_data', 'connection_details', 'processes_window', 'process_widgets')


def page_keys():
    return re.findall(r'key: "([a-z]+)"', (NEXUS / 'PageRegistry.qml').read_text())


class NativePagesTests(unittest.TestCase):
    def sections(self):
        return re.findall(r'\{route: "([^"]+)"[^}]*sub: (\d+)', CATALOGUE.read_text())

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
        self.assertEqual(len(re.findall(r'^        Component \{$', components, re.M)), len(keys))
        self.assertLess(keys.index('about'), keys.index('desktop'))
        self.assertIn('processes', keys)
        self.assertIn('ssh', keys)

    def test_every_section_has_a_distinct_route_and_an_existing_sub_page(self):
        sections = self.sections()
        routes = [route for route, _ in sections]
        self.assertEqual(len(routes), len(set(routes)))
        self.assertGreaterEqual(len(routes), 9)
        components = (NEXUS / 'PageCompRegistry.qml').read_text()
        desktop = components[components.index('DesktopPage {}'):]
        listed = len(re.findall(r'^                Component \{$', desktop.split('\n        }\n    ]')[0], re.M)) + 1
        for route, sub in sections:
            self.assertLess(int(sub), listed, route)
        for page in ('DisplaysPage', 'WorkspacesPage', 'ShortcutsPage', 'ShortcutEditPage', 'WindowsPage',
                     'RuleEditPage', 'ComponentPage', 'StartupPage', 'BackupsPage'):
            self.assertTrue((NEXUS / 'pages' / (page + '.qml')).is_file(), page)

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
        result = subprocess.run([node], input=source + '\nconsole.log(JSON.stringify([sections.length, section("displays").sub, section("nope")]));',
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        count, sub, missing = json.loads(result.stdout)
        self.assertGreaterEqual(count, 9)
        self.assertEqual(sub, 1)
        self.assertIsNone(missing)


if __name__ == '__main__':
    unittest.main()

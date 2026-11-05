"""Wysun Drive in the shell: bar logic (DriveLogic.js, node) and static wiring of bar, Settings and launcher."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

SHELL = Path(__file__).resolve().parents[2] / 'apps/shell'


def js(body):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node not available')
    source = (SHELL / 'services/DriveLogic.js').read_text().replace('.pragma library', '')
    script = source + '\nprocess.stdout.write(JSON.stringify((() => {' + body + '})()));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


UPLOAD = "{pid: 7, updated: 1000, started: 900, title: 'fotos', items: [], done: 512, total: 2048}"


class LogicTests(unittest.TestCase):
    def test_live_drops_stale_and_broken(self):
        out = js(f'''const a = {UPLOAD}; const b = Object.assign({{}}, a, {{pid: 8, started: 800}});
                     const gone = Object.assign({{}}, a, {{pid: 9, updated: 960}});
                     return live([a, null, {{}}, gone, b], 1029).map(u => u.pid)''')
        self.assertEqual(out, [8, 7])

    def test_progress_texts(self):
        out = js(f'''const u = {UPLOAD};
            return [fraction(u), detail(u), detail({{total: 0}}), size(1536), size(5 * 1024 * 1024 * 1024),
                    overall([u, Object.assign({{}}, u, {{done: 2048}})])]''')
        self.assertEqual(out, [0.25, '512 B de 2,0 KB · 25 %', 'Preparando…', '1,5 KB', '5,0 GB', 0.625])


class WiringTests(unittest.TestCase):
    def test_bar_icon_opens_the_drive_popout(self):
        self.assertIn('name: "drive"', (SHELL / 'modules/bar/components/StatusIcons.qml').read_text())
        self.assertIn('DrivePopout {}', (SHELL / 'modules/bar/popouts/Content.qml').read_text())

    def test_service_reads_status_and_cancels_through_the_cli(self):
        text = (SHELL / 'services/Drive.qml').read_text()
        self.assertIn('wysun-drive', text)
        self.assertIn('"--detener"', text)

    def test_settings_page_registered_in_the_same_slot(self):
        pages = (SHELL / 'modules/nexus/PageRegistry.qml').read_text()
        comps = (SHELL / 'modules/nexus/PageCompRegistry.qml').read_text()
        self.assertLess(pages.index('key: "drive"'), pages.index('key: "about"'))
        self.assertLess(pages.index('key: "language"'), pages.index('key: "drive"'))
        self.assertLess(comps.index('LanguageAndRegion {}'), comps.index('DrivePage {}'))
        self.assertLess(comps.index('DrivePage {}'), comps.index('AboutPage {}'))
        self.assertIn('drive: "drive"', (SHELL / 'modules/nexus/pages/SettingsRoutes.js').read_text())
        page = (SHELL / 'modules/nexus/pages/DrivePage.qml').read_text()
        for command in ('"estado", "--json"', '"ajustes"', '"login"', '"logout"'):
            self.assertIn(command, page)


if __name__ == '__main__':
    unittest.main()

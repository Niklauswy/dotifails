"""LANShare in the bar: popout logic (LanShareLogic.js, node) and static QML wiring."""
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
    source = (SHELL / 'services/LanShareLogic.js').read_text().replace('.pragma library', '')
    script = source + '\nprocess.stdout.write(JSON.stringify((() => {' + body + '})()));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


SERVER = "{pid: 7, updated: 1000, started: 900, shutdownAt: 1000 + 42*60, clients: [], transfers: [], uploads: false}"


class LogicTests(unittest.TestCase):
    def test_live_drops_dead_and_broken_files(self):
        out = js(f'''const a = {SERVER}; const b = Object.assign({{}}, a, {{pid: 8, started: 800}});
                     const dead = Object.assign({{}}, a, {{pid: 9, updated: 960}});
                     return live([a, null, {{}}, dead, b], 1029).map(s => s.pid)''')
        self.assertEqual(out, [8, 7])

    def test_remaining(self):
        out = js(f'''const s = {SERVER};
            return [remaining(s, 1000), remaining(s, 1000 + 42*60 - 30), remaining(Object.assign({{}}, s, {{shutdownAt: 1000 + 3600 + 600}}), 1000),
                    remaining(Object.assign({{}}, s, {{shutdownAt: 1000 + 7200}}), 1000),
                    remaining(Object.assign({{}}, s, {{shutdownAt: null}}), 1000), remaining(s, 9999),
                    remaining(Object.assign({{}}, s, {{transfers: [{{}}]}}), 9999)]''')
        self.assertEqual(out, ['Se apaga en 42 min', 'Se apaga en menos de 1 min', 'Se apaga en 1 h 10 min', 'Se apaga en 2 h',
                               'Sin apagado automático', 'Se apaga en un momento', 'Se apaga al terminar las transferencias'])

    def test_people_and_transfers(self):
        out = js('''return [people({clients: []}), people({clients: [{device: "iPhone"}]}),
                            people({clients: [{device: "iPhone"}, {device: "Windows"}]}),
                            progress({done: 50, total: 200}), progress({done: 5, total: null}),
                            transferText({device: "iPhone", direction: "view", name: "Expo.mp4"}),
                            transferText({device: "Mac", direction: "up", name: "a.zip"}),
                            access({uploads: true}), access({uploads: false})]''')
        self.assertEqual(out, ['Nadie conectado', '1 persona conectada — iPhone', '2 personas conectadas — iPhone · Windows',
                               0.25, 0, 'iPhone · Ve Expo.mp4', 'Mac · Sube a.zip', 'Subidas permitidas', 'Solo ver y descargar'])


class WiringTests(unittest.TestCase):
    def test_bar_icon_opens_the_lanshare_popout(self):
        self.assertIn('name: "lanshare"', (SHELL / 'modules/bar/components/StatusIcons.qml').read_text())
        self.assertIn('name: "lanshare"', (SHELL / 'modules/bar/popouts/Content.qml').read_text())

    def test_service_reads_the_status_directory_and_stops_through_the_cli(self):
        text = (SHELL / 'services/LanShare.qml').read_text()
        self.assertIn('wysun-lanshare', text)
        self.assertIn('"--detener"', text)
        self.assertIn('Logic.live(', text)


if __name__ == '__main__':
    unittest.main()

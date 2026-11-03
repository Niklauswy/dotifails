"""Window tools for Wysun Processes in the shell: address parsing, halo placement on the right monitor, the label of
a window on another workspace (WindowToolsLogic.js, node) and the IPC wiring (thumbs/locate)."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / 'apps/shell'


def js(body):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node not available')
    source = (SHELL / 'services/WindowToolsLogic.js').read_text().replace('.pragma library', '')
    script = source + '\nprocess.stdout.write(JSON.stringify((() => {' + body + '})()));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class LogicTests(unittest.TestCase):
    def test_addresses_are_validated_and_bounded(self):
        out = js('return parseAddresses("0xaa,0xBB, nope,0x1;rm,0xcc,0xaa")')
        self.assertEqual(out, ['aa', 'bb', 'cc'])
        self.assertEqual(len(js('return parseAddresses(Array.from({length: 40}, (_, i) => "0x" + (i + 10)).join(","))')), 24)

    def test_same_address_in_both_forms(self):
        self.assertTrue(js('return sameAddress("0x55dE", "55de")'))
        self.assertFalse(js('return sameAddress("0x55de", "55df")'))

    def test_halo_on_the_monitor_of_the_window(self):
        out = js('''return placement({at: [1992, 22], size: [1826, 1036]}, {name: "DP-2", x: 1920, y: 0, width: 1920, height: 1080},
                                    {name: "DP-2", activeWs: 8}, 8)''')
        self.assertEqual(out, {'visible': True, 'x': 72, 'y': 22, 'width': 1826, 'height': 1036})

    def test_other_monitor_or_workspace_hides_the_halo(self):
        self.assertFalse(js('return placement({at: [10, 10], size: [100, 100]}, {name: "DP-1", x: 0, y: 0, width: 1920, height: 1080}, {name: "DP-2", activeWs: 1}, 1).visible'))
        self.assertFalse(js('return placement({at: [10, 10], size: [100, 100]}, {name: "DP-1", x: 0, y: 0, width: 1920, height: 1080}, {name: "DP-1", activeWs: 2}, 1).visible'))

    def test_label(self):
        self.assertEqual(js('return elsewhere("Firefox", 3)'), 'Firefox está en el espacio 3')
        self.assertEqual(js('return elsewhere("", 3)'), 'La ventana está en el espacio 3')

    def test_thumbnail_path(self):
        self.assertEqual(js('return thumbPath("/run/user/1000", "0xAB")'), '/run/user/1000/wysun-processes/thumbs/ab.png')


class WiringTests(unittest.TestCase):
    def test_bridge_exposes_thumbs_and_locate(self):
        qml = (SHELL / 'wysun/WysunBridge.qml').read_text()
        self.assertIn('function thumbs(addresses: string): string', qml)
        self.assertIn('function locate(address: string): bool', qml)

    def test_launcher_script_forwards_them(self):
        script = (ROOT / 'bin/wysun-shell').read_text()
        self.assertIn('thumbs) shift; exec "$runtime" ipc call wysunShell thumbs', script)
        self.assertIn('locate) shift; exec "$runtime" ipc call wysunShell locate', script)

    def test_module_is_loaded_by_the_shell(self):
        self.assertIn('WindowTools {}', (SHELL / 'shell.qml').read_text())


if __name__ == '__main__':
    unittest.main()

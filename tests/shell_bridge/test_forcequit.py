"""Super+Shift+Esc: force-quitting the active window from the shell (ForceQuitLogic.js, node) and its wiring: IPC,
the wysun-shell subcommand, the Hyprland binding and the module in the shell."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / 'apps/shell'


def js(body):
    node = shutil.which('node')
    if not node:
        raise unittest.SkipTest('node not available')
    source = (SHELL / 'modules/forcequit/ForceQuitLogic.js').read_text().replace('.pragma library', '')
    script = source + '\nprocess.stdout.write(JSON.stringify((() => {' + body + '})()));'
    result = subprocess.run([node], input=script, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class LogicTests(unittest.TestCase):
    def test_session_pieces_are_never_offered(self):
        for cls in ('quickshell', 'Hyprland', 'xwaylandvideobridge', 'wysun-shell'):
            self.assertFalse(js(f'return canForceQuit({{cls: "{cls}", pid: 4000}})'), cls)
        self.assertFalse(js('return canForceQuit({cls: "kitty", pid: 1})'))
        self.assertFalse(js('return canForceQuit(null)'))
        self.assertTrue(js('return canForceQuit({cls: "kitty", pid: 4000})'))

    def test_question(self):
        self.assertEqual(js('return question("Kitty")'), '¿Forzar el cierre de Kitty?')
        self.assertEqual(js('return question("")'), '¿Forzar el cierre de esta ventana?')


class WiringTests(unittest.TestCase):
    def test_bridge_and_script(self):
        self.assertIn('function forceQuit(): bool', (SHELL / 'wysun/WysunBridge.qml').read_text())
        self.assertIn('forcequit) exec "$runtime" ipc call wysunShell forceQuit', (ROOT / 'bin/wysun-shell').read_text())
        self.assertIn('ForceQuit {}', (SHELL / 'shell.qml').read_text())

    def test_binding_is_unique(self):
        lua = (ROOT / 'config/.config/wysun/hyprland.lua').read_text()
        binds = re.findall(r'hl\.bind\("SUPER \+ SHIFT \+ Escape", hl\.dsp\.exec_cmd\("([^"]+)"\)', lua)
        self.assertEqual(binds, ['wysun-shell forcequit'])


if __name__ == '__main__':
    unittest.main()

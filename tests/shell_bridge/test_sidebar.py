"""Exercise the real bridge JavaScript and the distributed shortcut contract."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SidebarTests(unittest.TestCase):
    def test_global_ctrl_x_is_unique_and_keeps_super_ctrl_x(self):
        lua = (ROOT / 'config/.config/wysun/hyprland.lua').read_text()
        binds = re.findall(r'^hl\.bind\("([^"]+)", (.+)$', lua, re.M)
        normalize = lambda key: tuple(sorted(p.strip().upper() for p in key.split('+')))
        keys = [normalize(key) for key, _ in binds]
        self.assertEqual(len(keys), len(set(keys)), 'Duplicate distributed global bindings')
        ctrl_x = [body for key, body in binds if normalize(key) == normalize('CTRL + X')]
        self.assertEqual(len(ctrl_x), 1)
        self.assertIn('wysun shell sidebar', ctrl_x[0])
        inherited = [body for key, body in binds if normalize(key) == normalize('SUPER + CTRL + X')]
        self.assertEqual(len(inherited), 1)
        self.assertNotIn('wysun shell sidebar', inherited[0])

    def test_bridge_toggle_repeats_closes_other_outputs_and_handles_missing_focus(self):
        source = (ROOT / 'apps/shell/wysun/WysunBridge.qml').read_text()
        surfaces = re.search(r'property var surfaces: \((\{.*?\})\)', source, re.S)[1]
        functions = '\n'.join(re.findall(r'^    function .*?^    }', source, re.M | re.S))
        script = """
var screens = [{name: 'left'}, {name: 'right'}];
var states = [{sidebar: false, launcher: true}, {sidebar: false, session: true}];
var active = 0;
var Quickshell = {screens: screens};
var ShellState = {
    forActive: function() { return active < 0 ? null : states[active]; },
    forScreen: function(screen) { return states[screens.indexOf(screen)]; }
};
var root = {surfaces: SURFACES};
var surfaces = root.surfaces;
FUNCTIONS
root.current = current; root.close = close; root.show = show;
function check(value, message) { if (!value) throw Error(message); }
check(root.surfaces.sidebar === 'sidebar', 'sidebar alias missing');
check(root.surfaces.notifications === 'sidebar', 'legacy alias lost');
for (var n = 0; n < 6; ++n) {
    check(show('sidebar', true), 'toggle rejected');
    check(states[0].sidebar === (n % 2 === 0), 'toggle failed to alternate');
    check(!states[0].launcher && !states[1].session, 'other surface left open');
}
show('sidebar', false); show('sidebar', false);
check(states[0].sidebar, 'open should be idempotent');
active = 1; show('sidebar', true);
check(!states[0].sidebar && states[1].sidebar, 'wrong focused output');
active = -1;
check(!show('sidebar', true), 'missing focus must reject');
check(!show('unknown', true), 'unknown surface must reject');
close(); check(!states[0].sidebar && !states[1].sidebar, 'close failed');
""".replace('SURFACES', surfaces).replace('FUNCTIONS', functions)
        # Run the bridge JS without a compositor, IPC server or widgets.
        runner = """
import sys
from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine
app = QCoreApplication([])
engine = QJSEngine()
result = engine.evaluate(sys.stdin.read())
if result.isError():
    print(result.toString(), file=sys.stderr)
    sys.exit(1)
"""
        node = shutil.which('node')
        if node:
            command = [node]
        else:
            try:
                import PySide6.QtQml  # noqa: F401
            except ImportError:
                self.skipTest('JavaScript engine unavailable (Node or PySide6.QtQml)')
            command = [sys.executable, '-c', runner]
        result = subprocess.run(command, input=script, text=True,
                                capture_output=True, env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_sidebar_can_receive_keyboard_focus_and_close_on_escape(self):
        content = (ROOT / 'apps/shell/modules/sidebar/Content.qml').read_text()
        self.assertIn('Keys.onEscapePressed: root.screenState.sidebar = false', content)
        self.assertIn('onSidebarChanged()', content)
        window = (ROOT / 'apps/shell/modules/drawers/ContentWindow.qml').read_text()
        keyboard = next(line for line in window.splitlines() if 'WlrLayershell.keyboardFocus:' in line)
        self.assertIn('screenState.sidebar', keyboard)


if __name__ == '__main__':
    unittest.main()

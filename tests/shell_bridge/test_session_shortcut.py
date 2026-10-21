"""Exercise the real bridge JavaScript and the distributed shortcut contract."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SessionShortcutTests(unittest.TestCase):
    def test_ctrl_x_is_free_and_super_x_toggles_session(self):
        lua = (ROOT / 'config/.config/wysun/hyprland.lua').read_text()
        binds = re.findall(r'^hl\.bind\("([^"]+)", (.+)$', lua, re.M)
        normalize = lambda key: tuple(sorted(p.strip().upper() for p in key.split('+')))
        keys = [normalize(key) for key, _ in binds]
        self.assertEqual(len(keys), len(set(keys)), 'Duplicate distributed global bindings')
        self.assertEqual([b for k, b in binds if normalize(k) == normalize('CTRL + X')], [])
        super_x = [body for key, body in binds if normalize(key) == normalize('SUPER + X')]
        self.assertEqual(len(super_x), 1)
        self.assertIn('wysun shell session', super_x[0])
        power = [body for key, body in binds if normalize(key) == normalize('SUPER + SHIFT + X')]
        self.assertIn('wysun power', power[0])
        inherited = [body for key, body in binds if normalize(key) == normalize('SUPER + CTRL + X')]
        self.assertEqual(len(inherited), 1)
        self.assertNotIn('wysun shell', inherited[0])

    def test_bridge_toggle_repeats_closes_other_outputs_and_handles_missing_focus(self):
        source = (ROOT / 'apps/shell/wysun/WysunBridge.qml').read_text()
        surfaces = re.search(r'property var surfaces: \((\{.*?\})\)', source, re.S)[1]
        functions = '\n'.join(re.findall(r'^    function .*?^    }', source, re.M | re.S))
        script = """
var screens = [{name: 'left'}, {name: 'right'}];
var states = [{launcher: true}, {session: true}];
var active = 0;
var Quickshell = {screens: screens};
var ShellState = {
    forActive: function() { return active < 0 ? null : states[active]; },
    forScreen: function(screen) { return states[screens.indexOf(screen)]; },
    componentsFor: function(screen) { return {panels: {launcher: {available: launcherAvailable}}}; }
};
var launcherAvailable = false;
var root = {surfaces: SURFACES};
var surfaces = root.surfaces;
FUNCTIONS
root.current = current; root.close = close; root.show = show;
function check(value, message) { if (!value) throw Error(message); }
check(root.surfaces.session === 'session', 'session surface missing');
check(root.surfaces.notifications === 'sidebar', 'legacy alias lost');
for (var n = 0; n < 6; ++n) {
    check(show('session', true), 'toggle rejected');
    check(states[0].session === (n % 2 === 0), 'toggle failed to alternate');
    check(!states[0].launcher && !states[1].session, 'other surface left open');
}
show('session', false); show('session', false);
check(states[0].session, 'open should be idempotent');
active = 1; show('session', true);
check(!states[0].session && states[1].session, 'wrong focused output');
active = -1;
check(!show('session', true), 'missing focus must reject');
check(!show('unknown', true), 'unknown surface must reject');
close(); check(!states[0].session && !states[1].session, 'close failed');
active = 0;
check(!show('launcher', true), 'disabled launcher must reject for fallback');
launcherAvailable = true;
check(show('launcher', true) && states[0].launcher, 'native launcher not accepted');
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

    def test_session_panel_closes_on_escape_and_survives_fullscreen(self):
        window = (ROOT / 'apps/shell/modules/drawers/ContentWindow.qml').read_text()
        keyboard = next(line for line in window.splitlines() if 'WlrLayershell.keyboardFocus:' in line)
        self.assertIn('screenState.session', keyboard)
        self.assertIn('interactivePanelOpen', window)
        self.assertRegex(window, r'interactivePanelOpen[^\n]*screenState\.session')
        content = (ROOT / 'apps/shell/modules/session/Content.qml').read_text()
        self.assertIn('Keys.onEscapePressed', content)

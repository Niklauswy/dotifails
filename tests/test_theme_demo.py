"""A demo widget follows the theme live in all five variants (Qt and Quickshell)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = [('space-black', 'space-black'), ('space-black', 'tokyo'), ('space-black', 'severance'), ('fluent', 'light'), ('fluent', 'dark')]


class QtDemo(unittest.TestCase):
    def test_widget_repaints_for_each_variant_without_restart(self):
        script = r'''
import json, os, sys
sys.path.insert(0, %r)
os.environ.pop('WYSUN_THEME', None); os.environ.pop('ORBIT_THEME', None)
from PySide6.QtWidgets import QApplication
app = QApplication(['demo']); app.setStyle('Fusion')
import theme_core
from theme_tokens import apply_palette, refresh_widgets, color, tokens
from theme_demo import ThemeDemo
widget = ThemeDemo(); widget.resize(260, 120); widget.show(); app.processEvents()
seen = {}
for style, variant in %r:
    os.environ['WYSUN_THEME'] = style + ':' + variant
    theme_core.invalidate(); refresh_widgets(); app.processEvents()
    image = widget.grab().toImage()
    expected = color('surface').name().lower()
    seen[style + ':' + variant] = [image.pixelColor(130, 60).name().lower() == expected or image.pixelColor(30, 60).name().lower() == expected, widget.caption.text(), widget.action.styleSheet() != '' or widget.styleSheet().count(color('accent').name()) > 0]
print(json.dumps(seen))
''' % (str(ROOT / 'apps/wysun'), VARIANTS)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        out = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        seen = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(set(seen), {a + ':' + b for a, b in VARIANTS})
        self.assertTrue(all(row[0] for row in seen.values()), seen)
        self.assertEqual(len({row[1] for row in seen.values()}), 5, 'caption names every variant')


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is not installed')
class QuickshellDemo(unittest.TestCase):
    def test_singleton_follows_theme_json_live_for_each_variant(self):
        with tempfile.TemporaryDirectory(prefix='wysun-qs-') as temp:
            temp = Path(temp)
            shell = temp / 'shell'
            shutil.copytree(ROOT / 'apps/shell', shell, ignore=shutil.ignore_patterns('tests', '__pycache__'))
            config = temp / 'cfg'
            (config / 'orbit').mkdir(parents=True)
            (config / 'orbit/theme.json').write_text('{"id":"Tokyo"}')
            steps = ['{"style":"%s","variant":"%s"}' % pair for pair in VARIANTS]
            (shell / 'shell.qml').write_text('''
import Quickshell
import QtQuick
ShellRoot {
    Preferences { id: prefs }
    ThemeDemo { id: demo }
    property var steps: %s
    property int index: -1
    function report(tag) { console.log("RESULT|" + tag + "|" + Appearance.style + "|" + Appearance.variant + "|" + Appearance.surface + "|" + demo.color + "|" + demo.border.color); }
    Timer { id: first; interval: 400; running: true; onTriggered: { report("legacy"); step.start(); } }
    Timer {
        id: step; interval: 350; repeat: true
        onTriggered: {
            if (index >= 0) report("step");
            index++;
            if (index >= steps.length) { Qt.quit(); return; }
            Quickshell.execDetached(["sh", "-c", "printf '%%s' '" + steps[index] + "' > '%s/orbit/theme.json.new' && mv '%s/orbit/theme.json.new' '%s/orbit/theme.json'"]);
        }
    }
}
''' % (json.dumps(steps), config, config, config))
            env = dict(os.environ, HOME=str(temp), XDG_CONFIG_HOME=str(config), XDG_RUNTIME_DIR=str(temp), QT_QPA_PLATFORM='offscreen', WAYLAND_DISPLAY='')
            run = subprocess.run(['quickshell', '-p', str(shell / 'shell.qml'), '-n'], env=env, capture_output=True, text=True, timeout=40)
            rows = [line.split('RESULT|', 1)[1].split('|') for line in (run.stdout + run.stderr).splitlines() if 'RESULT|' in line]
            self.assertEqual([r[0] for r in rows], ['legacy'] + ['step'] * 5, run.stdout + run.stderr)
            self.assertEqual(rows[0][1:3], ['space-black', 'tokyo'], 'the legacy {"id"} file is understood')
            self.assertEqual([tuple(r[1:3]) for r in rows[1:]], VARIANTS)
            surfaces = [r[3] for r in rows[1:]]
            self.assertEqual(len(set(surfaces)), 5, 'each variant has its own surface colour')
            for row in rows[1:]:
                self.assertEqual(row[3], row[4], 'the widget paints the token it was given')


if __name__ == '__main__':
    unittest.main()

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


class CaelestiaPalettes(unittest.TestCase):
    """The Caelestia shell paints from the Wysun scheme producer: five distinct palettes."""
    def test_bridge_exposes_a_distinct_surface_for_each_variant(self):
        with tempfile.TemporaryDirectory(prefix='wysun-qs-') as home:
            env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home + '/config', XDG_STATE_HOME=home + '/state')
            out = subprocess.run([sys.executable, str(ROOT / 'apps/shell/wysun/backend.py'), 'schemes'], env=env,
                                 capture_output=True, text=True, timeout=60, check=True)
        palettes = json.loads(out.stdout)
        self.assertEqual(set(palettes), {a + ':' + b if a == 'fluent' else b for a, b in VARIANTS})
        surfaces = {key: value['default']['surface'] for key, value in palettes.items()}
        self.assertEqual(len(set(surfaces.values())), 5, surfaces)


if __name__ == '__main__':
    unittest.main()

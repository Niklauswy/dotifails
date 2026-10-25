"""A demo widget follows the theme live in the light and dark palettes and in every wallpaper (Qt and Quickshell)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = [('material-you', 'light'), ('material-you', 'dark')]


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
        self.assertEqual(len({row[1] for row in seen.values()}), 2, 'caption names every variant')


class ShellPalettes(unittest.TestCase):
    """The Wysun shell paints from the Wysun scheme producer: every wallpaper gives its own palette."""
    def test_bridge_exposes_a_distinct_palette_for_each_wallpaper_and_mode(self):
        from PIL import Image
        with tempfile.TemporaryDirectory(prefix='wysun-qs-') as home:
            env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home + '/config', XDG_STATE_HOME=home + '/state')
            for key in ('WYSUN_THEME', 'ORBIT_THEME'):
                env.pop(key, None)
            palettes = {}
            for name, rgb in (('red', (225, 36, 72)), ('blue', (25, 82, 224)), ('bright', (245, 240, 225))):
                image = Path(home, name + '.png')
                Image.new('RGB', (32, 32), rgb).save(image)
                out = subprocess.run([sys.executable, str(ROOT / 'apps/shell/wysun/backend.py'), 'preview', str(image)], env=env,
                                     capture_output=True, text=True, timeout=60, check=True)
                palettes[name] = json.loads(out.stdout)
        self.assertEqual({key: value['mode'] for key, value in palettes.items()}, {'red': 'dark', 'blue': 'dark', 'bright': 'light'})
        surfaces = {key: value['colours']['surface'] for key, value in palettes.items()}
        self.assertEqual(len(set(surfaces.values())), 3, surfaces)


if __name__ == '__main__':
    unittest.main()

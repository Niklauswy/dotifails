"""Contrato de fuentes: Rubik y Material Symbols desde el repo y la shell."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLYPHS = ROOT / "apps/wysun/assets/fonts/material-symbols-glyphs.txt"
MUSIC = {
    "music_note", "library_music", "favorite", "group", "download",
    "folder_open", "play_arrow", "pause", "skip_previous", "skip_next",
    "shuffle", "repeat", "lyrics", "volume_up", "search", "arrow_forward",
}


class GlyphContractTests(unittest.TestCase):
    def test_glyph_list_is_the_shared_contract(self):
        names = [line.strip() for line in GLYPHS.read_text().splitlines() if line.strip()]
        self.assertGreaterEqual(len(names), 150)
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(MUSIC.issubset(names))
        for name in ("dashboard", "notifications", "settings", "screenshot_monitor"):
            self.assertIn(name, names)
        # One per line, no inline annotations: the subset script reads them raw.
        for name in names:
            self.assertRegex(name, r"^[a-z0-9_]+$")


class QtFontTests(unittest.TestCase):
    def test_fonts_register_and_every_icon_is_a_ligature(self):
        with tempfile.TemporaryDirectory() as empty:
            script = r'''
import json, sys
from pathlib import Path
sys.path.insert(0, %r)
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication
app = QApplication([])
import wysun_fonts

fonts = wysun_fonts.register()
size = 48
metrics_font = QFont(fonts.icon_family()); metrics_font.setPixelSize(size)
metrics = QFontMetrics(metrics_font)
widths = {name: metrics.horizontalAdvance(fonts.icon(name)) for name in fonts.names()}
wide = {name: width for name, width in widths.items() if width > size + 1}
missing = [name for name, width in widths.items() if width <= 0]
fallback = wysun_fonts.Fonts(%r).register()
print(json.dumps({
    "text_family": fonts.family(),
    "icon_family": fonts.icon_family(),
    "text_path": str(fonts.text_path or ""),
    "icon_path": str(fonts.icon_path or ""),
    "count": len(fonts.names()),
    "wide": wide,
    "missing": missing,
    "unknown_icon": fonts.icon("not_a_real_icon"),
    "fallback_icons": fallback.icons_available,
    "fallback_icon": fallback.icon("play_arrow"),
    "fallback_family": fallback.family(),
}))
''' % (str(ROOT / "apps/wysun"), empty)
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            result = subprocess.run(["/usr/bin/python3", "-c", script], text=True,
                                    capture_output=True, env=env, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(data["text_family"], "Rubik", data)
        self.assertEqual(data["icon_family"], "Material Symbols Rounded", data)
        self.assertTrue(Path(data["text_path"]).is_file())
        self.assertTrue(Path(data["icon_path"]).is_file())
        self.assertGreaterEqual(data["count"], 150)
        self.assertEqual(data["missing"], [])
        self.assertEqual(data["wide"], {})
        self.assertEqual(data["unknown_icon"], "\u25cb")
        self.assertFalse(data["fallback_icons"])
        self.assertEqual(data["fallback_icon"], "\u25cb")
        self.assertTrue(data["fallback_family"])


if __name__ == "__main__":
    unittest.main()

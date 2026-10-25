"""wysun_core.ui: bundled fonts, Material symbols and the type scale every Qt app shares."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wysun'))
from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from wysun_core.qt_theme import tokens  # noqa: E402
from wysun_core.ui import fonts, style  # noqa: E402


class CoreUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_fonts_load_from_wysun_core(self):
        families = fonts.load_fonts()
        self.assertIn(fonts.TEXT_FAMILY, families)
        self.assertIn(fonts.SYMBOL_FAMILY, families)
        self.assertTrue(str(fonts.FONT_DIR).endswith('wysun_core/fonts'))

    def paint(self, name):
        image = QImage(48, 48, QImage.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        painted = style.paint_symbol(painter, QRectF(0, 0, 48, 48), name, 'text', 24)
        painter.end()
        return painted, image

    def test_paint_symbol_reports_a_missing_glyph(self):
        painted, image = self.paint('play_arrow')
        self.assertTrue(painted)
        self.assertTrue(any(image.pixelColor(x, y).alpha() for x in range(48) for y in range(48)))
        painted, image = self.paint('no_such_ligature_xyz')
        self.assertFalse(painted)
        self.assertFalse(any(image.pixelColor(x, y).alpha() for x in range(48) for y in range(48)))

    def test_text_font_and_metric_follow_tokens(self):
        self.assertEqual(style.text_font('body').pixelSize(), tokens()['font_body'])
        self.assertEqual(style.metric('space_m'), tokens()['space_m'])

    def test_clock_formats(self):
        self.assertEqual((style.clock(5), style.clock(3725), style.clock(None)), ('0:05', '1:02:05', '0:00'))


if __name__ == '__main__':
    unittest.main()

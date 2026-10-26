"""Files wraps names with the font it paints them in (the theme's point-sized type scale)."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from PySide6.QtGui import QFontMetrics  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from wysun_core.ui.style import text_font  # noqa: E402
from wysun_files.fileview import wrapped  # noqa: E402


class WrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_lines_fit_the_width_in_the_painted_font(self):
        font = text_font('title.large', 600, 1.5)
        metrics = QFontMetrics(font)
        width = metrics.horizontalAdvance('informe') * 2
        lines = wrapped('informe trimestral de ventas por región.pdf', font, width, 3)
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertLessEqual(metrics.horizontalAdvance(line), width, line)


if __name__ == '__main__':
    unittest.main()

"""Music home tiles keep their text clear of the corner badge at the point type scale."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


class Covers(QObject):
    updated = Signal(object)

    def path(self, _key):
        return None


class BentoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_text_never_runs_under_the_badge(self):
        from wysun_music.ui.cards import BentoTile
        for style, title, subtitle in (('accent', 'Tus me gusta', '0 canciones'),
                                       ('tonal', 'Mezcla', 'Toda tu biblioteca, al azar')):
            tile = BentoTile(Covers(), title, subtitle, style, eyebrow='Colección')
            tile.resize(206, 200)
            eyebrow, heading, sub = tile.text_rects()
            badge = tile.badge_rect().toAlignedRect()
            self.assertFalse(sub.intersects(badge), (style, sub, badge))
            self.assertLessEqual(eyebrow.bottom(), heading.top())
            self.assertLessEqual(heading.top(), sub.top())
            tile.deleteLater()


if __name__ == '__main__':
    unittest.main()

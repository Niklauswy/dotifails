"""The PDF reader paints from the shared theme. No PyMuPDF needed, so the default suite runs it.

The reader's only theme choice of its own is the sun/moon menu (pdf_theme.ReaderMode), a thin layer over
qt_theme: a pinned mode different from the desktop's selects that base palette for the reader's process.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

APP = Path(__file__).resolve().parents[1] / 'apps/wysun'
sys.path.insert(0, str(APP))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication  # noqa: E402


class PdfThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {'HOME': self.tmp.name, 'XDG_CONFIG_HOME': self.tmp.name + '/config',
                                               'XDG_STATE_HOME': self.tmp.name + '/state', 'WYSUN_THEME': 'dark'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        from wysun_core import qt_theme
        qt_theme.invalidate()
        self.addCleanup(qt_theme.invalidate)

    def reader_mode(self):
        from pdf_state import Preferences
        from pdf_theme import ReaderMode
        mode = ReaderMode(Preferences())
        self.addCleanup(mode.release)
        return mode

    def test_the_reader_follows_the_desktop_until_a_mode_is_pinned(self):
        from wysun_core import qt_theme
        mode = self.reader_mode()
        self.assertIsNone(mode.pinned)
        self.assertEqual(mode.mode, 'dark')
        self.assertEqual(os.environ['WYSUN_THEME'], 'dark')
        self.assertEqual(qt_theme.tokens()['mode'], 'dark')

    def test_pinning_the_other_mode_repaints_the_reader_with_that_palette(self):
        from wysun_core import qt_theme
        mode = self.reader_mode()
        dark = qt_theme.color('canvas').lightnessF()
        mode.set('light')
        self.assertEqual(qt_theme.tokens()['mode'], 'light')
        self.assertGreater(qt_theme.color('canvas').lightnessF(), dark)
        mode.set(None)
        self.assertEqual(qt_theme.tokens()['mode'], 'dark')
        self.assertEqual(os.environ['WYSUN_THEME'], 'dark')

    def test_pinning_the_desktop_mode_keeps_the_wallpaper_colours(self):
        with mock.patch.dict(os.environ):
            del os.environ['WYSUN_THEME']
            mode = self.reader_mode()
            desktop = mode.mode
            mode.set(desktop)
            self.assertNotIn('WYSUN_THEME', os.environ)
            self.assertEqual(mode.pinned, desktop)

    def test_a_pinned_mode_is_kept_across_launches(self):
        self.reader_mode().set('light')
        stored = json.loads((Path(self.tmp.name) / 'config/wysun/pdf-reader.json').read_text())
        self.assertEqual(stored['mode'], 'light')
        self.assertEqual(self.reader_mode().mode, 'light')

    def test_links_open_with_the_original_environment(self):
        mode = self.reader_mode()
        mode.set('light')
        self.assertEqual(mode.environment()['WYSUN_THEME'], 'dark')

    def test_every_symbol_the_reader_paints_is_in_the_bundled_font(self):
        from pdf_theme import SYMBOLS
        from wysun_core.ui.fonts import ligature_available, load_fonts
        load_fonts()
        self.assertGreater(len(SYMBOLS), 20)
        for name in SYMBOLS:
            self.assertTrue(ligature_available(name), name)


if __name__ == '__main__':
    unittest.main()

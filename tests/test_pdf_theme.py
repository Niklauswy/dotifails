"""The PDF reader paints from the shared theme tokens. No PyMuPDF needed, so the default suite runs it.

A token or font helper the reader depends on that is renamed or removed fails here, not when someone opens a PDF.
"""
import json
import os
import re
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

    def test_every_role_resolves_to_a_colour_in_both_modes(self):
        from pdf_material import ROLES, ReaderTheme
        for mode in ('light', 'dark'):
            theme = ReaderTheme(mode=mode)
            for role in ROLES:
                self.assertTrue(theme.color(role).isValid(), f'{role} in {mode}')

    def test_every_size_the_reader_asks_for_resolves(self):
        from pdf_material import M
        source = ''.join((APP / name).read_text() for name in ('pdf_window.py', 'pdf_material.py'))
        # Text sizes are looked up as M['font_' + role] for the roles the widgets are built with.
        names = set(re.findall(r"\bM\['([a-z_]+)'\]", source)) | {f'font_{role}' for role in ('small', 'body', 'heading', 'title')}
        self.assertGreater(len(names), 10)
        for name in names:
            self.assertGreater(M[name], 0, name)

    def test_fonts_for_text_and_icons_load(self):
        from pdf_material import ReaderTheme
        theme = ReaderTheme()
        self.assertTrue(theme.font('body', 500).pixelSize() > 0)
        from wysun_core.ui.fonts import symbol_family
        self.assertEqual(symbol_family(), 'Material Symbols Rounded')

    def test_reader_follows_the_desktop_until_its_button_pins_a_mode(self):
        from pdf_material import ReaderTheme
        from wysun_core import qt_theme
        self.assertEqual(ReaderTheme().mode, 'dark')
        with mock.patch.dict(os.environ, {'WYSUN_THEME': 'light'}):
            qt_theme.invalidate()
            self.assertEqual(ReaderTheme().mode, 'light')
        qt_theme.invalidate()
        theme = ReaderTheme()
        theme.set_mode('light')
        self.assertEqual(theme.mode, 'light')
        self.assertFalse(theme.path.exists(), 'pinning without persist must not write')

    def test_a_pinned_mode_is_kept_across_launches(self):
        from pdf_material import ReaderTheme
        ReaderTheme().set_mode('light', persist=True)
        self.assertEqual(json.loads(ReaderTheme().path.read_text()), {'mode': 'light'})
        self.assertEqual(ReaderTheme().mode, 'light')

    def test_the_pinned_mode_paints_with_its_own_palette(self):
        from pdf_material import ReaderTheme
        theme = ReaderTheme()
        dark = theme.color('canvas').lightnessF()
        theme.set_mode('light')
        self.assertGreater(theme.color('canvas').lightnessF(), dark)


if __name__ == '__main__':
    unittest.main()

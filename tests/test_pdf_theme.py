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

    def test_the_reader_has_no_theme_of_its_own(self):
        self.assertFalse((APP / 'pdf_material.py').exists())
        for path in APP.glob('pdf_*.py'):
            self.assertNotIn('ReaderTheme', path.read_text(), path.name)


class PdfChromeTests(unittest.TestCase):
    """The reader's widgets build from the kit in both modes, are named for assistive tech and behave."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from wysun_core import qt_theme
        qt_theme.invalidate()
        self.addCleanup(qt_theme.invalidate)

    def widgets(self):
        from PySide6.QtWidgets import QWidget
        from pdf_chrome import EmptyState, NoteDialog, PageIndicator, SelectionBar, ViewModeSwitch, ZoomControl
        from pdf_sidebar import Sidebar
        host = QWidget()
        host.resize(900, 700)
        self.addCleanup(host.deleteLater)
        return host, [ZoomControl(), ViewModeSwitch(), PageIndicator(host), SelectionBar(host), EmptyState(),
                      Sidebar(), NoteDialog(host, 'texto')]

    def test_widgets_build_in_both_modes_with_accessible_names(self):
        from PySide6.QtWidgets import QAbstractButton
        for mode in ('light', 'dark'):
            with mock.patch.dict(os.environ, {'WYSUN_THEME': mode}):
                from wysun_core import qt_theme
                qt_theme.invalidate()
                _, widgets = self.widgets()
                for widget in widgets:
                    self.assertFalse(widget.grab().isNull(), type(widget).__name__)
                    self.assertNotIn('@', widget.styleSheet())
                    for button in widget.findChildren(QAbstractButton):
                        self.assertTrue(button.accessibleName(), f'{type(widget).__name__}: unnamed button')

    def test_zoom_control_shows_percent_and_reports_choices(self):
        from pdf_chrome import ZoomControl
        control = ZoomControl()
        control.set_zoom(1.25, 'custom')
        self.assertEqual(control.label.text(), '125 %')
        chosen = []
        control.fit.connect(chosen.append)
        control.percent.connect(chosen.append)
        control.choose('width')
        control.choose(2.0)
        self.assertEqual(chosen, ['width', 2.0])

    def test_view_mode_switch_is_exclusive(self):
        from pdf_chrome import ViewModeSwitch
        switch = ViewModeSwitch()
        modes = []
        switch.changed.connect(modes.append)
        switch.buttons['spread'].click()
        self.assertEqual(modes, ['spread'])
        self.assertFalse(switch.buttons['single'].isChecked())
        switch.set_mode('single')
        self.assertTrue(switch.buttons['single'].isChecked())

    def test_page_indicator_jumps_to_a_typed_page(self):
        from PySide6.QtWidgets import QWidget
        from pdf_chrome import PageIndicator
        host = QWidget()
        indicator = PageIndicator(host)
        indicator.set_page(2, 40)
        self.assertIn('3', indicator.accessibleName())
        jumps = []
        indicator.jump.connect(jumps.append)
        indicator.start_edit()
        indicator.editor.setText('17')
        indicator.editor.returnPressed.emit()
        self.assertEqual(jumps, [16])
        indicator.start_edit()
        indicator.editor.setText('99')
        indicator.editor.returnPressed.emit()
        self.assertEqual(jumps, [16, 39])

    def test_selection_bar_sits_above_the_selection_and_hides_edits(self):
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QWidget
        from pdf_chrome import SelectionBar
        host = QWidget()
        host.resize(800, 600)
        bar = SelectionBar(host)
        bar.place(QRect(300, 300, 120, 20))
        self.assertLessEqual(bar.geometry().bottom(), 300)
        bar.place(QRect(300, 4, 120, 20))
        self.assertGreaterEqual(bar.geometry().top(), 24)
        bar.set_editable(False)
        self.assertTrue(bar.buttons['highlight'].isHidden())
        self.assertFalse(bar.buttons['copy'].isHidden())

    def test_sidebar_lists_results_with_context_and_emits(self):
        from pdf_sidebar import Sidebar
        sidebar = Sidebar()
        sidebar.set_results('idea', [(4, 'una idea clara'), (9, 'otra idea')])
        self.assertEqual(sidebar.results.count(), 2)
        chosen = []
        sidebar.result_requested.connect(chosen.append)
        sidebar.results.itemActivated.emit(sidebar.results.item(1))
        self.assertEqual(chosen, [1])
        sidebar.set_notes([{'page': 2, 'xref': 7, 'type': 'Text', 'text': 'Volver aquí'}])
        self.assertIn('Volver aquí', sidebar.notes.item(0).text())
        sidebar.set_tab(2)
        self.assertEqual(sidebar.heading.text(), 'Notas')

    def test_inks_start_with_the_theme_accent(self):
        from pdf_chrome import ink_colours
        from wysun_core import qt_theme
        inks = ink_colours()
        self.assertEqual(inks[0][1], qt_theme.color('accent'))
        self.assertEqual(len(inks), 5)


if __name__ == '__main__':
    unittest.main()

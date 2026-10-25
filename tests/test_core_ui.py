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
from unittest import mock  # noqa: E402


class CoreUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_fonts_load_from_wysun_core(self):
        families = fonts.load_fonts()
        self.assertIn(fonts.TEXT_FAMILY, families)
        self.assertIn(fonts.SYMBOL_FAMILY, families)
        self.assertTrue(str(fonts.FONT_DIR).endswith('wysun_core/fonts'))

    def test_symbol_family_is_named_once_loaded(self):
        fonts.load_fonts()
        self.assertEqual(fonts.symbol_family(), fonts.SYMBOL_FAMILY)

    def paint(self, name):
        image = QImage(48, 48, QImage.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        painted = style.paint_symbol(painter, QRectF(0, 0, 48, 48), name, 'text', 24)
        painter.end()
        return painted, image

    def test_paint_symbol_reports_a_missing_glyph(self):
        self.addCleanup(style.set_symbol_fallback, style.set_symbol_fallback(None))   # as in the Recorder
        painted, image = self.paint('play_arrow')
        self.assertTrue(painted)
        self.assertTrue(any(image.pixelColor(x, y).alpha() for x in range(48) for y in range(48)))
        painted, image = self.paint('no_such_ligature_xyz')
        self.assertFalse(painted)
        self.assertFalse(any(image.pixelColor(x, y).alpha() for x in range(48) for y in range(48)))

    def test_a_registered_fallback_paints_missing_glyphs(self):
        calls = []
        previous = style.set_symbol_fallback(lambda painter, rect, name, ink, size: calls.append(name))
        self.addCleanup(style.set_symbol_fallback, previous)
        painted, _ = self.paint('no_such_ligature_xyz')
        self.assertTrue(painted)
        self.assertEqual(calls, ['no_such_ligature_xyz'])

    def test_kit_buttons_fall_back_to_lucide_in_wysun_apps(self):
        import icons  # noqa: F401  (registers the Lucide fallback, as every Wysun app does)
        from wysun_core.ui.widgets import IconButton
        def render():
            with mock.patch('wysun_core.ui.style.ligature_available', return_value=False):
                button = IconButton('play_arrow', 'Reproducir', lambda: None)
                button.resize(40, 40)
                return button.grab().toImage()
        lucide = style.set_symbol_fallback(None)
        self.addCleanup(style.set_symbol_fallback, lucide)
        self.assertIsNotNone(lucide, 'importing icons registers the Lucide fallback')
        blank = render()
        style.set_symbol_fallback(lucide)
        self.assertNotEqual(render(), blank, 'the Lucide glyph is drawn where the symbol is missing')

    def test_text_font_and_metric_follow_tokens(self):
        self.assertEqual(style.text_font('body').pixelSize(), tokens()['font_body'])
        self.assertEqual(style.metric('space_m'), tokens()['space_m'])

    def test_clock_formats(self):
        self.assertEqual((style.clock(5), style.clock(3725), style.clock(None)), ('0:05', '1:02:05', '0:00'))


class FramelessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def window(self, drag_height):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QWidget
        from wysun_core.ui.frameless import FramelessResize

        class Window(FramelessResize, QWidget):
            pass
        window = Window()
        window.drag_height = drag_height
        window.resize(400, 300)
        window.show()
        self.addCleanup(window.close)
        handle = mock.Mock()
        window.windowHandle = lambda: handle

        def press(x, y):
            window.mousePressEvent(QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(x, y), QPointF(x, y),
                                               Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        return window, handle, press

    def test_edges_and_drag_area(self):
        from PySide6.QtCore import QPoint, Qt
        from wysun_core.ui.frameless import resize_edges
        window, handle, press = self.window(50)
        self.assertEqual(resize_edges(window, QPoint(2, 150)), Qt.Edges(Qt.LeftEdge))
        self.assertEqual(resize_edges(window, QPoint(398, 298)), Qt.Edges(Qt.RightEdge | Qt.BottomEdge))
        self.assertEqual(resize_edges(window, QPoint(200, 150)), Qt.Edges())
        press(200, 20)
        handle.startSystemMove.assert_called_once()
        press(2, 150)
        handle.startSystemResize.assert_called_once_with(Qt.Edges(Qt.LeftEdge))
        press(200, 150)
        self.assertEqual(handle.startSystemMove.call_count, 1, 'below the drag strip nothing moves')

    def test_whole_window_drags_without_a_strip_and_gestures_can_be_disabled(self):
        window, handle, press = self.window(None)
        press(200, 250)
        handle.startSystemMove.assert_called_once()
        window.frame_gestures_enabled = lambda: False
        press(200, 250)
        handle.startSystemMove.assert_called_once()

    def test_toast_shows_and_hides(self):
        import time
        from PySide6.QtWidgets import QWidget
        from wysun_core.ui.toast import Toast
        parent = QWidget()
        parent.resize(400, 300)
        parent.show()
        self.addCleanup(parent.close)
        toast = Toast(parent, duration=60, bottom=112)
        toast.show_message('Hola')
        self.assertTrue(toast.isVisible())
        self.assertEqual((toast.text(), toast.geometry().top()), ('Hola', 300 - 112))
        end = time.monotonic() + 1
        while toast.isVisible() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(.01)
        self.assertFalse(toast.isVisible())

if __name__ == '__main__':
    unittest.main()

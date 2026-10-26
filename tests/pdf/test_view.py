"""DocumentView with a scripted source: virtualization, zoom anchoring, spreads, selection and links."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AVAILABLE = importlib.util.find_spec('PySide6') is not None
if AVAILABLE:
    from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, Signal
    from PySide6.QtGui import QMouseEvent, QWheelEvent
    from PySide6.QtWidgets import QApplication
    from wysun_pdf.layout import anchor, locate
    from wysun_pdf.view import DocumentView

    class FakeSource(QObject):
        changed = Signal(int)
        info_ready = Signal(int)

        def __init__(self):
            super().__init__()
            self.wants, self.infos = [], {}

        def want(self, requests):
            self.wants.append(list(requests))

        def image(self, page, width):
            return None, False

        def info(self, page):
            return self.infos.get(page)

A4 = [595.0, 842.0]
WORDS = [[72, 90, 110, 100, 'one', 0, 0], [120, 90, 160, 100, 'two', 0, 0], [72, 110, 110, 120, 'three', 0, 1]]


@unittest.skipUnless(AVAILABLE, 'PySide6 required')
class ViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.source = FakeSource()
        self.view = DocumentView(self.source)
        self.view.resize(800, 600)
        self.view.show()
        self.view.set_document([A4] * 60)
        self.app.processEvents()

    def tearDown(self):
        self.view.close()

    def requested_pages(self):
        return {page for want in self.source.wants for page, _ in want}

    def mouse(self, kind, point, buttons=Qt.LeftButton, button=Qt.LeftButton):
        self.app.sendEvent(self.view.viewport(), QMouseEvent(kind, point, self.view.viewport().mapToGlobal(point),
                                                             button, buttons, Qt.NoModifier))

    def test_only_visible_pages_are_requested(self):
        self.view.set_zoom(1.0)
        self.view.go(30)
        self.source.wants.clear()
        self.view.request()
        top = self.view.verticalScrollBar().value()
        height = self.view.viewport().height()
        band = set(self.view.layout.visible(top - height / 2, top + height * 1.5))
        pages = self.requested_pages()
        self.assertIn(30, pages)
        self.assertTrue(pages <= band, (pages, band))
        self.assertEqual(self.source.wants[-1][0][0], 30, 'visible pages are asked first')

    def test_requested_width_follows_zoom_and_pixel_ratio(self):
        self.view.set_zoom(1.0)
        self.view.request()
        width = self.source.wants[-1][0][1]
        expected = 595 * 4 / 3 * self.view.devicePixelRatioF()
        self.assertLessEqual(abs(width - expected), 8)

    def test_zoom_defers_new_rasters_until_it_settles(self):
        self.view.set_zoom(1.0)
        self.view.request()
        self.source.wants.clear()
        self.view.zoom_by(1.1, QPointF(300, 200))
        self.view.zoom_by(1.1, QPointF(300, 200))
        self.assertEqual(self.source.wants, [], 'zoom steps scale what is there')
        self.view.render_timer.timeout.emit()
        self.assertEqual(len(self.source.wants), 1)

    def test_ctrl_wheel_keeps_point_under_cursor(self):
        self.view.set_zoom(1.0)
        self.view.go(10)
        point = QPointF(300, 200)
        hbar, vbar = self.view.horizontalScrollBar(), self.view.verticalScrollBar()
        mark = anchor(self.view.layout, hbar.value() + point.x(), vbar.value() + point.y())
        event = QWheelEvent(point, self.view.viewport().mapToGlobal(point), QPoint(), QPoint(0, 120),
                            Qt.NoButton, Qt.ControlModifier, Qt.NoScrollPhase, False)
        self.app.sendEvent(self.view.viewport(), event)
        self.assertAlmostEqual(self.view.zoom, 1.1, places=3)
        self.assertEqual(self.view.zoom_mode, 'custom')
        x, y = locate(self.view.layout, mark)
        self.assertLess(abs(x - hbar.value() - point.x()), 2)
        self.assertLess(abs(y - vbar.value() - point.y()), 2)

    def test_keyboard_zoom_keeps_the_centre(self):
        self.view.set_zoom(1.0)
        self.view.go(10)
        before = self.view.current_page()
        self.view.zoom_by(1.25)
        self.assertEqual(self.view.current_page(), before)

    def test_spread_places_pairs_side_by_side(self):
        self.view.set_mode('spread')
        rects = self.view.layout.rects
        self.assertEqual(rects[0][1], rects[1][1])
        self.assertGreater(rects[1][0], rects[0][0])
        self.view.go(7)
        self.assertIn(self.view.current_page(), (6, 7))

    def test_fit_width_tracks_resize(self):
        self.view.set_fit('width')
        self.view.resize(1000, 600)
        self.app.processEvents()
        width = self.view.layout.rects[0][2]
        self.assertAlmostEqual(width, self.view.viewport().width() - 2 * self.view.layout.margin, delta=1)

    def test_position_roundtrip(self):
        self.view.set_mode('spread')
        self.view.set_zoom(1.5)
        self.view.go(20)
        state = self.view.position()
        other = DocumentView(FakeSource())
        other.resize(800, 600)
        other.set_document([A4] * 60)
        other.restore(state)
        self.assertEqual((other.mode, other.zoom, other.current_page()), ('spread', 1.5, self.view.current_page()))

    def test_drag_selects_across_lines(self):
        self.source.infos[0] = {'words': WORDS, 'links': [], 'annotations': []}
        self.view.set_zoom(1.0)
        self.view.go(0)
        finished = []
        self.view.selectionFinished.connect(lambda: finished.append(True))
        start = self.view.to_viewport(0, 90, 95)
        end = self.view.to_viewport(0, 90, 115)
        self.mouse(QEvent.MouseButtonPress, start)
        self.mouse(QEvent.MouseMove, end, Qt.LeftButton, Qt.NoButton)
        self.mouse(QEvent.MouseButtonRelease, end, Qt.NoButton)
        self.assertEqual(self.view.selection, (0, [0, 1, 2]))
        self.assertEqual(self.view.selected_text(), 'one two\nthree')
        self.assertEqual(finished, [True])
        self.assertTrue(self.view.selection_rect().isValid())

    def test_selection_paints_one_band_per_line(self):
        bands = list(DocumentView._lines(WORDS, [0, 1, 2]))
        self.assertEqual(bands, [[72, 90, 160, 100], [72, 110, 110, 120]])

    def test_click_on_link_emits(self):
        self.source.infos[0] = {'words': WORDS, 'links': [{'rect': [72, 200, 200, 220], 'page': 3, 'y': 0}],
                                'annotations': []}
        self.view.set_zoom(1.0)
        self.view.go(0)
        links = []
        self.view.linkActivated.connect(links.append)
        point = self.view.to_viewport(0, 100, 210)
        self.mouse(QEvent.MouseButtonPress, point)
        self.mouse(QEvent.MouseButtonRelease, point, Qt.NoButton)
        self.assertEqual(links[0]['page'], 3)
        self.assertEqual(self.view.selection, (None, []))

    def test_note_mode_reports_the_page_point(self):
        self.view.set_zoom(1.0)
        self.view.go(2)
        notes = []
        self.view.noteRequested.connect(lambda page, point: notes.append((page, point)))
        self.view.note_mode = True
        self.mouse(QEvent.MouseButtonPress, self.view.to_viewport(2, 100, 150))
        self.assertEqual(notes[0][0], 2)
        self.assertAlmostEqual(notes[0][1].x(), 100, delta=1)
        self.assertAlmostEqual(notes[0][1].y(), 150, delta=1)

    def test_go_to_a_hit_scrolls_it_into_view(self):
        self.view.set_zoom(1.0)
        self.view.set_hits({40: [[72, 700, 120, 712]]}, current=(40, 0))
        point = self.view.to_viewport(40, 96, 706)
        self.assertTrue(self.view.viewport().rect().contains(point.toPoint()))


if __name__ == '__main__':
    unittest.main()

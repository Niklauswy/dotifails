"""Run with QT_QPA_PLATFORM=offscreen and an isolated HOME/XDG tree."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
AVAILABLE = all(importlib.util.find_spec(m) for m in ('fitz', 'PySide6'))
if AVAILABLE:
    import fitz
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPointF, Qt, QEvent
    from PySide6.QtGui import QMouseEvent
    from pdf_window import PdfWindow


@unittest.skipUnless(AVAILABLE, 'PySide6 and python3-fitz required')
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def wait(self, condition, timeout=8):
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            self.app.processEvents(); time.sleep(.01)
        self.assertTrue(condition(), 'asynchronous operation did not finish')

    def test_reader_workflow_and_live_themes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'Design notes.pdf'
            doc = fitz.open()
            for n in range(3):
                page = doc.new_page()
                page.insert_text((60, 80), 'WYSUN / DESIGN NOTES', fontsize=22)
                page.insert_text((60, 125), 'A quieter space for reading.', fontsize=15)
                page.insert_text((60, 165), 'Select a passage. Keep an idea. Return to what matters.', fontsize=12)
            doc.set_toc([[1, 'Reading with intention', 1], [1, 'Annotations', 2], [1, 'Next steps', 3]])
            doc.save(source); doc.close()
            window = PdfWindow(str(source)); window.show()
            try:
                self.wait(lambda: window.displayed_page == 0)
                self.assertFalse(window.canvas.image.isNull())
                self.assertEqual(window.pages, 3)
                self.wait(lambda: len(window.page_model.images) >= 2)
                self.assertEqual(window.page_model.rowCount(), 3)
                word = window.canvas.words[0]
                x = int((word[0] + word[2]) / 2 * window.canvas.width() / window.canvas.page_width)
                y = int((word[1] + word[3]) / 2 * window.canvas.height() / window.canvas.page_height)
                self.app.sendEvent(window.canvas, QMouseEvent(QEvent.MouseButtonPress, QPointF(x, y), QPointF(x, y), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
                self.app.sendEvent(window.canvas, QMouseEvent(QEvent.MouseButtonRelease, QPointF(x, y), QPointF(x, y), Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
                self.assertEqual(window.canvas.text(), 'WYSUN')
                window.mark('highlight')
                self.wait(lambda: not window.busy and window.annotations.count() == 1)
                self.assertTrue(window.dirty)
                window.save()
                self.wait(lambda: not window.busy)
                self.assertFalse(window.dirty)
                window.focus_search(); window.search.setText('quieter'); window.find()
                self.wait(lambda: '3/3' in window.search_status.text())
                self.assertEqual(window.results.count(), 3)
                window.search_go(window.results.item(1))
                self.wait(lambda: window.displayed_page == 1 and bool(window.canvas.hits))
                for variant in ('light', 'dark'):
                    window.reader_theme.set_mode(variant); self.app.processEvents()
                    self.assertEqual(window.reader_theme.mode, variant)
                    self.assertNotIn('@', window.styleSheet())
                    self.assertEqual(window.page, 1)
                    if os.environ.get('WYSUN_PDF_SCREENSHOTS'):
                        output = Path(os.environ['WYSUN_PDF_SCREENSHOTS']); output.mkdir(parents=True, exist_ok=True)
                        window.grab().save(str(output / (variant + '.png')))
                window.navigate(0); window.document_section(0)
                window.go(2); self.wait(lambda: window.displayed_page == 2)
                self.assertEqual(window.thumbnails.currentIndex().row(), 2)
                self.assertFalse(window.next.isEnabled())
            finally:
                window.dirty = False; window.busy = False; window.close()
            with fitz.open(source) as result:
                self.assertEqual(len(list(result[0].annots())), 1)


if __name__ == '__main__':
    unittest.main()

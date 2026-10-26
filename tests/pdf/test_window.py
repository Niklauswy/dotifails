"""The real reader window against the real engine. Run with QT_QPA_PLATFORM=offscreen and an isolated HOME/XDG tree.

WYSUN_PDF_SCREENSHOTS=<dir> also saves light and dark captures of the reader.
"""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
AVAILABLE = all(importlib.util.find_spec(m) for m in ('fitz', 'PySide6'))
if AVAILABLE:
    import fitz
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QKeyEvent, QKeySequence, QMouseEvent, QShortcut
    from PySide6.QtWidgets import QApplication
    from wysun_pdf.window import PdfWindow

LOREM = ('A quieter space for reading. Select a passage, keep an idea and return to what matters. '
         'Wysun lays every page out at once and paints only what you see.')


def make_pdf(path, pages=3, links=False):
    doc = fitz.open()
    for n in range(pages):
        page = doc.new_page()
        page.insert_text((60, 80), f'Chapter {n + 1}: Design notes', fontsize=22)
        y = 125
        for line in range(18):
            page.insert_text((60, y), LOREM[line * 7 % 60:][:70], fontsize=12)
            y += 20
        page.insert_text((60, 600), 'A quieter space for reading.', fontsize=12)
    if links:
        doc[0].insert_link({'kind': fitz.LINK_GOTO, 'page': 2, 'from': fitz.Rect(60, 690, 200, 710), 'to': fitz.Point(0, 0)})
        doc[0].insert_link({'kind': fitz.LINK_URI, 'uri': 'https://example.org/wysun', 'from': fitz.Rect(60, 720, 200, 740)})
    doc.set_toc([[1, 'Reading with intention', 1], [1, 'Annotations', 2], [1, 'Next steps', min(3, pages)]])
    doc.save(path)
    doc.close()


@unittest.skipUnless(AVAILABLE, 'PySide6 and python3-fitz required')
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def wait(self, condition, timeout=10, message='asynchronous operation did not finish'):
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(condition(), message)

    def open(self, name='Design notes.pdf', pages=3, links=False, path=None):
        if path is None:
            path = Path(self.tmp.name) / name
            make_pdf(path, pages, links)
        window = PdfWindow(str(path))
        window.resize(1280, 860)
        window.show()
        self.addCleanup(self.close, window)
        self.wait(lambda: window.ready())
        return window, path

    def close(self, window):
        window.dirty = False
        window.busy = False
        window.close()

    def select_first_word(self, window, page=0):
        view = window.view
        self.wait(lambda: view.source.info(page) is not None)
        word = view.source.info(page)['words'][0]
        start = view.to_viewport(page, word[0] + 1, (word[1] + word[3]) / 2)
        end = view.to_viewport(page, word[2] - 1, (word[1] + word[3]) / 2)
        for kind, point, buttons in ((QEvent.MouseButtonPress, start, Qt.LeftButton),
                                     (QEvent.MouseMove, end + QPointF(8, 0), Qt.LeftButton),
                                     (QEvent.MouseMove, end, Qt.LeftButton),
                                     (QEvent.MouseButtonRelease, end, Qt.NoButton)):
            button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
            self.app.sendEvent(view.viewport(), QMouseEvent(kind, point, view.viewport().mapToGlobal(point),
                                                            button, buttons, Qt.NoModifier))
        return view.selected_text()

    def test_study_note_library_and_reopen(self):
        window, source = self.open()
        text = self.select_first_word(window)
        window.study_note()
        self.assertTrue(window.notebook.isVisible())
        self.assertFalse(window.sidebar.isVisible())
        window.notebook.editor.setPlainText('A reflection anchored to this passage')
        self.assertTrue(window.notebook.save())
        self.assertFalse(window.dirty, 'Study notes must not dirty the PDF')
        identifier = window.study_document['id']
        self.assertEqual(window.study.entries(identifier)[0]['quote'], text)
        window.view.go(1)
        window.show_library()
        self.assertIs(window.workspace.currentWidget(), window.library)
        self.assertEqual(window.study.entries(identifier)[0]['page'], 0)
        window.open_recent(str(source))
        self.assertIs(window.workspace.currentWidget(), window.reader)
        self.assertEqual(window.view.current_page(), 1)
        window.close()
        reopened, _ = self.open(path=source)
        self.assertEqual(reopened.study_document['id'], identifier)
        self.assertEqual(reopened.study.entries(identifier)[0]['body'], 'A reflection anchored to this passage')

    def test_study_unsaved_note_blocks_navigation_on_cancel(self):
        from PySide6.QtWidgets import QMessageBox
        window, source = self.open()
        window.study_note()
        window.notebook.editor.setPlainText('Do not lose this')
        with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.Cancel):
            window.show_library()
            self.assertIs(window.workspace.currentWidget(), window.reader)
            window.close()
            self.assertTrue(window.isVisible())
        self.assertEqual(window.notebook.editor.toPlainText(), 'Do not lose this')
        window.notebook.save()

    def test_study_narrow_window_keeps_editor_and_toolbar_accessible(self):
        window, _ = self.open()
        window.study_note()
        window.resize(720, 480)
        self.app.processEvents()
        self.assertEqual(window.width(), 720)
        self.assertEqual(window.height(), 480)
        self.assertTrue(window.notebook.page_scroll.verticalScrollBar().maximum() > 0)
        window.focus_search()
        self.app.processEvents()
        self.assertEqual(window.width(), 720)
        self.assertTrue(window.search.isVisible())
        self.assertTrue(window.notebook.editor.isEnabled())

    def test_lookup_opens_without_network_and_reference_keeps_original_page(self):
        import json
        window, _ = self.open()
        selected = self.select_first_word(window)
        with mock.patch.object(window.lookup_panel.client, 'search') as search:
            window.consult_selection()
            self.assertTrue(window.lookup_panel.isVisible())
            self.assertEqual(window.lookup_panel.term.text(), selected)
            search.assert_not_called()
        original = window.view.current_page()
        window.view.go(1)
        window.save_reference(dict(title='Concept', body='An attributed excerpt', source='Wikipedia',
            url='https://en.wikipedia.org/wiki/Concept', attribution='CC BY-SA', language='en',
            term=selected, kind='concept'))
        entry = window.study.entries(window.study_document['id'])[0]
        self.assertEqual(entry['page'], original)
        self.assertEqual(entry['quote'], selected)
        self.assertIn('reference', json.loads(entry['anchor']))
        self.assertFalse(window.dirty)
        window.show_library()
        self.assertIsNone(window.lookup_context)
        window.save_reference(dict())
        self.assertEqual(len(window.study.entries(window.study_document['id'])), 1)

    def test_narrow_lookup_preserves_readable_canvas_on_return(self):
        window, _ = self.open()
        window.consult_selection()
        window.resize(720, 480)
        self.app.processEvents()
        self.assertFalse(window.stage.isVisible())
        self.assertTrue(window.lookup_panel.isVisible())
        window.hide_lookup()
        self.app.processEvents()
        self.assertTrue(window.stage.isVisible())
        self.assertEqual(window.width(), 720)

    def test_discard_study_edits_restores_saved_body(self):
        from PySide6.QtWidgets import QMessageBox
        window, _ = self.open()
        window.study_note()
        window.notebook.editor.setPlainText('Idea guardada')
        window.notebook.save()
        window.notebook.editor.setPlainText('Cambio descartado')
        with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.Discard):
            self.assertTrue(window.notebook.can_leave())
        self.assertEqual(window.notebook.editor.toPlainText(), 'Idea guardada')
        self.assertFalse(window.notebook.unsaved)

    def test_lookup_consent_cancel_does_not_send_text(self):
        from PySide6.QtWidgets import QMessageBox
        window, _ = self.open()
        window.preferences.set(lookup_allowed_translation=False)
        window.consult_selection()
        window.lookup_panel.term.setText('justice')
        with mock.patch.object(QMessageBox, 'question', return_value=QMessageBox.Cancel), \
                mock.patch.object(window.lookup_panel.client, 'search') as search:
            window.lookup_panel.search()
            search.assert_not_called()
        self.assertFalse(window.preferences.get('lookup_allowed_translation', False))

    def test_lookup_revocation_is_persistent(self):
        from wysun_pdf.study_ui import StudySettings
        from PySide6.QtWidgets import QCheckBox
        window, _ = self.open()
        window.preferences.set(lookup_allowed_translation=True)
        dialog = StudySettings(window.preferences, window.study, window)
        checkbox = next(box for box in dialog.findChildren(QCheckBox) if 'MyMemory' in box.text())
        self.assertTrue(checkbox.isChecked())
        checkbox.setChecked(False)
        self.assertFalse(window.preferences.get('lookup_allowed_translation'))
        checkbox.setChecked(True)
        self.assertFalse(checkbox.isChecked(), 'Consent is only granted with the contextual query preview')
        dialog.close()

    def test_reader_workflow_annotations_save_and_themes(self):
        window, source = self.open()
        self.assertEqual(window.pages, 3)
        self.assertEqual(window.sidebar.outline.count(), 3)
        self.assertEqual(self.select_first_word(window), 'Chapter')
        self.assertTrue(window.selection_bar.isVisible())
        window.mark('highlight')
        self.wait(lambda: not window.busy and window.sidebar.notes.count() == 1
                  and window.sidebar.selected_note() is None and window.dirty)
        self.assertTrue(window.save_button.isEnabled())
        window.save()
        self.wait(lambda: not window.busy)
        self.assertFalse(window.dirty)
        with fitz.open(source) as result:
            first = result[0]
            self.assertEqual([annotation.type[1] for annotation in first.annots()], ['Highlight'])
        for variant in ('light', 'dark'):
            window.reader_mode.set(variant)
            self.app.processEvents()
            self.assertEqual(window.reader_mode.mode, variant)
            self.assertNotIn('@', window.styleSheet())
            if os.environ.get('WYSUN_PDF_SCREENSHOTS'):
                output = Path(os.environ['WYSUN_PDF_SCREENSHOTS'])
                output.mkdir(parents=True, exist_ok=True)
                window.sidebar.set_tab(0)
                self.wait(lambda: len(window.sidebar.page_model.images) >= 2)
                self.wait(lambda: window.view.source.image(0, window.view.pixel_width(0))[1])
                window.grab().save(str(output / f'reader-{variant}.png'))
        window.reader_mode.set(None)

    def test_thumbnails_load_after_opening_another_document(self):
        window, _ = self.open(pages=12)
        window.set_sidebar(True)
        window.load_thumbnails()
        self.wait(lambda: window.thumbnail_pending)
        other = Path(self.tmp.name) / 'Other.pdf'
        make_pdf(other, 5)
        window.open_path(str(other), confirmed=True)
        self.wait(lambda: window.ready() and window.pages == 5)
        self.wait(lambda: bool(window.sidebar.page_model.images), message='thumbnails never loaded')

    def test_virtualization_in_window(self):
        window, _ = self.open('Long.pdf', pages=60)
        view = window.view
        window.fit('width')
        self.wait(lambda: view.source.image(0, view.pixel_width(0))[1])
        view.source.requested.clear()
        view.go(30)
        self.wait(lambda: view.source.image(30, view.pixel_width(30))[1])
        top, height = view.verticalScrollBar().value(), view.viewport().height()
        band = set(view.layout.visible(top - height / 2, top + height * 1.5))
        requested = {page for page, _ in view.source.requested}
        self.assertIn(30, requested)
        self.assertTrue(requested <= band, (requested, band))
        self.assertLessEqual(view.source.cache.bytes, 192 * 2 ** 20)
        self.assertEqual(window.indicator.label(), f'{view.current_page() + 1} / 60')

    def test_search_highlights_and_enter_navigates(self):
        window, _ = self.open()
        window.search.setText('quieter')
        window.search.returnPressed.emit()
        self.wait(lambda: window.search_done)
        self.assertEqual(len(window.matches), 6)
        self.assertEqual(sorted(window.view.hits), [0, 1, 2])
        self.assertEqual(window.sidebar.results.count(), 6)
        self.assertIn('quieter', window.sidebar.results.item(0).text())
        self.assertEqual(window.view.current_hit, (0, 0))
        self.assertEqual(window.hit_count.text(), '1/6')
        window.search.returnPressed.emit()
        window.search.returnPressed.emit()
        self.assertEqual(window.view.current_hit, (1, 0))
        self.assertEqual(window.view.current_page(), 1)
        shift_enter = QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.ShiftModifier)
        self.app.sendEvent(window.search, shift_enter)
        self.assertEqual(window.view.current_hit, (0, 1))
        window.sidebar.result_requested.emit(5)
        self.assertEqual(window.view.current_hit, (2, 1))

    def test_escape_in_search_clears_it(self):
        window, _ = self.open()
        window.activateWindow()
        window.focus_search()
        self.wait(lambda: window.search.hasFocus())
        window.search.setText('quieter')
        # The window-level Escape shortcut is what fires for a real key press in the field.
        escape = next(s for s in window.findChildren(QShortcut) if s.key() == QKeySequence('Escape'))
        escape.activated.emit()
        self.assertEqual(window.search.text(), '')
        self.assertFalse(window.search.hasFocus())

    def test_new_query_discards_old_hits(self):
        window, _ = self.open('Long.pdf', pages=12)
        window.search.setText('quieter')
        window.start_search()
        window.search.setText('matters')
        window.start_search()
        self.wait(lambda: window.search_done)
        contexts = [window.sidebar.results.item(i).text() for i in range(window.sidebar.results.count())]
        self.assertTrue(contexts)
        self.assertTrue(all('matters' in text for text in contexts), contexts)
        self.assertEqual(window.search_term, 'matters')

    def test_internal_and_external_links(self):
        window, _ = self.open('Links.pdf', links=True)
        view = window.view
        self.wait(lambda: view.source.info(0) is not None)
        links = view.source.info(0)['links']
        internal = next(link for link in links if 'page' in link)
        external = next(link for link in links if 'uri' in link)
        view.linkActivated.emit(internal)
        self.assertEqual(view.current_page(), 2)
        launched = []
        with mock.patch.object(window, 'confirm_link', return_value=True) as confirm, \
                mock.patch.object(window, 'launch_url', side_effect=launched.append):
            window.follow_link(external)
            confirm.assert_called_once_with('https://example.org/wysun')
            window.follow_link({'uri': 'javascript:alert(1)', 'rect': [0, 0, 1, 1]})
            window.follow_link({'uri': 'file:///etc/passwd', 'rect': [0, 0, 1, 1]})
        self.assertEqual(launched, ['https://example.org/wysun'])
        with mock.patch.object(window, 'confirm_link', return_value=False), \
                mock.patch.object(window, 'launch_url', side_effect=launched.append):
            window.follow_link(external)
        self.assertEqual(len(launched), 1)

    def test_spread_mode_and_zoom(self):
        window, _ = self.open(pages=6)
        window.set_view_mode('spread')
        self.assertEqual(window.view.mode, 'spread')
        self.assertTrue(window.view_switch.buttons['spread'].isChecked())
        rects = window.view.layout.rects
        self.assertEqual(rects[0][1], rects[1][1])
        window.fit('width')
        fitted = window.view.zoom
        window.zoom_in()
        self.assertGreater(window.view.zoom, fitted)
        self.assertEqual(window.view.zoom_mode, 'custom')
        self.assertEqual(window.zoom.label.text(), f'{round(window.view.zoom * 100)} %')
        window.fit('page')
        self.assertEqual(window.view.zoom_mode, 'page')

    def test_position_is_remembered(self):
        window, source = self.open('Remember.pdf', pages=20)
        window.set_view_mode('single')
        window.view.set_zoom(1.5)
        window.view.go(12)
        self.app.processEvents()
        page = window.view.current_page()
        window.close()
        again, _ = self.open(path=source)
        self.assertEqual(again.view.current_page(), page)
        self.assertEqual(again.view.zoom, 1.5)
        self.assertEqual(again.view.zoom_mode, 'custom')

    def test_note_and_delete_annotation(self):
        window, source = self.open()
        with mock.patch('wysun_pdf.window.NoteDialog') as dialog:
            dialog.return_value.exec.return_value = True
            dialog.return_value.editor.toPlainText.return_value = 'Remember this'
            window.view.noteRequested.emit(1, QPointF(100, 100))
        self.wait(lambda: not window.busy and window.sidebar.notes.count() == 1
                  and window.sidebar.notes.item(0).data(Qt.UserRole) is not None)
        note = window.sidebar.notes.item(0).data(Qt.UserRole)
        self.assertEqual((note['page'], note['text']), (1, 'Remember this'))
        window.sidebar.delete_requested.emit(note)
        self.wait(lambda: not window.busy and window.sidebar.notes.item(0).data(Qt.UserRole) is None)
        self.assertTrue(window.dirty)

    def test_engine_crash_disables_the_reader(self):
        window, _ = self.open()
        window.worker.process.kill()
        self.wait(lambda: window.busy)
        self.assertFalse(window.save_button.isEnabled())


if __name__ == '__main__':
    unittest.main()

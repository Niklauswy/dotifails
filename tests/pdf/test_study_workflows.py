"""Persistence and actual Files selector integration, using synthetic data only."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from wysun_pdf.study import StudyStore, StudyConflict
from wysun_pdf.study_ui import Notebook
from wysun_pdf.file_picker import pick_file
from wysun_files.chooser import FileChooser
from wysun_pdf.review_ui import ReviewDialog


class StudyWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = StudyStore(self.root / 'study.db')
        self.book = self.store.opened(self.root / 'original.pdf', 10)

    def test_collection_relocation_and_global_review_preserve_identity(self):
        note = self.store.save_entry(self.book['id'], 2, 'A passage', {}, 'Why? #ethics', 'question')
        self.store.collection(self.book['id'], 'Philosophy')
        moved = self.root / 'moved.pdf'
        moved.write_bytes(b'%PDF')
        self.store.relocate(self.book['id'], moved)
        self.store.forget(self.book['id'])
        self.assertEqual(self.store.recent(), [])
        self.assertEqual(self.store.documents()[0]['collection'], 'Philosophy')
        self.store.review(note['id'], 'My explanation', True)
        other = StudyStore(self.store.path)
        found = other.all_entries('#ethics', True)[0]
        self.assertEqual(found['path'], str(moved))
        self.assertEqual(found['answer'], 'My explanation')
        self.assertEqual(found['understood'], 1)
        self.assertEqual(other.opened(moved, 10)['id'], self.book['id'])

    def test_draft_survives_before_autosave_and_conflicts_keep_it(self):
        panel = Notebook(self.store)
        self.addCleanup(panel.deleteLater)
        panel.bind(self.book)
        panel.editor.setPlainText('An interrupted thought')
        panel.autosave.stop()
        recovered = StudyStore(self.store.path).drafts(self.book['id'])
        self.assertEqual(json.loads(recovered[0]['payload'])['body'], 'An interrupted thought')
        self.assertTrue(panel.save())
        self.assertEqual(self.store.drafts(self.book['id']), [])
        first = panel.entry
        self.store.save_entry(self.book['id'], 0, '', {}, 'Other window', entry=first)
        panel.editor.setPlainText('My concurrent edit')
        panel.autosave.stop()
        self.assertFalse(panel.save())
        self.assertTrue(panel.unsaved)
        self.assertEqual(self.store.entries(self.book['id'])[0]['body'], 'Other window')
        self.assertTrue(self.store.drafts(self.book['id']))

    def test_delete_undo_and_global_dialog(self):
        entry = self.store.save_entry(self.book['id'], 0, '', {}, 'Keep this')
        self.store.delete_entry(entry)
        self.store.restore_entry(entry)
        self.assertEqual(self.store.entries(self.book['id']), [entry])
        dialog = ReviewDialog(self.store)
        dialog.toggle()
        self.assertTrue(dialog.questions)
        dialog.search.setText('missing')
        self.assertIn('Sin resultados', dialog.status.text())
        dialog.deleteLater()

    def test_picker_client_protocol_restores_parent(self):
        import sys
        from PySide6.QtWidgets import QWidget
        parent = QWidget()
        pdf = self.root / 'chosen.pdf'
        script = "import json,sys; request=json.loads(sys.stdin.readline()); print(json.dumps({'code':0,'uris':[sys.argv[1]]}))"
        with patch('wysun_pdf.file_picker.launch.argv', return_value=[sys.executable, '-c', script, pdf.as_uri()]):
            self.assertEqual(pick_file(parent, 'Synthetic choice'), str(pdf))
        self.assertTrue(parent.isEnabled())
        parent.deleteLater()

    def test_real_files_selector_open_and_cancel_in_its_own_process(self):
        import subprocess
        import sys
        from wysun_core import launch
        pdf = self.root / 'example.pdf'
        pdf.write_bytes(b'%PDF-1.7\n')
        script = """
import json, sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from wysun_files.picker import make_selector
app = QApplication([])
chooser = make_selector(dict(title='Synthetic', initial=sys.argv[1]))
chooser.completed.connect(lambda code, result: print(json.dumps(dict(code=code, **result)), flush=True))
chooser.show()
QTimer.singleShot(50, (lambda: chooser.accept_selection([sys.argv[1]])) if sys.argv[2] == 'open' else chooser.close)
app.exec()
"""
        for action, expected in (('open', 0), ('cancel', 1)):
            result = subprocess.run([sys.executable, '-c', script, str(pdf), action],
                env=launch.environment(), capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            response = json.loads(result.stdout)
            self.assertEqual(response['code'], expected)
            if expected == 0:
                self.assertEqual(response['uris'], [pdf.as_uri()])

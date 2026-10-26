"""Study data survives reopening; concurrent editors never overwrite each other."""
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from wysun_pdf.study import StudyStore, StudyConflict


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'private' / 'study.sqlite3'
        self.store = StudyStore(self.path)
        self.book = self.store.opened(Path(self.tmp.name) / 'Ideas.pdf', 80, 12)

    def entry(self, body='Una interpretación propia'):
        return self.store.save_entry(self.book['id'], 12, 'Un pasaje', {'rects': [[1, 2, 3, 4]]}, body)

    def test_library_note_and_position_survive_reopening(self):
        note = self.entry()
        self.store.position(self.book['id'], 14)
        other = StudyStore(self.path)
        self.assertEqual(other.recent()[0]['page'], 14)
        self.assertEqual(other.recent()[0]['notes'], 1)
        self.assertEqual(other.entries(self.book['id'])[0], note)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)

    def test_conflicting_edits_and_delete_preserve_the_newer_text(self):
        first = self.entry()
        second = StudyStore(self.path)
        updated = second.save_entry(self.book['id'], 12, '', {}, 'Otra ventana', entry=first)
        with self.assertRaises(StudyConflict):
            self.store.save_entry(self.book['id'], 12, '', {}, 'Texto obsoleto', entry=first)
        with self.assertRaises(StudyConflict):
            self.store.delete_entry(first)
        self.assertEqual(self.store.entries(self.book['id'])[0]['body'], 'Otra ventana')
        self.store.delete_entry(updated)
        self.assertEqual(self.store.entries(self.book['id']), [])

    def test_forget_does_not_delete_notes_and_reopen_reuses_identity(self):
        self.entry()
        self.store.forget(self.book['id'])
        self.assertEqual(self.store.recent(), [])
        again = self.store.opened(self.book['path'], 80)
        self.assertEqual(again['id'], self.book['id'])
        self.assertEqual(len(self.store.entries(again['id'])), 1)

    def test_copy_has_separate_notebook_and_export_has_provenance(self):
        self.entry()
        copy = self.store.opened(Path(self.tmp.name) / 'Ideas copy.pdf', 80)
        self.assertNotEqual(copy['id'], self.book['id'])
        self.assertEqual(self.store.entries(copy['id']), [])
        exported = self.store.export(self.book['id'])
        self.assertIn('página PDF 13', exported)
        self.assertIn('> Un pasaje', exported)
        self.assertIn('Una interpretación propia', exported)

    def test_empty_note_is_not_written(self):
        with self.assertRaises(ValueError):
            self.entry('  ')
        self.assertEqual(self.store.entries(self.book['id']), [])

    def test_disabled_recent_and_clear_preserve_study_data(self):
        self.entry()
        self.store.opened(self.book['path'], 80, remember=False)
        self.assertEqual(self.store.recent(), [])
        self.assertEqual(len(self.store.entries(self.book['id'])), 1)
        self.store.opened(self.book['path'], 80)
        self.store.clear_recent()
        self.assertEqual(self.store.recent(), [])
        self.assertEqual(len(self.store.entries(self.book['id'])), 1)

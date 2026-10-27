"""wysun_files.picker: document requests (PDF reader) and audio files/folders (Wysun Music import)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


class PickerRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.home = tempfile.TemporaryDirectory()

    def selector(self, **request):
        from wysun_files.picker import make_selector
        chooser = make_selector(dict(initial=self.home.name, **request))
        self.addCleanup(self.destroy, chooser)
        return chooser

    def destroy(self, chooser):
        # Really gone (not just deleteLater without an event loop): later tests change the theme, and a live
        # chooser would still be registered for it.
        import gc
        import shiboken6
        chooser.close()
        shiboken6.delete(chooser)
        gc.collect()

    def test_audio_files_are_multiple_with_an_audio_filter(self):
        chooser = self.selector(kind='audio', multiple=True, title='Importar música')
        self.assertTrue(chooser.multiple)
        self.assertFalse(chooser.directory)
        name, patterns = chooser.filters[0]
        self.assertEqual(name, 'Audio')
        self.assertEqual(sorted(p for _, p in patterns),
                         sorted(f'*.{s}' for s in ('m4a', 'opus', 'mp3', 'flac', 'ogg', 'wav', 'aac')))

    def test_audio_folder(self):
        chooser = self.selector(kind='audio', directory=True)
        self.assertTrue(chooser.directory)

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            self.selector(kind='video')

    def test_document_requests_are_unchanged(self):
        chooser = self.selector(suffix='md')
        self.assertFalse(chooser.multiple)
        self.assertEqual(chooser.filters[0][0], 'MD')


if __name__ == '__main__':
    unittest.main()

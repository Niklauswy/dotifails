"""wysun_files.picker: a folder request (the Recorder's «Carpeta de videos»)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/python'))


class FolderRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.home.cleanup)

    def test_folder_request_asks_for_a_directory(self):
        from wysun_files.picker import request_options
        mode, title, options = request_options({'kind': 'folder', 'initial': self.home.name, 'title': 'Carpeta de videos'})
        self.assertEqual((mode, title), ('open', 'Carpeta de videos'))
        self.assertEqual(options, {'current_folder': os.fsencode(self.home.name), 'multiple': False, 'directory': True,
                                   'accept_label': 'Elegir', 'filters': []})

    def test_folder_request_has_a_default_title(self):
        from wysun_files.picker import request_options
        self.assertEqual(request_options({'kind': 'folder', 'initial': self.home.name})[1], 'Elegir carpeta')

    def test_folder_request_starts_from_the_nearest_existing_folder(self):
        from wysun_files.picker import request_options
        gone = Path(self.home.name) / 'gone' / 'x'
        self.assertEqual(request_options({'kind': 'folder', 'initial': str(gone)})[2]['current_folder'],
                         os.fsencode(self.home.name))

    def test_unknown_kind_still_fails(self):
        from wysun_files.picker import request_options
        with self.assertRaises(ValueError):
            request_options({'kind': 'spreadsheet', 'initial': self.home.name})


if __name__ == '__main__':
    unittest.main()

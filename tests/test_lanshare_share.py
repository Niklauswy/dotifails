"""LANShare: what is shared and how paths stay confined to it."""
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))

from wysun_lanshare.share import Share  # noqa: E402


class ShareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(os.path.realpath(self.tmp.name))
        self.base = base
        self.folder = base / 'Videos'
        (self.folder / 'Clases').mkdir(parents=True)
        (self.folder / 'Clases' / 'uno.mp4').write_bytes(b'v')
        (self.folder / 'nota.txt').write_text('hola')
        (self.folder / '.oculto').write_text('x')
        self.outside = base / 'secreto.txt'
        self.outside.write_text('no')
        os.symlink(self.outside, self.folder / 'fuga.txt')
        (base / 'a').mkdir()
        (base / 'b').mkdir()
        (base / 'a' / 'foto.jpg').write_bytes(b'1')
        (base / 'b' / 'foto.jpg').write_bytes(b'22')

    def tearDown(self):
        self.tmp.cleanup()

    def names(self, share, rel=''):
        return sorted(e['name'] for e in share.listing(rel))

    def test_folder_mode(self):
        share = Share([str(self.folder)])
        self.assertEqual(share.mode, 'folder')
        self.assertEqual(share.title, 'Videos')
        self.assertEqual(self.names(share), ['Clases', 'nota.txt'])
        clases = next(e for e in share.listing('') if e['name'] == 'Clases')
        self.assertEqual((clases['kind'], clases['count']), ('dir', 1))
        self.assertEqual(share.resolve('nota.txt'), str(self.folder / 'nota.txt'))
        self.assertEqual(share.resolve(''), str(self.folder))

    def test_confinement(self):
        share = Share([str(self.folder)])
        self.assertIsNone(share.resolve('fuga.txt'))
        self.assertIsNone(share.resolve('../secreto.txt'))
        self.assertIsNone(share.resolve('Clases/../../secreto.txt'))
        self.assertIsNone(share.resolve('.oculto'))
        with self.assertRaises(LookupError):
            share.listing('../')

    def test_a_hidden_file_shared_on_purpose_can_be_opened(self):
        share = Share([str(self.folder / '.oculto'), str(self.folder / 'nota.txt')])
        self.assertEqual(share.resolve('.oculto'), str(self.folder / '.oculto'))
        self.assertIn('.oculto', self.names(share))
        alone = Share([str(self.folder / '.oculto')])
        self.assertEqual(alone.resolve('.oculto'), str(self.folder / '.oculto'))
        whole = Share([str(self.folder), str(self.base / 'a')])
        self.assertIsNone(whole.resolve('Videos/.oculto'), 'what is inside a shared folder stays hidden')

    def test_list_mode_with_same_names(self):
        share = Share([str(self.base / 'a' / 'foto.jpg'), str(self.base / 'b' / 'foto.jpg'), str(self.folder)])
        self.assertEqual(share.mode, 'list')
        self.assertEqual(share.title, '3 elementos')
        self.assertEqual(self.names(share), ['Videos', 'foto (2).jpg', 'foto.jpg'])
        self.assertEqual(Path(share.resolve('foto.jpg')).read_bytes(), b'1')
        self.assertEqual(Path(share.resolve('foto (2).jpg')).read_bytes(), b'22')
        self.assertIsNone(share.resolve(''))
        self.assertEqual(self.names(share, 'Videos'), ['Clases', 'nota.txt'])
        self.assertIsNone(share.resolve('Videos/fuga.txt'))
        self.assertIsNone(share.resolve('Videos/../a/foto.jpg'))
        self.assertIsNone(share.resolve('otro'))
        self.assertTrue(share.is_dir('') and share.is_dir('Videos/Clases'))
        self.assertEqual(share.display('Videos/Clases'), 'Videos/Clases')

    def test_single_file(self):
        share = Share([str(self.folder / 'nota.txt')])
        self.assertEqual((share.mode, share.title), ('list', 'nota.txt'))
        self.assertEqual(self.names(share), ['nota.txt'])

    def test_zip_members(self):
        share = Share([str(self.base / 'a' / 'foto.jpg'), str(self.base / 'b' / 'foto.jpg'), str(self.folder)])
        members = sorted(arc for _, arc in share.zip_members(''))
        self.assertEqual(members, ['Videos/Clases/uno.mp4', 'Videos/nota.txt', 'foto (2).jpg', 'foto.jpg'])
        self.assertEqual(share.zip_name(''), 'archivos')
        folder = Share([str(self.folder)])
        self.assertEqual(sorted(arc for _, arc in folder.zip_members('Clases')), ['Clases/uno.mp4'])
        self.assertEqual(sorted(arc for _, arc in folder.zip_members('')), ['Videos/Clases/uno.mp4', 'Videos/nota.txt'])
        self.assertEqual(folder.zip_name(''), 'Videos')


if __name__ == '__main__':
    unittest.main()

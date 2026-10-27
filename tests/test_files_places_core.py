"""Places of the Files navigation (wysun_files.core.places)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_files.core import places  # noqa: E402


class PlacesTests(unittest.TestCase):
    def test_most_specific_place(self):
        targets = ['/', '/home/a', '/home/a/Documentos', '/home/a/Documentos/x']
        self.assertEqual(places.most_specific('/home/a/Documentos/clase', targets), '/home/a/Documentos')
        self.assertEqual(places.most_specific('/home/a/Documentos/x', targets), '/home/a/Documentos/x')
        self.assertEqual(places.most_specific('/etc', targets), '/')
        self.assertEqual(places.most_specific('/home/ab', ['/home/a']), '')

    def test_favourites_start_with_home_and_exist(self):
        found = places.favourites()
        self.assertEqual(found[0]['path'], str(Path.home()))
        self.assertTrue(all(Path(p['path']).is_dir() for p in found))

    def test_devices_and_usage(self):
        found = places.devices()
        self.assertEqual(found[0]['path'], '/')
        used, caption = places.usage('/')
        self.assertTrue(0 < used <= 1)
        self.assertTrue(caption.endswith(' libres'))
        self.assertEqual(places.usage('/no/existe'), (0.0, ''))


if __name__ == '__main__':
    unittest.main()

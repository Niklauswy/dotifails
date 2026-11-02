"""Wysun Files' places for QML (venv Python): favourites, bookmarks that persist, devices with their free space
refreshed every 20 s and eject for removable ones, the trash, and the place that holds a folder (F-10, F-11)."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

DEVICES = [{'path': '/', 'label': 'Sistema', 'icon': 'hard_drive', 'removable': False},
           {'path': '/run/media/u/KINGSTON', 'label': 'KINGSTON', 'icon': 'usb', 'removable': True, 'device': '/dev/sdb1'}]


class PlacesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()

    def setUp(self):
        from PySide6.QtCore import QSettings
        from wysun_files.quick import places as module
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        self.tmp = tempfile.TemporaryDirectory(prefix='files-places-', dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'tesis').mkdir()
        self.settings = QSettings(str(self.root / 'files.ini'), QSettings.IniFormat)
        self.favourites = [{'path': str(Path.home()), 'label': 'Inicio', 'icon': 'home'},
                           {'path': str(self.root), 'label': 'Documentos', 'icon': 'description'}]
        patches = [patch.object(module.places, 'favourites', return_value=self.favourites),
                   patch.object(module.places, 'devices', return_value=DEVICES),
                   patch.object(module.places, 'usage', side_effect=lambda p: (0.31, '11 GB libres') if 'KINGSTON' in p else (0.78, '25 GB libres'))]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.runs = []
        self.places = module.Places(settings=self.settings, run=lambda argv, done: self.runs.append((argv, done)))
        self.addCleanup(self.places.close)

    def destinations(self):
        return self.places.property('destinations')

    def ids(self):
        return [d.get('id') or d.get('header') or ('—' if d.get('divider') else '?') for d in self.destinations()]

    def test_sections_in_order(self):
        self.assertEqual(self.ids(), ['Favoritos', str(Path.home()), str(self.root), 'Dispositivos', '/', '/run/media/u/KINGSTON',
                                      '—', self.places.property('trash')])

    def test_devices_have_usage_and_removable_ones_eject(self):
        by_id = {d.get('id'): d for d in self.destinations()}
        usb, system = by_id['/run/media/u/KINGSTON'], by_id['/']
        self.assertEqual((usb['progress'], usb['trailing'], usb['trailingAction']), (0.31, '11 GB', 'eject'))
        self.assertNotIn('trailingAction', system)
        self.assertEqual(system['trailing'], '25 GB')
        self.assertIs(usb.get('rail'), False)

    def test_bookmarks_persist_skip_duplicates_and_can_be_removed(self):
        target = str(self.root / 'tesis')
        changes = []
        self.places.changed.connect(lambda: changes.append(1))
        self.assertTrue(self.places.toggleBookmark(target))
        self.assertTrue(self.places.isBookmark(target))
        self.assertIn('Marcadores', self.ids())
        entry = [d for d in self.destinations() if d.get('id') == target][0]
        self.assertEqual((entry['label'], entry['icon']), ('tesis', 'bookmark'))
        self.places.toggleBookmark(str(self.root))         # a favourite already: listed once
        self.assertEqual(self.ids().count(str(self.root)), 1)
        self.settings.sync()
        from wysun_files.quick.places import Places
        again = Places(settings=self.settings, run=lambda *a: None)
        self.addCleanup(again.close)
        self.assertTrue(again.isBookmark(target))
        self.assertFalse(self.places.toggleBookmark(target))
        self.assertFalse(self.places.isBookmark(target))
        self.assertGreaterEqual(len(changes), 2)

    def test_place_of_a_folder_is_the_most_specific(self):
        self.places.toggleBookmark(str(self.root / 'tesis'))
        self.assertEqual(self.places.placeOf(str(self.root / 'tesis/cap1')), str(self.root / 'tesis'))
        self.assertEqual(self.places.placeOf(str(self.root / 'otra')), str(self.root))
        self.assertEqual(self.places.placeOf('/run/media/u/KINGSTON/fotos'), '/run/media/u/KINGSTON')
        self.assertEqual(self.places.placeOf('/etc'), '/')

    def test_devices_refresh_every_twenty_seconds(self):
        self.assertEqual(self.places.refresher.interval(), 20000)
        self.assertTrue(self.places.refresher.isActive())

    def test_eject_unmounts_through_gio_and_reports(self):
        messages = []
        self.places.message.connect(messages.append)
        self.places.eject('/run/media/u/KINGSTON')
        self.assertEqual(self.runs[0][0], ['gio', 'mount', '-u', '/run/media/u/KINGSTON'])
        self.runs[0][1](0, '')
        self.assertEqual(messages, ['KINGSTON se puede retirar'])
        self.places.eject('/run/media/u/KINGSTON')
        self.runs[1][1](1, 'ocupado')
        self.assertEqual(messages[-1], 'No se pudo expulsar KINGSTON: ocupado')

    def test_only_removable_devices_eject(self):
        self.places.eject('/')
        self.assertEqual(self.runs, [])


if __name__ == '__main__':
    unittest.main()

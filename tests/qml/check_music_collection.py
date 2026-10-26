"""Collection page, song and collection menus, playlist dialogs and «Mostrar en la carpeta»."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support, music_fixture  # noqa: E402


class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import Qt
        cls.Qt = Qt
        cls.h = support.Harness.get()
        cls.warnings = []
        music_fixture.setup()
        cls.music = music_fixture.app()
        cls.window = cls.music.window.window
        cls.music.window.engine.warnings.connect(lambda errors: cls.warnings.extend(e.toString() for e in errors))
        cls.music.window.bridge.setReducedMotion(True)
        cls.music.window.present()
        cls.window.resize(1100, 800)
        cls.keys = music_fixture.keys_by_title()
        cls.library = cls.music.library

    def setUp(self):
        self.warnings.clear()

    def tearDown(self):
        for collection in list(self.library.collections()):
            if collection.editable:
                self.library.delete_playlist(collection.id)
        for key in list(self.library.favorites):
            self.library.toggle_favorite(key)
        self.music.player.set_paused(True)
        self.h.call(self.window, 'navigate', 'home', True)

    def go(self, route):
        self.h.call(self.window, 'navigate', route, True)
        self.h.pump(80)

    def visible(self, name):
        from PySide6.QtQuick import QQuickItem
        stack, found = [self.window.contentItem()], []
        while stack:
            item = stack.pop()
            if item.objectName() == name and item.isVisible():
                found.append(item)
            stack.extend(item.childItems() if isinstance(item, QQuickItem) else [])
        return found

    def one(self, name):
        found = self.visible(name)
        self.assertTrue(found, name + ' is not visible')
        return found[-1]

    def menu(self, name):
        return self.h.find_in(self.window.contentItem(), name)

    def trigger(self, menu, entry_id):
        entries = menu.property('model').toVariant()
        index = next(i for i, e in enumerate(entries) if e.get('id') == entry_id)
        self.h.call(menu, 'trigger', index)
        self.h.pump(60)

    def test_artist_page(self):
        self.go('collection:artist:Synth')
        self.assertEqual(self.one('collectionTitle').property('text'), 'Synth')
        cover = self.one('heroCover')
        self.assertEqual(cover.property('shape'), 'cookie')
        self.assertEqual(cover.property('initials'), 'S')
        self.assertEqual(self.one('collectionTracks').property('count'), 2)
        self.assertEqual(self.warnings, [])

    def test_play_and_shuffle_buttons(self):
        key = self.library.create_playlist('Prueba', list(self.keys.values()))
        self.go('collection:' + key)
        self.h.call(self.one('collectionPlay'), 'activate')
        self.assertTrue(self.h.wait_for(lambda: self.music.player.playing, 5000))
        self.assertEqual(self.music.player.queue.context, key)
        self.assertEqual(self.one('collectionPlay').property('text'), 'Pausar')
        self.h.call(self.one('collectionPlay'), 'activate')
        self.assertTrue(self.h.wait_for(lambda: self.music.player.paused, 3000))

    def test_new_playlist_dialog(self):
        self.go('library:songs')
        self.h.key(self.window, self.Qt.Key_N, self.Qt.ControlModifier, 'n')
        field = self.one('playlistNameField')
        self.assertEqual(field.property('text'), 'Mi playlist n.º 1')
        field.setProperty('text', 'Para correr')
        self.h.call(self.one('action-ok'), 'activate')
        self.h.pump(80)
        created = [c for c in self.library.collections() if c.editable]
        self.assertEqual([c.title for c in created], ['Para correr'])
        self.assertEqual(self.window.property('route'), 'collection:' + created[0].id, 'an empty new playlist opens')

    def test_track_menu_add_remove_and_favorite(self):
        key = self.library.create_playlist('Lista', [self.keys['first']])
        self.go('collection:' + key)
        menus = self.h.find_in(self.window.contentItem(), 'musicNav').parentItem()
        music_menus = self.window.property('menus')
        self.h.call(music_menus, 'trackMenu', [self.keys['first']], key, 200, 200)
        track_menu = self.menu('trackMenu')
        labels = [e.get('text') for e in track_menu.property('model').toVariant() if not e.get('divider')]
        self.assertEqual(labels, ['Reproducir', 'Reproducir a continuación', 'Añadir a la cola', 'Añadir a playlist',
                                  'Quitar de esta playlist', 'Guardar en Tus me gusta', 'Ir al artista',
                                  'Mostrar en la carpeta'])
        self.trigger(track_menu, 'favorite')
        self.assertIn(self.keys['first'], self.library.favorites)
        self.h.call(music_menus, 'trackMenu', [self.keys['first']], key, 200, 200)
        self.trigger(track_menu, 'remove')
        self.assertEqual(self.library.collection(key).keys, [])
        self.h.call(music_menus, 'playlistMenu', [self.keys['third']], 200, 200)
        self.trigger(self.menu('playlistMenu'), key)
        self.assertEqual(self.library.collection(key).keys, [self.keys['third']])

    def test_several_artists_open_a_submenu(self):
        music_menus = self.window.property('menus')
        self.h.call(music_menus, 'trackMenu', [self.keys['second']], '', 200, 200)
        self.trigger(self.menu('trackMenu'), 'artists')
        names = [e['text'] for e in self.menu('artistMenu').property('model').toVariant()]
        self.assertEqual(names, ['Synth', 'Noise'])
        self.trigger(self.menu('artistMenu'), 'artist:Noise')
        self.assertEqual(self.window.property('route'), 'collection:artist:Noise')

    def test_collection_menu_rename_and_delete(self):
        key = self.library.create_playlist('Vieja', [])
        self.go('collection:' + key)
        music_menus = self.window.property('menus')
        self.h.call(music_menus, 'collectionMenu', key, None, 200, 200)
        menu = self.menu('collectionMenu')
        self.assertIn('Cambiar nombre…', [e.get('text') for e in menu.property('model').toVariant()])
        self.trigger(menu, 'rename')
        field = self.one('playlistNameField')
        field.setProperty('text', 'Nueva')
        self.h.call(self.one('action-ok'), 'activate')
        self.h.pump(60)
        self.assertEqual(self.library.collection(key).title, 'Nueva')
        self.h.call(music_menus, 'collectionMenu', key, None, 200, 200)
        self.trigger(menu, 'delete')
        self.h.call(self.one('action-delete'), 'activate')
        self.h.pump(60)
        self.assertIsNone(self.library.collection(key))
        self.assertEqual(self.window.property('route'), 'home')

    def test_filter_shows_from_nine_songs(self):
        key = self.library.create_playlist('Corta', list(self.keys.values()))
        self.go('collection:' + key)
        self.assertFalse(self.visible('collectionFilter'))


class ShowInFolderTests(unittest.TestCase):
    def test_file_manager_then_folder_fallback(self):
        music_fixture.setup()
        music = music_fixture.app()
        controller = music.window.music
        key = music_fixture.keys_by_title()['first']
        path = music.library.playable(key)['path']
        calls = []

        class Bus:
            def call_sync(self, *args):
                calls.append(args[3:5])

        with patch('gi.repository.Gio.bus_get_sync', return_value=Bus()):
            controller.showInFolder(key)
        self.assertEqual(calls[0][0], 'ShowItems')
        self.assertEqual(calls[0][1].unpack(), ([Path(path).as_uri()], ''))
        with patch('gi.repository.Gio.bus_get_sync', side_effect=RuntimeError('no bus')), \
                patch('PySide6.QtGui.QDesktopServices.openUrl') as open_url:
            controller.showInFolder(key)
        self.assertEqual(open_url.call_args.args[0].toLocalFile(), str(Path(path).parent))


if __name__ == '__main__':
    unittest.main()

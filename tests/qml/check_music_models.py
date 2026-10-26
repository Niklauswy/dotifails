"""Music's QML models and page data against a synthetic library (wording copied from the Widgets UI)."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support, music_fixture  # noqa: E402


def rows(model, role):
    from PySide6.QtCore import Qt
    names = {bytes(v).decode(): k for k, v in model.roleNames().items()}
    return [model.data(model.index(i), names[role]) for i in range(model.rowCount())]


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.Harness.get()
        music_fixture.setup()
        cls.music = music_fixture.app()
        cls.c = cls.music.window.music
        cls.library = cls.music.library
        cls.keys = music_fixture.keys_by_title()

    def tearDown(self):
        for collection in list(self.library.collections()):
            if collection.editable:
                self.library.delete_playlist(collection.id)
        for key in list(self.library.favorites):
            self.library.toggle_favorite(key)
        self.c.refresh()

    def test_text_helpers(self):
        from wysun_music.quick import text
        import time
        self.assertEqual(text.clock(75), '1:15')
        self.assertEqual(text.clock(3725), '1:02:05')
        self.assertEqual(text.long_duration(3720), '1 h 2 min')
        self.assertEqual(text.songs(1), '1 canción')
        self.assertEqual(text.greeting(6), 'Buenos días')
        self.assertEqual(text.greeting(13), 'Buenas tardes')
        self.assertEqual(text.greeting(23), 'Buenas noches')
        self.assertEqual(text.today(time.strptime('2026-10-26', '%Y-%m-%d')), 'lunes 26 de octubre')

    def test_routes(self):
        from wysun_music.quick import routes
        self.assertEqual(routes.restore(['collection', 'all']), 'library:songs')
        self.assertEqual(routes.restore(('artists',)), 'library:artists')
        self.assertEqual(routes.restore(['collection', 'artist:A:B']), 'collection:artist:A:B')
        self.assertEqual(routes.restore(['bogus']), 'home')
        self.assertEqual(routes.store('collection:artist:A'), ['collection', 'artist:A'])

    def test_library_pages(self):
        self.assertEqual(sorted(rows(self.c.librarySongs, 'title')), ['first', 'second', 'third'])
        self.assertEqual(rows(self.c.libraryArtists, 'title')[0], 'Synth')      # most songs first
        self.assertIn('Noise', rows(self.c.libraryArtists, 'title'))           # featured credits count
        self.assertEqual(rows(self.c.libraryLists, 'id')[:2], ['favorites', 'recent'])
        self.assertEqual(rows(self.c.librarySongs, 'durationText')[0], '0:12')

    def test_home(self):
        home = self.c.home
        self.assertIn(home['greeting'], ('Buenos días', 'Buenas tardes', 'Buenas noches'))
        self.assertEqual([b['title'] for b in home['bento']][1:3], ['Tus me gusta', 'Mezcla'])
        resume = home['bento'][0]
        if self.music.player.current:
            self.assertIn(resume['eyebrow'], ('Sonando ahora', 'Sigue escuchando'))
        else:
            self.assertEqual(resume['title'], 'Empieza por aquí')
        self.assertEqual(home['summary'], '3 canciones disponibles · 0 playlists')

    def test_favorites_follow(self):
        self.library.toggle_favorite(self.keys['first'])
        self.c.refresh()
        self.assertEqual(self.c.home['bento'][1]['subtitle'], '1 canción')
        info = self.c.openCollection('favorites')
        self.assertEqual((info['title'], info['byline'], info['count']), ('Tus me gusta', 'Guardadas por ti', 1))
        self.assertTrue(rows(self.c.collectionTracks, 'favorite')[0])

    def test_collection_filter_sort_and_meta(self):
        key = self.library.create_playlist('Mi lista', [self.keys['third'], self.keys['first'], self.keys['second']])
        self.c.refresh()
        info = self.c.openCollection(key)
        self.assertEqual(info['byline'], 'Tu playlist')
        self.assertTrue(info['editable'])
        self.assertEqual(info['meta'], '3 canciones · 0 min')
        self.assertFalse(info['filterable'])
        self.assertEqual(rows(self.c.collectionTracks, 'title'), ['third', 'first', 'second'])
        self.c.setSort('title')
        self.assertEqual(rows(self.c.collectionTracks, 'title'), ['first', 'second', 'third'])
        self.c.setFilter('sec')
        self.assertEqual(rows(self.c.collectionTracks, 'title'), ['second'])
        self.c.openCollection('favorites')
        self.assertEqual(self.c.collection['sort'], 'custom', 'another collection starts unsorted')

    def test_artist_collection(self):
        info = self.c.openCollection('artist:Synth')
        self.assertEqual((info['kind'], info['initials']), ('artist', 'S'))
        self.assertEqual(sorted(rows(self.c.collectionTracks, 'title')), ['first', 'second'])

    def test_orphan_collection(self):
        self.assertFalse(self.c.openCollection('user-gone')['exists'])
        self.assertEqual(self.c.collectionTracks.rowCount(), 0)

    def test_search(self):
        self.c.setQuery('sÉcond')
        self.assertEqual(rows(self.c.searchSongs, 'title'), ['second'])
        self.assertEqual(self.c.search['top']['kind'], 'song')
        self.c.setQuery('synth')
        self.assertEqual(self.c.search['top'], {'kind': 'artist', 'id': 'artist:Synth', 'title': 'Synth',
                                                'subtitle': 'Artista'})
        self.c.setQuery('zzzz')
        self.assertTrue(self.c.search['empty'])
        self.c.setQuery('')
        self.assertFalse(self.c.search['searching'])
        self.assertGreater(self.c.explore.rowCount(), 0)

    def test_models_follow_library_reload(self):
        from wysun_music import data as music_data
        path = Path(music_data.DATA) / 'library.json'
        original = path.read_text()
        try:
            state = json.loads(original)
            state['tracks'][self.keys['third']]['status'] = 'error'
            path.write_text(json.dumps(state))
            self.library.reload(force=True)
            self.c.refresh()
            self.assertEqual(sorted(rows(self.c.librarySongs, 'title')), ['first', 'second'])
        finally:
            path.write_text(original)
            self.library.reload(force=True)
            self.c.refresh()

    def test_no_network_means_empty_cover_urls(self):
        self.assertEqual(rows(self.c.librarySongs, 'cover'), ['', '', ''])


if __name__ == '__main__':
    unittest.main()

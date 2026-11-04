"""The library's catalog of songs that are not on disk: listenable only online, local copies win, liking or adding
to a playlist downloads them, and played ones survive a restart."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_music import data as music_data  # noqa: E402

SPOTIFY = 'A' * 22


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QCoreApplication
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = patch.object(music_data, 'DATA', self.root / 'state')
        self.patch.start()
        audio = self.root / 'local.m4a'
        audio.write_bytes(b'x')
        with music_data.edit_state() as state:
            state['tracks']['local'] = dict(id='local', title='Despacito', artist='Luis Fonsi', duration=282,
                                            status='ready', path=str(audio), spotify_ids=['B' * 22])
        self.library = self.make()

    def make(self):
        from wysun_music.library import Library
        from wysun_music.store import MusicStore
        library = Library(store=MusicStore(self.root / 'state'), watch=False)
        library.start_downloads = lambda: None
        return library

    def tearDown(self):
        self.library.store.close()
        self.patch.stop()
        self.tmp.cleanup()

    def test_catalog_songs_are_listenable_only_online(self):
        [key] = self.library.register([dict(id=SPOTIFY, title='Nueva', artist='Alguien', duration=200)])
        self.assertEqual(key, SPOTIFY)
        self.assertEqual(self.library.track(key)['title'], 'Nueva')
        self.assertFalse(self.library.listenable(key))
        self.library.set_online(True)
        self.assertTrue(self.library.listenable(key))
        self.assertFalse(self.library.local(key))
        self.library.set_online(False)
        self.assertTrue(self.library.listenable('local'), 'local songs play offline')

    def test_local_copy_wins(self):
        keys = self.library.register([dict(id='B' * 22, title='Despacito', artist='Luis Fonsi', duration=282),
                                      dict(id='yt-abcdefghijk', title='Despacito', artist='Luis Fonsi', duration=283)])
        self.assertEqual(keys, ['local', 'local'])

    def test_liking_a_streamed_song_downloads_it_and_keeps_it_liked(self):
        self.library.set_online(True)
        [key] = self.library.register([dict(id=SPOTIFY, title='Nueva', artist='Alguien', duration=200)])
        self.library.toggle_favorite(key)
        state = music_data.read_state()
        self.assertEqual(state['tracks'][key]['status'], 'pending')
        self.assertIn(key, state['collections']['personal']['tracks'])
        self.assertIn(key, self.library.collection('favorites').keys)

    def test_adding_to_a_playlist_downloads(self):
        [key] = self.library.register([dict(id='yt-abcdefghijk', title='Otra', artist='X', duration=100,
                                            youtube_url='https://www.youtube.com/watch?v=abcdefghijk')])
        playlist = self.library.create_playlist('Mía', [key])
        self.assertEqual(music_data.read_state()['tracks'][key]['youtube_url'],
                         'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertEqual(self.library.collection(playlist).keys, [key])

    def test_online_collections_and_played_songs_persist(self):
        self.library.set_online_collections([dict(id='top', title='Top 50', source='https://open.spotify.com/x',
                                                  cover_url='https://i/x.jpg',
                                                  tracks=[dict(id=SPOTIFY, title='Nueva', artist='Alguien')])])
        collection = self.library.collection('online:top')
        self.assertEqual((collection.title, collection.kind, collection.keys), ('Top 50', 'online', [SPOTIFY]))
        self.assertEqual(self.library.raw_collection('online:top')['cover_url'], 'https://i/x.jpg')
        self.library.remember_video(SPOTIFY, 'https://www.youtube.com/watch?v=zzzzzzzzzzz')
        self.library.record_play(SPOTIFY)
        self.library.store.close()
        self.library = self.make()
        self.assertEqual(self.library.track(SPOTIFY)['youtube_url'], 'https://www.youtube.com/watch?v=zzzzzzzzzzz')
        self.assertIn(SPOTIFY, self.library.collection('recent').keys)


if __name__ == '__main__':
    unittest.main()

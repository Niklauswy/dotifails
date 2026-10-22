"""Wysun Music core without UI: queue rules, library facade, playlists, history, imports."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wysun'))
import music_data
from music_library import MusicStore
from wysun_music.queue import PlayQueue

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def available(key):
    return True


class QueueTests(unittest.TestCase):
    def test_up_next_plays_before_context_and_keeps_its_cursor(self):
        queue = PlayQueue()
        queue.start(['A', 'B', 'C', 'D'], 'A', shuffle=False)
        queue.add(['X'])
        queue.add_next(['Y'])
        self.assertEqual(queue.upcoming(), ['Y', 'X', 'B', 'C', 'D'])
        self.assertEqual([queue.next(available) for _ in range(3)], ['Y', 'X', 'B'])
        self.assertEqual(queue.previous(available), 'A')

    def test_repeat_modes_cycle_and_wrap(self):
        queue = PlayQueue()
        queue.start(['A', 'B'], 'B', shuffle=False)
        self.assertIsNone(queue.next(available))
        self.assertEqual(queue.cycle_repeat(), 'all')
        self.assertEqual(queue.next(available), 'A')
        self.assertEqual(queue.upcoming(), ['B'])
        self.assertEqual(queue.cycle_repeat(), 'one')
        self.assertEqual(queue.cycle_repeat(), 'off')

    def test_remove_upcoming_and_shuffle_keep_history(self):
        queue = PlayQueue()
        queue.start(['A', 'B', 'C', 'D', 'E'], 'A', shuffle=False)
        queue.next(available)
        queue.add(['X'])
        queue.remove_upcoming(0)
        queue.remove_upcoming(0)
        self.assertEqual(queue.upcoming(), ['D', 'E'])
        queue.set_shuffle(True)
        self.assertEqual(queue.order.keys[:2], ['A', 'B'])
        self.assertEqual(sorted(queue.upcoming()), ['D', 'E'])

    def test_export_restore_and_legacy_order(self):
        queue = PlayQueue()
        queue.start(['A', 'B', 'C'], 'B', shuffle=False, context='list')
        queue.add(['C'])
        queue.set_repeat('one')
        restored = PlayQueue()
        restored.restore(queue.export())
        self.assertEqual((restored.order.current, restored.up_next, restored.repeat, restored.context),
                         ('B', ['C'], 'one', 'list'))
        legacy = PlayQueue()
        legacy.restore(dict(keys=['A', 'B'], source=['A', 'B'], index=1, shuffle=False, repeat=True))
        self.assertEqual((legacy.order.current, legacy.repeat), ('B', 'all'))


class StoreTests(unittest.TestCase):
    def test_playlists_and_history(self):
        with tempfile.TemporaryDirectory() as root:
            store = MusicStore(root)
            key = store.create_playlist('Para correr')
            store.add_to_playlist(key, ['A', 'B', 'A'])
            store.add_to_playlist(key, ['C'])
            store.remove_from_playlist(key, ['B'])
            self.assertEqual(store.playlists(), [dict(id=key, title='Para correr', tracks=['A', 'C'])])
            store.rename_playlist(key, 'Gym')
            self.assertEqual(store.playlists()[0]['title'], 'Gym')
            for track in ('A', 'B', 'A'):
                store.record_play(track)
            self.assertEqual(store.recent(), ['A', 'B'])
            self.assertEqual(store.most_played(1), ['A'])
            store.delete_playlist(key)
            self.assertEqual(store.playlists(), [])
            store.close()


class LibraryTests(unittest.TestCase):
    def setUp(self):
        from PySide6.QtCore import QCoreApplication
        self.app = QCoreApplication.instance() or QCoreApplication([])
        self.root = Path(tempfile.mkdtemp(prefix='wysun-music-core-'))
        self.patch = patch.object(music_data, 'DATA', self.root / 'state')
        self.patch.start()
        audio = self.root / 'song.opus'
        audio.write_bytes(b'x')
        music_data.enqueue({'collections': [
            dict(id='mix', title='Mix', source='https://open.spotify.com/playlist/1', tracks=[
                dict(id='a' * 22, title='Café (feat. Ñu)', artist='Ána, Bee', duration=100),
                dict(id='b' * 22, title='Missing', artist='Bee', duration=50)])]})
        music_data.update_track('a' * 22, status='ready', path=str(audio))

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.root)

    def test_collections_search_favorites_and_playlists(self):
        from wysun_music.library import Library
        library = Library(watch=False)
        self.assertEqual(library.all_keys(), ['a' * 22])
        self.assertEqual(library.search('CAFE ana'), ['a' * 22])
        self.assertEqual(library.search('missing'), [])
        self.assertEqual(set(library.artists()), {'Ána', 'Bee', 'Ñu'})
        kinds = {c.id: c.kind for c in library.collections()}
        self.assertEqual(kinds, {'favorites': 'favorites', 'mix': 'playlist'})
        self.assertEqual(library.collection('mix').keys, ['a' * 22], 'Undownloaded songs stay out of lists')
        library.toggle_favorite('a' * 22)
        self.assertEqual(library.collection('favorites').keys, ['a' * 22])
        key = library.create_playlist('  ', ['a' * 22])
        playlist = library.collection(key)
        self.assertEqual((playlist.title, playlist.keys, playlist.editable), ('Mi playlist', ['a' * 22], True))
        self.assertEqual(library.collection('artist:Bee').keys, ['a' * 22])
        self.assertEqual(library.collection('search:café').keys, ['a' * 22])
        self.assertIsNone(library.collection('nope'))
        library.store.close()


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'needs ffmpeg')
class ImportTests(unittest.TestCase):
    def test_folder_import_reads_embedded_tags(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            folder = root / 'album' / 'disc'
            folder.mkdir(parents=True)
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=duration=1', '-metadata', 'title=Tono',
                            '-metadata', 'artist=Synth', '-metadata', 'album=Pruebas', str(folder / 'x.ogg')], check=True)
            (folder / 'notes.txt').write_text('not audio')
            with patch.object(music_data, 'DATA', root / 'state'):
                keys = music_data.import_files([root / 'album'])
                track = music_data.read_state()['tracks'][keys[0]]
        self.assertEqual(len(keys), 1)
        self.assertEqual((track['title'], track['artist'], track['album']), ('Tono', 'Synth', 'Pruebas'))
        self.assertGreater(track['duration'], .5)


if __name__ == '__main__':
    unittest.main()

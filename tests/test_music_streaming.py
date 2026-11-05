"""The player streams songs that are not on disk: resolved URL to mpv, stale answers ignored, failures skipped,
the next song prepared ahead, and nothing streamed offline."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_music import data as music_data  # noqa: E402

from PySide6.QtCore import QObject, Signal  # noqa: E402


class FakeEngine(QObject):
    position_changed = Signal(float)
    duration_changed = Signal(float)
    pause_changed = Signal(bool)
    volume_changed = Signal(int)
    mute_changed = Signal(bool)
    ended = Signal()
    failed = Signal(str)

    def __init__(self, volume=60, parent=None):
        super().__init__(parent)
        self.volume, self.paused, self.running, self.loaded = volume, True, True, []

    def load(self, path, start=0.0, paused=False):
        self.loaded.append(str(path))
        self.paused = paused

    def set_paused(self, paused):
        self.paused = paused

    def seek(self, seconds):
        pass

    def quit(self):
        pass


class FakeResolver(QObject):
    resolved = Signal(str, str)
    failed = Signal(str, str)
    video_found = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.requests = []

    def request(self, key, track):
        self.requests.append(key)


class StreamingPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QCoreApplication
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(music_data, 'DATA', root / 'state'),
                        patch('wysun_music.player.MpvEngine', FakeEngine)]
        for item in self.patches:
            item.start()
        audio = root / 'local.ogg'
        audio.write_bytes(b'x')
        with music_data.edit_state() as state:
            state['tracks']['local'] = dict(id='local', title='Local', artist='Yo', duration=10, status='ready',
                                            path=str(audio))
        from wysun_music.library import Library
        from wysun_music.player import Player
        from wysun_music.store import MusicStore
        self.library = Library(store=MusicStore(root / 'state'), watch=False)
        self.library.register([dict(id='yt-aaaaaaaaaaa', title='Uno', artist='A', duration=100),
                               dict(id='yt-bbbbbbbbbbb', title='Dos', artist='B', duration=100)])
        self.library.set_online(True)
        self.resolver = FakeResolver()
        self.player = Player(self.library, persist=False, resolver=self.resolver)

    def tearDown(self):
        self.library.store.close()
        for item in self.patches:
            item.stop()
        self.tmp.cleanup()

    def test_streamed_song_plays_the_resolved_url(self):
        self.player.play_collection(['yt-aaaaaaaaaaa', 'yt-bbbbbbbbbbb'], 'yt-aaaaaaaaaaa')
        self.assertEqual(self.player.current, 'yt-aaaaaaaaaaa')
        self.assertTrue(self.player.buffering)
        self.assertEqual(self.player.engine.loaded, [])
        self.resolver.resolved.emit('yt-aaaaaaaaaaa', 'https://audio/1')
        self.assertEqual(self.player.engine.loaded, ['https://audio/1'])
        self.assertFalse(self.player.buffering)
        self.assertIn('yt-bbbbbbbbbbb', self.resolver.requests, 'the next song is prepared ahead')

    def test_stale_resolution_is_ignored(self):
        self.player.play_collection(['yt-aaaaaaaaaaa', 'yt-bbbbbbbbbbb'], 'yt-aaaaaaaaaaa')
        self.player.next()
        self.resolver.resolved.emit('yt-aaaaaaaaaaa', 'https://audio/1')
        self.assertEqual(self.player.engine.loaded, [])
        self.resolver.resolved.emit('yt-bbbbbbbbbbb', 'https://audio/2')
        self.assertEqual(self.player.engine.loaded, ['https://audio/2'])

    def test_failure_skips_to_the_next_song(self):
        self.player.play_collection(['yt-aaaaaaaaaaa', 'local'], 'yt-aaaaaaaaaaa')
        self.resolver.failed.emit('yt-aaaaaaaaaaa', 'sin red')
        self.assertEqual(self.player.current, 'local')
        self.assertTrue(self.player.engine.loaded[-1].endswith('local.ogg'))

    def test_offline_skips_streamed_songs(self):
        self.library.set_online(False)
        self.player.play_collection(['yt-aaaaaaaaaaa', 'local'], 'yt-aaaaaaaaaaa')
        self.assertEqual(self.player.current, 'local')
        self.assertEqual(self.resolver.requests, [])

    def test_video_found_is_remembered(self):
        self.resolver.video_found.emit('yt-aaaaaaaaaaa', 'https://www.youtube.com/watch?v=aaaaaaaaaaa')
        self.assertEqual(self.library.track('yt-aaaaaaaaaaa')['youtube_url'],
                         'https://www.youtube.com/watch?v=aaaaaaaaaaa')


if __name__ == '__main__':
    unittest.main()

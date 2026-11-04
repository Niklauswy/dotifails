"""Streaming: song → YouTube video → audio URL, without writing audio anywhere."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_music import stream  # noqa: E402


def fake(stdout, code=0):
    script = f'import sys; print({stdout!r}); sys.exit({code})'
    return patch('wysun_music.data.ytdlp', return_value=[sys.executable, '-c', script])


class StreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QCoreApplication
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def settle(self, resolver):
        resolver.wait(10000)
        self.app.processEvents()

    def test_audio_url_takes_the_first_url(self):
        with fake('https://audio.example/a\nhttps://audio.example/b'):
            self.assertEqual(stream.audio_url('https://www.youtube.com/watch?v=abcdefghijk'), 'https://audio.example/a')
        with fake('', 1), self.assertRaises(RuntimeError):
            stream.audio_url('https://www.youtube.com/watch?v=abcdefghijk')

    def test_entry_track_splits_artist_and_title(self):
        track = stream.entry_track({'id': 'abcdefghijk', 'title': 'Luis Fonsi - Despacito (Official Video)',
                                    'channel': 'LuisFonsiVEVO', 'duration': 282})
        self.assertEqual((track['id'], track['artist'], track['title'], track['duration']),
                         ('yt-abcdefghijk', 'Luis Fonsi', 'Despacito', 282))
        topic = stream.entry_track({'id': 'abcdefghijk', 'title': 'Song - Remastered', 'channel': 'Band - Topic'})
        self.assertEqual((topic['artist'], topic['title']), ('Band', 'Song - Remastered'))

    def test_resolver_emits_resolved_and_caches(self):
        resolver = stream.StreamResolver()
        got, videos = [], []
        resolver.resolved.connect(lambda k, u: got.append((k, u)))
        resolver.video_found.connect(lambda k, v: videos.append(v))
        track = {'title': 'A', 'artist': 'B', 'youtube_url': 'https://www.youtube.com/watch?v=abcdefghijk'}
        with fake('https://audio.example/a'):
            resolver.request('k', track)
            self.settle(resolver)
        self.assertEqual(got, [('k', 'https://audio.example/a')])
        self.assertEqual(videos, ['https://www.youtube.com/watch?v=abcdefghijk'])
        resolver.request('k', track)            # cached: no process
        self.assertEqual(got[-1], ('k', 'https://audio.example/a'))

    def test_resolver_fails_without_a_match(self):
        resolver = stream.StreamResolver()
        failed = []
        resolver.failed.connect(lambda k, m: failed.append(k))
        with patch('wysun_music.data.find_video', return_value=None):
            resolver.request('k', {'title': 'A', 'artist': 'B'})
            self.settle(resolver)
        self.assertEqual(failed, ['k'])


if __name__ == '__main__':
    unittest.main()

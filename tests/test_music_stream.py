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

    def helper(self, body):
        import tempfile
        script = Path(tempfile.mkdtemp()) / 'helper.py'
        script.write_text('import json, sys\n'
                          'for line in sys.stdin:\n'
                          '    r = json.loads(line)\n' + body +
                          '    print(json.dumps(a), flush=True)\n')
        return stream.StreamResolver(command=[sys.executable, str(script)])

    def test_resolver_uses_the_warm_helper_and_caches(self):
        resolver = self.helper("    t = r.get('track', {'youtube_url': '', 'title': ''})\n"
                               "    a = {'id': r['id'], 'ok': True, 'video': t['youtube_url'],"
                               " 'audio': 'https://audio.example/' + t['title']}\n")
        got, videos = [], []
        resolver.resolved.connect(lambda k, u: got.append((k, u)))
        resolver.video_found.connect(lambda k, v: videos.append(v))
        track = {'title': 'A', 'artist': 'B', 'youtube_url': 'https://www.youtube.com/watch?v=abcdefghijk'}
        resolver.request('k', track)
        self.settle(resolver)
        self.assertEqual(got, [('k', 'https://audio.example/A')])
        self.assertEqual(videos, ['https://www.youtube.com/watch?v=abcdefghijk'])
        resolver.request('k', track)            # cached: no request
        self.assertEqual(got[-1], ('k', 'https://audio.example/A'))
        answers = []
        resolver.call({'op': 'search', 'query': 'x'}, answers.append)
        self.settle(resolver)
        self.assertTrue(answers[0]['ok'])
        resolver.shutdown()

    def test_resolver_reports_helper_failures(self):
        resolver = self.helper("    a = {'id': r['id'], 'ok': False, 'error': 'No está en YouTube.'}\n")
        failed = []
        resolver.failed.connect(lambda k, m: failed.append((k, m)))
        resolver.request('k', {'title': 'A', 'artist': 'B'})
        self.settle(resolver)
        self.assertEqual(failed, [('k', 'No está en YouTube.')])
        resolver.shutdown()

    def test_without_helper_each_song_runs_yt_dlp(self):
        resolver = stream.StreamResolver(command=['/nonexistent/python'])
        got = []
        resolver.resolved.connect(lambda k, u: got.append(u))
        with fake('https://audio.example/a'):
            resolver.request('k', {'title': 'A', 'artist': 'B',
                                   'youtube_url': 'https://www.youtube.com/watch?v=abcdefghijk'})
            self.settle(resolver)
        self.assertEqual(got, ['https://audio.example/a'])


if __name__ == '__main__':
    unittest.main()

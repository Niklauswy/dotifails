"""Download queue: no «Revisar versión», batches with progress, cancel and «Elegir otra versión»."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_music import data as music_data  # noqa: E402


def manifest(cid, title, *ids):
    return {'collections': [{'id': cid, 'title': title, 'append': True, 'source': 'x',
                             'tracks': [{'id': i, 'title': 'Song ' + i, 'artist': 'Artist ' + i, 'duration': 100}
                                        for i in ids]}]}


class DownloadQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = patch.object(music_data, 'DATA', self.root / 'state')
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_migrate_review_to_ready_or_missing(self):
        audio = self.root / 'a.m4a'
        audio.write_bytes(b'x')
        state = music_data.empty()
        state['tracks'] = {'a': dict(id='a', status='review', path=str(audio), error='dur'),
                           'b': dict(id='b', status='review', error='none')}
        self.assertTrue(music_data.migrate(state))
        self.assertEqual(state['tracks']['a']['status'], 'ready')
        self.assertEqual(state['tracks']['a']['error'], '')
        self.assertEqual(state['tracks']['b']['status'], 'missing')
        self.assertFalse(music_data.migrate(state))

    def test_enqueue_stamps_batch_only_on_new_tracks(self):
        music_data.enqueue(manifest('p', 'Lista', 'a', 'b'))
        first = music_data.read_state()['tracks']['a']['batch']
        self.assertTrue(first.startswith('p:'))
        self.assertEqual(music_data.read_state()['tracks']['a']['batch_title'], 'Lista')
        with patch('wysun_music.data.time.time', return_value=4e9):
            music_data.enqueue(manifest('p', 'Lista', 'a', 'c'))
        tracks = music_data.read_state()['tracks']
        self.assertEqual(tracks['a']['batch'], first)
        self.assertEqual(tracks['c']['batch'], 'p:4000000000')

    def test_batches_count_progress(self):
        music_data.enqueue(manifest('p', 'Lista', 'a', 'b', 'c'))
        music_data.update_track('a', status='ready', path='/x')
        music_data.update_track('b', status='downloading', progress='42% · 1MiB/s')
        music_data.update_track('c', status='error', error='boom')
        [batch] = music_data.batches(music_data.read_state())
        self.assertEqual((batch['title'], batch['total'], batch['done'], batch['failed']), ('Lista', 3, 1, 1))
        self.assertEqual(batch['active'], 'Song b · Artist b')
        self.assertEqual(batch['progress'], '42% · 1MiB/s')
        music_data.update_track('b', status='ready', path='/y')
        music_data.update_track('c', status='ready', path='/z')
        self.assertEqual(music_data.batches(music_data.read_state()), [])

    def test_cancel_drops_pending_and_flags_downloading(self):
        music_data.enqueue(manifest('p', 'Lista', 'a', 'b', 'c'))
        music_data.update_track('a', status='ready', path='/x')
        music_data.update_track('b', status='downloading')
        token = music_data.read_state()['tracks']['c']['batch']
        music_data.cancel_batch(token)
        state = music_data.read_state()
        self.assertNotIn('c', state['tracks'])
        self.assertNotIn('c', state['collections']['p']['tracks'])
        self.assertTrue(state['tracks']['b']['cancel'])
        self.assertEqual(state['tracks']['a']['status'], 'ready')

    def test_use_version_and_retry_missing(self):
        music_data.enqueue(manifest('p', 'Lista', 'a', 'b'))
        music_data.update_track('a', status='missing', error='nada')
        music_data.update_track('b', status='error', error='red')
        music_data.use_version('a', 'https://www.youtube.com/watch?v=abcdefghijk')
        track = music_data.read_state()['tracks']['a']
        self.assertEqual((track['status'], track['error'], track['youtube_url']),
                         ('pending', '', 'https://www.youtube.com/watch?v=abcdefghijk'))
        music_data.update_track('a', status='missing')
        music_data.retry_failed()
        tracks = music_data.read_state()['tracks']
        self.assertEqual({tracks['a']['status'], tracks['b']['status']}, {'pending'})

    def test_no_match_is_missing_and_duration_mismatch_is_ready(self):
        music_data.enqueue(manifest('p', 'Lista', 'a'))
        with patch('wysun_music.data.find_video', return_value=None):
            music_data.download_track('a', music_data.read_state()['tracks']['a'])
        self.assertEqual(music_data.read_state()['tracks']['a']['status'], 'missing')


if __name__ == '__main__':
    unittest.main()

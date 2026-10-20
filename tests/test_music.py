import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'apps/wysun'))
import music_data as music


class MusicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch.object(music, 'DATA', self.root/'state')
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_shared_track_in_two_lists_downloads_once(self):
        track = {'id': 'one', 'title': 'Song', 'artist': 'Artist'}
        music.enqueue({'collections': [dict(id='a', title='A', tracks=[track]), dict(id='b', title='B', tracks=[track])]})
        music.update_track('one', status='ready', path='existing.opus')
        music.enqueue({'collections': [dict(id='a', title='A', tracks=[track])]})
        state = music.read_state()
        self.assertEqual(len(state['tracks']), 1)
        self.assertEqual(state['tracks']['one']['status'], 'ready')
        self.assertEqual(state['collections']['b']['tracks'], ['one'])

    def test_manual_youtube_import_reuses_existing_spotify_track(self):
        url = 'https://www.youtube.com/watch?v=one'
        music.enqueue({'collections': [dict(id='a', title='A', tracks=[dict(id='spotify-one', title='Song', artist='Artist', youtube_url=url)])]})
        music.enqueue({'collections': [dict(id='personal', title='Personal', append=True, tracks=[dict(id='yt-one', title='Song', artist='Artist', youtube_url=url)])]})
        state = music.read_state()
        self.assertEqual(len(state['tracks']), 1)
        self.assertEqual(state['collections']['personal']['tracks'], ['spotify-one'])

    def test_retry_preserves_downloaded_files_and_resets_only_failures(self):
        music.enqueue({'collections': [dict(id='a', title='A', tracks=[dict(id=k, title=k, artist='A') for k in ['ok', 'bad']])]})
        music.update_track('ok', status='ready', path='/existing/music.opus')
        music.update_track('bad', status='error', error='403')
        music.set_paused(True)
        music.retry_failed()
        state = music.read_state()
        self.assertEqual(state['tracks']['ok']['path'], '/existing/music.opus')
        self.assertEqual(state['tracks']['ok']['status'], 'ready')
        self.assertEqual(state['tracks']['bad']['status'], 'pending')
        self.assertFalse(state['paused'])

    def test_matching_rejects_covers_wrong_artists_and_wrong_duration(self):
        track = dict(title='NADIE SABE', artist='Bad Bunny', duration=379)
        official = dict(title='BAD BUNNY - NADIE SABE (Visualizer)', channel='Bad Bunny', duration=379, channel_is_verified=True)
        self.assertGreater(music.candidate_score(track, official), 10)
        for change in [dict(title='BAD BUNNY - NADIE SABE cover'), dict(title='Nadie sabe', channel='Other Artist'), dict(duration=3700)]:
            self.assertLess(music.candidate_score(track, dict(official, **change)), 0)

    def test_feature_credits_do_not_require_every_collaborator_in_video_title(self):
        track = dict(title='Diles (feat. Arcangel, Nengo Flow, Dj Luian & Mambo Kings)',
                     artist='Ozuna, Bad Bunny, Farruko', duration=279)
        entry = dict(title='Diles - Bad Bunny, Ozuna, Farruko, Arcangel, Ñengo Flow', duration=279)
        self.assertGreater(music.candidate_score(track, entry), 10)


if __name__ == '__main__':
    unittest.main()

class ImportIdentityTests(unittest.TestCase):
    def test_two_spotify_releases_reuse_recording_but_keep_live_version(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(music,'DATA',Path(folder)):
            music.enqueue({'collections':[dict(id='first',title='First',tracks=[dict(id='id-a',title='Canción',artist='Artista',duration=200)])]})
            music.update_track('id-a',status='ready',path='/unchanged/file.opus',duration=200.2)
            music.enqueue({'collections':[dict(id='next',title='Next',tracks=[dict(id='id-b',title='Cancion',artist='Artista',duration=200.1),dict(id='id-live',title='Cancion - Live',artist='Artista',duration=210)])]})
            state=music.read_state();self.assertEqual(state['collections']['next']['tracks'],['id-a','id-live'])
            self.assertEqual(state['tracks']['id-a']['path'],'/unchanged/file.opus')

    def test_audio_selection_rejects_long_videoclip(self):
        track=dict(title='NO ME QUIERO CASAR',artist='Bad Bunny',duration=225.6,prefer_audio=True)
        self.assertLess(music.candidate_score(track,dict(title='Bad Bunny - No Me Quiero Casar (Official Video)',channel='Bad Bunny',duration=540)),0)
        self.assertGreater(music.candidate_score(track,dict(title='Bad Bunny - No Me Quiero Casar (Official Audio)',channel='Bad Bunny',duration=226)),10)

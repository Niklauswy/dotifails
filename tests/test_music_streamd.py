"""The warm yt-dlp helper: one process that keeps yt-dlp loaded, so a song resolves without paying its start-up."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from wysun_music import streamd  # noqa: E402

SEARCH = {'entries': [
    {'id': 'cover000000', 'title': 'Housewife (cover)', 'channel': 'Fans', 'duration': 180},
    {'id': 'real0000000', 'title': 'Tate McRae - Housewife (Official Audio)', 'channel': 'Tate McRae', 'duration': 181,
     'channel_is_verified': True}]}


class FakeYDL:
    calls = []

    def __init__(self, flat):
        self.flat = flat

    def extract_info(self, url, download=False):
        FakeYDL.calls.append((self.flat, url))
        if url.startswith('ytsearch'):
            return SEARCH
        if 'list=RD' in url:
            return {'entries': [{'id': 'seed0000000', 'title': 'Seed'}, {'id': 'next0000000', 'title': 'A - B'}]}
        return {'url': 'https://audio.example/' + url[-11:], 'title': 'x'}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        FakeYDL.calls = []
        self.service = streamd.Service(FakeYDL)

    def test_resolve_known_video_skips_the_search(self):
        answer = self.service.handle({'id': 1, 'op': 'resolve',
                                      'track': {'title': 'A', 'artist': 'B',
                                                'youtube_url': 'https://www.youtube.com/watch?v=abcdefghijk'}})
        self.assertEqual(answer, {'id': 1, 'ok': True, 'video': 'https://www.youtube.com/watch?v=abcdefghijk',
                                  'audio': 'https://audio.example/abcdefghijk'})
        self.assertEqual(len(FakeYDL.calls), 1)

    def test_resolve_searches_and_scores_like_the_downloader(self):
        answer = self.service.handle({'id': 2, 'op': 'resolve',
                                      'track': {'title': 'Housewife', 'artist': 'Tate McRae', 'duration': 181}})
        self.assertEqual(answer['video'], 'https://www.youtube.com/watch?v=real0000000')
        self.assertTrue(FakeYDL.calls[0][0], 'the search is flat')

    def test_resolve_without_a_match_fails(self):
        answer = self.service.handle({'id': 3, 'op': 'resolve', 'track': {'title': 'Otra cosa', 'artist': 'Nadie'}})
        self.assertFalse(answer['ok'])

    def test_search_and_mix(self):
        found = self.service.handle({'id': 4, 'op': 'search', 'query': 'housewife', 'limit': 5})
        self.assertEqual([e['id'] for e in found['entries']], ['cover000000', 'real0000000'])
        self.assertIn('ytsearch5:housewife', FakeYDL.calls[-1][1])
        mix = self.service.handle({'id': 5, 'op': 'mix', 'url': 'https://www.youtube.com/watch?v=seed0000000'})
        self.assertEqual([e['id'] for e in mix['entries']], ['next0000000'])

    def test_errors_become_answers(self):
        class Broken(FakeYDL):
            def extract_info(self, url, download=False):
                raise OSError('sin red')
        answer = streamd.Service(Broken).handle({'id': 6, 'op': 'search', 'query': 'x'})
        self.assertEqual((answer['ok'], answer['error']), (False, 'sin red'))


if __name__ == '__main__':
    unittest.main()

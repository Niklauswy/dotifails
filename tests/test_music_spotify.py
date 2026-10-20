import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/wysun'))
from music_spotify import spotify_entity,parse_embed

class SpotifyImportTests(unittest.TestCase):
    def test_public_link_and_uri_validation(self):
        key='37i9dQZF1DX2apWzyECwyZ'
        self.assertEqual(spotify_entity('https://open.spotify.com/playlist/'+key+'?si=x'),('playlist',key))
        self.assertEqual(spotify_entity('spotify:album:'+key),('album',key))
        for url in ['https://open.spotify.com.evil/playlist/'+key,'https://evil/playlist/'+key,'http://open.spotify.com/playlist/'+key]:
            with self.assertRaises(ValueError):spotify_entity(url)

    def test_public_metadata_import_and_private_fallback(self):
        entity=dict(title='Mi playlist',trackList=[dict(uri='spotify:track:AAAAAAAAAAAAAAAAAAAAAA',title='Canción',subtitle='Artista',duration=201000),dict(uri='spotify:episode:podcast',title='Podcast')])
        payload=dict(props=dict(pageProps=dict(state=dict(data=dict(entity=entity)))))
        page='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(payload)+'</script>'
        data=parse_embed(page,'playlist','BBBBBBBBBBBBBBBBBBBBBB');self.assertEqual(data['published_count'],1)
        self.assertEqual(data['collections'][0]['tracks'][0]['duration'],201)
        self.assertTrue(data['collections'][0]['tracks'][0]['prefer_audio'])
        with self.assertRaises(ValueError):parse_embed('<html>Private</html>','playlist','x')

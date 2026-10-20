import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/wysun'))
from music_library import PlaybackOrder,MusicStore,normalize,artists,parse_lrc

class PlayerTests(unittest.TestCase):
    def test_shuffle_previous_next_are_inverse(self):
        for seed in range(30):
            random.seed(seed);order=PlaybackOrder();order.start(['A','B','C','D','E'],'C',True)
            a=order.current;b=order.move(-1);self.assertIsNotNone(b)
            self.assertEqual(order.move(1),a);self.assertEqual(order.move(-1),b)
            remaining=order.keys.copy();self.assertEqual(len(remaining),len(set(remaining)))

    def test_end_repeat_and_skip_missing(self):
        order=PlaybackOrder();order.start(['A','B','C'],'A')
        self.assertEqual(order.move(1,lambda k:k!='B'),'C')
        self.assertIsNone(order.move(1));self.assertEqual(order.current,'C')
        order.repeat=True;self.assertEqual(order.move(1),'A')
        self.assertIsNone(order.move(1,lambda k:False))

    def test_persistent_order_and_favorites_are_separate_from_downloads(self):
        with tempfile.TemporaryDirectory() as root:
            state=Path(root)/'library.json';state.write_text('{"private":true}')
            store=MusicStore(root);self.assertTrue(store.toggle('A'))
            order=PlaybackOrder();order.start(['A','B','C'],'B',True);order.move(-1)
            store.put('order',order.export());store.close();store=MusicStore(root)
            restored=PlaybackOrder();restored.restore(store.get('order'))
            self.assertEqual(restored.keys,order.keys);self.assertEqual(restored.current,order.current)
            self.assertEqual(store.favorites(),{'A'});self.assertFalse(store.toggle('A'))
            self.assertEqual(json.loads(state.read_text()),{'private':True});store.close()

    def test_accents_collaborations_and_timed_lyrics(self):
        self.assertEqual(normalize(' MÉXICO '),'mexico')
        self.assertEqual(artists(dict(title='Song (feat. C & D)',artist='A, B')),['A','B','C','D'])
        self.assertEqual(parse_lrc('[offset:500]\n[00:03.20][00:08.00]Hello\n[00:01]First'),[(1.5,'First'),(3.7,'Hello'),(8.5,'Hello')])

    def test_album_reference_survives_playlist_import(self):
        with tempfile.TemporaryDirectory() as root:
            store=MusicStore(root)
            store.import_references({'collections':[dict(title='Album',source='https://open.spotify.com/album/1',tracks=[dict(id='A',duration=30)])]})
            store.import_references({'collections':[dict(title='Top',source='x',tracks=[dict(id='A',duration=31)])]})
            self.assertEqual(store.reference('A')['album'],'Album');self.assertEqual(store.reference('A')['duration'],30)
            store.close()

if __name__=='__main__':unittest.main()

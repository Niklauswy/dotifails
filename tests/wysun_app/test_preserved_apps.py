"""Private fixtures for preserved data/operation behavior; no devices or network."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))

class PreservedAppsTests(unittest.TestCase):
    def test_music_close_reopen_preserves_session_favorites_order_and_lyrics(self):
        from music_library import MusicStore,PlaybackOrder,parse_lrc
        with tempfile.TemporaryDirectory() as folder:
            order=PlaybackOrder();order.start(['own-a','own-b','own-c'],'own-b');order.repeat=True
            store=MusicStore(folder);store.toggle('own-b');store.put('session',dict(track='own-b',position=12.75,volume=37,order=order.export()));store.close()
            reopened=MusicStore(folder);session=reopened.get('session');restored=PlaybackOrder();restored.restore(session['order'])
            self.assertEqual(reopened.favorites(),{'own-b'});self.assertEqual(session['position'],12.75);self.assertEqual(session['volume'],37)
            self.assertEqual(restored.current,'own-b');self.assertEqual(restored.move(1),'own-c');self.assertEqual(restored.move(-1),'own-b');reopened.close()
        self.assertEqual(parse_lrc('[offset:+500]\n[00:01.00][00:03.00]Synthetic line'),[(1.5,'Synthetic line'),(3.5,'Synthetic line')])
    def test_download_queue_resumes_without_network_or_duplicate_entries(self):
        import music_data
        manifest={'collections':[dict(id='own-list',title='Synthetic',tracks=[dict(id='own-track',title='Own fixture',artist='Own artist',duration=4)])]}
        with tempfile.TemporaryDirectory() as folder,patch.object(music_data,'DATA',Path(folder)),patch.object(music_data.subprocess,'Popen') as spawn:
            music_data.enqueue(manifest);music_data.set_paused(True);self.assertTrue(music_data.read_state()['paused'])
            music_data.update_track('own-track',status='error',error='fixture interrupted');music_data.retry_failed();music_data.enqueue(manifest)
            state=music_data.read_state();self.assertEqual(state['collections']['own-list']['tracks'],['own-track']);self.assertEqual(state['tracks']['own-track']['status'],'pending');self.assertFalse(state['paused']);spawn.assert_not_called()
    def test_files_copy_collision_recursive_guard_and_safe_move(self):
        from files_ops import execute_operation
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'original.txt';source.write_text('synthetic preserved');dest=root/'dest';dest.mkdir()
            copied=execute_operation('copy',[str(source)],str(dest));self.assertEqual(Path(copied[0]).read_text(),source.read_text())
            with self.assertRaises(FileExistsError):execute_operation('copy',[str(source)],str(dest))
            self.assertEqual(source.read_text(),'synthetic preserved')
            nested=dest/'nested';nested.mkdir()
            with self.assertRaises(ValueError):execute_operation('copy',[str(dest)],str(nested))
            moved=execute_operation('rename',copied,str(dest/'renamed.txt'));self.assertFalse(Path(copied[0]).exists());self.assertEqual(Path(moved[0]).read_text(),'synthetic preserved')
    def test_native_session_processes_are_protected_without_signals(self):
        from process_data import Processes
        model=Processes.__new__(Processes);model.protected=set()
        for name in ('Hyprland','quickshell','pipewire','wireplumber','xdg-desktop-por','swaylock'):
            self.assertIn('protegido',model.action_reason(dict(uid=os.getuid(),pid=999999,name=name,state='S')))
        self.assertIsNone(model.action_reason(dict(uid=os.getuid(),pid=999999,name='own-fixture',state='S')))

if __name__=='__main__':unittest.main()

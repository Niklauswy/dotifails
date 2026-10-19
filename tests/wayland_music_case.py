"""Installed native Music/mini with generated files and a private null sink.

Invoked only by the guarded portal runner; never reads a personal library.
The child uses actual installed widgets and Qt input, without replacing methods.
"""
import json
from pathlib import Path


CHILD = r'''
import array,json,os,sys,subprocess,time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
import PySide6
PySide6.__path__.insert(0,'/tmp/wysun-qml-bindings/root/usr/lib/python3/dist-packages/PySide6')
from PySide6.QtTest import QTest
run=Path(sys.argv[1]);home=Path.home()
assert str(run).startswith('/tmp/ws-') and home.is_relative_to(run)
assert os.environ['PULSE_SERVER'].startswith('unix:'+str(run/'r'))
sys.path.insert(0,str(home/'.local/share/orbit/app'))
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
import music_data as music
assert music.DATA.is_relative_to(home)
music.import_files([run/'Synthetic tone A.wav',run/'Synthetic tone B.wav'])
from music_app_window import MusicAppWindow
from music_mini import MiniPlayer
player=MusicAppWindow();mini=None
def spin(predicate,description,timeout=12):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  app.processEvents();time.sleep(.025)
  if predicate():return
 raise RuntimeError(description)
def delay(seconds):
 end=time.monotonic()+seconds
 while time.monotonic()<end:app.processEvents();time.sleep(.025)
try:
 player.present()
 def native():
  clients=json.loads(subprocess.check_output(['hyprctl','-j','clients'],text=True))
  return next((c for c in clients if c['pid']==os.getpid() and c['mapped'] and not c['xwayland']),None)
 spin(native,'Music native window');keys=player.all_keys();assert len(keys)==2,keys
 player.go('tracks');player.play_key(keys[0]);spin(lambda:player.current_position>.4,'Music actual playback')
 mpv_pid=int(player.process.processId());assert mpv_pid>0
 QTest.mouseClick(player.play_button,Qt.LeftButton);spin(lambda:player.paused,'pause button')
 before=player.current_position;delay(.5);assert abs(player.current_position-before)<.25
 player.seek_to(3);spin(lambda:abs(player.current_position-3)<.35,'paused seek')
 QTest.mouseClick(player.play_button,Qt.LeftButton);spin(lambda:not player.paused,'resume button')
 QTest.mouseClick(player.favorite_button,Qt.LeftButton);assert keys[0] in player.store.favorites()
 player.hide();before=player.current_position;delay(.7)
 assert player.current_position>before+.3,'Panel hiding stopped music'
 mini=MiniPlayer(player);mini.present();spin(lambda:mini.isVisible(),'native mini')
 QTest.mouseClick(mini.next,Qt.LeftButton);spin(lambda:player.current_key==keys[1] and player.current_position>.2,'mini next')
 assert int(player.process.processId())==mpv_pid,'Mini started duplicate audio player'
 QTest.mouseClick(mini.play,Qt.LeftButton);spin(lambda:player.paused,'mini pause')
 mini.close();player.present();spin(native,'Music reopen')
 QTest.mouseClick(player.play_button,Qt.LeftButton);spin(lambda:not player.paused,'resume for PCM')
 raw=subprocess.check_output(['ffmpeg','-v','error','-f','pulse','-i',os.environ['PULSE_SINK']+'.monitor',
  '-t','0.6','-ac','1','-ar','48000','-f','s16le','-'],timeout=8)
 samples=array.array('h',raw);assert samples and max(map(abs,samples))>100,'Private sink has no decoded tone'
 player.save_session();saved=player.store.get('session');assert saved['track']==keys[1]
 inputs=json.loads(subprocess.check_output(['pactl','-f','json','list','sink-inputs'],text=True))
 assert inputs,'No private Pulse playback stream'
 player.shutdown_jobs();player.hide()
 restored=MusicAppWindow()
 try:
  assert restored.current_key==saved['track']
  assert keys[0] in restored.store.favorites()
  assert int(restored.process.processId())==0,'Restoration unexpectedly autoplayed'
 finally:restored.shutdown_jobs();restored.hide()
 result=dict(result='WYSUN_NATIVE_MUSIC_OK',scope='actual installed classes, native window, Qt button input; no public CLI assertion',
  native_window=True,generated_tracks=2,pause_seek_resume=True,hidden_playback_continues=True,
  mini_next_pause_same_mpv=True,favorite_and_session_restored=True,restoration_autoplay=False,
  private_sink_pcm_peak=max(map(abs,samples)),private_sink_pcm_samples=len(samples))
 (run/'native-music-results.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result),flush=True)
finally:
 if mini:mini.close()
 player.shutdown_jobs();player.hide()
'''


def run_case(run_dir, env, command, start, wait_for):
    sink='wysun-music-only'
    command(['pactl','load-module','module-null-sink','sink_name='+sink,'channels=1','rate=48000'])
    for name, hz in [('A',440),('B',880)]:
        command(['ffmpeg','-v','error','-f','lavfi','-i',f'sine=frequency={hz}:duration=12',
                 '-c:a','pcm_s16le',run_dir/f'Synthetic tone {name}.wav'])
    child=run_dir/'native-music-child.py';child.write_text(CHILD)
    process=start('native-music',['/usr/bin/python3',child,run_dir],{'PULSE_SINK':sink,'LD_LIBRARY_PATH':'/tmp/wysun-qml-bindings/root/usr/lib/x86_64-linux-gnu:'+env.get('LD_LIBRARY_PATH','')})
    wait_for(lambda:process.poll() is not None,'native Music proof',timeout=50)
    assert process.returncode==0,(run_dir/'native-music.log').read_text(errors='replace')[-6000:]
    result=json.loads((run_dir/'native-music-results.json').read_text())
    print(json.dumps(result,indent=2),flush=True)
    return result

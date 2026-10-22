"""Installed native Music/full player with generated files and a private null sink.

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
from wysun_music.app import build
music_app=build(publish=False);player=music_app.player;library=music_app.library;window=music_app.window
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
 window.present()
 def native():
  clients=json.loads(subprocess.check_output(['hyprctl','-j','clients'],text=True))
  return next((c for c in clients if c['pid']==os.getpid() and c['mapped'] and not c['xwayland']),None)
 spin(native,'Music native window');keys=library.all_keys();assert len(keys)==2,keys
 window.navigate(('collection','all'));player.play_collection(keys,keys[0],'all');spin(lambda:player.position>.4,'Music actual playback')
 mpv_pid=int(player.engine.process.processId());assert mpv_pid>0
 QTest.mouseClick(window.bar.play,Qt.LeftButton);spin(lambda:player.paused,'pause button')
 before=player.position;delay(.5);assert abs(player.position-before)<.25
 player.seek(3);spin(lambda:abs(player.position-3)<.35,'paused seek')
 QTest.mouseClick(window.bar.play,Qt.LeftButton);spin(lambda:not player.paused,'resume button')
 QTest.mouseClick(window.bar.favorite,Qt.LeftButton);assert keys[0] in library.store.favorites()
 window.hide();before=player.position;delay(.7)
 assert player.position>before+.3,'Panel hiding stopped music'
 window.present();spin(native,'Music reopen');window.toggle_panel('now');spin(lambda:window.side.isVisible(),'full player')
 QTest.mouseClick(window.side.next,Qt.LeftButton);spin(lambda:player.current==keys[1] and player.position>.2,'full player next')
 assert int(player.engine.process.processId())==mpv_pid,'Full player started duplicate audio player'
 QTest.mouseClick(window.side.play,Qt.LeftButton);spin(lambda:player.paused,'full player pause')
 window.toggle_panel(None)
 QTest.mouseClick(window.bar.play,Qt.LeftButton);spin(lambda:not player.paused,'resume for PCM')
 raw=subprocess.check_output(['ffmpeg','-v','error','-f','pulse','-i',os.environ['PULSE_SINK']+'.monitor',
  '-t','0.6','-ac','1','-ar','48000','-f','s16le','-'],timeout=8)
 samples=array.array('h',raw);assert samples and max(map(abs,samples))>100,'Private sink has no decoded tone'
 player.save();saved=library.store.get('session');assert saved['track']==keys[1]
 inputs=json.loads(subprocess.check_output(['pactl','-f','json','list','sink-inputs'],text=True))
 assert inputs,'No private Pulse playback stream'
 music_app.shutdown();window.hide()
 restored=build(publish=False)
 try:
  assert restored.player.current==saved['track']
  assert keys[0] in restored.library.favorites
  assert not restored.player.engine.running,'Restoration unexpectedly autoplayed'
 finally:restored.shutdown();restored.window.hide()
 result=dict(result='WYSUN_NATIVE_MUSIC_OK',scope='actual installed classes, native window, Qt button input; no public CLI assertion',
  native_window=True,generated_tracks=2,pause_seek_resume=True,hidden_playback_continues=True,
  full_player_next_pause_same_mpv=True,favorite_and_session_restored=True,restoration_autoplay=False,
  private_sink_pcm_peak=max(map(abs,samples)),private_sink_pcm_samples=len(samples))
 (run/'native-music-results.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result),flush=True)
finally:
 if player.engine.running:player.shutdown()
 window.hide()
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

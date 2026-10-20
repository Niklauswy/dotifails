"""Exercise native rendering and real mpv IPC using silent audio and isolated data."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'apps/wysun'))
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
import music_data as music
from music_app_window import MusicAppWindow as MusicWindow
from music_mini import MiniPlayer
from PySide6.QtCore import Qt,QPoint
from PySide6.QtCore import QEvent,QPointF
from PySide6.QtGui import QMouseEvent,QKeyEvent

with tempfile.TemporaryDirectory(prefix='orbit-music-qa-') as folder:
    temp = Path(folder)
    music.DATA = temp/'state'
    music.LIBRARY = temp/'audio'
    binary = temp/'mpv'
    binary.write_text('#!/bin/sh\nexec /usr/bin/mpv --ao=null "$@"\n')
    binary.chmod(0o755)
    os.environ['PATH'] = str(temp)+os.pathsep+os.environ['PATH']
    audio = temp/'first.wav'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=440:duration=10', str(audio)], check=True)
    audio2 = temp/'second.wav'
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=220:duration=10', str(audio2)], check=True)
    music.import_files([audio, audio2])
    app = QApplication([])
    window = MusicWindow(test=True)
    window.show()
    def wait_until(predicate, seconds=5):
        until = time.monotonic()+seconds
        while time.monotonic() < until:
            app.processEvents()
            if predicate():
                return
            time.sleep(.02)
        raise AssertionError('Timed out waiting for player state: '+window.status.text())
    window.go('tracks')
    mini=MiniPlayer(window);mini.show();app.processEvents()
    mini.search.setText('first');assert mini.matches.count()==1
    def press(widget,key,mods=Qt.NoModifier,text=''):
        QApplication.sendEvent(widget,QKeyEvent(QEvent.ShortcutOverride,key,mods,text))
        QApplication.sendEvent(widget,QKeyEvent(QEvent.KeyPress,key,mods,text))
        QApplication.sendEvent(widget,QKeyEvent(QEvent.KeyRelease,key,mods,text))
        app.processEvents()
    mini.activateWindow();mini.search.setFocus();mini.search.setText('local');app.processEvents()
    assert mini.matches.count()==2
    assert mini.matches.visualItemRect(mini.matches.item(0)).height()>=54
    assert mini.matches.viewport().height()>=116,'Two complete result rows must fit without clipping'
    assert mini.matches.horizontalScrollBar().maximum()==0
    press(mini.search,Qt.Key_Down)
    assert mini.matches.currentRow()==1
    played=[];original=mini.keyboard.activate;mini.keyboard.activate=lambda item:played.append(item.data(Qt.UserRole))
    press(mini.search,Qt.Key_Return)
    assert played==[mini.matches.item(1).data(Qt.UserRole)],'Enter must activate the highlighted result'
    mini.keyboard.activate=original
    press(mini.search,Qt.Key_Escape)
    assert not mini.search.text() and mini.isVisible(),'First Escape clears search without hiding player'
    window.activateWindow();window.search.setFocus();window.search.clear();app.processEvents()
    favorites=window.favorite_keys.copy()
    press(window.search,Qt.Key_F,text='f')
    assert window.search.text()=='f' and window.favorite_keys==favorites,'Typing F must not trigger favorites'
    press(window.search,Qt.Key_Escape);assert not window.search.text()
    window.search.setText('local');press(window.search,Qt.Key_Down)
    assert window.tree.currentItem() is not None
    clicked=[];window.hero_play.clicked.connect(lambda:clicked.append(True))
    window.hero_play.setFocus();press(window.hero_play,Qt.Key_Return)
    assert clicked,'Enter must activate focused buttons'
    window.search.clear();window.go('tracks')
    assert window.tree.topLevelItemCount() == 2
    keys = list(window.state['tracks'])
    window.tree.setCurrentItem(window.tree.topLevelItem(0))
    window.play_selection()
    wait_until(lambda: window.duration > 0 and window.socket is not None)
    assert window.current_key == keys[0] and not window.paused
    mini.sync();assert mini.title.text()=='first' and mini.rendered[0] is False
    window.toggle_play()
    wait_until(lambda: window.paused)
    point=QPointF(window.seek.width()/2,window.seek.height()/2)
    QApplication.sendEvent(window.seek,QMouseEvent(QEvent.MouseButtonPress,point,point,Qt.LeftButton,Qt.LeftButton,Qt.NoModifier))
    QApplication.sendEvent(window.seek,QMouseEvent(QEvent.MouseButtonRelease,point,point,Qt.LeftButton,Qt.NoButton,Qt.NoModifier))
    wait_until(lambda: window.seek.value() >= 4)
    window.close()
    wait_until(lambda: not window.isVisible())
    assert window.process.state() == QProcess.Running, 'Hiding panel must preserve playback'
    window.present()
    window.advance(1)
    assert window.current_key == keys[1]
    window.advance(-1)
    assert window.current_key == keys[0]
    window.advance(1)
    assert window.current_key == keys[1]
    window.favorite(keys[1]);window.go('favorites')
    assert window.tree.topLevelItemCount()==1
    window.search.setText('first')
    assert window.tree.topLevelItemCount()==1, 'Global search must escape favorites/playlist'
    assert window.tree.topLevelItem(0).data(0,Qt.UserRole)==keys[0]
    assert window.order.current==keys[1], 'Browsing must preserve queue'
    window.show_lyrics(dict(synced='[00:00]First line\n[00:05]Second line'))
    assert window.lyric_list.count()==2
    window.seek_lyric(window.lyric_list.item(1))
    wait_until(lambda:window.seek.value()>=4)
    window.command(['set_property','pause',False])
    window.command(['seek',9.8,'absolute'])
    wait_until(lambda:window.ended)
    window.toggle_play()
    wait_until(lambda:not window.paused and window.seek.value()<3)
    window.go('artist',artist='Archivo local')
    assert window.tree.topLevelItemCount()==2
    window.go('tracks')
    window.search.setText('second')
    assert window.tree.topLevelItemCount() == 1
    window.resize(900, 660)
    app.processEvents()
    window.grab().save('/tmp/orbit-music-qa.png')
    window.shutdown_jobs()
    assert window.process.state() == QProcess.NotRunning
    mini.timer.stop();mini.hide();window.store.close()
    # Dedicated singleton IPC: launch twice, preserve one process, clean endpoint on exit.
    import socket
    runtime=temp/'runtime';runtime.mkdir()
    environment=dict(os.environ,ORBIT_MUSIC_HOME=str(music.DATA),ORBIT_MUSIC_LIBRARY=str(music.LIBRARY),XDG_RUNTIME_DIR=str(runtime))
    log=(temp/'app.log').open('w')
    dedicated=subprocess.Popen([sys.executable,str(root/'apps/wysun/music_app.py')],env=environment,stdout=log,stderr=log)
    endpoint=runtime/f'orbit-music-app-{os.getuid()}.sock'
    started=time.monotonic()
    try:
        wait_until(lambda:endpoint.exists(),5)
        assert time.monotonic()-started<2,'Dedicated startup should take less than two seconds'
        duplicate=subprocess.run([sys.executable,str(root/'apps/wysun/music_app.py')],env=environment,timeout=3,stdout=log,stderr=log)
        assert duplicate.returncode==0 and dedicated.poll() is None
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(endpoint));client.sendall(b'present\n')
    finally:
        time.sleep(.3)
        dedicated.terminate()
        try:dedicated.wait(timeout=10)
        except subprocess.TimeoutExpired:
            dedicated.kill();dedicated.wait();raise
        finally:log.close()
    assert not endpoint.exists(),'Exit must remove dedicated socket'
    print('MUSIC_UI_OK: real mpv IPC, duration, pause, seek, next, filtering, hide/resume and clean shutdown')

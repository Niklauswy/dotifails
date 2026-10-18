#!/usr/bin/env python3
"""Single-instance dedicated music process, independent from the Orbit daemon."""
import fcntl
import json
import os
from pathlib import Path
import socket
import sys
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from settings_app import LocalSettingsServer


def ipc_properties(endpoint, properties):
    values={}
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(.5);client.connect(endpoint)
        for i, name in enumerate(properties):
            client.sendall((json.dumps({'command':['get_property',name],'request_id':i})+'\n').encode())
        buffer=b'';until=time.monotonic()+1
        while len(values)<len(properties) and time.monotonic()<until:
            buffer+=client.recv(65536)
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1)
                data=json.loads(line)
                if isinstance(data.get('request_id'),int) and data.get('error')=='success':values[properties[data['request_id']]]=data.get('data')
    return values


def legacy_player():
    """Read only the old daemon's mpv. Never touch another user's music player."""
    from music_data import DATA
    restart=DATA/'restart-handoff.json'
    if restart.exists():
        try:
            values=json.loads(restart.read_text());restart.unlink()
            if time.time()-values.get('created',0)<60:return values
        except (OSError,ValueError):pass
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():continue
        try:
            args=(directory/'cmdline').read_bytes().decode().split('\0')
            endpoint=next((a.split('=',1)[1] for a in args if a.startswith('--input-ipc-server=/tmp/orbit-music-')),None)
            if not endpoint:continue
            parent=next(line.split()[1] for line in (directory/'status').read_text().splitlines() if line.startswith('PPid:'))
            owner=Path('/proc')/parent
            if owner.stat().st_uid!=os.getuid():continue
            command=(owner/'cmdline').read_bytes().decode()
            if 'orbit.py' not in command or 'music_app.py' in command:continue
            values=ipc_properties(endpoint,['path','time-pos','pause','volume'])
            if values.get('path'):return dict(values,endpoint=endpoint)
        except (OSError,ValueError,StopIteration):continue
    return None


def main():
    if os.environ.get('ORBIT_MUSIC_DEBUG'):
        import faulthandler,signal
        faulthandler.register(signal.SIGUSR1)
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.cache/orbit')))
    runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
    endpoint=runtime/f'orbit-music-app-{os.getuid()}.sock'
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(.3);client.connect(str(endpoint));client.sendall((('mini' if '--mini' in sys.argv else 'present')+'\n').encode());return 0
    except OSError:pass
    lock=(runtime/f'orbit-music-app-{os.getuid()}.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    if endpoint.exists():
        if not endpoint.is_socket():raise RuntimeError('La ruta del reproductor está ocupada por otro archivo.')
        endpoint.unlink()
    app=QApplication(['Orbit','-name','Orbit']);app.setStyle('Fusion')
    app.setApplicationName('Orbit');app.setApplicationDisplayName('Wysun Music');app.setDesktopFileName('orbit-music');app.setQuitOnLastWindowClosed(False)
    from theme_tokens import watch_theme
    watch_theme()
    from music_app_window import MusicAppWindow
    server=LocalSettingsServer(endpoint,app)
    window=MusicAppWindow()
    from music_mini import MiniPlayer
    mini=MiniPlayer(window)
    def present(route):
        if route=='mini':
            if mini.isVisible():mini.close()
            else:mini.present()
        else:mini.close();window.present()
    server.requested.connect(present)
    handoff=legacy_player()
    if handoff:
        key=next((k for k,t in window.state['tracks'].items() if t.get('path')==handoff['path']),None)
        if key:
            key=window.state['tracks'][key].get('album_audio_of') or key
            # Keep exactly the recording being listened to during migration.
            if not handoff.get('created') or window.order.current!=key:
                window.order.start(window.all_keys(),key,window.shuffle.isChecked())
            window.queue=window.order.keys.copy();window.current_key=key
            window.pending_path=handoff['path'];window.resume_position=handoff.get('time-pos') or 0
            window.resume_paused=handoff.get('pause',True);window.volume.setValue(round(handoff.get('volume') or 0))
            window.current_audio=next(t.copy() for t in window.state['tracks'].values() if t.get('path')==handoff['path'])
            window.legacy_endpoint=handoff.get('endpoint');window.show_current();window.start_player()
    QTimer.singleShot(0,lambda:present('mini' if '--mini' in sys.argv else 'present'))
    def finish():
        window.shutdown_jobs();server.close()
    app.aboutToQuit.connect(finish)
    import signal
    signal.signal(signal.SIGTERM,lambda *_:QTimer.singleShot(0,lambda:app.exit(0)))
    signal.signal(signal.SIGINT,lambda *_:QTimer.singleShot(0,lambda:app.exit(0)))
    signal_timer=QTimer(app);signal_timer.timeout.connect(lambda:None);signal_timer.start(500)
    return app.exec()

if __name__=='__main__':sys.exit(main())

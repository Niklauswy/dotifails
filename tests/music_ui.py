"""Exercise Wysun Music with real mpv IPC, synthetic audio and isolated data.

Covers playback through the UI controls, the full player sharing one engine,
queue/up-next, favourites, synced lyrics seeking, hiding without stopping,
MPRIS (when a session bus and playerctl exist) and the single-instance launcher.
"""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'apps/wysun'))

with tempfile.TemporaryDirectory(prefix='wysun-music-qa-') as folder:
    temp = Path(folder)
    os.environ.update(ORBIT_MUSIC_HOME=str(temp / 'state'), ORBIT_MUSIC_LIBRARY=str(temp / 'audio'),
                      XDG_RUNTIME_DIR=str(temp / 'run'))
    (temp / 'run').mkdir(mode=0o700)
    binary = temp / 'mpv'
    binary.write_text('#!/bin/sh\nexec /usr/bin/mpv --ao=null "$@"\n')
    binary.chmod(0o755)
    os.environ['PATH'] = str(temp) + os.pathsep + os.environ['PATH']
    for name, hz in (('first', 440), ('second', 220), ('third', 330)):
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                        f'sine=frequency={hz}:duration=10', '-metadata', 'title=' + name,
                        '-metadata', 'artist=Synth', str(temp / f'{name}.ogg')], check=True)

    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QKeyEvent, QMouseEvent
    from PySide6.QtWidgets import QApplication
    import music_data
    music_data.import_files([temp / f'{n}.ogg' for n in ('first', 'second', 'third')])
    app = QApplication([])
    from wysun_music.app import build
    publish = bool(os.environ.get('DBUS_SESSION_BUS_ADDRESS')) and bool(shutil.which('playerctl'))
    music = build(test=True)
    window, player, library = music.window, music.player, music.library
    if publish:
        from wysun_music import mpris
        music.mpris = mpris.start(player, music.covers, window.present, app.quit, instance=os.getpid())
    window.show()

    def wait_until(predicate, seconds=6, what='player state'):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            app.processEvents()
            if predicate():
                return
            time.sleep(.02)
        raise AssertionError('Timed out waiting for ' + what)

    def click(widget):
        point = QPointF(widget.width() / 2, widget.height() / 2)
        for kind, buttons in ((QEvent.MouseButtonPress, Qt.LeftButton), (QEvent.MouseButtonRelease, Qt.NoButton)):
            QApplication.sendEvent(widget, QMouseEvent(kind, point, point, Qt.LeftButton, buttons, Qt.NoModifier))
        app.processEvents()

    def press(widget, key, text=''):
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QApplication.sendEvent(widget, QKeyEvent(kind, key, Qt.NoModifier, text))
        app.processEvents()

    by_title = {library.track(k)['title']: k for k in library.all_keys()}
    first, second, third = by_title['first'], by_title['second'], by_title['third']

    # Search → Enter plays the first match in the search context.
    window.search.setFocus()
    window.search.setText('second')
    wait_until(lambda: window.search_page.songs.keys == [second], what='search results')
    press(window.search, Qt.Key_Return)
    press(window.search_page.songs, Qt.Key_Return)
    wait_until(lambda: player.current == second and player.position > .3, what='search playback')
    assert player.queue.context == 'search:second'

    # Collection page: play from the list; transport buttons drive the shared engine.
    window.navigate(('collection', 'all'))
    window.collection.tracks.play_requested.emit(first)
    wait_until(lambda: player.current == first and not player.paused, what='list playback')
    click(window.bar.play)
    wait_until(lambda: player.paused, what='pause button')
    held = player.position
    time.sleep(.4)
    app.processEvents()
    assert abs(player.position - held) < .2, 'Paused audio kept advancing'
    click(window.bar.play)
    wait_until(lambda: not player.paused, what='resume button')
    window.bar.progress.released.emit(.5)
    wait_until(lambda: abs(player.position - 5) < .5, what='seek')

    # Up next, previous restarts after 3 s, next/previous across the context.
    player.play_next([third])
    assert player.queue.upcoming()[0] == third
    click(window.bar.next)
    wait_until(lambda: player.current == third, what='up next')
    player.seek(4)
    wait_until(lambda: player.position > 3.5, what='seek before previous')
    player.previous()
    wait_until(lambda: player.current == third and player.position < 1, what='previous restarts')

    # Repeat one replays the song at its end; repeat off ends the list.
    player.set_repeat('one')
    player.seek(9.7)
    wait_until(lambda: player.current == third and 0 < player.position < 2, what='repeat one')
    player.set_repeat('off')

    # Favourites from the bar reach every view.
    click(window.bar.favorite)
    assert third in library.favorites and window.bar.favorite.isChecked()
    window.navigate(('collection', 'favorites'))
    assert window.collection.tracks.keys == [third]

    # Lyrics: clicking a synced line seeks.
    window.toggle_panel('lyrics')
    window.side.lyrics.set_lyrics({'synced': '[00:00]Uno\n[00:06]Dos'})
    window.side.lyrics.seek_requested.emit(6.0)
    wait_until(lambda: abs(player.position - 6) < .5, what='lyric seek')
    window.toggle_panel('queue')
    assert window.side.queue.now.keys == [third]

    # Hiding the window keeps playing; «Ahora suena» drives the same mpv.
    engine_pid = player.engine.process.processId()
    window.close()
    wait_until(lambda: not window.isVisible(), what='hide')
    before = player.position
    time.sleep(.5)
    app.processEvents()
    assert player.position > before + .2, 'Hiding the window stopped music'
    window.present()
    window.toggle_panel('now')
    click(window.side.next)
    wait_until(lambda: player.current != third, what='full player next')
    assert player.engine.process.processId() == engine_pid, 'Full player started a second audio engine'
    click(window.side.play)
    wait_until(lambda: player.paused, what='full player pause')
    window.toggle_panel(None)

    if publish:
        def playerctl(*args):
            result = []
            thread = threading.Thread(target=lambda: result.append(subprocess.run(
                ['playerctl', '-p', f'wysun_music.instance{os.getpid()}', *args], capture_output=True, text=True, timeout=5)))
            thread.start()
            wait_until(lambda: not thread.is_alive(), what='playerctl ' + ' '.join(args))
            return result[0].stdout.strip()
        assert playerctl('status') == 'Paused'
        assert playerctl('metadata', 'title') == library.track(player.current)['title']
        playerctl('play')
        wait_until(lambda: not player.paused, what='MPRIS play')
        playerctl('loop', 'Playlist')
        wait_until(lambda: player.repeat == 'all', what='MPRIS loop')
        playerctl('shuffle', 'On')
        wait_until(lambda: player.shuffle, what='MPRIS shuffle')
        print('MPRIS: status, metadata, play, loop and shuffle round-trip')

    window.resize(900, 640)
    window.present()
    app.processEvents()
    window.grab().save(str(temp / 'music.png'))
    music.shutdown()
    assert not player.engine.running

    # Dedicated singleton process: second launch forwards, exit removes the socket.
    runtime = temp / 'runtime'
    runtime.mkdir()
    environment = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM='offscreen')
    log = (temp / 'app.log').open('w')
    launcher = root / 'apps/wysun/music_app.py'
    dedicated = subprocess.Popen([sys.executable, str(launcher)], env=environment, stdout=log, stderr=log)
    endpoint = runtime / f'orbit-music-app-{os.getuid()}.sock'
    started = time.monotonic()
    try:
        wait_until(endpoint.exists, 5, 'dedicated socket')
        assert time.monotonic() - started < 3, 'Dedicated startup should take less than three seconds'
        duplicate = subprocess.run([sys.executable, str(launcher)], env=environment, timeout=3, stdout=log, stderr=log)
        assert duplicate.returncode == 0 and dedicated.poll() is None
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(endpoint))
            client.sendall(b'present\n')
    finally:
        time.sleep(.3)
        dedicated.terminate()
        try:
            dedicated.wait(timeout=10)
        except subprocess.TimeoutExpired:
            dedicated.kill()
            dedicated.wait()
            raise
        finally:
            log.close()
    assert not endpoint.exists(), 'Exit must remove the dedicated socket'
    print('MUSIC_UI_OK: real mpv, transport, seek, up next, repeat, favourites, lyrics, hide/full player, singleton')

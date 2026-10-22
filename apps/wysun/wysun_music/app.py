"""Composition root and single-instance entry point of Wysun Music."""
from dataclasses import dataclass
import fcntl
import os
from pathlib import Path
import signal
import socket
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .covers import CoverStore
from .library import Library
from .player import Player


@dataclass
class MusicApp:
    library: Library
    covers: CoverStore
    player: Player
    window: object
    mpris: object = None

    def present(self, route='present'):
        """``background`` only makes sure the player runs (shell media widget)."""
        if route == 'present':
            self.window.present()

    def shutdown(self):
        self.window.save_ui()
        self.player.shutdown()
        self.library.store.close()


def build(test=False, *, persist=None, network=None, publish=None):
    """Wire the layers together. ``test`` turns persistence, network and MPRIS
    off; each can be re-enabled on its own (e.g. session tests without network)."""
    from .ui.window import MusicWindow
    persist = not test if persist is None else persist
    network = not test if network is None else network
    publish = not test if publish is None else publish
    library = Library(watch=persist)
    covers = CoverStore(library, network=network)
    player = Player(library, persist=persist)
    window = MusicWindow(library, covers, player, test=test)
    app = MusicApp(library, covers, player, window)
    if publish:
        from . import mpris
        app.mpris = mpris.start(player, covers, present=window.present, quit_app=QApplication.instance().quit)
    return app


def _runtime():
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', str(Path.home() / '.cache/orbit')))
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    return runtime


def _forward(endpoint, route):
    """Hand the request to a running instance; True when one answered."""
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(.3)
            client.connect(str(endpoint))
            client.sendall((route + '\n').encode())
        return True
    except OSError:
        return False


def main(argv=None):
    argv = sys.argv if argv is None else argv
    route = 'background' if '--background' in argv else 'present'
    runtime = _runtime()
    endpoint = runtime / f'orbit-music-app-{os.getuid()}.sock'
    if _forward(endpoint, route):
        return 0
    lock = (runtime / f'orbit-music-app-{os.getuid()}.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    if endpoint.exists():
        if not endpoint.is_socket():
            raise RuntimeError('La ruta del reproductor está ocupada por otro archivo.')
        endpoint.unlink()

    qt = QApplication(['Orbit', '-name', 'Orbit'])
    qt.setStyle('Fusion')
    qt.setApplicationName('Orbit')
    qt.setApplicationDisplayName('Wysun Music')
    qt.setDesktopFileName('orbit-music')
    qt.setQuitOnLastWindowClosed(False)
    from theme_tokens import watch_theme
    watch_theme()
    from local_ipc import LocalSettingsServer
    server = LocalSettingsServer(endpoint, qt)
    music = build()
    server.requested.connect(music.present)
    QTimer.singleShot(0, lambda: music.present(route))

    def finish():
        music.shutdown()
        server.close()

    qt.aboutToQuit.connect(finish)
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: QTimer.singleShot(0, lambda: qt.exit(0)))
    # Python only runs signal handlers between bytecodes: wake the interpreter.
    wake = QTimer(qt, interval=500)
    wake.timeout.connect(lambda: None)
    wake.start()
    return qt.exec()

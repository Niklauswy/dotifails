"""Composition root and single-instance entry point of Wysun Music."""
from dataclasses import dataclass
import os
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from wysun_core.instance import SingleInstance, send
from wysun_core.qt_instance import InstanceNotifier

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


def main(argv=None):
    argv = sys.argv if argv is None else argv
    route = 'background' if '--background' in argv else 'present'
    owner = SingleInstance(f'orbit-music-app-{os.getuid()}')
    if send(owner.endpoint, route.encode(), timeout=.3):
        return 0
    if not owner.claim():
        return 0

    qt = QApplication(['Orbit', '-name', 'Orbit'])
    qt.setStyle('Fusion')
    qt.setApplicationName('Orbit')
    qt.setApplicationDisplayName('Wysun Music')
    qt.setDesktopFileName('orbit-music')
    qt.setQuitOnLastWindowClosed(False)
    from theme_tokens import watch_theme
    watch_theme()
    music = build()
    server = InstanceNotifier(owner, lambda line: music.present(line.decode(errors='replace').strip()), qt,
                              limit=128, timeout=2.0)
    QTimer.singleShot(0, lambda: music.present(route))

    def finish():
        music.shutdown()
        server.close()
        owner.close()

    qt.aboutToQuit.connect(finish)
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: QTimer.singleShot(0, lambda: qt.exit(0)))
    # Python only runs signal handlers between bytecodes: wake the interpreter.
    wake = QTimer(qt, interval=500)
    wake.timeout.connect(lambda: None)
    wake.start()
    return qt.exec()

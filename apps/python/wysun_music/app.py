"""Composition root and single-instance entry point of Wysun Music."""
from dataclasses import dataclass
import os
import signal
import sys

from wysun_core.instance import SingleInstance, release_on_termination, send

UIS = ('widgets', 'qml')


@dataclass
class MusicApp:
    library: object
    covers: object
    player: object
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


def ui_choice():
    """The UI to build: WYSUN_MUSIC_UI (widgets until the QML one replaces it)."""
    choice = os.environ.get('WYSUN_MUSIC_UI', 'widgets')
    return choice if choice in UIS else 'widgets'


def build(test=False, *, persist=None, network=None, publish=None, ui=None):
    """Wire the layers together. ``test`` turns persistence, network and MPRIS
    off; each can be re-enabled on its own (e.g. session tests without network)."""
    from .covers import CoverStore
    from .library import Library
    from .player import Player
    ui = ui or ui_choice()
    if ui == 'qml':
        from .quick.window import QmlMusicWindow as MusicWindow
    else:
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
        from PySide6.QtCore import QCoreApplication
        app.mpris = mpris.start(player, covers, present=window.present, quit_app=QCoreApplication.instance().quit)
    return app


def main(argv=None):
    argv = sys.argv if argv is None else argv
    route = 'background' if '--background' in argv else 'present'
    owner = SingleInstance(f'wysun-music-{os.getuid()}')
    if send(owner.endpoint, route.encode(), timeout=.3):
        return 0
    ui = ui_choice()
    if ui == 'qml':
        # The QML UI runs on the qml-runtime venv (PySide6 bindings on the shell's Qt). The instance check above
        # runs with any Python, so presenting an open window never pays for the re-exec.
        from wysun_qml import bootstrap
        bootstrap.ensure_runtime_python('wysun_music', argv[1:])
        bootstrap.require_qt()
        bootstrap.configure_qt()                # plugins (wayland) before the application exists
    if not owner.claim():
        send(owner.endpoint, route.encode(), timeout=.3, retry=2.0)   # another launch is starting it
        return 0
    release_on_termination(owner)            # until the Qt handlers below take over
    from PySide6.QtCore import QTimer
    from wysun_core.qt_instance import InstanceNotifier
    if ui == 'qml':
        from PySide6.QtGui import QGuiApplication
        qt = QGuiApplication(['wysun-music', '-name', 'wysun-music'])
    else:
        from PySide6.QtWidgets import QApplication
        qt = QApplication(['wysun-music', '-name', 'wysun-music'])
        qt.setStyle('Fusion')
        from wysun_core.qt_theme import watch_theme
        watch_theme()
    qt.setApplicationName('Wysun Music')
    qt.setApplicationDisplayName('Wysun Music')
    qt.setDesktopFileName('wysun-music')
    qt.setQuitOnLastWindowClosed(False)
    music = build(ui=ui)
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

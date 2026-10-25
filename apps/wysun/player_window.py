"""The windows and request server of the Wysun Player process (see player_app.py for the command line)."""
import json
import signal

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow
from shiboken6 import isValid

import media_host
import player_client
from theme_tokens import apply_style, watch_theme
from ui_theme import PALETTE_STYLE
from wysun_media import mpv
from wysun_media.player import MediaPlayer
from wysun_core.qt_instance import InstanceNotifier

WINDOW_LIMIT = 24
GRACE_MS = 400                      # after the last window closes, wait for a request that is already on its way


class PlayerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName('wysunPlayer')
        self.setWindowTitle('Wysun Player')
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.player = MediaPlayer(self, mode='full', backdrop='canvas', remember=True)
        self.player.enable_integration()
        self.setCentralWidget(self.player)
        self.player.titleChanged.connect(lambda name: self.setWindowTitle(f'{name} · Wysun Player' if name else 'Wysun Player'))
        self.player.fullscreenRequested.connect(lambda on: self.showFullScreen() if on else self.showNormal())
        self.player.filesDropped.connect(self.show_files)
        self.player.session.propertyChanged.connect(self._fit_to_video)
        self._fitted = False
        self.resize(960, 600)

    def show_files(self, files, paused=False, start=None):
        if len(files) == 1:
            self.player.open(files[0], paused=paused, start=start, browse='folder')
        else:
            self.player.open_many(files, paused=paused, start=start)

    def _fit_to_video(self, *_):
        """Once, size a floating window to the picture of the first video (never while tiled or fullscreen)."""
        params = self.player.session.props.get('video-params') or {}
        if self._fitted or self.player.kind != 'video' or not params.get('w') or self.isFullScreen() or self.isMaximized():
            return
        self._fitted = True
        screen = self.screen().availableGeometry()
        scale = min(1.0, screen.width() * .8 / params['w'], screen.height() * .8 / params['h'])
        self.resize(max(480, round(params['w'] * scale)), max(300, round(params['h'] * scale)))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            self.player.set_fullscreen(self.isFullScreen(), notify=False)

    def closeEvent(self, event):
        self.player.shutdown()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        control = bool(event.modifiers() & Qt.ControlModifier)
        if event.key() == Qt.Key_O and (control or not event.modifiers()):
            chosen, _ = QFileDialog.getOpenFileNames(self, 'Abrir en Wysun Player')
            if chosen:
                self.show_files(chosen)
        elif event.key() in (Qt.Key_Q, Qt.Key_W) and control:
            self.close()
        else:
            super().keyPressEvent(event)


class RequestServer(QObject):
    """Accepts one JSON line per connection on the user's socket and acknowledges it."""

    received = Signal(dict)

    def __init__(self, owner=None, parent=None):
        super().__init__(parent)
        if owner is None:
            owner = player_client.instance()
            if not owner.claim():
                raise RuntimeError('Wysun Player ya está en ejecución.')
        self.owner = owner
        self.notifier = InstanceNotifier(owner, self._handle, self, limit=player_client.LIMIT, timeout=2.0)

    def _handle(self, line):
        payload = self.parse(line)
        if payload is None:
            return b'no'
        QTimer.singleShot(0, self, lambda: self.received.emit(payload))   # acknowledge first, then open
        return b'ok'

    @staticmethod
    def parse(line):
        try:
            payload = json.loads(line)
        except ValueError:
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get('files', []), list):
            return None
        payload['files'] = [str(f) for f in payload.get('files', [])]
        return payload

    def close(self):
        self.notifier.close()
        self.owner.close()


class Process(QObject):
    """Everything one Wysun Player process owns: its windows, the request socket and the idle exit."""

    def __init__(self, quit_application, owner=None, parent=None):
        super().__init__(parent)
        # Load the native library during process startup, before the first window
        # is mapped. Its first dlopen can take hundreds of milliseconds; opening
        # a video later must not freeze an already visible image window for it.
        # Images remain available on systems without libmpv.
        try:
            mpv.library()
        except RuntimeError:
            pass
        self.windows = []
        self._quit = quit_application
        self.grace = QTimer(self, singleShot=True, interval=GRACE_MS)
        self.grace.timeout.connect(self._maybe_quit)
        self.requests = RequestServer(owner, self)
        self.requests.received.connect(self.show)

    def show(self, payload):
        """Open a window for the request, or choose files first when it names none."""
        files = payload.get('files') or []
        if not files:
            files, _ = QFileDialog.getOpenFileNames(None, 'Abrir en Wysun Player')
            if not files:
                self._finish_soon()
                return None
        if len(self.windows) >= WINDOW_LIMIT:
            self.windows[-1].show_files(files)
            return self.windows[-1]
        window = PlayerWindow()
        self.windows.append(window)
        window.destroyed.connect(lambda *_: self._forget(window))
        window.show_files(files, bool(payload.get('paused')), payload.get('start'))
        # Create the GL child before mapping the window. Adding QOpenGLWidget to an
        # already visible raster window makes Qt recreate its native surface.
        window.show()
        if payload.get('fullscreen'):
            window.player.set_fullscreen(True)
        self.grace.stop()
        return window

    def _forget(self, window):
        if not isValid(self):                   # the application is shutting down and Qt already freed this object
            return
        if window in self.windows:
            self.windows.remove(window)
        self._finish_soon()

    def _finish_soon(self):
        if not self.windows:
            self.grace.start()

    def _maybe_quit(self):
        if not self.windows:                    # a request that arrived meanwhile has opened a window
            self._quit()

    def shutdown(self):
        self.requests.close()
        for window in list(self.windows):
            window.player.shutdown()


def run(first, owner=None):
    """Create the application, show the window for ``first`` and serve requests until the last window closes."""
    qt = QApplication(['wysun-player', '-name', 'wysun-player'])
    qt.setStyle('Fusion')
    qt.setApplicationName('Wysun Player')
    qt.setApplicationDisplayName('Wysun Player')
    qt.setDesktopFileName('wysun-player')
    apply_style(qt, PALETTE_STYLE)
    watch_theme()
    media_host.install()
    process = Process(qt.quit, owner, qt)
    qt.aboutToQuit.connect(process.shutdown)
    qt.aboutToQuit.connect(mpv.wait_closed)
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: QTimer.singleShot(0, qt.quit))
    wake = QTimer(qt, interval=500)             # Python only runs signal handlers while the interpreter is awake
    wake.timeout.connect(lambda: None)
    wake.start()
    QTimer.singleShot(0, lambda: process.show(first))
    return qt.exec()

"""The windows and request server of the Wysun Player process (see player_app.py for the command line)."""
import json
import signal
import socket

from PySide6.QtCore import QObject, QSocketNotifier, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow
from shiboken6 import isValid

import media_host
import player_client
from theme_tokens import apply_style, watch_theme
from ui_theme import PALETTE_STYLE
from wysun_media import mpv
from wysun_media.player import MediaPlayer

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

    def __init__(self, parent=None):
        super().__init__(parent)
        path = player_client.endpoint()
        if path.exists() or path.is_symlink():
            if not path.is_socket():
                raise RuntimeError('La ruta del reproductor está ocupada por otro archivo.')
            path.unlink()
        self.path = path
        self.server = socket.socket(socket.AF_UNIX)
        self.server.bind(str(path))
        path.chmod(0o600)
        self.server.listen(8)
        self.server.setblocking(False)
        self.clients = {}
        self.notifier = QSocketNotifier(self.server.fileno(), QSocketNotifier.Read, self)
        self.notifier.activated.connect(self.accept)

    def accept(self, *_):
        while True:
            try:
                connection, _ = self.server.accept()
            except BlockingIOError:
                return
            connection.setblocking(False)
            notifier = QSocketNotifier(connection.fileno(), QSocketNotifier.Read, self)
            self.clients[connection] = [notifier, b'']
            notifier.activated.connect(lambda *_, c=connection: self.read(c))
            QTimer.singleShot(2000, self, lambda c=connection: self.drop(c))
            self.read(connection)

    def read(self, connection):
        if connection not in self.clients:
            return
        try:
            data = connection.recv(65536)
        except BlockingIOError:
            return
        except OSError:
            self.drop(connection)
            return
        if not data:
            self.drop(connection)
            return
        state = self.clients[connection]
        state[1] += data
        if len(state[1]) > player_client.LIMIT:
            self.drop(connection)
        elif b'\n' in state[1]:
            payload = self.parse(state[1].split(b'\n', 1)[0])
            try:
                connection.send(b'ok\n' if payload is not None else b'no\n')
            except OSError:
                pass
            self.drop(connection)
            if payload is not None:
                self.received.emit(payload)

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

    def drop(self, connection):
        state = self.clients.pop(connection, None)
        if state:
            state[0].setEnabled(False)
            state[0].deleteLater()
            connection.close()

    def close(self):
        self.notifier.setEnabled(False)
        self.server.close()
        if self.path.is_socket():
            self.path.unlink(missing_ok=True)


class Process(QObject):
    """Everything one Wysun Player process owns: its windows, the request socket and the idle exit."""

    def __init__(self, quit_application, parent=None):
        super().__init__(parent)
        self.windows = []
        self._quit = quit_application
        self.grace = QTimer(self, singleShot=True, interval=GRACE_MS)
        self.grace.timeout.connect(self._maybe_quit)
        self.requests = RequestServer(self)
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


def run(first):
    """Create the application, show the window for ``first`` and serve requests until the last window closes."""
    qt = QApplication(['wysun-player', '-name', 'wysun-player'])
    qt.setStyle('Fusion')
    qt.setApplicationName('Wysun Player')
    qt.setApplicationDisplayName('Wysun Player')
    qt.setDesktopFileName('wysun-player')
    apply_style(qt, PALETTE_STYLE)
    watch_theme()
    media_host.install()
    process = Process(qt.quit, qt)
    qt.aboutToQuit.connect(process.shutdown)
    qt.aboutToQuit.connect(mpv.wait_closed)
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: QTimer.singleShot(0, qt.quit))
    wake = QTimer(qt, interval=500)             # Python only runs signal handlers while the interpreter is awake
    wake.timeout.connect(lambda: None)
    wake.start()
    QTimer.singleShot(0, lambda: process.show(first))
    return qt.exec()

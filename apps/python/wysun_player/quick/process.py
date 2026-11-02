"""The Wysun Player process on QML: its windows, the request socket and the exit after the last window.

Every window is a ``Main.qml`` instance with its own context (``player`` = its PlayerController) on one engine.
The process uses the basic render loop: the video item renders from Python, and with the threaded loop the render
thread would need the GIL while the GUI thread holds it waiting for that thread (a deadlock on grab or resize).
"""
import json
import os
import signal

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from shiboken6 import isValid

from wysun_core.qt_instance import InstanceNotifier
from wysun_player import client as player_client

WINDOW_LIMIT = 24
GRACE_MS = 400                      # after the last window closes, wait for a request that is already on its way
FIT_SHARE = .8                      # a first video sizes a floating window to at most this share of the screen


def qml_dir():
    from wysun_qml import bootstrap
    return bootstrap.library_path() / 'player'


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


class PlayerWindow(QObject):
    """One window: Main.qml with its PlayerController."""

    closed = Signal()

    def __init__(self, engine, covers):
        super().__init__()
        from PySide6.QtQml import QQmlComponent, QQmlContext
        from wysun_player.quick.controller import PlayerController
        from wysun_player.quick.video import renderer_name
        self.controller = PlayerController(renderer=renderer_name(), covers=covers)
        self.controller.enable_integration()
        self.context = QQmlContext(engine.rootContext())
        self.context.setContextProperty('player', self.controller)
        # PySide deletes what a component created when the component goes: it lives as long as the window.
        component = self.component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_dir() / 'Main.qml')))
        self.window = component.create(self.context)
        if self.window is None:
            raise RuntimeError('Wysun Player: Main.qml no se pudo cargar: ' +
                               '; '.join(e.toString() for e in component.errors()))
        # The window owns its context, controller and this helper: they go with it, after its items.
        for owned in (self.context, self.controller, self):
            owned.setParent(self.window)
        self.controller.attach_window(self.window)
        self._fitted = False
        self._done = False
        self._choosing = False
        self.controller.session.propertyChanged.connect(self._fit_to_video)
        self.controller.mediaChanged.connect(self._chosen)
        self.controller.closeRequested.connect(self._close_unshown)
        self.window.visibleChanged.connect(self._visible_changed)

    def show_files(self, files, paused=False, start=None):
        self.controller.show_files(files, paused=paused, start=start)

    def choose(self):
        """A request without files: ask for them; the window appears with them, or goes away if none come."""
        self._choosing = True
        self.controller.chooseFiles()

    def _chosen(self):
        if self._choosing and self.controller.source is not None:
            self._choosing = False
            self.present()

    def _close_unshown(self):
        if self.window is not None and not self.window.isVisible() and not self._done:
            self._done = True
            self.controller.shutdown()
            QTimer.singleShot(0, self, self._dispose)

    def present(self, fullscreen=False):
        window = self.window
        if fullscreen and self.controller.kind != 'audio':
            self.controller.set_fullscreen(True)
        else:
            window.show()
        window.raise_()
        window.requestActivate()

    def _fit_to_video(self, name):
        """Once, size a floating window to the picture of the first video (never in full screen or maximized)."""
        from PySide6.QtGui import QWindow
        if name != 'video-params' or self._fitted or self.controller.kind != 'video':
            return
        params = self.controller.session.props.get('video-params') or {}
        window = self.window
        if not params.get('w') or window.visibility() in (QWindow.Visibility.FullScreen, QWindow.Visibility.Maximized):
            return
        self._fitted = True
        screen = window.screen().availableGeometry()
        scale = min(1.0, screen.width() * FIT_SHARE / params['w'], screen.height() * FIT_SHARE / params['h'])
        window.resize(max(480, round(params['w'] * scale)), max(300, round(params['h'] * scale)))

    def _visible_changed(self, visible):
        if visible or self._done:
            return
        self._done = True               # closed (Main.qml released the video and shut the controller down)
        self.controller.shutdown()
        QTimer.singleShot(0, self, self._dispose)

    def _dispose(self):
        window = self.window
        self.closed.emit()
        if window is not None and isValid(window):
            window.deleteLater()        # takes the context, the controller and this helper with it

    def shutdown(self):
        """Application exit: closing runs Main.qml's onClosing (video released before the core)."""
        if self.window is not None and isValid(self.window) and self.window.isVisible():
            self.window.close()
        self.controller.shutdown()


class Process(QObject):
    """Everything one Wysun Player process owns: its windows, the request socket and the idle exit."""

    def __init__(self, quit_application, owner=None, window_factory=None, parent=None):
        super().__init__(parent)
        # Load the native library during process startup, before the first window is mapped: its first dlopen can
        # take hundreds of milliseconds. Images remain available on systems without libmpv.
        from wysun_media import mpv
        try:
            mpv.library()
        except RuntimeError:
            pass
        self.windows = []
        self._quit = quit_application
        self._factory = window_factory
        self.grace = QTimer(self, singleShot=True, interval=GRACE_MS)
        self.grace.timeout.connect(self._maybe_quit)
        self.requests = RequestServer(owner, self)
        self.requests.received.connect(self.show)

    def show(self, payload):
        """Open a window for the request; without files it asks for them with the Files selector."""
        files = payload.get('files') or []
        if files and len(self.windows) >= WINDOW_LIMIT:
            self.windows[-1].show_files(files)
            self.windows[-1].present()
            return self.windows[-1]
        window = self._factory()
        self.windows.append(window)
        window.closed.connect(lambda: self._forget(window))
        if files:
            window.show_files(files, bool(payload.get('paused')), payload.get('start'))
            window.present(bool(payload.get('fullscreen')))
        else:
            window.choose()             # shown when files arrive; closed if the choice is cancelled
        self.grace.stop()
        return window

    def _forget(self, window):
        if not isValid(self):                   # the application is shutting down and Qt already freed this object
            return
        if window in self.windows:
            self.windows.remove(window)
        if not self.windows:
            self.grace.start()

    def _maybe_quit(self):
        if not self.windows:                    # a request that arrived meanwhile has opened a window
            self._quit()

    def shutdown(self):
        self.requests.close()
        for window in list(self.windows):
            window.shutdown()


def run(first, owner=None):
    """Create the application, show the window for ``first`` and serve requests until the last window closes."""
    os.environ['QSG_RENDER_LOOP'] = 'basic'
    from wysun_qml import engine as qml_engine, theme_bridge
    from PySide6.QtGui import QGuiApplication
    from wysun_media import mpv
    from wysun_player.quick import video
    from wysun_player.quick.controller import CoverStore, cover_provider
    qt = QGuiApplication.instance() or QGuiApplication(['wysun-player', '-name', 'wysun-player'])
    qt.setApplicationName('Wysun Player')
    qt.setApplicationDisplayName('Wysun Player')
    qt.setDesktopFileName('wysun-player')
    qt.setQuitOnLastWindowClosed(False)
    _, engine = qml_engine.create_engine('wysun-player')
    qml_engine.collect_on_gui_thread()
    video.register()
    covers = CoverStore()
    engine.addImageProvider('cover', cover_provider(covers))
    bridge = theme_bridge.ThemeBridge(parent=engine)
    engine.rootContext().setContextProperty('bridge', bridge)

    def factory():
        return PlayerWindow(engine, covers)

    process = Process(qt.quit, owner, factory, qt)
    qt.aboutToQuit.connect(process.shutdown)
    qt.aboutToQuit.connect(mpv.wait_closed)
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: QTimer.singleShot(0, qt.quit))
    wake = QTimer(qt, interval=500)             # Python only runs signal handlers while the interpreter is awake
    wake.timeout.connect(lambda: None)
    wake.start()
    QTimer.singleShot(0, lambda: process.show(first))
    return qt.exec()

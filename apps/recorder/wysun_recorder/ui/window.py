"""The settings window of Wysun Recorder: one engine, Main.qml and the bridges it binds to (theme, settings).

``wysun recorder`` with no arguments opens it. One window per user and display: a second launch asks the first to
come forward. It runs on the qml-runtime venv; recording itself (``--start``, ``--prefs``…) never loads Qt.
"""
import signal
import sys
from pathlib import Path


def qml_dir():
    return Path(__file__).resolve().parent / 'qml'


class RecorderSettingsWindow:
    def __init__(self, controller=None, engine=None):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQuick import QQuickWindow  # noqa: F401  (root objects come back as QQuickWindow)
        from wysun_qml import engine as qml_engine, theme_bridge
        from .controller import SettingsController
        if engine is None:
            self.app, self.engine = qml_engine.create_engine('wysun-recorder')
        else:
            self.app, self.engine = None, engine
        QGuiApplication.instance().setDesktopFileName('wysun-recorder')      # the Wayland app_id
        self.bridge = theme_bridge.ThemeBridge(parent=self.engine)
        self.settings = controller or SettingsController(parent=self.engine)
        context = self.engine.rootContext()
        context.setContextProperty('bridge', self.bridge)
        context.setContextProperty('settings', self.settings)
        before = len(self.engine.rootObjects())
        self.engine.load(QUrl.fromLocalFile(str(qml_dir() / 'Main.qml')))
        roots = self.engine.rootObjects()
        if len(roots) <= before:
            raise RuntimeError('Wysun Recorder: Main.qml did not load')
        self.window = roots[-1]

    def present(self):
        from PySide6.QtGui import QCursor, QGuiApplication
        window = self.window
        if not window.isVisible():
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            area = screen.availableGeometry()
            window.resize(min(window.width(), area.width() - 32), min(window.height(), area.height() - 32))
            window.setPosition(area.x() + (area.width() - window.width()) // 2,
                               area.y() + (area.height() - window.height()) // 2)
            window.show()
        # An open window is only brought forward: show() again would let the compositor maximize it.
        window.raise_()
        window.requestActivate()


def serve(instance):
    """Become the window of this user: Qt is imported only now."""
    from wysun_qml import bootstrap
    bootstrap.require_qt()                   # the runtime's Qt before any PySide6 import: it would load another Qt
    bootstrap.configure_qt()
    from PySide6.QtCore import QTimer
    win = RecorderSettingsWindow()
    app = win.app
    app.setApplicationName('Wysun Recorder')
    app.setOrganizationName('Wysun')
    win.present()
    poll = QTimer(app, interval=100)
    poll.timeout.connect(lambda: instance.poll(lambda action: (win.present(), {'state': 'focused'})[1]))
    poll.start()
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: QTimer.singleShot(0, win.window.close))
    wake = QTimer(app, interval=500)          # Python runs signal handlers between bytecodes
    wake.timeout.connect(lambda: None)
    wake.start()
    code = app.exec()
    win.window.deleteLater()
    return code


def run(argv=None, instance=None):
    """Open the settings window, or bring the one already open forward. Returns the exit code."""
    from wysun_qml import bootstrap
    bootstrap.ensure_runtime_python('wysun_recorder', sys.argv[1:] if argv is None else list(argv))
    if instance is None:
        from .instance import Instance
        instance = Instance()
    if not instance.claim():
        try:
            instance.request('focus')
        except RuntimeError:
            return 1
        return 0
    try:
        return serve(instance)
    finally:
        instance.close()

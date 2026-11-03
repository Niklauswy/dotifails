"""The QML window of Wysun Processes: one engine, Main.qml, the theme bridge and the controller (`procs`)."""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (root objects come back as QQuickWindow)

from wysun_qml import bootstrap, engine as qml_engine, theme_bridge
from .controller import ProcessesController


def qml_dir():
    return bootstrap.library_path() / 'processes'


class QmlProcessesWindow:
    def __init__(self, controller=None, engine=None):
        if engine is None:
            self.app, self.engine = qml_engine.create_engine('wysun-processes')
        else:
            self.app, self.engine = None, engine
        QGuiApplication.setDesktopFileName('wysun-processes')     # the Wayland app id, before the window maps
        self.bridge = theme_bridge.ThemeBridge(parent=self.engine)
        if controller is None:
            from wysun_processes.core.services import Services
            from wysun_processes.core.startup import Startup
            services = Services()
            controller = ProcessesController(services=services, startup=Startup(services=services), parent=self.engine)
        self.procs = controller
        context = self.engine.rootContext()
        context.setContextProperty('bridge', self.bridge)
        context.setContextProperty('procs', self.procs)
        before = len(self.engine.rootObjects())
        self.engine.load(QUrl.fromLocalFile(str(qml_dir() / 'Main.qml')))
        roots = self.engine.rootObjects()
        if len(roots) <= before:
            raise RuntimeError('Wysun Processes: Main.qml did not load')
        self.window = roots[-1]

    def present(self):
        window = self.window
        if not window.isVisible():
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            area = screen.availableGeometry()
            window.resize(min(window.width(), area.width() - 32), min(window.height(), area.height() - 32))
        window.show()
        window.raise_()
        window.requestActivate()

    def close(self):
        self.procs.close()

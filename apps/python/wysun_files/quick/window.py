"""The QML window of Wysun Files: one engine, Main.qml, and the bridges it binds to (theme, controller, places)."""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (root objects come back as QQuickWindow)

from wysun_qml import bootstrap, engine as qml_engine, theme_bridge
from .controller import FilesController
from .places import Places


def qml_dir():
    return bootstrap.library_path() / 'files'


class QmlFilesWindow:
    def __init__(self, paths=None, settings=None, thumbnails=True, engine=None):
        if engine is None:
            self.app, self.engine = qml_engine.create_engine('wysun-files')
        else:
            self.app, self.engine = None, engine
        self.bridge = theme_bridge.ThemeBridge(parent=self.engine)
        self.files = FilesController(paths, settings=settings, thumbnails=thumbnails, parent=self.engine)
        self.places = Places(settings=self.files.settings, parent=self.engine)
        self.bridges = {'bridge': self.bridge, 'files': self.files, 'places': self.places}
        self._extend()
        context = self.engine.rootContext()
        for name, value in self.bridges.items():
            context.setContextProperty(name, value)
        before = len(self.engine.rootObjects())
        self.engine.load(QUrl.fromLocalFile(str(qml_dir() / 'Main.qml')))
        roots = self.engine.rootObjects()
        if len(roots) <= before:
            raise RuntimeError('Wysun Files: Main.qml did not load')
        self.window = roots[-1]
        self.files.closeRequested.connect(self.window.close)

    def _extend(self):
        from .operations import Operations
        self.ops = Operations(self.files, parent=self.engine)
        self.files.openRequested.connect(self.ops.open)
        self.bridges['fileOps'] = self.ops
        from .preview import Preview
        self.preview = Preview(parent=self.engine)
        self.bridges['preview'] = self.preview

    def present(self):
        window = self.window
        if not window.isVisible():
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            area = screen.availableGeometry()
            window.resize(min(window.width(), area.width() - 32), min(window.height(), area.height() - 32))
            window.setPosition(area.x() + (area.width() - window.width()) // 2,
                               area.y() + (area.height() - window.height()) // 2)
        window.show()
        window.raise_()
        window.requestActivate()

    def close(self):
        self.ops.close()
        self.preview.close()
        self.places.close()
        self.files.close()

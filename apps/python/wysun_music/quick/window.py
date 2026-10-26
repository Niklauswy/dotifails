"""The QML window of Wysun Music: one engine, Main.qml, and the bridges it binds to."""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (root objects come back as QQuickWindow)

from wysun_qml import bootstrap, engine as qml_engine, theme_bridge
from .controller import MusicController
from .covers import CoverUrls


def qml_dir():
    return bootstrap.library_path() / 'music'


class QmlMusicWindow:
    """What app.MusicApp needs of a window: ``present()``, ``save_ui()``; closing only hides it."""

    def __init__(self, library, covers, player, test=False):
        self.library, self.covers, self.player = library, covers, player
        self.app, self.engine = qml_engine.create_engine('wysun-music')
        self.bridge = theme_bridge.ThemeBridge(parent=self.engine)
        self.urls = CoverUrls(covers, self.engine)
        self.music = MusicController(library, covers, player, self.urls, test=test, parent=self.engine)
        self.music.hideRequested.connect(self.hide)
        self.bridges = {'bridge': self.bridge, 'covers': self.urls, 'music': self.music}
        self._extend()
        context = self.engine.rootContext()
        for name, value in self.bridges.items():
            context.setContextProperty(name, value)
        self.engine.load(QUrl.fromLocalFile(str(qml_dir() / 'Main.qml')))
        roots = self.engine.rootObjects()
        if not roots:
            raise RuntimeError('Wysun Music: Main.qml did not load')
        self.window = roots[-1]

    def _extend(self):
        from .playback import PlayerBridge
        self.playback = PlayerBridge(self.library, self.player, self.urls, self.engine)
        self.bridges['player'] = self.playback
        from .playback import LyricsBridge
        self.lyrics = LyricsBridge(self.library, self.covers.metadata, self.player, self.engine)
        self.bridges['lyrics'] = self.lyrics

    # ----------------------------------------------------------------- window
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

    def hide(self):
        """Closing hides the window; playback keeps going (MPRIS / shell media widget)."""
        self.save_ui()
        self.window.hide()

    def isVisible(self):
        return self.window.isVisible()

    def save_ui(self):
        self.music.save_ui()

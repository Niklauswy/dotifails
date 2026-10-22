"""Main Wysun Music window: sidebar, routed pages, player capsule, full player."""
from PySide6.QtCore import QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QStackedWidget,
                               QVBoxLayout, QWidget)

from theme_tokens import color, on_theme_changed
from ui_motion import WindowMotion, reveal_content
from ui_theme import paint_surface
from .actions import Actions
from .browse import GridPage
from .collection import CollectionPage
from .downloads import DownloadsPage
from .home import HomePage
from .nowplaying import FullPlayer
from .playerbar import PlayerBar
from .search import SearchPage
from .sidebar import Panel, Sidebar
from .style import apply_style, metric, text_font
from .widgets import ElidedLabel, IconButton

HISTORY_LIMIT = 50
RESIZE_MARGIN = 6
SHORTCUTS = '''Espacio: reproducir / pausar (fuera de campos de texto)
Ctrl+← / →: anterior / siguiente
Ctrl+↑ / ↓: volumen ±5 · M: silenciar
Ctrl+S: aleatorio · Ctrl+R: cambiar repetición
Ctrl+Shift+F: Tus me gusta (canción actual)
Ctrl+F o Ctrl+K: buscar · Esc: limpiar / cerrar
Alt+← / →: atrás / adelante
Ctrl+P: Ahora suena · Ctrl+L: letra · Ctrl+Q: cola
Ctrl+N: nueva playlist · Ctrl+O: importar archivos
En la lista: Enter reproducir · F me gusta · Ctrl+Enter artista · Menú: opciones'''


class Toast(QLabel):
    """Short-lived pill message floating over the content."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFont(text_font('small', 600))
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.timer = QTimer(self, singleShot=True, interval=3500)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text):
        self.setText(text)
        self.setAccessibleName(text)
        width = min(self.parentWidget().width() - 48, self.fontMetrics().horizontalAdvance(text) + 40)
        self.setGeometry((self.parentWidget().width() - width) // 2, self.parentWidget().height() - 64, width, 36)
        self.raise_()
        self.show()
        self.timer.start()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('tooltip'))
        painter.drawRoundedRect(QRectF(self.rect()), self.height() / 2, self.height() / 2)
        painter.setPen(color('on_tooltip'))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignCenter,
                         self.fontMetrics().elidedText(self.text(), Qt.ElideRight, self.width() - 24))


class MusicWindow(WindowMotion, QWidget):
    def __init__(self, library, covers, player, test=False):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.library, self.covers, self.player = library, covers, player
        self.test = test
        self.history, self.future = [], []
        self.route = None
        self.panel = None
        self._leaving_search = False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('Wysun Music')
        self.setMinimumSize(900, 600)
        self.resize(1280, 820)
        self.setMouseTracking(True)
        apply_style(self)
        self.actions = Actions(library, covers, player, self)
        self.actions.navigate.connect(self.navigate)
        self.actions.show_player.connect(lambda tab: self.panel != tab and self.toggle_panel(tab))
        self._build()
        self._shortcuts()
        player.message.connect(self.toast)
        on_theme_changed(self.refresh_theme)
        session = library.store.get('ui', {}) if not test else {}
        route = tuple(session.get('route') or ('home',))
        self.navigate(route, remember=False)
        if self.route is None:
            self.navigate(('home',), remember=False)

    # ----------------------------------------------------------------- build
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        # Everything but «Ahora suena» lives in ``frame``: hiding it while the
        # full player covers the window stops every repaint underneath.
        self.frame = QWidget()
        root.addWidget(self.frame)
        outer = QHBoxLayout(self.frame)
        margin = metric('space_s')
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(margin)

        left = QVBoxLayout()
        left.setSpacing(metric('space_s'))
        nav = QHBoxLayout()
        nav.setContentsMargins(metric('space_xs'), metric('space_xs'), 0, 0)
        nav.setSpacing(2)
        close = IconButton('close', 'Ocultar · la música sigue sonando', self.close, size=34)
        self.back = IconButton('chevron_left', 'Atrás · Alt+←', self.go_back, size=34)
        self.forward = IconButton('chevron_right', 'Adelante · Alt+→', self.go_forward, size=34)
        keys = IconButton('keyboard', 'Atajos de teclado · F1', self.show_shortcuts, size=34)
        for button in (close, self.back, self.forward, keys):
            button.setFocusPolicy(Qt.TabFocus)
        nav.addWidget(close)
        nav.addSpacing(metric('space_s'))
        nav.addWidget(self.back)
        nav.addWidget(self.forward)
        nav.addStretch()
        nav.addWidget(keys)
        left.addLayout(nav)
        left.addSpacing(metric('space_s'))
        self.sidebar = Sidebar(self.library, self.covers, self.player)
        self.sidebar.navigate.connect(self.navigate)
        self.sidebar.create_playlist.connect(self.actions.new_playlist)
        self.sidebar.menu_requested.connect(self.actions.collection_menu)
        self.search = self.sidebar.search
        self.search.textChanged.connect(self._search_changed)
        self.search.installEventFilter(self)
        left.addWidget(self.sidebar, 1)
        column = QWidget()
        column.setLayout(left)
        column.setFixedWidth(244)
        outer.addWidget(column)

        right = QVBoxLayout()
        right.setSpacing(margin)
        self.main = Panel()
        main = QVBoxLayout(self.main)
        main.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        self.home = HomePage(self.actions)
        self.collection = CollectionPage(self.actions)
        self.search_page = SearchPage(self.actions)
        self.downloads = DownloadsPage(self.actions)
        self.artists_page = GridPage(self.actions, 'artists')
        self.albums_page = GridPage(self.actions, 'albums')
        self.empty = QLabel('Esta lista ya no existe.')
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setObjectName('muted')
        for page in (self.home, self.collection, self.search_page, self.downloads, self.artists_page,
                     self.albums_page, self.empty):
            self.pages.addWidget(page)
        main.addWidget(self.pages)
        self.notice = Toast(self.main)
        right.addWidget(self.main, 1)
        self.bar = PlayerBar(self.library, self.covers, self.player)
        self.bar.panel_requested.connect(self.toggle_panel)
        self.bar.artist_requested.connect(lambda name: self.navigate(('collection', 'artist:' + name)))
        self.bar.cover_clicked.connect(lambda: self.toggle_panel('now'))
        right.addWidget(self.bar)
        outer.addLayout(right, 1)

        self.side = FullPlayer(self.actions, self)
        self.side.closed.connect(lambda: self.toggle_panel(None))
        self.side.hide()

    def _shortcuts(self):
        bindings = {
            'Ctrl+Left': self.player.previous, 'Ctrl+Right': self.player.next,
            'Ctrl+Up': lambda: self.player.set_volume(min(100, self.player.volume + 5)),
            'Ctrl+Down': lambda: self.player.set_volume(max(0, self.player.volume - 5)),
            'Ctrl+Space': self.player.toggle, 'Media Play': self.player.toggle,
            'Ctrl+S': lambda: self.player.set_shuffle(not self.player.shuffle),
            'Ctrl+R': self.player.cycle_repeat,
            'Ctrl+Shift+F': self._favorite_current,
            'Ctrl+F': self.focus_search, 'Ctrl+K': self.focus_search,
            'Alt+Left': self.go_back, 'Alt+Right': self.go_forward,
            'Ctrl+L': lambda: self.toggle_panel('lyrics'), 'Ctrl+Q': lambda: self.toggle_panel('queue'),
            'Ctrl+P': lambda: self.toggle_panel('now'),
            'Ctrl+N': self.actions.new_playlist, 'Ctrl+O': self.downloads.import_files,
            'F1': self.show_shortcuts, 'Escape': self._escape,
        }
        for keys, callback in bindings.items():
            QShortcut(QKeySequence(keys), self).activated.connect(callback)
        # Application-wide: Space/M must work wherever focus sits inside this window.
        QApplication.instance().installEventFilter(self)

    # ------------------------------------------------------------ navigation
    def navigate(self, route, remember=True):
        route = tuple(route)
        if route == self.route:
            if route[0] == 'search':
                self.focus_search()
            return
        page = self._open(route)
        if page is None:
            return
        if remember and self.route is not None:
            self.history = (self.history + [self.route])[-HISTORY_LIMIT:]
            self.future.clear()
        self.route = route
        self.pages.setCurrentWidget(page)
        self.sidebar.set_route(route)
        self.back.setEnabled(bool(self.history))
        self.forward.setEnabled(bool(self.future))
        if route[0] != 'search' and self.search.text():
            # Not blockSignals: QLineEdit's clear button listens to textChanged too.
            self._leaving_search = True
            self.search.clear()
            self._leaving_search = False
        reveal_content(page, metric('motion_fast'))

    def _open(self, route):
        kind = route[0]
        if kind == 'home':
            return self.home
        if kind == 'search':
            self.search_page.set_query(route[1] if len(route) > 1 else '')
            return self.search_page
        if kind == 'downloads':
            return self.downloads
        if kind == 'artists':
            return self.artists_page
        if kind == 'albums':
            return self.albums_page
        if kind == 'collection':
            return self.collection if self.collection.open(route[1]) else self.empty
        return None

    def go_back(self):
        if self.history:
            self.future.append(self.route)
            route = self.history.pop()
            self.route = None
            self.navigate(route, remember=False)

    def go_forward(self):
        if self.future:
            route = self.future.pop()
            self.history.append(self.route)
            self.route = None
            self.navigate(route, remember=False)

    def _search_changed(self, text):
        if self._leaving_search:
            return
        if self.route and self.route[0] == 'search':
            # Typing refines the same history entry instead of stacking one per key.
            self.route = ('search', text)
            self.search_page.type_query(text)
        else:
            self.navigate(('search', text))

    def focus_search(self):
        if not self.route or self.route[0] != 'search':
            self.navigate(('search', self.search.text()))
        self.search.setFocus()
        self.search.selectAll()

    # ----------------------------------------------------------------- panels
    def toggle_panel(self, key):
        """Open «Ahora suena» on ``key`` (now/lyrics/queue); the same key again closes it."""
        if key is None or (key == self.panel and self.side.isVisible()):
            self.panel = None
            self.frame.show()
            self.side.hide()
            if self.pages.currentWidget() is not None:
                self.pages.currentWidget().setFocus()
        else:
            self.panel = key
            self.side.show_tab(key)
            if not self.side.isVisible():
                self.side.open(covered=self.frame.hide)
        self.bar.set_panel(self.panel)

    # ----------------------------------------------------------------- input
    def eventFilter(self, watched, event):
        if event.type() == QEvent.KeyPress and self.isActiveWindow():
            if watched is self.search and event.key() in (Qt.Key_Down, Qt.Key_Return, Qt.Key_Enter):
                self._enter_results()
                return True
            if self._plain_key(event, watched):
                return True
        return super().eventFilter(watched, event)

    def _plain_key(self, event, watched):
        """Space / M act on playback unless the user is typing."""
        if event.modifiers() not in (Qt.NoModifier, Qt.KeypadModifier):
            return False
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit) or not isinstance(watched, QWidget) or watched.window() is not self:
            return False
        if event.key() == Qt.Key_Space and not hasattr(focus, 'isCheckable'):
            self.player.toggle()
            return True
        if event.key() == Qt.Key_M:
            self.player.toggle_mute()
            return True
        return False

    def _enter_results(self):
        page = self.pages.currentWidget()
        view = getattr(page, 'songs', None) or getattr(page, 'tracks', None)
        if view is not None and view.keys:
            view.setFocus()
            view.setCurrentIndex(view.model().index(0, 0))

    def _escape(self):
        if self.search.hasFocus() and self.search.text():
            self.search.clear()
        elif self.side.isVisible():
            self.toggle_panel(None)
        else:
            self.close()

    def _favorite_current(self):
        if self.player.current:
            self.library.toggle_favorite(self.player.current)

    def show_shortcuts(self):
        QMessageBox.information(self, 'Wysun Music · Teclado', SHORTCUTS)

    def toast(self, message):
        self.notice.show_message(message)

    # --------------------------------------------------------------- window
    def present(self):
        if getattr(self, '_motion_exiting', False):
            self.show()
            self.raise_()
            self.activateWindow()
            return
        screen = QApplication.screenAt(self.cursor().pos()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.resize(min(self.width(), area.width() - 32), min(self.height(), area.height() - 32))
        if not self.isVisible():
            self.move(area.x() + (area.width() - self.width()) // 2, area.y() + (area.height() - self.height()) // 2)
        self.show()
        self.raise_()
        self.activateWindow()
        if not self.search.hasFocus() and self.pages.currentWidget() is not None:
            self.pages.currentWidget().setFocus()

    def closeEvent(self, event):
        """Closing hides the window; playback keeps going (MPRIS / mini player)."""
        event.ignore()
        self.save_ui()
        self.dismiss()

    def save_ui(self):
        if not self.test:
            self.library.store.put('ui', dict(route=list(self.route or ('home',))))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.side.isVisible():
            self.side.setGeometry(self.rect())

    def refresh_theme(self):
        apply_style(self)
        self.side.invalidate()
        for label in self.findChildren(ElidedLabel):
            label.refresh_font()
        self.update()

    def paintEvent(self, _event):
        paint_surface(self)

    def _edges(self, point):
        edges = Qt.Edges()
        if point.x() <= RESIZE_MARGIN:
            edges |= Qt.LeftEdge
        if point.x() >= self.width() - RESIZE_MARGIN:
            edges |= Qt.RightEdge
        if point.y() <= RESIZE_MARGIN:
            edges |= Qt.TopEdge
        if point.y() >= self.height() - RESIZE_MARGIN:
            edges |= Qt.BottomEdge
        return edges

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.windowHandle() is None:
            return
        edges = self._edges(event.position().toPoint())
        if edges:
            self.windowHandle().startSystemResize(edges)
        elif event.position().y() < 72:
            self.windowHandle().startSystemMove()

    def mouseMoveEvent(self, event):
        edges = self._edges(event.position().toPoint())
        horizontal = bool(edges & (Qt.LeftEdge | Qt.RightEdge))
        vertical = bool(edges & (Qt.TopEdge | Qt.BottomEdge))
        if horizontal and vertical:
            diagonal = edges in (Qt.Edges(Qt.LeftEdge | Qt.TopEdge), Qt.Edges(Qt.RightEdge | Qt.BottomEdge))
            self.setCursor(Qt.SizeFDiagCursor if diagonal else Qt.SizeBDiagCursor)
        elif horizontal or vertical:
            self.setCursor(Qt.SizeHorCursor if horizontal else Qt.SizeVerCursor)
        else:
            self.unsetCursor()

"""Wysun Recorder: library, basic player and settings.

Recording itself lives in the shell (``wysun-shell record``): the area picker with
its nodes and strings, the countdown, and the HUD with pause and stop. This window
is where finished recordings are found, played and managed.
"""
import subprocess
import sys

from PySide6.QtCore import QEasingCurve, QEvent, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLineEdit, QMessageBox, QStackedWidget, QVBoxLayout,
                               QWidget)

from .app_kit import (reduced_motion, IconButton, Panel, RESIZE_MARGIN, Button, StateLayer, Toast, apply_style, color, metric,
                      paint_surface, paint_symbol, reveal_content, section_label, text_font, tokens)
from .app_library import LibraryPage
from .app_pages import PlayerPage, SettingsPage
from .tokens import on_theme_changed

from PySide6.QtCore import QRect, Signal
from PySide6.QtWidgets import QLabel, QScrollArea

HISTORY_LIMIT = 50
LIBRARY = (('all', 'video_library', 'Todas', ('library', 'all')),
           ('recent', 'history', 'Recientes', ('library', 'recent')),
           ('trash', 'delete', 'Papelera', ('library', 'trash')))
SHORTCUTS = '''Super+Shift+L: elegir qué grabar, o terminar la grabación
Ctrl+Shift+R: pausar / reanudar · Ctrl+Shift+S: terminar
Ctrl+Shift+A: dibujar sobre la pantalla mientras grabas
Ctrl+L: cambiar entre cuadrícula y lista
En la biblioteca: Enter reproduce · Menú: renombrar, carpeta, papelera
En el reproductor: Espacio pausa · M silencia · ← / → saltan 5 s
Ctrl+F o Ctrl+K: buscar · Alt+← / →: atrás / adelante · Esc: volver'''


class NavItem(QWidget):
    """Sidebar row: symbol + label, pill when active."""

    clicked = Signal()

    def __init__(self, symbol, label, parent=None):
        super().__init__(parent)
        self.symbol, self.label = symbol, label
        self.active = False
        self.layer = StateLayer(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(label)
        self.setFixedHeight(36)

    def set_active(self, active):
        if active != self.active:
            self.active = active
            self.update()

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        if self.layer.amount and not self.active:
            # The selected row's pill belongs to the rail behind it, which glides between rows.
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('tint', round(12 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        pad = metric('space_m')
        paint_symbol(painter, QRect(pad - 4, 0, 28, self.height()), self.symbol, 'accent' if self.active else 'glyph', 21,
                     filled=self.active and self.symbol not in ('history',))
        left = pad + 24 + metric('space_s')
        painter.setFont(text_font('body', 600 if self.active else 450))
        painter.setPen(color('text_strong' if self.active else 'text'))
        painter.drawText(QRect(left, 0, self.width() - left - pad, self.height()), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self.label, Qt.ElideRight, self.width() - left - pad))
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(color('focus'))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)


class Rail(QWidget):
    """Scroll content that paints the selection pill behind the rows and glides it between them."""

    def __init__(self):
        super().__init__()
        self.pill = QRectF()
        self.target = None
        self.anim = QVariantAnimation(self)
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self._step)
        self._from = self._to = QRectF()

    def glide(self, target, animate=True):
        self.target = target
        self.anim.stop()
        if target is None:
            self.pill = QRectF()
            self.update()
            return
        if self.pill.isNull() or not animate or reduced_motion(self.window()) or not self.isVisible():
            self.pill = QRectF(target)
            self.update()
            return
        self._from, self._to = QRectF(self.pill), QRectF(target)
        self.anim.setDuration(tokens()['motion_enter'] + 60)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def _step(self, t):
        t = float(t)
        a, b = self._from, self._to
        self.pill = QRectF(a.left() + (b.left() - a.left()) * t, a.top() + (b.top() - a.top()) * t,
                           a.width() + (b.width() - a.width()) * t, a.height() + (b.height() - a.height()) * t)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.target is not None:
            self.glide(self.target, animate=False)

    def paintEvent(self, _event):
        if self.pill.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('nav_selected'))
        painter.drawRoundedRect(self.pill, min(22, self.pill.height() / 2), min(22, self.pill.height() / 2))


class Storage(QWidget):
    """Free space where the recordings go, as a thin meter (the device row of Wysun Files)."""

    def __init__(self):
        super().__init__()
        self.used, self.caption = 0.0, ''
        self.setFixedHeight(52)
        self.refresh()

    def refresh(self):
        import shutil
        from ..videolibrary import videos_root
        try:
            usage = shutil.disk_usage(videos_root())
            self.used = usage.used / usage.total if usage.total else 0.0
            free = usage.free
            self.caption = f'{free / 1e9:.0f} GB libres' if free >= 1e9 else f'{free / 1e6:.0f} MB libres'
        except OSError:
            self.used, self.caption = 0.0, ''
        self.setToolTip(f'Espacio para grabar · {self.caption}' if self.caption else 'Espacio para grabar')
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pad = metric('space_m')
        paint_symbol(painter, QRect(pad - 4, 0, 28, 30), 'hard_drive', 'glyph', 21, filled=True)
        left = pad + 24 + metric('space_s')
        painter.setFont(text_font('body', 450))
        painter.setPen(color('text'))
        painter.drawText(QRect(left, 5, self.width() - left - pad, 20), Qt.AlignLeft | Qt.AlignVCenter, 'Espacio')
        painter.setFont(text_font('caption'))
        painter.setPen(color('muted'))
        painter.drawText(QRect(left, 5, self.width() - left - pad, 20), Qt.AlignRight | Qt.AlignVCenter, self.caption)
        track = QRectF(left, 33, self.width() - left - pad, 5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('track'))
        painter.drawRoundedRect(track, 2.5, 2.5)
        if self.used:
            painter.setBrush(color('danger' if self.used > .92 else 'accent'))
            painter.drawRoundedRect(QRectF(track.left(), track.top(), max(5, track.width() * self.used), track.height()), 2.5, 2.5)


class SearchField(QLineEdit):
    """Pill search with a painted Material search glyph."""

    def __init__(self):
        super().__init__()
        self.setObjectName('search')
        self.setPlaceholderText('Buscar')
        self.setAccessibleName('Buscar en tus grabaciones')
        self.setToolTip('Buscar · Ctrl+K')
        self.setClearButtonEnabled(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        paint_symbol(painter, QRectF(8, 0, 24, self.height()), 'search', 'muted', 20)


class Sidebar(QWidget):
    navigate = Signal(tuple)
    record = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(metric('space_xs'), 0, 0, 0)
        layout.setSpacing(metric('space_s'))
        self.search = SearchField()
        layout.addWidget(self.search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = self.rail = Rail()
        self.column = QVBoxLayout(content)
        self.column.setContentsMargins(0, 0, metric('space_xs'), metric('space_m'))
        self.column.setSpacing(1)
        new = Button('Nueva grabación', 'fiber_manual_record', 'primary', self.record.emit)
        new.setFixedHeight(40)
        new.setToolTip('Elegir qué grabar · Super+Shift+L')
        self.column.addSpacing(metric('space_s'))
        self.column.addWidget(new)
        self.column.addWidget(section_label('Biblioteca'))
        self.items = {}
        for key, symbol, label, route in LIBRARY:
            item = NavItem(symbol, label)
            item.clicked.connect(lambda route=route: self.navigate.emit(route))
            self.items[key] = (item, route)
            self.column.addWidget(item)
        self.column.addStretch()
        self.storage = Storage()
        self.column.addWidget(self.storage)
        settings = NavItem('settings', 'Ajustes')
        settings.clicked.connect(lambda: self.navigate.emit(('settings',)))
        self.items['settings'] = (settings, ('settings',))
        self.column.addWidget(settings)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def set_route(self, route):
        current = None
        for item, target in self.items.values():
            item.set_active(route == target)
            if route == target:
                current = item
        # Layout may not be done yet on the first call: glide once it is.
        QTimer.singleShot(0, lambda: self.rail.glide(QRectF(current.geometry()) if current else None))


class RecorderWindow(QWidget):
    def __init__(self, library, test=False):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint)
        self.library = library
        self.test = test
        self.history, self.future = [], []
        self.route = None
        self._leaving_search = False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('Wysun Recorder')
        self.setMinimumSize(900, 600)
        self.resize(1180, 760)
        self.setMouseTracking(True)
        apply_style(self)
        self._build()
        self._shortcuts()
        on_theme_changed(self.refresh_theme)
        self.navigate(('library', 'all'), remember=False)

    def _build(self):
        outer = QHBoxLayout(self)
        margin = metric('space_s')
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(margin)
        left = QVBoxLayout()
        left.setSpacing(metric('space_s'))
        nav = QHBoxLayout()
        nav.setContentsMargins(metric('space_xs'), metric('space_xs'), 0, 0)
        nav.setSpacing(2)
        close = IconButton('close', 'Cerrar · las grabaciones en curso siguen', self.close, size=34)
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
        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self.navigate)
        self.sidebar.record.connect(self.record)
        self.search = self.sidebar.search
        self.search.textChanged.connect(self._search_changed)
        left.addWidget(self.sidebar, 1)
        column = QWidget()
        column.setLayout(left)
        column.setFixedWidth(244)
        outer.addWidget(column)

        self.main = Panel()
        main = QVBoxLayout(self.main)
        main.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        self.library_pages = {
            'all': LibraryPage(self.library, 'Grabaciones'),
            'recent': LibraryPage(self.library, 'Recientes', recent=True),
            'trash': LibraryPage(self.library, 'Papelera', trash=True),
        }
        self.player = PlayerPage()
        self.settings = SettingsPage()
        for page in (*self.library_pages.values(), self.player, self.settings):
            self.pages.addWidget(page)
        for page in self.library_pages.values():
            page.play.connect(self.play)
            page.message.connect(self.toast)
            page.view_changed.connect(self._sync_view)
        self.library_pages['all'].record_button.clicked.connect(self.record)
        self.player.closed.connect(self.go_back)
        self.player.message.connect(self.toast)
        self.settings.message.connect(self.toast)
        self.settings.folder_changed.connect(lambda: self.toast('Carpeta cambiada: reinicia el Recorder para verla en todo'))
        main.addWidget(self.pages)
        self.notice = Toast(self.main)
        outer.addWidget(self.main, 1)

    def _shortcuts(self):
        bindings = {'Ctrl+F': self.focus_search, 'Ctrl+K': self.focus_search, 'Alt+Left': self.go_back,
                    'Alt+Right': self.go_forward, 'F1': self.show_shortcuts, 'Escape': self._escape,
                    'Ctrl+N': self.record, 'Ctrl+L': self.toggle_view}
        for keys, callback in bindings.items():
            QShortcut(QKeySequence(keys), self).activated.connect(callback)

    # ------------------------------------------------------------ navigation
    def navigate(self, route, remember=True):
        route = tuple(route)
        if route == self.route:
            return
        if self.route and self.route[0] == 'play':
            self.player.stop()
        if route[0] == 'library':
            page = self.library_pages[route[1]]
            page.set_query(self.search.text())
        elif route[0] == 'play':
            page = self.player
        else:
            page = self.settings
        if remember and self.route is not None and self.route[0] != 'play':
            self.history = (self.history + [self.route])[-HISTORY_LIMIT:]
            self.future.clear()
        self.route = route
        self.pages.setCurrentWidget(page)
        self.sidebar.set_route(route if route[0] != 'play' else (self.history[-1] if self.history else ('library', 'all')))
        self.back.setEnabled(bool(self.history) or route[0] == 'play')
        self.forward.setEnabled(bool(self.future))
        self.search.setEnabled(route[0] == 'library')
        reveal_content(page, metric('motion_fast'))
        page.setFocus()

    def play(self, item):
        previous = self.route
        self.navigate(('play', str(item.video)))
        self._came_from = previous
        self.player.load(item)

    def go_back(self):
        if self.route and self.route[0] == 'play':
            target = getattr(self, '_came_from', None) or ('library', 'all')
            self.route = None
            self.navigate(target, remember=False)
        elif self.history:
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
        if self.route and self.route[0] == 'library':
            self.library_pages[self.route[1]].set_query(text)

    def focus_search(self):
        if self.route and self.route[0] != 'library':
            self.navigate(('library', 'all'))
        self.search.setFocus()
        self.search.selectAll()

    def _sync_view(self, listed):
        for page in self.library_pages.values():
            page.apply_view(listed)

    def toggle_view(self):
        if self.route and self.route[0] == 'library':
            self.library_pages[self.route[1]].toggle_view()

    def _escape(self):
        if self.search.hasFocus() and self.search.text():
            self.search.clear()
        elif self.route and self.route[0] == 'play':
            self.go_back()
        else:
            self.close()

    def record(self):
        """Hand over to the shell's picker; this window steps aside so it is not in the shot."""
        self.hide()
        QTimer.singleShot(260, lambda: subprocess.Popen(['wysun-shell', 'record', 'start'], start_new_session=True,
                                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    def show_shortcuts(self):
        QMessageBox.information(self, 'Wysun Recorder · Teclado', SHORTCUTS)

    def toast(self, message):
        self.notice.show_message(message)

    # ---------------------------------------------------------------- window
    def open_requested(self):
        """Someone asked for a video (a recording that just finished): show it playing."""
        from pathlib import Path
        from ..headless import take_show_request
        from .app_library import Item, describe
        video = take_show_request()
        if video is None:
            return
        target = Path(video).resolve()
        item = None
        for entry in self.library.entries():
            found = describe(entry)
            if found.video is not None and Path(found.video).resolve() == target:
                item = found
                break
        if item is None:
            from ..library import Entry
            item = Item(Entry(target, target.stem, 0, target.stat().st_mtime), target, 'ready')
        self.present()
        self.play(item)

    def present(self):
        screen = QApplication.screenAt(self.cursor().pos()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.resize(min(self.width(), area.width() - 32), min(self.height(), area.height() - 32))
        if not self.isVisible():
            self.move(area.x() + (area.width() - self.width()) // 2, area.y() + (area.height() - self.height()) // 2)
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        self.player.stop()
        event.accept()
        QApplication.instance().quit()

    def refresh_theme(self):
        apply_style(self)
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


def main():
    import os
    from .instance import Instance
    from ..videolibrary import VideoLibrary
    from .tokens import apply_theme
    instance = Instance()
    if not instance.claim():
        try:
            instance.request('focus')
        except RuntimeError:
            return 1
        return 0
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName('Wysun Recorder')
        app.setOrganizationName('Wysun')
        app.setDesktopFileName('wysun-recorder')
        apply_theme(app)
        window = RecorderWindow(VideoLibrary())
        window.present()
        window.open_requested()
        timer = QTimer(window)
        timer.timeout.connect(lambda: instance.poll(lambda action: (window.present(), window.open_requested(), {'state': 'focused'})[2]))
        timer.start(100)
        return app.exec()
    finally:
        instance.close()


if __name__ == '__main__':
    main()

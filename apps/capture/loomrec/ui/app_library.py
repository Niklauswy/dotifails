"""Recording library: a grid of thumbnails with the usual per-recording actions."""
import math
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (QAbstractListModel, QEasingCurve, QEvent, QModelIndex, QObject, QPointF, QRect, QRectF, QRunnable,
                            QSize, Qt, QThreadPool, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QInputDialog, QLabel, QListView, QMenu, QMessageBox,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from ..videolibrary import VideoLibrary, recording_video, finalization_status
from .app_kit import Button, IconButton, StateLayer, clock, color, metric, paint_symbol, reduced_motion, text_font, tokens

ROLE_ENTRY = Qt.UserRole + 1
ROLE_VIDEO = Qt.UserRole + 2
ROLE_STATE = Qt.UserRole + 3      # 'ready' | 'preparing' | 'error'
CARD_WIDTH = 288


class Item:
    """One recording as the grid sees it."""

    def __init__(self, entry, video, state):
        self.entry, self.video, self.state = entry, video, state
        self.title = entry.title
        self.duration = entry.duration
        self.modified = entry.modified


def describe(entry):
    """Playable file and state of a catalogue row (editable projects point at their MP4)."""
    if entry.path.name != 'project.json':
        return Item(entry, entry.path, 'ready')
    try:
        video, _ = recording_video(entry.path)
    except (OSError, ValueError):
        video = None
    if video:
        return Item(entry, video, 'ready')
    try:
        state = finalization_status(entry.path).get('state')
    except (OSError, ValueError):
        state = 'error'
    return Item(entry, None, 'preparing' if state in ('pending', 'running') else 'error')


class Signals(QObject):
    done = Signal(object)


class Job(QRunnable):
    def __init__(self, fn, signals):
        super().__init__()
        self.fn, self.signals = fn, signals

    def run(self):
        try:
            result = self.fn()
        except Exception as exc:
            result = exc
        self.signals.done.emit(result)


class LibraryModel(QAbstractListModel):
    changed = Signal()

    def __init__(self, library, trash=False, recent=False):
        super().__init__()
        self.library, self.trash, self.recent = library, trash, recent
        self.items = []
        self.query = ''
        self.sort = 'date'
        self.born = {}          # video key -> monotonic time it first appeared, for the entrance
        self.arrived = time.monotonic()
        self.thumbs = {}
        self.pending = set()
        self.generation = 0
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self._signals = Signals()
        self._signals.done.connect(self._loaded)

    # ------------------------------------------------------------ data
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self.items[index.row()]
        if role == Qt.DisplayRole:
            return item.title
        if role == ROLE_ENTRY:
            return item
        if role == ROLE_VIDEO:
            return item.video
        if role == ROLE_STATE:
            return item.state
        return None

    def refresh(self):
        self.generation += 1
        generation = self.generation
        query, trash, recent = self.query, self.trash, self.recent

        def work():
            rows = [describe(entry) for entry in self.library.entries(query, trash)]
            if recent:
                cutoff = time.time() - 14 * 86400
                rows = [row for row in rows if row.modified >= cutoff]
            return generation, rows
        self.pool.start(Job(work, self._signals))

    def _loaded(self, result):
        if isinstance(result, Exception):
            return
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], list):
            generation, rows = result
            if generation != self.generation:
                return
            self.beginResetModel()
            self.items = self._sorted(rows)
            now = time.monotonic()
            first = not self.born
            for index, row in enumerate(self.items):
                # New cards rise in one after the other; ones already known stay put.
                if str(row.entry.path) not in self.born:
                    self.born[str(row.entry.path)] = now + (index * .045 if first else 0)
            self.endResetModel()
            for row in rows:
                self._need_thumbnail(row)
            self.changed.emit()
            return
        # a thumbnail finished
        path, image = result
        self.pending.discard(path)
        if image is not None:
            self.thumbs[path] = image
            for row, item in enumerate(self.items):
                if str(item.video) == path:
                    self.dataChanged.emit(self.index(row), self.index(row))

    def _need_thumbnail(self, item):
        if item.video is None or str(item.video) in self.thumbs or str(item.video) in self.pending:
            return
        path = item.video
        self.pending.add(str(path))

        def work():
            try:
                if item.entry.path == path:
                    self.library.enrich(item.entry)
                    item.duration = item.entry.duration
                image = QImage(str(self.library.thumbnail(path)))
                if not item.duration:
                    from ..videolibrary import probe
                    item.duration = probe(path)[0]
                return str(path), (image if not image.isNull() else None)
            except Exception:
                return str(path), None
        self.pool.start(Job(work, self._signals))

    def _sorted(self, rows):
        if self.sort == 'name':
            return sorted(rows, key=lambda r: r.title.casefold())
        if self.sort == 'length':
            return sorted(rows, key=lambda r: r.duration, reverse=True)
        return sorted(rows, key=lambda r: r.modified, reverse=True)

    def set_sort(self, key):
        self.sort = key
        self.beginResetModel()
        self.items = self._sorted(self.items)
        self.endResetModel()

    def set_query(self, text):
        self.query = text
        self.refresh()


def ease(value):
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** 3


class Motion:
    """Per-row hover/selection amounts and entrance progress that the delegates read.

    Rows animate on their own clock; the view repaints only the rows that move.
    """

    def __init__(self, view):
        self.view = view
        self.hover = {}      # row -> 0..1
        self.pop = {}        # row -> time of selection
        self.running = {}
        self.timer = QTimer(view, interval=16)
        self.timer.timeout.connect(self._tick)

    def hover_to(self, row, target):
        if row < 0:
            return
        if reduced_motion(self.view.window()):
            self.hover[row] = float(target)
            self._repaint(row)
            return
        old = self.running.pop(row, None)
        if old:
            old.stop()
        animation = QVariantAnimation(self.view)
        animation.setStartValue(self.hover.get(row, 0.0))
        animation.setEndValue(float(target))
        animation.setDuration(metric('motion_fast') + 60)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.valueChanged.connect(lambda value, row=row: (self.hover.__setitem__(row, float(value)), self._repaint(row)))
        animation.finished.connect(lambda row=row: self.running.pop(row, None))
        self.running[row] = animation
        animation.start()

    def select(self, row):
        if row >= 0 and not reduced_motion(self.view.window()):
            self.pop[row] = time.monotonic()
            self.timer.start()

    def entering(self):
        now = time.monotonic()
        return any(now - born < .6 for born in self.view.model().born.values())

    def _tick(self):
        now = time.monotonic()
        self.pop = {row: t for row, t in self.pop.items() if now - t < .4}
        self.view.viewport().update()
        if not self.pop and not self.entering():
            self.timer.stop()

    def _repaint(self, row):
        self.view.viewport().update(self.view.visualRect(self.view.model().index(row)).adjusted(-12, -12, 12, 12))

    def arrival(self, item):
        """0..1: how far the card has come in."""
        born = self.view.model().born.get(str(item.entry.path), 0)
        return 1.0 if reduced_motion(self.view.window()) else ease((time.monotonic() - born) / .32)

    def selected_scale(self, row):
        t = self.pop.get(row)
        x = 1.0 if t is None else (time.monotonic() - t) / .36
        return 1.0 if x >= 1 else 1 + .04 * math.sin(math.pi * x) * (1 - x * .5)


def thumbnail(painter, model, item, art, radius, zoom=1.0):
    clip = QPainterPath()
    clip.addRoundedRect(art, radius, radius)
    painter.save()
    painter.setClipPath(clip)
    painter.fillRect(art, color('media'))
    image = model.thumbs.get(str(item.video)) if item.video else None
    if image is not None:
        size = (art.size() * zoom).toSize()
        pixmap = QPixmap.fromImage(image).scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(art.toRect(), pixmap, QRect((pixmap.width() - int(art.width())) // 2, (pixmap.height() - int(art.height())) // 2, int(art.width()), int(art.height())))
    else:
        symbol = 'hourglass_top' if item.state == 'preparing' else 'error' if item.state == 'error' else 'videocam'
        paint_symbol(painter, art, symbol, 'muted', 40)
    painter.restore()


def badge(painter, art, text):
    painter.setFont(text_font('caption', 700))
    width = painter.fontMetrics().horizontalAdvance(text) + 14
    box = QRectF(art.right() - width - 8, art.bottom() - 26, width, 20)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color('tooltip'))
    painter.drawRoundedRect(box, 10, 10)
    painter.setPen(color('on_tooltip'))
    painter.drawText(box, Qt.AlignCenter, text)


def play_button(painter, art, amount):
    """Round play button that grows in over the thumbnail while hovering."""
    if amount <= 0.02:
        return
    side = 52 * (.7 + .3 * ease(amount))
    box = QRectF(art.center().x() - side / 2, art.center().y() - side / 2, side, side)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color('accent', round(255 * ease(amount))))
    painter.drawEllipse(box)
    paint_symbol(painter, box, 'play_arrow', color('on_accent', round(255 * ease(amount))), round(side * .6), filled=True)


def info_line(item):
    if item.state == 'preparing':
        return 'Preparando el MP4…'
    if item.state == 'error':
        return 'No se pudo preparar el MP4'
    return datetime.fromtimestamp(item.modified).strftime('%d %b %Y · %H:%M')


class Delegate(QStyledItemDelegate):
    """Card: thumbnail with duration badge, title and date. Lifts on hover, pops when picked."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.motion = None

    def sizeHint(self, option, index):
        return QSize(CARD_WIDTH, round(CARD_WIDTH * 9 / 16) + 72)

    def paint(self, painter, option, index):
        item = index.data(ROLE_ENTRY)
        row = index.row()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        radius = tokens()['radius_m']
        hover = self.motion.hover.get(row, 0.0) if self.motion else 0.0
        arrival = self.motion.arrival(item) if self.motion else 1.0
        scale = (self.motion.selected_scale(row) if self.motion else 1.0) * (1 + .02 * hover)
        selected = bool(option.state & QStyle.State_Selected)
        card = QRectF(option.rect).adjusted(6, 6, -6, -6)
        center = card.center() + QPointF(0, (1 - arrival) * 18 - hover * 3)
        painter.setOpacity(arrival)
        painter.translate(center)
        painter.scale(scale, scale)
        painter.translate(-card.center())
        if selected or hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('nav_selected') if selected else color('tint', round(14 * hover)))
            painter.drawRoundedRect(card.adjusted(-4, -4, 4, 4), radius + 4, radius + 4)
        art = QRectF(card.left(), card.top(), card.width(), card.width() * 9 / 16)
        thumbnail(painter, self.model, item, art, radius, 1 + .05 * hover)
        if item.duration and item.state == 'ready':
            badge(painter, art, clock(item.duration))
        if item.video is not None:
            play_button(painter, art, hover)
        text = QRectF(card.left() + 2, art.bottom() + 8, card.width() - 4, 22)
        painter.setFont(text_font('body', 600))
        painter.setPen(color('text_strong'))
        painter.drawText(text, Qt.AlignLeft | Qt.AlignVCenter, painter.fontMetrics().elidedText(item.title, Qt.ElideRight, int(text.width())))
        painter.setFont(text_font('small'))
        painter.setPen(color('danger' if item.state == 'error' else 'muted'))
        painter.drawText(QRectF(text.left(), text.bottom() + 2, text.width(), 20), Qt.AlignLeft | Qt.AlignVCenter, info_line(item))
        if option.state & QStyle.State_HasFocus:
            painter.setPen(color('focus'))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(card.adjusted(-4, -4, 4, 4), radius + 4, radius + 4)
        painter.restore()


class RowDelegate(QStyledItemDelegate):
    """List row: small thumbnail, title and date, length at the right."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.motion = None

    def sizeHint(self, option, index):
        return QSize(option.rect.width() or 600, 76)

    def paint(self, painter, option, index):
        item = index.data(ROLE_ENTRY)
        row = index.row()
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        hover = self.motion.hover.get(row, 0.0) if self.motion else 0.0
        arrival = self.motion.arrival(item) if self.motion else 1.0
        selected = bool(option.state & QStyle.State_Selected)
        box = QRectF(option.rect).adjusted(4, 3, -4, -3)
        painter.setOpacity(arrival)
        painter.translate((1 - arrival) * 28, 0)   # rows come in from the side, like Files
        painter.translate(hover * 2, 0)
        if selected or hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('nav_selected') if selected else color('tint', round(14 * hover)))
            painter.drawRoundedRect(box, box.height() / 2.4, box.height() / 2.4)
        art = QRectF(box.left() + 8, box.top() + 7, 96, 54)
        thumbnail(painter, self.model, item, art, tokens()['radius_s'], 1 + .05 * hover)
        if item.video is not None:
            play_button(painter, art, hover * .9)
        left = art.right() + 14
        painter.setFont(text_font('body', 600))
        painter.setPen(color('text_strong'))
        right = box.right() - 72
        painter.drawText(QRectF(left, box.top() + 14, right - left, 22), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(item.title, Qt.ElideRight, int(right - left)))
        painter.setFont(text_font('small'))
        painter.setPen(color('danger' if item.state == 'error' else 'muted'))
        painter.drawText(QRectF(left, box.top() + 36, right - left, 20), Qt.AlignLeft | Qt.AlignVCenter, info_line(item))
        if item.duration and item.state == 'ready':
            painter.setFont(text_font('small', 600))
            painter.setPen(color('muted'))
            painter.drawText(QRectF(box.right() - 70, box.top(), 58, box.height()), Qt.AlignRight | Qt.AlignVCenter, clock(item.duration))
        if option.state & QStyle.State_HasFocus:
            painter.setPen(color('focus'))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(box, box.height() / 2.4, box.height() / 2.4)
        painter.restore()


class Grid(QListView):
    activatedItem = Signal(object)
    menuRequested = Signal(object, object)

    def __init__(self, model):
        super().__init__()
        self.setModel(model)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setSpacing(2)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setFrameShape(QListView.NoFrame)
        self.card, self.rowed = Delegate(model, self), RowDelegate(model, self)
        self.motion = Motion(self)
        self.card.motion = self.rowed.motion = self.motion
        self.setItemDelegate(self.card)
        self.hovered = -1
        self.setAccessibleName('Grabaciones')
        self.doubleClicked.connect(lambda index: self.activatedItem.emit(index.data(ROLE_ENTRY)))
        self.clicked.connect(lambda index: self.motion.select(index.row()))
        model.modelReset.connect(self._reset)
        model.modelReset.connect(self.motion.timer.start)

    def _reset(self):
        self.motion.hover.clear()
        self.hovered = -1

    def set_list(self, listed):
        """Cards in a grid, or full-width rows."""
        self.setItemDelegate(self.rowed if listed else self.card)
        self.setViewMode(QListView.ListMode if listed else QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setSpacing(0 if listed else 2)
        self.setUniformItemSizes(True)
        self.scheduleDelayedItemsLayout()
        self.motion.timer.start()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        row = self.indexAt(event.pos()).row()
        if row != self.hovered:
            self.motion.hover_to(self.hovered, 0.0)
            self.hovered = row
            self.motion.hover_to(row, 1.0)
        self.setCursor(Qt.PointingHandCursor if row >= 0 else Qt.ArrowCursor)

    def leaveEvent(self, event):
        self.motion.hover_to(self.hovered, 0.0)
        self.hovered = -1
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self.currentIndex().isValid():
            self.activatedItem.emit(self.currentIndex().data(ROLE_ENTRY))
        else:
            super().keyPressEvent(event)
            self.motion.select(self.currentIndex().row())

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if index.isValid():
            self.setCurrentIndex(index)
            self.motion.select(index.row())
            self.menuRequested.emit(index.data(ROLE_ENTRY), event.globalPos())


class Empty(QWidget):
    def __init__(self, symbol, title, hint):
        super().__init__()
        self.symbol = symbol
        column = QVBoxLayout(self)
        column.addStretch(2)
        self.title = QLabel(title)
        self.title.setObjectName('subheading')
        self.title.setAlignment(Qt.AlignCenter)
        self.hint = QLabel(hint)
        self.hint.setObjectName('muted')
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        column.addSpacing(72)
        column.addWidget(self.title)
        column.addWidget(self.hint)
        self.action = None
        self.holder = QHBoxLayout()
        column.addLayout(self.holder)
        column.addStretch(3)
        self.phase = 0.0
        self.drift = QTimer(self, interval=33)
        self.drift.timeout.connect(self._drift)

    def showEvent(self, event):
        super().showEvent(event)
        if not reduced_motion(self.window()):
            self.drift.start()

    def hideEvent(self, event):
        self.drift.stop()
        super().hideEvent(event)

    def _drift(self):
        self.phase += .06
        self.update()

    def add_action(self, button):
        self.holder.addStretch()
        self.holder.addWidget(button)
        self.holder.addStretch()

    def paintEvent(self, _event):
        painter = QPainter(self)
        paint_symbol(painter, QRectF(self.width() / 2 - 40, self.height() * .30 + math.sin(self.phase) * 5, 80, 80), self.symbol, 'muted', 64)


class LibraryPage(QWidget):
    """Header, then grid or an empty state; the same page serves Todas, Recientes and Papelera."""

    play = Signal(object)
    message = Signal(str)
    view_changed = Signal(bool)

    def __init__(self, library, title, trash=False, recent=False):
        super().__init__()
        self.library, self.trash = library, trash
        self.model = LibraryModel(library, trash, recent)
        column = QVBoxLayout(self)
        margin = metric('space_xl')
        column.setContentsMargins(margin, margin, margin, 0)
        head = QHBoxLayout()
        self.heading = QLabel(title)
        self.heading.setObjectName('heading')
        self.count = QLabel('')
        self.count.setObjectName('muted')
        head.addWidget(self.heading)
        head.addSpacing(metric('space_m'))
        head.addWidget(self.count, 0, Qt.AlignBottom)
        head.addStretch()
        from ..videolibrary import preferences
        saved = preferences()
        self.listed = saved.get('library_view') == 'list'
        self.sort_names = (('date', 'Más recientes'), ('name', 'Nombre'), ('length', 'Duración'))
        self.model.sort = saved.get('library_sort', 'date') if saved.get('library_sort') in dict(self.sort_names) else 'date'
        self.sorter = IconButton('sort', 'Ordenar', self.sort_menu, size=34)
        self.layout_button = IconButton('view_list' if not self.listed else 'grid_view', 'Cambiar vista · Ctrl+L', self.toggle_view, size=34)
        head.addWidget(self.sorter)
        head.addWidget(self.layout_button)
        self.trash_button = None
        if trash:
            self.trash_button = Button('Vaciar papelera', 'delete_forever', 'tonal', self.empty_trash)
            head.addWidget(self.trash_button)
        column.addLayout(head)
        column.addSpacing(metric('space_s'))
        self.grid = Grid(self.model)
        self.grid.activatedItem.connect(self.open)
        self.grid.menuRequested.connect(self.menu)
        if trash:
            self.empty = Empty('delete', 'La papelera está vacía', 'Lo que elimines de la biblioteca aparece aquí y se puede restaurar.')
        elif recent:
            self.empty = Empty('history', 'Nada reciente', 'Aquí aparecen las grabaciones de las últimas dos semanas.')
        else:
            self.empty = Empty('video_library', 'Todavía no hay grabaciones', 'Pulsa Super+Shift+L, elige qué grabar y tus videos aparecerán aquí.')
            self.record_button = Button('Nueva grabación', 'fiber_manual_record', 'primary')
            self.empty.add_action(self.record_button)
        column.addWidget(self.grid, 1)
        column.addWidget(self.empty, 1)
        self.grid.set_list(self.listed)
        self.model.changed.connect(self._sync)
        self.model.modelReset.connect(self._sync)
        self.timer = QTimer(self, interval=3000)
        self.timer.timeout.connect(self.model.refresh)
        self._sync()

    def _sync(self):
        total = self.model.rowCount()
        self.grid.setVisible(total > 0)
        self.empty.setVisible(total == 0)
        self.count.setText('' if total == 0 else f'{total} video' if total == 1 else f'{total} videos')
        if self.trash_button:
            self.trash_button.setEnabled(total > 0)
        # While a recording is still being prepared, keep looking.
        waiting = any(item.state == 'preparing' for item in self.model.items)
        if waiting and self.isVisible():
            self.timer.start()
        else:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.model.refresh()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def set_query(self, text):
        self.model.set_query(text)

    def sort_menu(self):
        menu = QMenu(self)
        for key, name in self.sort_names:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(self.model.sort == key)
            action.triggered.connect(lambda _=False, key=key: self.set_sort(key))
        menu.exec(self.sorter.mapToGlobal(self.sorter.rect().bottomLeft()))

    def set_sort(self, key):
        from ..videolibrary import save_preferences
        self.model.set_sort(key)
        save_preferences(library_sort=key)

    def toggle_view(self):
        from ..videolibrary import save_preferences
        save_preferences(library_view='grid' if self.listed else 'list')
        self.view_changed.emit(not self.listed)

    def apply_view(self, listed):
        self.listed = listed
        self.layout_button.set_symbol('grid_view' if listed else 'view_list')
        self.grid.set_list(listed)

    # --------------------------------------------------------- actions
    def open(self, item):
        if self.trash:
            return
        if item.video is None:
            self.message.emit('Este video aún se está preparando.' if item.state == 'preparing' else 'No se encontró el video de esta grabación.')
            return
        self.play.emit(item)

    def menu(self, item, position):
        menu = QMenu(self)
        if self.trash:
            menu.addAction('Restaurar', lambda: self._run(lambda: self.library.restore(item.entry.path), 'Grabación restaurada'))
            menu.addAction('Eliminar para siempre…', lambda: self.erase(item))
        else:
            play = menu.addAction('Reproducir', lambda: self.open(item))
            play.setEnabled(item.video is not None)
            menu.addAction('Renombrar…', lambda: self.rename(item))
            menu.addSeparator()
            folder = menu.addAction('Mostrar en la carpeta', lambda: self.reveal(item))
            folder.setEnabled(item.video is not None)
            copy = menu.addAction('Copiar ruta', lambda: self.copy_path(item))
            copy.setEnabled(item.video is not None)
            menu.addSeparator()
            menu.addAction('Mover a la papelera', lambda: self._run(lambda: self.library.delete(item.entry.path), 'Movida a la papelera'))
        menu.exec(position)

    def _run(self, action, success):
        try:
            action()
        except Exception as exc:
            self.message.emit(str(exc))
            return
        self.message.emit(success)
        self.model.refresh()

    def rename(self, item):
        title, accepted = QInputDialog.getText(self, 'Renombrar grabación', 'Título', text=item.title)
        if accepted and title.strip():
            self._run(lambda: self.library.rename(item.entry.path, title), 'Renombrada')

    def reveal(self, item):
        subprocess.Popen(['xdg-open', str(item.video.parent)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def copy_path(self, item):
        QGuiApplication.clipboard().setText(str(item.video))
        self.message.emit('Ruta copiada')

    def erase(self, item):
        if QMessageBox.question(self, 'Eliminar para siempre', f'«{item.title}» se borrará sin posibilidad de recuperarla.') != QMessageBox.Yes:
            return
        directory = item.entry.path.parent
        self._run(lambda: shutil.rmtree(directory), 'Eliminada')

    def empty_trash(self):
        if QMessageBox.question(self, 'Vaciar papelera', 'Todo lo que hay en la papelera se borrará para siempre.') != QMessageBox.Yes:
            return
        for item in list(self.model.items):
            shutil.rmtree(item.entry.path.parent, ignore_errors=True)
        self.message.emit('Papelera vaciada')
        self.model.refresh()

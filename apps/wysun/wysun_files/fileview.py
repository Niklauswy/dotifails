"""The file area: one painted list view with a grid and a list presentation.

Tiles are squircles tinted by the file kind (theme category tokens), images show
their thumbnail, selection is a tonal container with a check badge and hover is
an animated state layer. Folder changes replay a short staggered entrance.
"""
from functools import lru_cache
import os
import time

from PySide6.QtCore import QEvent, QModelIndex, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QTextLayout, QTextOption
from PySide6.QtWidgets import QAbstractItemView, QListView, QStyledItemDelegate, QWidget

from theme_tokens import color, tokens
from ui_motion import reduced_motion
from .kinds import describe
from .tiles import paint_icon
from .kit import clip_pixmap, metric, paint_symbol, squircle, text_font
from .model import COLUMNS, DATE, KIND, NAME, SIZE

GRID_MIN = 132
GRID_HEIGHT = 150
ROW_HEIGHT = 54
HEADER_HEIGHT = 34
ENTRANCE_ROWS = 36


@lru_cache(maxsize=512)
def _wrap(text, family, pixels, weight, width, lines):
    font = QFont(family)
    font.setPixelSize(pixels)
    font.setWeight(QFont.Weight(weight))
    layout = QTextLayout(text, font)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
    layout.setTextOption(option)
    spans = []
    layout.beginLayout()
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(width)
        spans.append((line.textStart(), line.textLength()))
    layout.endLayout()
    from PySide6.QtGui import QFontMetrics
    metrics = QFontMetrics(font)
    out = [text[a:a + n].rstrip() for a, n in spans[:lines]]
    if len(spans) > lines:
        out[-1] = metrics.elidedText(text[spans[lines - 1][0]:], Qt.ElideMiddle, width)
    return tuple(out)


def wrapped(text, font, width, lines):
    return _wrap(text, font.family(), font.pixelSize(), int(font.weight()), max(8, int(width)), lines)


def list_columns(width):
    """Right-aligned columns shared by the rows and their header: {key: (x, w)}."""
    columns = {}
    right = width - metric('space_l')
    for key, size in (('size', 86), ('date', 150), ('kind', 150)):
        if key == 'kind' and width < 760 or key == 'date' and width < 540:
            continue
        columns[key] = (right - size, size)
        right -= size + metric('space_s')
    return columns


class Hover:
    """Per-row hover amount (0..1) easing with a light timer; instant when motion is reduced."""

    def __init__(self, widget):
        self.widget = widget
        self.amounts = {}
        self.targets = {}
        self.timer = QTimer(widget, interval=16)
        self.timer.timeout.connect(self._step)

    def amount(self, key):
        return self.amounts.get(key, 0.0)

    def point(self, key, target):
        if self.targets.get(key, 0.0) == target:
            return
        self.targets[key] = target
        if reduced_motion(self.widget.window()):
            self.amounts[key] = target
            self.widget.viewport().update()
            return
        self.timer.start()

    def clear(self):
        self.amounts.clear()
        self.targets.clear()
        self.timer.stop()

    def _step(self):
        moving = False
        for key, target in list(self.targets.items()):
            value = self.amounts.get(key, 0.0)
            value += (target - value) * .32
            if abs(target - value) < .02:
                value = target
                if not target:
                    self.targets.pop(key)
                    self.amounts.pop(key, None)
                    continue
            else:
                moving = True
            self.amounts[key] = value
        self.widget.viewport().update()
        if not moving:
            self.timer.stop()


class FileDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        view = option.widget
        if view is not None and view.mode == 'grid':
            return view.gridSize()
        return QSize(option.rect.width(), ROW_HEIGHT)

    # ------------------------------------------------------------------ paint
    def paint(self, painter, option, index):
        view = option.widget
        model = index.model()
        path = model.filePath(index)
        is_dir = model.isDir(index)
        selected = bool(option.state & option.state.State_Selected)
        hover = view.hover.amount(path)
        progress, shift, slide = view.entrance(index.row())
        if not progress:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(progress * (.5 if view.is_cut(path) else .62 if model.fileName(index).startswith('.') else 1))
        painter.translate(slide, shift)
        pop = view.pop_scale(path)
        if pop != 1.0:
            center = QRectF(option.rect).center()
            painter.translate(center)
            painter.scale(pop, pop)
            painter.translate(-center)
        if view.mode == 'grid':
            self._grid(painter, option, view, model, index, path, is_dir, selected, hover)
        else:
            self._row(painter, option, view, model, index, path, is_dir, selected, hover)
        painter.restore()

    def _container(self, painter, rect, radius, selected, hover, focus):
        if selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('selection'))
            painter.drawRoundedRect(rect, radius, radius)
        if hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('tint', round(14 * hover)))
            painter.drawRoundedRect(rect, radius, radius)
        if focus:
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)

    def tile(self, painter, rect, view, model, index, path, is_dir, selected, hover=0.0):
        """Kind-specific hand-painted icon (see ``tiles``)."""
        paint_icon(painter, rect, path, is_dir, view.model_thumbnail(index), hover, selected)

    def _grid(self, painter, option, view, model, index, path, is_dir, selected, hover):
        card = QRectF(option.rect).adjusted(5, 4, -5, -4)
        radius = tokens()['radius_l'] * .8
        focus = bool(option.state & option.state.State_HasFocus) and view.keyboard and view.window().isActiveWindow()
        self._container(painter, card, radius, selected, hover, focus)
        side = min(card.width() - 16, 92)
        tile = QRectF(card.center().x() - side / 2, card.top() + 10, side, side * .8)
        tile.translate(0, -hover * 1.5)
        self.tile(painter, tile, view, model, index, path, is_dir, selected, hover)
        if selected:
            badge = QRectF(tile.left() + 5, tile.top() + 5, 20, 20)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('accent'))
            painter.drawEllipse(badge)
            paint_symbol(painter, badge, 'check', 'on_accent', 15)
        font = text_font('small', 600 if selected else 500)
        painter.setFont(font)
        painter.setPen(color('text_strong' if selected else 'text'))
        lines = wrapped(model.fileName(index), font, card.width() - 12, 2)
        top = tile.bottom() + 8
        step = painter.fontMetrics().height()
        for number, line in enumerate(lines):
            painter.drawText(QRectF(card.left() + 6, top + number * step, card.width() - 12, step), Qt.AlignHCenter | Qt.AlignVCenter, line)
        meta = model.size_text(index)
        if meta and len(lines) < 2:
            painter.setFont(text_font('caption', 400))
            painter.setPen(color('muted'))
            painter.drawText(QRectF(card.left() + 6, top + step, card.width() - 12, step), Qt.AlignHCenter | Qt.AlignVCenter, meta)

    def _row(self, painter, option, view, model, index, path, is_dir, selected, hover):
        card = QRectF(option.rect).adjusted(4, 2, -4, -2)
        radius = card.height() / 2.6
        focus = bool(option.state & option.state.State_HasFocus) and view.keyboard and view.window().isActiveWindow()
        self._container(painter, card, radius, selected, hover, focus)
        pad = metric('space_m')
        tile = QRectF(card.left() + pad - 2, card.center().y() - 18, 36, 36)
        self.tile(painter, tile, view, model, index, path, is_dir, selected, hover)
        columns = list_columns(option.rect.width())
        text_left = tile.right() + metric('space_m')
        text_right = min([x for x, _w in columns.values()] + [option.rect.width() - pad]) - metric('space_m') + option.rect.left()
        name_font = text_font('body', 600 if is_dir or selected else 450)
        painter.setFont(name_font)
        painter.setPen(color('text_strong' if selected else 'text'))
        name = painter.fontMetrics().elidedText(model.fileName(index), Qt.ElideMiddle, int(text_right - text_left - option.rect.left()))
        painter.drawText(QRectF(option.rect.left() + text_left, card.top(), text_right - text_left - option.rect.left(), card.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, name)
        painter.setFont(text_font('small', 400))
        painter.setPen(color('muted'))
        for key, (x, width) in columns.items():
            value = {'date': model.lastModified(index).toString('d MMM yyyy · HH:mm'),
                     'size': model.size_text(index) or '—', 'kind': describe(path, is_dir)[2]}[key]
            align = Qt.AlignRight if key == 'size' else Qt.AlignLeft
            painter.drawText(QRectF(option.rect.left() + x, card.top(), width, card.height()), align | Qt.AlignVCenter,
                             painter.fontMetrics().elidedText(value, Qt.ElideRight, width))


class FileView(QListView):
    """List/grid presentation of a ``FileModel``; see the module docstring."""

    context_requested = Signal(object)
    up_requested = Signal()
    type_requested = Signal(str)
    mode_changed = Signal(str)

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.mode = 'grid'
        self.hover = Hover(self)
        self.cut = set()
        self.message = ''
        self.symbol = 'folder_open'
        self._hover_key = None
        self.keyboard = False
        self._entrance = None
        self._direction = 0
        self.pops = {}
        self.loading = False
        self.phase = 0.0
        self._entrance_timer = QTimer(self, interval=16)
        self._entrance_timer.timeout.connect(self._tick_entrance)
        self.setModel(model)
        self.setItemDelegate(FileDelegate(self))
        self.selectionModel().selectionChanged.connect(self.mark_selected)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda point: self.context_requested.emit(self.viewport().mapToGlobal(point)))
        self.setFrameShape(QListView.NoFrame)
        self.setProperty('wysunKind', 'files')
        self.set_mode('grid')

    # ---------------------------------------------------------------- modes
    def set_mode(self, mode):
        self.mode = mode
        grid = mode == 'grid'
        self.setViewMode(QListView.IconMode if grid else QListView.ListMode)
        self.setWrapping(grid)
        self.setFlow(QListView.LeftToRight if grid else QListView.TopToBottom)
        self.setSpacing(0)
        self.setWordWrap(False)
        self.setGridSize(QSize(1, 1))
        self._fit()
        self.hover.clear()
        self.viewport().update()
        self.mode_changed.emit(mode)

    def _fit(self):
        """Cell size from the widget width minus a fixed scrollbar lane.

        Using the viewport width here made the layout chase its own scrollbar (it
        appears, the viewport narrows, the columns change, it disappears...) and spin the CPU.
        """
        if self.mode == 'grid':
            usable = max(GRID_MIN, self.width() - 22)
            columns = max(1, usable // GRID_MIN)
            size = QSize(usable // columns, GRID_HEIGHT)
        else:
            size = QSize()
        if size != self.gridSize():
            self.setGridSize(size)
            self.doItemsLayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def model_thumbnail(self, index):
        return self.model().thumbnail(index) if hasattr(self.model(), 'thumbnail') else None

    def is_cut(self, path):
        return path in self.cut

    def set_cut(self, paths):
        self.cut = set(paths)
        self.viewport().update()

    # ------------------------------------------------------------- entrance
    def start_entrance(self, direction=0):
        """Replay the entrance; ``direction`` +1 slides in from the right (going in), -1 from the left (going up)."""
        if reduced_motion(self.window()):
            self._entrance = None
            return
        self._direction = direction
        self._entrance = time.monotonic()
        self._entrance_timer.start()

    def _tick_entrance(self):
        now = time.monotonic()
        if self._entrance is not None and now - self._entrance > .26 + ENTRANCE_ROWS * .016 + .05:
            self._entrance = None
        self.pops = {path: t0 for path, t0 in self.pops.items() if now - t0 < .32}
        self.phase = (self.phase + .06) % 6.2832
        if self._entrance is None and not self.pops and not self.loading:
            self._entrance_timer.stop()
        self.viewport().update()

    def entrance(self, row):
        """(opacity, vertical shift, horizontal slide) of a row in the folder-change entrance."""
        if self._entrance is None or row >= ENTRANCE_ROWS:
            return 1.0, 0.0, 0.0
        t = (time.monotonic() - self._entrance - row * .016) / .26
        t = max(0.0, min(1.0, t))
        eased = 1 - (1 - t) ** 3
        return eased, (1 - eased) * 8, (1 - eased) * 26 * self._direction

    # ------------------------------------------------------------ selection pop
    def mark_selected(self, selected, deselected):
        if reduced_motion(self.window()):
            return
        now = time.monotonic()
        model = self.model()
        for index in selected.indexes():
            if index.column() == 0:
                self.pops[model.filePath(index)] = now
        if self.pops:
            self._entrance_timer.start()

    def pop_scale(self, path):
        """1.0 at rest; a short overshoot when an item was just selected (M3 expressive spring)."""
        t0 = self.pops.get(path)
        if t0 is None:
            return 1.0
        t = min(1.0, (time.monotonic() - t0) / .3)
        c1, c3 = 1.9, 2.9
        back = 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
        return .93 + .07 * back

    def set_loading(self, loading):
        if loading != self.loading:
            self.loading = loading
            if loading and not reduced_motion(self.window()):
                self._entrance_timer.start()
            self.viewport().update()

    def keyPressEvent(self, event):
        self.keyboard = True
        key, text = event.key(), event.text()
        plain = not event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)
        if plain and key == Qt.Key_Backspace or plain and key == Qt.Key_Left and self.mode == 'list':
            self.up_requested.emit()
        elif plain and key == Qt.Key_Right and self.mode == 'list' and self.currentIndex().isValid():
            self.doubleClicked.emit(self.currentIndex())
        elif plain and text and text.isprintable() and text != ' ':
            self.type_requested.emit(text)       # typing starts a filter, like the launcher
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self.keyboard = False
        super().mousePressEvent(event)

    # --------------------------------------------------------------- hover
    def mouseMoveEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        key = self.model().filePath(index) if index.isValid() else None
        if key != self._hover_key:
            if self._hover_key:
                self.hover.point(self._hover_key, 0.0)
            if key:
                self.hover.point(key, 1.0)
            self._hover_key = key
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hover_key:
            self.hover.point(self._hover_key, 0.0)
            self._hover_key = None
        super().leaveEvent(event)

    # ---------------------------------------------------------- empty state
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.model().rowCount(self.rootIndex()) or not self.message:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        area = QRectF(self.viewport().rect())
        if self.loading:
            self._skeleton(painter, area)
            return
        disc = QRectF(0, 0, 96, 96)
        disc.moveCenter(QPoint(int(area.center().x()), int(area.center().y()) - 28))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('tile'))
        painter.drawPath(squircle(disc, .8))
        paint_symbol(painter, disc, self.symbol, 'subtle', 44, filled=True)
        painter.setFont(text_font('body', 500))
        painter.setPen(color('muted'))
        painter.drawText(QRectF(area.left() + 24, disc.bottom() + 12, area.width() - 48, 28), Qt.AlignCenter, self.message)


def _skeleton(self, painter, area):
    """Pulsing placeholders while a folder loads (a wave runs across the cells)."""
    import math
    painter.setPen(Qt.NoPen)
    if self.mode == 'grid':
        cell = self.gridSize()
        columns = max(1, int(area.width() // cell.width()))
        for number in range(columns * 3):
            col, row = number % columns, number // columns
            card = QRectF(col * cell.width() + 5, row * cell.height() + 4, cell.width() - 10, cell.height() - 8)
            glow = 10 + 14 * (.5 + .5 * math.sin(self.phase - number * .55))
            painter.setBrush(color('tint', round(glow)))
            tile = QRectF(card.center().x() - 46, card.top() + 10, 92, 74)
            painter.drawPath(squircle(tile, .55))
            painter.drawRoundedRect(QRectF(card.center().x() - 30, tile.bottom() + 14, 60, 9), 4.5, 4.5)
    else:
        for number in range(9):
            card = QRectF(4, number * ROW_HEIGHT + 2, area.width() - 8, ROW_HEIGHT - 4)
            glow = 10 + 14 * (.5 + .5 * math.sin(self.phase - number * .5))
            painter.setBrush(color('tint', round(glow)))
            painter.drawPath(squircle(QRectF(card.left() + 10, card.center().y() - 18, 36, 36), .55))
            painter.drawRoundedRect(QRectF(card.left() + 58, card.center().y() - 5, min(220, card.width() * .4), 10), 5, 5)


FileView._skeleton = _skeleton


class ListHeader(QWidget):
    """Sortable column titles aligned with ``list_columns``."""

    sort_requested = Signal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.column, self.order = NAME, Qt.AscendingOrder
        self.setFixedHeight(HEADER_HEIGHT)
        self.setMouseTracking(True)
        self._hover = None
        self.setCursor(Qt.PointingHandCursor)

    def set_sort(self, column, order):
        self.column, self.order = column, order
        self.update()

    def _targets(self):
        columns = list_columns(self.width())
        pad = metric('space_m')
        targets = {NAME: (pad + 38 + metric('space_m'), 200)}
        for key, column in (('date', DATE), ('size', SIZE), ('kind', KIND)):
            if key in columns:
                targets[column] = columns[key]
        return targets

    def _column_at(self, x):
        for column, (left, width) in self._targets().items():
            if left - 6 <= x <= left + max(width, 60):
                return column
        return None

    def mouseMoveEvent(self, event):
        column = self._column_at(event.position().x())
        if column != self._hover:
            self._hover = column
            self.update()

    def leaveEvent(self, event):
        self._hover = None
        self.update()

    def mouseReleaseEvent(self, event):
        column = self._column_at(event.position().x())
        if event.button() == Qt.LeftButton and column is not None:
            order = Qt.DescendingOrder if column == self.column and self.order == Qt.AscendingOrder else Qt.AscendingOrder
            self.sort_requested.emit(column, order)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        labels = {NAME: COLUMNS[0], DATE: COLUMNS[1], SIZE: COLUMNS[2], KIND: COLUMNS[3]}
        font = text_font('caption', 700)
        font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, .9)
        painter.setFont(font)
        for column, (left, width) in self._targets().items():
            active = column == self.column
            painter.setPen(color('accent' if active else 'text' if column == self._hover else 'muted'))
            right_aligned = column == SIZE
            text = labels[column].upper()
            area = QRectF(left, 0, width, self.height())
            painter.drawText(area, (Qt.AlignRight if right_aligned else Qt.AlignLeft) | Qt.AlignVCenter, text)
            if active:
                advance = painter.fontMetrics().horizontalAdvance(text)
                x = area.right() - advance - 18 if right_aligned else area.left() + advance + 2
                paint_symbol(painter, QRectF(x, 0, 16, self.height()), 'arrow_upward' if self.order == Qt.AscendingOrder else 'arrow_downward', 'accent', 14)
        painter.setPen(QPen(color('divider'), 1))
        painter.drawLine(metric('space_m'), self.height() - 1, self.width() - metric('space_m'), self.height() - 1)

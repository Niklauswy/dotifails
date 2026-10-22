"""Breadcrumb pill: tap a segment to go there, tap the empty end (or Ctrl+L) to type a path."""
from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from theme_tokens import color
from .kit import metric, paint_symbol, text_font

HEIGHT = 42


class PathBar(QWidget):
    navigate_requested = Signal(str)
    copy_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = str(Path.home())
        self.segments = []      # [(label, path, QRectF)]
        self.hidden_parents = []
        self.hover = None
        self.setFixedHeight(HEIGHT)
        self.setMouseTracking(True)
        self.setAccessibleName('Ruta de la carpeta')
        self.setToolTip('Haz clic en un tramo para ir · clic al final para escribir una ruta · Ctrl+L')
        self.edit = QLineEdit(self)
        self.edit.setObjectName('musicSearch')
        self.edit.setAccessibleName('Ruta de la carpeta')
        self.edit.hide()
        self.edit.returnPressed.connect(self._commit)
        self.edit.installEventFilter(self)

    def set_path(self, path):
        self.path = path
        self._layout()
        if not self.edit.isVisible():
            self.update()

    # ---------------------------------------------------------------- layout
    def _chain(self):
        path = Path(self.path)
        home = Path.home()
        chain = list(reversed(path.parents)) + [path]
        if home in chain:
            chain = chain[chain.index(home):]
        return [('Inicio' if part == home else part.name or 'Sistema', str(part)) for part in chain]

    def _layout(self):
        chain = self._chain()
        font = text_font('body', 600)
        metrics_ = QFontMetrics(font)
        pad = metric('space_m')
        gap = 20
        widths = [min(metrics_.horizontalAdvance(label) + pad * 2 - 4, 220) for label, _ in chain]
        icon = 34
        budget = self.width() - icon - pad
        total = sum(widths) + gap * (len(chain) - 1)
        skipped = 0
        while total > budget and len(chain) - skipped > 1:
            total -= widths[skipped] + gap
            skipped += 1
            if skipped == 1:
                total += 40 + gap
        self.hidden_parents = chain[:skipped]
        x = icon
        self.segments = []
        if skipped:
            self.segments.append(('…', '', QRectF(x, 5, 40, HEIGHT - 10)))
            x += 40 + gap
        for (label, path), width in zip(chain[skipped:], widths[skipped:]):
            self.segments.append((label, path, QRectF(x, 5, width, HEIGHT - 10)))
            x += width + gap

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout()
        self.edit.setGeometry(self.rect().adjusted(6, 4, -6, -4))

    # ----------------------------------------------------------------- paint
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('well'))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        if self.edit.isVisible():
            return
        paint_symbol(painter, QRectF(8, 0, 28, HEIGHT), 'home' if self.path == str(Path.home()) else 'folder_open', 'accent', 20, filled=True)
        last = len(self.segments) - 1
        for number, (label, path, box) in enumerate(self.segments):
            current = number == last
            if number:
                paint_symbol(painter, QRectF(box.left() - 20, 0, 20, HEIGHT), 'chevron_right', 'muted', 16)
            if self.hover == number and not current:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color('tint', 22))
                painter.drawRoundedRect(box, box.height() / 2, box.height() / 2)
            painter.setFont(text_font('body', 700 if current else 500))
            painter.setPen(color('text_strong' if current else 'muted' if self.hover != number else 'text'))
            painter.drawText(box, Qt.AlignCenter, painter.fontMetrics().elidedText(label, Qt.ElideMiddle, int(box.width() - 8)))

    # ----------------------------------------------------------------- input
    def _segment_at(self, point):
        for number, (_l, _p, box) in enumerate(self.segments):
            if box.contains(point):
                return number
        return None

    def mouseMoveEvent(self, event):
        hovered = self._segment_at(event.position())
        self.setCursor(Qt.PointingHandCursor if hovered is not None else Qt.IBeamCursor)
        if hovered != self.hover:
            self.hover = hovered
            self.update()

    def leaveEvent(self, event):
        self.hover = None
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        number = self._segment_at(event.position())
        if number is None:
            self.begin_edit()
            return
        label, path, box = self.segments[number]
        if label == '…':
            from .menu import ActionMenu
            menu = ActionMenu(self.window())
            for name, target in reversed(self.hidden_parents):
                menu.add('folder', name, lambda target=target: self.navigate_requested.emit(target))
            menu.popup(self.mapToGlobal(box.bottomLeft().toPoint()))
        elif number != len(self.segments) - 1:
            self.navigate_requested.emit(path)

    def contextMenuEvent(self, event):
        from .menu import ActionMenu
        menu = ActionMenu(self.window())
        menu.add('link', 'Copiar ruta', self.copy_requested.emit, 'Ctrl+Shift+C')
        menu.add('edit', 'Escribir una ruta', self.begin_edit, 'Ctrl+L')
        menu.popup(event.globalPos())

    # --------------------------------------------------------------- editing
    def begin_edit(self):
        self.edit.setText(self.path)
        self.edit.show()
        self.edit.setFocus()
        self.edit.selectAll()
        self.update()

    def end_edit(self):
        if self.edit.isVisible():
            self.edit.hide()
            self.update()

    def _commit(self):
        target = self.edit.text().strip()
        self.end_edit()
        if target:
            self.navigate_requested.emit(target)

    def eventFilter(self, watched, event):
        if watched is self.edit:
            if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
                self.end_edit()
                return True
            if event.type() == QEvent.FocusOut:
                self.end_edit()
        return super().eventFilter(watched, event)

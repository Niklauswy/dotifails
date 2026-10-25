"""Containers and navigation rows shared by the Qt apps: raised panels, sidebar rows, search, section titles."""
from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

from ..qt_theme import color, tokens
from .style import metric, paint_symbol, text_font
from .widgets import StateLayer

OUTLINE_ONLY = {'explore', 'history', 'album', 'download', 'artist'}  # glyphs whose filled form loses detail


class Panel(QWidget):
    """Rounded raised surface, like the shell's StyledRect containers."""

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('surface'))
        radius = tokens()['radius_l']
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)


class SearchField(QLineEdit):
    """Pill search with a painted Material search glyph."""

    def __init__(self, accessible_name='Buscar', object_name='kitSearch'):
        super().__init__()
        self.setObjectName(object_name)          # the app's QSS styles its own field
        self.setPlaceholderText('Buscar')
        self.setAccessibleName(accessible_name)
        self.setToolTip('Buscar · Ctrl+K')
        self.setClearButtonEnabled(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        paint_symbol(painter, QRectF(8, 0, 24, self.height()), 'search', 'muted', 20)


class NavItem(QWidget):
    """Sidebar row: symbol + label; pill when active. Subclasses may paint something else on the left."""

    clicked = Signal()
    menu_requested = Signal(object)  # global position

    def __init__(self, symbol, label, parent=None):
        super().__init__(parent)
        self.symbol, self.label = symbol, label
        self.active = False
        self.playing = False
        self.layer = StateLayer(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(label)
        self.setToolTip(label if len(label) > 22 else '')
        self.setFixedHeight(36)

    def set_active(self, active):
        if active != self.active:
            self.active = active
            self.update()

    def set_playing(self, playing):
        if playing != self.playing:
            self.playing = playing
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

    def contextMenuEvent(self, event):
        self.menu_requested.emit(event.globalPos())

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
        if self.active or self.layer.amount:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('nav_selected') if self.active else color('tint', round(12 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        pad = metric('space_m')
        text_left = self.paint_leading(painter, pad)
        right = self.width() - pad - (22 if self.playing else 0)
        painter.setFont(text_font('body', 600 if self.active else 450))
        painter.setPen(color('text_strong' if self.active else 'text'))
        painter.drawText(QRect(text_left, 0, right - text_left, self.height()), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self.label, Qt.ElideRight, right - text_left))
        if self.playing:
            paint_symbol(painter, QRect(self.width() - pad - 20, 0, 20, self.height()), 'graphic_eq', 'accent', 18)
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(color('focus'))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)

    def paint_leading(self, painter, pad):
        """Paint what sits left of the label; return where the label starts."""
        paint_symbol(painter, QRect(pad - 4, 0, 28, self.height()), self.symbol,
                     'accent' if self.active else 'glyph', 21,
                     filled=self.active and self.symbol not in OUTLINE_ONLY)
        return pad + 24 + metric('space_s')


def section_label(text):
    label = QLabel(text.upper())
    font = text_font('caption', 700)
    font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1.1)
    label.setFont(font)
    label.setObjectName('muted')
    label.setContentsMargins(metric('space_m'), metric('space_m'), 0, metric('space_xs'))
    return label

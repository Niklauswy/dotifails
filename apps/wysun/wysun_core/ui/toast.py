"""Short-lived pill message floating over the content."""
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel

from ..qt_theme import color
from .style import text_font


class Toast(QLabel):
    def __init__(self, parent, duration=3500, bottom=64):
        """``bottom``: distance from the parent's bottom edge to the pill's top."""
        super().__init__(parent)
        self.bottom = bottom
        self.setFont(text_font('small', 600))
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.timer = QTimer(self, singleShot=True, interval=duration)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text):
        self.setText(text)
        self.setAccessibleName(text)
        width = min(self.parentWidget().width() - 48, self.fontMetrics().horizontalAdvance(text) + 40)
        self.setGeometry((self.parentWidget().width() - width) // 2, self.parentWidget().height() - self.bottom, width, 36)
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

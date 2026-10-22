"""In-window sheets (prompt, confirm, properties) and the floating toast, on the same scrim."""
from PySide6.QtCore import QEasingCurve, QEvent, QRectF, QTimer, QVariantAnimation, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from theme_tokens import color, tokens
from ui_motion import reduced_motion
from .kit import PillButton, metric, text_font


class _Card(QWidget):
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = tokens()['radius_l'] + 4
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.setPen(color('line_strong'))
        painter.setBrush(color('surface_raised'))
        painter.drawRoundedRect(rect, radius, radius)


class Sheet(QWidget):
    """A card over a scrim that covers the whole window; Esc cancels, Enter accepts."""

    closed = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.host = window
        self.accept_callback = None
        self.card = _Card(self)
        self.column = QVBoxLayout(self.card)
        self.column.setContentsMargins(24, 22, 24, 20)
        self.column.setSpacing(metric('space_m'))
        self.fade = QVariantAnimation(self, duration=tokens()['motion_enter'])
        self.fade.setEasingCurve(QEasingCurve.OutCubic)
        self.fade.valueChanged.connect(self._animate)
        self.progress = 1.0
        self.setFocusPolicy(Qt.StrongFocus)
        self.hide()
        window.installEventFilter(self)

    # ------------------------------------------------------------- building
    def _reset(self, title, width=440):
        while self.column.count():
            item = self.column.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
            elif item.layout():
                self._drop(item.layout())
        heading = QLabel(title)
        heading.setFont(text_font('heading', 650))
        self.column.addWidget(heading)
        self.card.setFixedWidth(width)

    def _drop(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()

    def _buttons(self, buttons):
        row = QHBoxLayout()
        row.setSpacing(metric('space_s'))
        row.addStretch()
        for label, callback, variant in buttons:
            button = PillButton('check' if variant == 'filled' else 'close', label, callback, variant=variant, height=40)
            if variant == 'filled':
                self.accept_button = button
            row.addWidget(button)
        self.column.addSpacing(metric('space_xs'))
        self.column.addLayout(row)

    def prompt(self, title, label, text, accept, callback, validate=None, select_stem=False):
        self._reset(title)
        caption = QLabel(label)
        caption.setObjectName('muted')
        self.column.addWidget(caption)
        self.edit = QLineEdit(text)
        self.edit.setAccessibleName(label)
        self.error = QLabel()
        self.error.setStyleSheet(f'color:{color("danger").name()};')
        self.error.setFont(text_font('small'))
        self.error.hide()
        self.column.addWidget(self.edit)
        self.column.addWidget(self.error)

        def submit():
            value = self.edit.text().strip()
            problem = validate(value) if validate else ''
            if problem:
                self.error.setText(problem)
                self.error.show()
                return
            self.dismiss()
            callback(value)
        self.accept_callback = submit
        self._buttons([('Cancelar', self.dismiss, 'tonal'), (accept, submit, 'filled')])
        self.edit.returnPressed.connect(submit)
        self._present(self.edit)
        stem = text.rfind('.') if select_stem and text.rfind('.') > 0 else len(text)
        self.edit.setSelection(0, stem)

    def confirm(self, title, message, accept, callback, details=''):
        self._reset(title)
        body = QLabel(message)
        body.setWordWrap(True)
        self.column.addWidget(body)
        if details:
            extra = QLabel(details)
            extra.setObjectName('muted')
            extra.setWordWrap(True)
            self.column.addWidget(extra)

        def submit():
            self.dismiss()
            callback()
        self.accept_callback = submit
        self._buttons([('Cancelar', self.dismiss, 'tonal'), (accept, submit, 'filled')])
        self._present(self.accept_button)

    def info(self, title, rows):
        self._reset(title, 480)
        for label, value in rows:
            line = QWidget()
            inner = QHBoxLayout(line)
            inner.setContentsMargins(0, 2, 0, 2)
            name = QLabel(label)
            name.setObjectName('muted')
            name.setFixedWidth(110)
            data = QLabel(value)
            data.setWordWrap(True)
            data.setTextInteractionFlags(Qt.TextSelectableByMouse)
            inner.addWidget(name, 0, Qt.AlignTop)
            inner.addWidget(data, 1)
            self.column.addWidget(line)
        self.accept_callback = self.dismiss
        self._buttons([('Cerrar', self.dismiss, 'filled')])
        self._present(self.accept_button)

    # ---------------------------------------------------------------- flow
    def _present(self, focus):
        self.setGeometry(self.host.rect())
        self.card.adjustSize()
        self._place()
        self.show()
        self.raise_()
        focus.setFocus()
        self.fade.stop()
        if reduced_motion(self.host):
            self._animate(1.0)
        else:
            self.fade.setStartValue(0.0)
            self.fade.setEndValue(1.0)
            self.fade.start()

    def _place(self):
        rise = round(14 * (1 - self.progress))
        self.card.move((self.width() - self.card.width()) // 2, (self.height() - self.card.height()) // 2 + rise)

    def _animate(self, value):
        self.progress = float(value)
        self._place()
        self.card.setGraphicsEffect(None)
        self.update()

    def dismiss(self):
        if self.isVisible():
            self.hide()
            self.closed.emit()
            self.host.setFocus()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('scrim', round(color('scrim').alpha() * self.progress)))
        painter.drawRoundedRect(QRectF(self.rect()), tokens()['radius_l'], tokens()['radius_l'])

    def mousePressEvent(self, event):
        if not self.card.geometry().contains(event.position().toPoint()):
            self.dismiss()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.dismiss()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter) and self.accept_callback:
            self.accept_callback()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.host and event.type() == QEvent.Resize and self.isVisible():
            self.setGeometry(self.host.rect())
            self._place()
        return super().eventFilter(watched, event)


class Toast(QLabel):
    """Short-lived pill message floating over the content."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setFont(text_font('small', 600))
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.timer = QTimer(self, singleShot=True, interval=3200)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text):
        self.setText(text)
        self.setAccessibleName(text)
        width = min(self.parentWidget().width() - 48, self.fontMetrics().horizontalAdvance(text) + 40)
        self.setGeometry((self.parentWidget().width() - width) // 2, self.parentWidget().height() - 112, width, 36)
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
        painter.drawText(self.rect(), Qt.AlignCenter, self.fontMetrics().elidedText(self.text(), Qt.ElideRight, self.width() - 24))

"""Native, keyboard-accessible installer surfaces and desktop previews."""
from pathlib import Path
import os

from PySide6.QtCore import Qt, QRectF, QSize, Property, QPropertyAnimation, QEasingCurve, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QLinearGradient
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsOpacityEffect, QLabel,
                               QPushButton, QSizePolicy, QStyle, QStyleOptionButton, QVBoxLayout, QWidget)


STYLE = '''
QWidget {font-family:Inter,"DejaVu Sans";font-size:13px;color:#E9EEF5;}
QMainWindow,QDialog {background:#10151D;}
QWidget#sidebar {background:#151D27;border-right:1px solid #253141;}
QLabel {background:transparent;}
QLabel#eyebrow {color:#8CAAC4;font-size:10px;font-weight:600;letter-spacing:2px;}
QLabel#heading {font-size:30px;font-weight:600;color:#F4F6FA;}
QLabel#hero {font-size:38px;font-weight:600;color:#F4F6FA;}
QLabel#body {color:#A9B7C9;font-size:13px;line-height:1.5;}
QLabel#small {color:#99ACC1;font-size:11px;}
QLabel#cardTitle {font-size:15px;font-weight:600;}
QLabel#section {font-size:16px;font-weight:600;}
QLabel#success {color:#A5DAC2;}
QLabel#warning {color:#F2CB94;}
QLabel#error {color:#F4ADB4;}
QFrame#surface {background:#19232F;border:1px solid #2B3B4D;border-radius:16px;}
QFrame#subtle {background:#131D28;border:1px solid #243445;border-radius:12px;}
QFrame#footer {background:#131B25;border-top:1px solid #293747;}
QPushButton {background:#202E3E;color:#D5E1F0;border:1px solid transparent;border-radius:10px;padding:11px 17px;min-height:18px;}
QPushButton:hover {background:#2B3D51;}
QPushButton:pressed {background:#344B63;}
QPushButton:focus {border-color:#B7D4F5;}
QPushButton:checked {background:#30465C;color:#F1F6FC;border-color:#7E9FC0;}
QPushButton:disabled {background:#18212C;color:#697C92;}
QPushButton#primary {background:#B7D2EF;color:#122034;font-weight:600;padding:12px 23px;}
QPushButton#primary:hover {background:#D2E5F8;}
QPushButton#primary:disabled {background:#2B3A4A;color:#7F93A9;}
QPushButton#quiet {background:transparent;color:#A8BACF;text-align:left;padding:10px 12px;}
QPushButton#quiet:hover {background:#263546;color:#E9F2FF;}
QPushButton#nav {text-align:left;background:transparent;color:#8396AE;border-radius:10px;padding:13px 12px;}
QPushButton#nav:checked {background:#25374B;color:#E2EEFC;border-color:transparent;}
QPushButton#nav:disabled {color:#55677D;}
QPushButton#danger {color:#EDB5B9;background:#33262F;}
QLineEdit,QComboBox {background:#131E2B;color:#E7EEF7;border:1px solid #38506A;border-radius:9px;padding:10px;}
QLineEdit:focus,QComboBox:focus {border-color:#B7D2EF;}
QCheckBox {spacing:10px;padding:8px 0;color:#C5D3E4;}
QCheckBox::indicator {width:18px;height:18px;border:1px solid #607993;border-radius:5px;background:#101923;}
QCheckBox::indicator:checked {background:#BCD7F2;image:url(__CHECK__);}
QCheckBox:focus {color:white;}
QCheckBox:disabled {color:#6D7C90;}
QPlainTextEdit {background:#0C121B;color:#B2C4D8;border:1px solid #2B3F54;border-radius:10px;padding:10px;font-family:"DejaVu Sans Mono";font-size:11px;selection-background-color:#365774;}
QScrollArea {background:transparent;border:0;}
QWidget#scrollBody {background:transparent;}
QScrollBar:vertical {background:transparent;width:7px;margin:5px 0;}
QScrollBar::handle:vertical {background:#41536A;min-height:28px;border-radius:3px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:none;}
QProgressBar {background:#233346;border:0;border-radius:4px;height:8px;text-align:center;color:transparent;}
QProgressBar::chunk {background:#B1D1F1;border-radius:4px;}
QListWidget {background:#131E2A;border:1px solid #304257;border-radius:10px;padding:5px;outline:0;}
QListWidget::item {padding:12px;border-radius:7px;}
QListWidget::item:selected {background:#30465F;}
QToolTip {background:#28394D;color:#EDF4FC;border:1px solid #617B98;padding:8px;}
'''.replace('__CHECK__', str(Path(__file__).parent / 'check.svg'))


def label(text, role='body', wrap=True):
    widget = QLabel(text)
    widget.setObjectName(role)
    widget.setTextFormat(Qt.PlainText)
    widget.setWordWrap(wrap)
    if wrap:
        widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    return widget


def motion_disabled():
    return os.environ.get('ORBIT_REDUCED_MOTION', '').lower() in ('1', 'true', 'yes')


class Button(QPushButton):
    def __init__(self, title, callback=None, role='', parent=None):
        super().__init__(title, parent)
        self.setObjectName(role)
        self.setCursor(Qt.PointingHandCursor)
        self._scale = 1.0
        self._animation = QPropertyAnimation(self, b'pressScale', self)
        self.pressed.connect(lambda: self.animate(.96, 85))
        self.released.connect(lambda: self.animate(1., 140))
        if callback:
            self.clicked.connect(callback)

    def animate(self, target, duration):
        self._animation.stop()
        self._animation.setStartValue(self._scale)
        self._animation.setEndValue(target)
        self._animation.setDuration(0 if motion_disabled() else duration)
        curve = QEasingCurve(QEasingCurve.BezierSpline)
        curve.addCubicBezierSegment(QPointF(.2, 0), QPointF(0, 1), QPointF(1, 1))
        self._animation.setEasingCurve(curve)
        self._animation.start()

    def set_scale(self, value):
        self._scale = value
        self.update()

    pressScale = Property(float, lambda self: self._scale, set_scale)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.translate(self.width()/2, self.height()/2)
        painter.scale(self._scale, self._scale)
        painter.translate(-self.width()/2, -self.height()/2)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        self.style().drawControl(QStyle.CE_PushButton, option, painter, self)


class ChoiceCard(QAbstractButton):
    def __init__(self, title, description, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self.setMinimumHeight(82)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(22, 16, 52, 16)
        self.box.setSpacing(5)
        self.title = label(title, 'cardTitle')
        self.description = label(description, 'body')
        for item in (self.title, self.description):
            item.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.box.addWidget(item)
        self.toggled.connect(self.update)

    def sizeHint(self):
        return QSize(300, max(82, self.box.sizeHint().height()))

    def minimumSizeHint(self):
        return QSize(140, 82)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        selected = self.isChecked()
        hovered = self.underMouse() and self.isEnabled()
        p.setBrush(QColor('#23374B' if selected else ('#1D2B3B' if hovered else '#18222F')))
        p.setPen(QPen(QColor('#BCD7F2' if self.hasFocus() else ('#7096BC' if selected else '#304052')), 1))
        p.drawRoundedRect(QRectF(1, 1, self.width()-2, self.height()-2), 14, 14)
        p.setPen(QPen(QColor('#BAD5F1' if selected else '#61778F'), 1.3))
        p.setBrush(QColor('#BAD5F1') if selected else Qt.NoBrush)
        box = QRectF(self.width()-37, 23, 17, 17)
        p.drawRoundedRect(box, 5, 5)
        if selected:
            p.setPen(QPen(QColor('#172A3E'), 1.8))
            p.drawLine(QPointF(box.x()+4, box.y()+8), QPointF(box.x()+7, box.y()+11))
            p.drawLine(QPointF(box.x()+7, box.y()+11), QPointF(box.x()+13, box.y()+5))


class DesktopPreview(QWidget):
    def __init__(self, source, theme='severance', parent=None):
        super().__init__(parent)
        self.source = Path(source)
        self.setMinimumHeight(215)
        self.setMinimumWidth(200)
        self.setAccessibleName('Vista orientativa del escritorio')
        self.set_theme(theme)

    def set_theme(self, theme):
        self.theme = theme
        filename = {'severance':'azul.jpg', 'tokyo':'tokyo.png', 'space-black':'space-black.png'}.get(theme, 'azul.jpg')
        self.wallpaper = QPixmap(str(self.source / 'assets/backgrounds' / filename))
        if self.wallpaper.isNull():
            self.wallpaper = QPixmap(str(Path(__file__).parent / 'previews' / (theme + '.jpg')))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        area = QRectF(1, 1, self.width()-2, self.height()-2)
        clip = QPainterPath(); clip.addRoundedRect(area, 16, 16)
        p.setClipPath(clip)
        p.fillRect(area, QColor('#111E2A'))
        if not self.wallpaper.isNull():
            scaled = self.wallpaper.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap((self.width()-scaled.width())//2, (self.height()-scaled.height())//2, scaled)
        shade = QLinearGradient(0, 0, 0, self.height())
        shade.setColorAt(0, QColor(4, 10, 20, 10)); shade.setColorAt(1, QColor(4, 10, 20, 155))
        p.fillRect(area, shade)
        # This schematic uses the actual wallpaper; it is never presented as a screenshot.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(13, 22, 33, 225))
        p.drawRoundedRect(QRectF(18, 15, self.width()-36, 25), 9, 9)
        p.setFont(QFont('Inter', 9)); p.setPen(QColor('#DFEAF7'))
        p.drawText(QRectF(30, 15, self.width()-60, 25), Qt.AlignVCenter, 'Ó   01  ·  02  ·  03')
        p.drawText(QRectF(30, 15, self.width()-60, 25), Qt.AlignRight|Qt.AlignVCenter, 'Wi-Fi    85%')
        w, h = self.width(), self.height()
        terminal = QRectF(w*.08, h*.27, w*.54, h*.57)
        p.setBrush(QColor(12, 20, 32, 235)); p.setPen(QPen(QColor(255,255,255,32), 1))
        p.drawRoundedRect(terminal, 11, 11)
        p.setPen(QColor('#A8BBD3')); p.setFont(QFont('Inter', 9))
        p.drawText(terminal.adjusted(16, 10, -16, -10), Qt.AlignTop, 'ghostty  /  ~')
        p.setFont(QFont('DejaVu Sans Mono', 10)); p.setPen(QColor('#A7D8C1'))
        p.drawText(terminal.adjusted(16, 42, -16, -10), Qt.AlignTop, '❯  Tu próximo espacio de trabajo' if w > 650 else '❯  Bienvenido a Wysun')
        p.setPen(QColor('#9BAFC7')); p.setFont(QFont('DejaVu Sans Mono', 9))
        p.drawText(terminal.adjusted(16, 68, -16, -10), Qt.AlignTop, 'Listo para crear.')
        panel = QRectF(w*.58, h*.38, w*.34, h*.46)
        p.setBrush(QColor(23, 35, 52, 245)); p.setPen(QPen(QColor(255,255,255,45), 1))
        p.drawRoundedRect(panel, 12, 12)
        p.setPen(QColor('#E3ECF7')); p.setFont(QFont('Inter', 10))
        p.drawText(panel.adjusted(17, 13, -12, -8), Qt.AlignTop, 'Buscar en Wysun')
        p.setPen(QColor('#ACBED4')); p.setFont(QFont('Inter', 9))
        p.drawText(panel.adjusted(17, 40, -12, -8), Qt.AlignTop, 'Aplicaciones   ·   Archivos')
        p.setClipping(False)
        p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(255,255,255,34), 1))
        p.drawRoundedRect(area, 16, 16)


def reveal(widget):
    if motion_disabled():
        return
    effect = getattr(widget, '_fade_effect', None)
    if effect is None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        widget._fade_effect = effect
        widget._fade = QPropertyAnimation(effect, b'opacity', widget)
    animation = widget._fade
    animation.stop(); animation.setDuration(140)
    animation.setStartValue(.65); animation.setEndValue(1.)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.start()

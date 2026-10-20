"""Native, keyboard-accessible installer surfaces and desktop previews."""
from pathlib import Path
import os
import sys

# The installer runs from the repository: colours come from the same token file as the desktop.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wysun'))
import theme_core  # noqa: E402
from theme_tokens import color, font, apply_style  # noqa: E402

from PySide6.QtCore import Qt, QRectF, QSize, Property, QPropertyAnimation, QEasingCurve, QPointF
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPen, QPixmap, QLinearGradient
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsOpacityEffect, QLabel,
                               QPushButton, QSizePolicy, QStyle, QStyleOptionButton, QVBoxLayout, QWidget)


# Template: @token markers resolve against the active Wysun theme (apps/wysun/wysun_theme.json).
STYLE = '''
QWidget {font-family:@font_family;font-size:@font_body;color:@text;}
QMainWindow,QDialog {background:@canvas;}
QWidget#sidebar {background:@surface;border-right:@border solid @line;}
QLabel {background:transparent;}
QLabel#eyebrow {color:@subtle;font-size:@font_caption;font-weight:600;letter-spacing:2px;}
QLabel#heading {font-size:30px;font-weight:600;color:@text_strong;}
QLabel#hero {font-size:38px;font-weight:600;color:@text_strong;}
QLabel#body {color:@muted;font-size:@font_body;line-height:1.5;}
QLabel#small {color:@muted;font-size:@font_small;}
QLabel#cardTitle {font-size:15px;font-weight:600;}
QLabel#section {font-size:16px;font-weight:600;}
QLabel#success {color:@success;}
QLabel#warning {color:@warning;}
QLabel#error {color:@danger;}
QFrame#surface {background:@surface;border:@border solid @line;border-radius:@radius_l;}
QFrame#subtle {background:@well;border:@border solid @line;border-radius:@radius_m;}
QFrame#footer {background:@well;border-top:@border solid @line;}
QPushButton {background:@fill;color:@control_text;border:@border solid transparent;border-radius:@radius_control;padding:11px 17px;min-height:18px;}
QPushButton:hover {background:@hover;}
QPushButton:pressed {background:@pressed;}
QPushButton:focus {border-color:@focus;}
QPushButton:checked {background:@selection;color:@selection_text;border-color:@selection_line;}
QPushButton:disabled {background:@disabled_surface;color:@disabled;}
QPushButton#primary {background:@accent;color:@on_accent;font-weight:600;padding:12px 23px;}
QPushButton#primary:hover {background:@accent_hover;}
QPushButton#primary:pressed {background:@accent_pressed;}
QPushButton#primary:disabled {background:@disabled_surface;color:@disabled;}
QPushButton#quiet {background:transparent;color:@muted;text-align:left;padding:10px 12px;}
QPushButton#quiet:hover {background:@hover;color:@text_strong;}
QPushButton#nav {text-align:left;background:transparent;color:@muted;border-radius:@radius_control;padding:13px 12px;}
QPushButton#nav:checked {background:@nav_selected;color:@selection_text;border-color:transparent;}
QPushButton#nav:disabled {color:@disabled;}
QPushButton#danger {color:@danger;background:@danger_soft;}
QLineEdit,QComboBox {background:@well;color:@text;border:@border solid @line_strong;border-radius:@radius_control;padding:10px;}
QLineEdit:focus,QComboBox:focus {border-color:@focus_input;}
QCheckBox {spacing:10px;padding:8px 0;color:@control_text;}
QCheckBox::indicator {width:18px;height:18px;border:@border solid @check_line;border-radius:5px;background:@check;}
QCheckBox::indicator:checked {background:@check_on;border-color:@check_on_line;image:url(@svg(check-dark,check_mark));}
QCheckBox:focus {color:@text_strong;}
QCheckBox:disabled {color:@disabled;}
QPlainTextEdit {background:@inset;color:@ink;border:@border solid @line;border-radius:@radius_control;padding:10px;font-family:@font_mono;font-size:@font_small;selection-background-color:@text_selection;}
QScrollArea {background:transparent;border:0;}
QWidget#scrollBody {background:transparent;}
QScrollBar:vertical {background:transparent;width:7px;margin:5px 0;}
QScrollBar::handle:vertical {background:@scrollbar;min-height:28px;border-radius:3px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:none;}
QProgressBar {background:@track;border:0;border-radius:4px;height:8px;text-align:center;color:transparent;}
QProgressBar::chunk {background:@accent;border-radius:4px;}
QListWidget {background:@well;border:@border solid @line;border-radius:@radius_control;padding:5px;outline:0;}
QListWidget::item {padding:12px;border-radius:@radius_s;}
QListWidget::item:selected {background:@selection;color:@selection_text;}
QToolTip {background:@tooltip;color:@on_tooltip;border:@border solid @tooltip_line;padding:8px;}
'''


def theme_tokens_radius():
    from theme_tokens import tokens
    return tokens()['radius_m']


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
        p.setBrush(color('selection' if selected else ('hover' if hovered else 'card')))
        p.setPen(QPen(color('focus' if self.hasFocus() else ('selection_line' if selected else 'card_line')), 1))
        radius = theme_tokens_radius()
        p.drawRoundedRect(QRectF(1, 1, self.width()-2, self.height()-2), radius, radius)
        p.setPen(QPen(color('accent' if selected else 'line_strong'), 1.3))
        p.setBrush(color('accent') if selected else Qt.NoBrush)
        box = QRectF(self.width()-37, 23, 17, 17)
        p.drawRoundedRect(box, 5, 5)
        if selected:
            p.setPen(QPen(color('on_accent'), 1.8))
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
        self.values = theme_core.resolve(*(theme_core.parse(theme) or theme_core.default()))
        filename = self.values['wallpaper']
        self.wallpaper = QPixmap(str(self.source / 'assets/backgrounds' / filename))
        if self.wallpaper.isNull():
            self.wallpaper = QPixmap(str(Path(__file__).parent / 'previews' / (theme + '.jpg')))
        self.update()

    def paintEvent(self, event):
        # The schematic is drawn in the previewed theme's own material, accent and radii.
        v = self.values
        c = lambda name, alpha=None: color(name, alpha, v)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        area = QRectF(1, 1, self.width()-2, self.height()-2)
        clip = QPainterPath(); clip.addRoundedRect(area, v['radius_l'], v['radius_l'])
        p.setClipPath(clip)
        p.fillRect(area, c('canvas'))
        if not self.wallpaper.isNull():
            scaled = self.wallpaper.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap((self.width()-scaled.width())//2, (self.height()-scaled.height())//2, scaled)
        shade = QLinearGradient(0, 0, 0, self.height())
        shade.setColorAt(0, c('region_scrim', 10)); shade.setColorAt(1, c('region_scrim', 155))
        p.fillRect(area, shade)
        # This schematic uses the actual wallpaper; it is never presented as a screenshot.
        p.setPen(Qt.NoPen)
        p.setBrush(c('material_mid', 235))
        p.drawRoundedRect(QRectF(18, 15, self.width()-36, 25), v['radius_m'], v['radius_m'])
        p.setFont(font(9, values=v)); p.setPen(c('text'))
        p.drawText(QRectF(30, 15, self.width()-60, 25), Qt.AlignVCenter, 'Ó   01  ·  02  ·  03')
        p.drawText(QRectF(30, 15, self.width()-60, 25), Qt.AlignRight|Qt.AlignVCenter, 'Wi-Fi    85%')
        w, h = self.width(), self.height()
        terminal = QRectF(w*.08, h*.27, w*.54, h*.57)
        p.setBrush(c('material_bottom', 240)); p.setPen(QPen(c('material_edge'), 1))
        p.drawRoundedRect(terminal, v['radius_m'], v['radius_m'])
        p.setPen(c('muted')); p.setFont(font(9, values=v))
        p.drawText(terminal.adjusted(16, 10, -16, -10), Qt.AlignTop, 'ghostty  /  ~')
        p.setFont(QFont(v['font_mono'][0], 10)); p.setPen(c('success'))
        p.drawText(terminal.adjusted(16, 42, -16, -10), Qt.AlignTop, '❯  Tu próximo espacio de trabajo' if w > 650 else '❯  Bienvenido a Wysun')
        p.setPen(c('muted')); p.setFont(QFont(v['font_mono'][0], 9))
        p.drawText(terminal.adjusted(16, 68, -16, -10), Qt.AlignTop, 'Listo para crear.')
        panel = QRectF(w*.58, h*.38, w*.34, h*.46)
        p.setBrush(c('material_top', 245)); p.setPen(QPen(c('material_edge'), 1))
        p.drawRoundedRect(panel, v['radius_m'], v['radius_m'])
        p.setPen(c('text')); p.setFont(font(10, values=v))
        p.drawText(panel.adjusted(17, 13, -12, -8), Qt.AlignTop, 'Buscar en Wysun')
        p.setPen(c('muted')); p.setFont(font(9, values=v))
        p.drawText(panel.adjusted(17, 40, -12, -8), Qt.AlignTop, 'Aplicaciones   ·   Archivos')
        p.setBrush(c('accent')); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(panel.right()-52, panel.bottom()-26, 38, 14), v['radius_s']*.6, v['radius_s']*.6)
        p.setClipping(False)
        p.setBrush(Qt.NoBrush); p.setPen(QPen(c('material_edge'), 1))
        p.drawRoundedRect(area, v['radius_l'], v['radius_l'])


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

"""Shared building blocks of the Wysun Recorder window.

The window follows Wysun Music and Wysun Files: frameless glass window, a quiet
navigation column on the window material and one raised content panel. Colours,
radii, spacing, type and motion all come from the theme tokens. These helpers
mirror the ones those apps use; the Recorder installs separately and never
imports them.
"""
import json
import os
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QFont, QFontDatabase, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient, QTextLayout)
from PySide6.QtWidgets import QAbstractButton, QGraphicsOpacityEffect, QLabel, QWidget

from .material import load_fonts
from .tokens import color, qss, tokens

SYMBOL_FAMILY = 'Material Symbols Rounded'
TEXT_FAMILY = 'Rubik'
RESIZE_MARGIN = 6


def metric(name, scale=1.0):
    return round(tokens()[name] * scale)


def reduced_motion(widget=None):
    if os.environ.get('ORBIT_REDUCED_MOTION', '').lower() in ('1', 'true', 'yes') or getattr(widget, 'test', False):
        return True
    root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    try:
        return json.loads((root / 'orbit/appearance.json').read_text()).get('reduced_motion') is True
    except (OSError, ValueError, AttributeError):
        return False


def surface_opacity(values=None):
    """Window material opacity: the user's preference for glass, solid otherwise."""
    values = values or tokens()
    if not values['translucent']:
        return 255
    root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    try:
        opacity = json.loads((root / 'orbit/appearance.json').read_text()).get('opacity', 80)
        opacity = max(65, min(100, round(opacity)))
    except (OSError, ValueError, TypeError, AttributeError):
        opacity = 80
    return round(opacity * 2.55)


# ------------------------------------------------------------------- text
@lru_cache(maxsize=64)
def _text_font(family, pixels, weight):
    result = QFont(family)
    result.setPixelSize(max(8, pixels))
    result.setWeight(QFont.Weight(weight))
    return result


def display_family():
    load_fonts()
    return TEXT_FAMILY if TEXT_FAMILY in set(QFontDatabase.families()) else QFont().family()


def text_font(role='body', weight=400, scale=1.0):
    """Rubik at a theme size role (caption/small/body/heading/title) × scale."""
    return QFont(_text_font(display_family(), round(tokens()['font_' + role] * scale), weight))


# ---------------------------------------------------------------- symbols
@lru_cache(maxsize=128)
def _renders_one_glyph(text, family):
    layout = QTextLayout(text, QFont(family))
    layout.beginLayout()
    line = layout.createLine()
    layout.endLayout()
    if line.isValid() and line.textLength() == len(text):
        return sum(len(run.glyphIndexes()) for run in layout.glyphRuns()) == 1
    return False


@lru_cache(maxsize=64)
def _symbol_font(pixels):
    result = QFont(SYMBOL_FAMILY)
    result.setPixelSize(pixels)
    return result


@lru_cache(maxsize=256)
def _symbol_path(name, pixels):
    """Filled glyph outline: only outer contours, since PySide6 cannot reach the FILL axis."""
    font = _symbol_font(pixels)
    path = QPainterPath()
    path.addText(0, 0, font, name)
    polygons = path.toSubpathPolygons()
    bounds = [polygon.boundingRect() for polygon in polygons]
    path = QPainterPath()
    path.setFillRule(Qt.WindingFill)
    for index, polygon in enumerate(polygons):
        inner = any(j != index and other != bounds[index] and other.contains(bounds[index]) for j, other in enumerate(bounds))
        if not inner:
            path.addPolygon(polygon)
            path.closeSubpath()
    metrics = QFontMetricsF(font)
    return path.simplified().translated(-metrics.horizontalAdvance(name) / 2, (metrics.ascent() - metrics.descent()) / 2)


def symbols_ready():
    load_fonts()
    return SYMBOL_FAMILY in set(QFontDatabase.families())


def paint_symbol(painter, rect, name, tint, size=None, filled=False):
    """Draw a Material symbol centred in ``rect``; ``tint`` is a token name or a QColor."""
    size = round(size or tokens()['icon_size'] * 1.2)
    ink = color(tint) if isinstance(tint, str) else tint
    if not symbols_ready() or not _renders_one_glyph(name, SYMBOL_FAMILY):
        return
    rect = QRectF(rect)
    painter.save()
    if filled:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(rect.center())
        painter.fillPath(_symbol_path(name, size), ink)
    else:
        painter.setFont(_symbol_font(size))
        painter.setPen(ink)
        painter.drawText(rect, Qt.AlignCenter, name)
    painter.restore()


def clock(seconds):
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    return f'{hours}:{rest // 60:02}:{rest % 60:02}' if hours else f'{rest // 60}:{rest % 60:02}'


# ----------------------------------------------------------------- motion
class StateLayer:
    """Hover/press amount animated with the theme's fast motion token."""

    def __init__(self, widget):
        self.widget = widget
        self.amount = 0.0
        self.animation = QVariantAnimation(widget)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self._set)

    def _set(self, value):
        self.amount = float(value)
        self.widget.update()

    def to(self, target):
        self.animation.stop()
        if reduced_motion(self.widget.window()):
            self._set(target)
            return
        self.animation.setDuration(metric('motion_fast'))
        self.animation.setStartValue(self.amount)
        self.animation.setEndValue(float(target))
        self.animation.start()


def reveal_content(widget, duration=140):
    """Only on navigation, never on every refresh of live content."""
    if not widget or not widget.isVisible() or reduced_motion(widget.window()):
        return
    effect = getattr(widget, '_reveal_effect', None)
    if effect is None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        widget._reveal_effect = effect
        widget._reveal_animation = QPropertyAnimation(effect, b'opacity', widget)
    animation = widget._reveal_animation
    running = animation.state() == QAbstractAnimation.Running
    animation.stop()
    animation.setDuration(duration)
    animation.setStartValue(effect.opacity() if running else .55)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.start()


# ---------------------------------------------------------------- widgets
class IconButton(QAbstractButton):
    """Round icon button: ``ghost`` (bare), ``tonal`` (container), ``filled`` (accent) or ``danger``."""

    def __init__(self, symbol, label, callback=None, variant='ghost', size=36, checkable=False, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.variant = variant
        self.layer = StateLayer(self)
        self.setCheckable(checkable)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.set_label(label)
        if callback:
            self.clicked.connect(lambda _=False: callback())

    def set_label(self, label):
        self.setToolTip(label)
        self.setAccessibleName(label.split(' · ')[0])

    def set_symbol(self, symbol):
        if symbol != self.symbol:
            self.symbol = symbol
            self.update()

    def sizeHint(self):
        return self.size()

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.isDown():
            painter.translate(rect.center())
            painter.scale(.94, .94)
            painter.translate(-rect.center())
        if not self.isEnabled():
            background, ink = ('disabled_surface' if self.variant != 'ghost' else None), 'disabled'
        elif self.variant == 'filled':
            background, ink = 'accent', 'on_accent'
        elif self.variant == 'danger':
            background, ink = 'danger_fill', 'on_accent'
        elif self.variant == 'tonal':
            background, ink = ('selection' if self.isChecked() else 'fill'), ('selection_text' if self.isChecked() else 'glyph')
        else:
            background, ink = None, ('accent' if self.isChecked() else 'glyph')
        painter.setPen(Qt.NoPen)
        if background:
            painter.setBrush(color(background))
            painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        if self.layer.amount and self.isEnabled():
            painter.setBrush(color('on_accent' if self.variant in ('filled', 'danger') else 'tint', round(30 * self.layer.amount)))
            painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        paint_symbol(painter, rect, self.symbol, ink, round(self.width() * .55), filled=self.variant in ('filled', 'danger'))
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)


class Button(QAbstractButton):
    """Pill button with an optional symbol: ``primary`` (accent), ``tonal`` or ``quiet``."""

    def __init__(self, text, symbol=None, variant='tonal', callback=None, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.variant = variant
        self.layer = StateLayer(self)
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        if callback:
            self.clicked.connect(lambda _=False: callback())

    def _inner(self):
        return metric('space_l')

    def sizeHint(self):
        from PySide6.QtCore import QSize
        text = QFontMetricsF(text_font('body', 600)).horizontalAdvance(self.text())
        icon = 28 if self.symbol else 0
        return QSize(round(text + icon + self._inner() * 2), 40)

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = rect.height() / 2
        if not self.isEnabled():
            background, ink = 'disabled_surface', 'disabled'
        elif self.variant == 'primary':
            background, ink = 'accent', 'on_accent'
        elif self.variant == 'danger':
            background, ink = 'danger_fill', 'on_accent'
        elif self.variant == 'quiet':
            background, ink = None, 'text'
        else:
            background, ink = 'fill', 'control_text'
        if self.isDown():
            painter.translate(rect.center())
            painter.scale(.97, .97)
            painter.translate(-rect.center())
        painter.setPen(Qt.NoPen)
        if background:
            painter.setBrush(color(background))
            painter.drawRoundedRect(rect, radius, radius)
        if self.layer.amount and self.isEnabled():
            painter.setBrush(color('on_accent' if self.variant in ('primary', 'danger') else 'tint', round(30 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        font = text_font('body', 600)
        painter.setFont(font)
        painter.setPen(color(ink))
        text_width = QFontMetricsF(font).horizontalAdvance(self.text())
        total = text_width + (28 if self.symbol else 0)
        left = rect.center().x() - total / 2
        if self.symbol:
            paint_symbol(painter, QRectF(left, rect.top(), 24, rect.height()), self.symbol, ink, 20,
                         filled=self.variant in ('primary', 'danger'))
            left += 28
        painter.drawText(QRectF(left, rect.top(), text_width + 2, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, self.text())
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.drawRoundedRect(rect, radius, radius)


class Switch(QAbstractButton):
    """Material switch: track and sliding thumb, themed."""

    toggledByUser = Signal(bool)

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(52, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(label)
        self.slide = StateLayer(self)
        self.slide.amount = 0.0
        self.toggled.connect(lambda on: self.slide.to(1.0 if on else 0.0))
        self.clicked.connect(lambda _=False: self.toggledByUser.emit(self.isChecked()))

    def setChecked(self, value):
        super().setChecked(value)
        self.slide.animation.stop()
        self.slide._set(1.0 if value else 0.0)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        amount = self.slide.amount
        painter.setPen(QPen(color('line_strong'), 2) if amount < .5 else Qt.NoPen)
        painter.setBrush(color('accent') if amount >= .5 else color('well'))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        thumb = 14 + 8 * amount
        x = rect.left() + 8 + (rect.width() - 16 - thumb) * amount + (0 if amount else 0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('on_accent') if amount >= .5 else color('muted'))
        painter.drawEllipse(QRectF(x, rect.center().y() - thumb / 2, thumb, thumb))
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)


class Panel(QWidget):
    """Rounded raised surface, like the shell's StyledRect containers."""

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('surface'))
        radius = tokens()['radius_l']
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)


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
        painter.drawText(self.rect(), Qt.AlignCenter, self.fontMetrics().elidedText(self.text(), Qt.ElideRight, self.width() - 24))


def section_label(text):
    label = QLabel(text.upper())
    font = text_font('caption', 700)
    font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1.1)
    label.setFont(font)
    label.setObjectName('muted')
    label.setContentsMargins(metric('space_m'), metric('space_m'), 0, metric('space_xs'))
    return label


# ---------------------------------------------------------------- surface
def paint_surface(widget):
    """Window material. Dark: tinted glass; light: opaque pearl."""
    values = tokens()
    radius = values['radius_l']
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(.5, .5, widget.width() - 1, widget.height() - 1)
    alpha = surface_opacity(values)
    if values['material'] == 'glass':
        base = QLinearGradient(0, 0, widget.width() * .5, widget.height())
        base.setColorAt(0, color('material_top', alpha))
        base.setColorAt(.52, color('material_mid', alpha))
        base.setColorAt(1, color('material_bottom', min(255, alpha + 12)))
    else:
        base = QLinearGradient(0, 0, 0, widget.height())
        base.setColorAt(0, color('material_top', alpha))
        base.setColorAt(.52, color('material_mid', alpha))
        base.setColorAt(1, color('material_bottom', alpha))
    painter.setBrush(base)
    painter.setPen(QPen(color('material_edge'), values['border']))
    painter.drawRoundedRect(rect, radius, radius)
    if color('material_glow').alpha():
        glow = QRadialGradient(widget.width() * .8, -80, widget.width() * .7)
        glow.setColorAt(0, color('material_glow'))
        glow.setColorAt(1, color('material_glow', 0))
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
    if color('material_highlight').alpha():
        painter.setPen(QPen(color('material_highlight'), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
    painter.end()


STYLE = '''
QWidget {color:@text;}
QScrollArea, QListView, QAbstractScrollArea {background:transparent;border:0;outline:0;}
QScrollArea > QWidget > QWidget {background:transparent;}
QScrollBar:vertical {background:transparent;width:8px;margin:2px;}
QScrollBar::handle:vertical {background:@scrollbar;border-radius:3px;min-height:32px;}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {background:transparent;}
QScrollBar:horizontal {height:0;}
QLineEdit {background:@well;border:@border solid @line;border-radius:@radius_control;padding:@space_s @space_m;
           selection-background-color:@text_selection;}
QLineEdit:focus {border:@focus_width solid @focus_input;}
QLineEdit#search {border-radius:18px;padding:0 @space_m 0 34px;min-height:36px;background:@well;}
QMenu {background:@menu;color:@text;border:@border solid @line_strong;border-radius:@radius_m;padding:@space_xs;}
QMenu::item {padding:@space_s @space_xl @space_s @space_m;border-radius:@radius_s;}
QMenu::item:selected {background:@menu_selected;}
QMenu::item:disabled {color:@disabled;}
QMenu::separator {height:1px;background:@divider;margin:@space_xs @space_s;}
QToolTip {background:@tooltip;color:@on_tooltip;border:@border solid @tooltip_line;padding:@space_xs @space_s;}
QLabel {background:transparent;}
QLabel#heading {font-size:@font_title;font-weight:700;}
QLabel#subheading {font-size:@font_heading;font-weight:600;}
QLabel#muted {color:@muted;font-size:@font_small;}
QComboBox {min-width:220px;background:@well;border:@border solid @line;border-radius:@radius_control;padding:@space_s @space_m;min-height:24px;}
QComboBox::drop-down {border:0;width:24px;}
QComboBox QAbstractItemView {background:@menu;border:@border solid @line_strong;border-radius:@radius_m;selection-background-color:@menu_selected;outline:0;}
QSpinBox {background:@well;border:@border solid @line;border-radius:@radius_control;padding:@space_s @space_m;min-height:24px;}
QSpinBox:focus, QComboBox:focus {border:@focus_width solid @focus_input;}
'''


def apply_style(widget):
    """Themed QSS for colours/shapes plus the Rubik body font, inherited by children."""
    load_fonts()
    widget.setProperty('wysunThemeStyle', STYLE)
    widget.setStyleSheet(qss(STYLE))
    widget.setFont(text_font('body'))

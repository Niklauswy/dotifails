"""Painted controls of Wysun Installer, built on the Material kit Music and Files share.

Composition follows those apps: a quiet column on the window material, one raised panel for the
content and a separate bar underneath. Every colour, radius, size and duration comes from the
theme tokens; painters read them while painting, so a style or variant change is live.
"""
from functools import lru_cache
import math
from pathlib import Path

from ui_support import prepare_imports
RUNTIME = prepare_imports()

from PySide6.QtCore import (QEasingCurve, QEvent, QPointF, QRect, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsOpacityEffect, QLabel, QPlainTextEdit,
                               QSizePolicy, QVBoxLayout, QWidget)
import theme_core
from theme_tokens import apply_style as apply_tokens, color, tokens
from ui_motion import reduced_motion
from ui_theme import paint_surface
from wysun_music.ui.shapes import Drift, blurred, cookie, grain_tile, squircle
from wysun_music.ui.style import apply_style as apply_kit, metric, paint_symbol, text_font
from wysun_music.ui.widgets import IconButton, PillButton, StateLayer  # noqa: F401  (re-exported)

STYLE = '''
QLabel {background:transparent;}
QWidget#page, QWidget#scrollBody {background:transparent;}
QPlainTextEdit {background:@inset;color:@ink;border:0;border-radius:@radius_m;padding:@space_m;
                font-family:@font_mono;font-size:@font_small;selection-background-color:@text_selection;}
QListWidget {background:@well;color:@text;border:0;border-radius:@radius_m;padding:@space_s;outline:0;}
QListWidget::item {padding:@space_m;border-radius:@radius_s;}
QListWidget::item:selected {background:@selection;color:@selection_text;}
QDialog {background:@canvas;}
'''

ROLES = {
    'display': ('title', 800, 1.6, 'text_strong'), 'hero': ('title', 750, 1.25, 'text_strong'),
    'heading': ('title', 700, 1.0, 'text_strong'), 'section': ('heading', 650, 1, 'text_strong'),
    'cardTitle': ('body', 600, 1, 'text_strong'), 'eyebrow': ('caption', 700, 1, 'accent'),
    'small': ('small', 400, 1, 'muted'), 'body': ('body', 400, 1, 'muted'), 'strong': ('body', 500, 1, 'text'),
    'success': ('body', 500, 1, 'success'), 'warning': ('body', 500, 1, 'warning'), 'error': ('body', 500, 1, 'danger'),
    'mono': ('small', 400, 1, 'muted'),
}


def apply_style(widget, template=STYLE):
    apply_kit(widget)
    from theme_tokens import extend_style
    extend_style(widget, template)


def restyle_label(widget, role='body'):
    size, weight, scale, ink = ROLES[role]
    widget.setProperty('installerRole', role)
    font = text_font(size, weight, scale)
    if role == 'eyebrow':
        font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1.1)
    if role == 'mono':
        font.setFamilies(tokens()['font_mono'])
    widget.setFont(font)
    apply_tokens(widget, 'color:@' + ink + ';background:transparent;')


def label(text, role='body', wrap=True):
    widget = QLabel(text.upper() if role == 'eyebrow' else text)
    widget.setTextFormat(Qt.PlainText)
    widget.setWordWrap(wrap)
    if wrap:
        widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    restyle_label(widget, role)
    return widget


def surface(layout, role='panel'):
    """Compatibility helper for the boot recovery dialog: a padded tonal frame."""
    frame = Card(tone='well' if role == 'well' else 'surface_raised')
    inner = QVBoxLayout(frame)
    gap = metric('space_l')
    inner.setContentsMargins(gap, gap, gap, gap)
    inner.setSpacing(metric('space_s'))
    layout.addWidget(frame)
    return inner


class Button(PillButton):
    """Pill with a leading symbol: ``primary`` is filled, anything else tonal."""

    def __init__(self, title, callback=None, role='', parent=None, symbol=None, height=None):
        super().__init__(symbol or ('arrow_forward' if role == 'primary' else 'more_horiz'), title, callback,
                         'filled' if role == 'primary' else 'tonal', height or metric('space_xl') + metric('space_l'), parent)
        self.setObjectName(role)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)


def animate(owner, duration, callback, start=0.0, end=1.0, easing=QEasingCurve.OutCubic, finished=None, delay=0):
    """Tween ``callback(value)`` on ``owner``; jumps to the end when motion is reduced."""
    animation = QVariantAnimation(owner)
    animation.setStartValue(float(start))
    animation.setEndValue(float(end))
    animation.setDuration(max(1, duration))
    animation.setEasingCurve(easing)
    animation.valueChanged.connect(lambda value: callback(float(value)))
    if finished:
        animation.finished.connect(finished)
    if reduced_motion(owner.window() if isinstance(owner, QWidget) else None):
        callback(float(end))
        if finished:
            finished()
        animation.deleteLater()
        return None
    if delay:
        QTimer.singleShot(delay, owner, animation.start)
    else:
        animation.start()
    return animation


@lru_cache(maxsize=96)
def _unit_blob(sides, depth):
    """Cookie of radius 1 whose ripple ``depth`` can fall to 0 (a circle): shapes settle as they finish."""
    path = QPainterPath()
    steps = max(48, sides * 24)
    for index in range(steps + 1):
        angle = index / steps * 2 * math.pi
        radius = 1 - depth + depth * (1 + math.cos(sides * angle)) / 2
        point = QPointF(math.cos(angle - math.pi / 2) * radius, math.sin(angle - math.pi / 2) * radius)
        path.lineTo(point) if index else path.moveTo(point)
    path.closeSubpath()
    return path


def blob(rect, sides, depth, rotation=0.0):
    from PySide6.QtGui import QTransform
    rect = QRectF(rect)
    transform = QTransform()
    transform.translate(rect.center().x(), rect.center().y())
    transform.rotate(rotation)
    transform.scale(rect.width() / 2, rect.height() / 2)
    return transform.map(_unit_blob(sides, round(depth, 3)))


def focus_ring(painter, rect, radius):
    painter.setPen(QPen(color('focus'), max(2, tokens()['focus_width'] + 1)))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), radius, radius)


def wrapped_height(font, text, width):
    if not text:
        return 0
    return QFontMetrics(font).boundingRect(QRect(0, 0, max(1, int(width)), 100000), Qt.TextWordWrap, text).height()


class Entrance:
    """Rows fade and rise a few pixels, staggered, whenever their page is entered (launcher ResultRow)."""

    def init_entrance(self):
        self.enter_amount = 1.0
        self._entrance = None

    def enter(self, order=0):
        if reduced_motion(self.window()):
            self.enter_amount = 1.0
            self.update()
            return
        self.enter_amount = 0.0
        self.update()

        def step(value):
            self.enter_amount = value
            self.update()
        self._entrance = animate(self, tokens()['motion_enter'], step, delay=min(order, 12) * 28)

    def apply_entrance(self, painter):
        if self.enter_amount < 1:
            painter.setOpacity(min(1.0, self.enter_amount * 1.4))
            painter.translate(0, (1 - self.enter_amount) * metric('space_m'))


class Card(QWidget):
    """Rounded tonal container (``surface_raised``, ``well``, ``nav_selected``…)."""

    def __init__(self, tone='surface_raised', parent=None, radius='radius_l'):
        super().__init__(parent)
        self.tone, self.radius = tone, radius

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color(self.tone))
        radius = tokens()[self.radius]
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)


class Panel(Card):
    """The single raised surface of the window, like Music's main panel."""

    def __init__(self, parent=None):
        super().__init__('surface', parent)


class Material(QWidget):
    """Window background: the same glass/pearl/mica material Music and Files paint."""

    def paintEvent(self, _event):
        paint_surface(self)


# --------------------------------------------------------------------------- switch / rows
def paint_switch(painter, rect, amount, enabled=True, locked=False):
    """M3 switch: an outlined track with a small thumb that grows into a check when on."""
    rect = QRectF(rect)
    radius = rect.height() / 2
    painter.setPen(Qt.NoPen)
    on = color('accent' if enabled else 'accent_disabled')
    off = color('fill')
    track = QColor(off)
    track.setRedF(off.redF() + (on.redF() - off.redF()) * amount)
    track.setGreenF(off.greenF() + (on.greenF() - off.greenF()) * amount)
    track.setBlueF(off.blueF() + (on.blueF() - off.blueF()) * amount)
    track.setAlphaF(off.alphaF() + (on.alphaF() - off.alphaF()) * amount)
    painter.setBrush(track)
    painter.drawRoundedRect(rect, radius, radius)
    if amount < 1:
        painter.setPen(QPen(color('line_strong', round(255 * (1 - amount))), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
    small, large = rect.height() * .5, rect.height() - 8
    side = small + (large - small) * amount
    x = rect.left() + radius + (rect.width() - 2 * radius) * amount
    thumb = QRectF(x - side / 2, rect.center().y() - side / 2, side, side)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color('on_accent' if amount > .5 else 'glyph_muted'))
    painter.drawEllipse(thumb)
    if amount > .5:
        paint_symbol(painter, thumb, 'lock' if locked else 'check', 'accent' if enabled else 'disabled', side * .7)


class ToggleRow(Entrance, QAbstractButton):
    """A choice with its explanation: leading shape, title, detail, optional note and a switch.

    ``locked`` keeps it on and explains why (``note``); the whole row is one keyboard target.
    """

    def __init__(self, symbol, title, detail='', parent=None, compact=False):
        super().__init__(parent)
        self.init_entrance()
        self.symbol, self.title, self.detail, self.note = symbol, title, detail, ''
        self.compact = compact
        self.locked = False
        self.layer = StateLayer(self)
        self.knob = StateLayer(self)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self.setAccessibleDescription(detail)
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.toggled.connect(lambda on: self.knob.to(1.0 if on else 0.0))

    def set_state(self, checked, enabled=True, locked=False, note=''):
        changed = (checked, locked, note) != (self.isChecked(), self.locked, self.note)
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self.knob.to(1.0 if checked else 0.0)
        self.locked, self.note = locked, note
        self.setEnabled(enabled and not locked)
        self.setFocusPolicy(Qt.StrongFocus if enabled and not locked else Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor if enabled and not locked else Qt.ArrowCursor)
        if changed:
            self.updateGeometry()
        self.update()

    def _metrics(self):
        pad = metric('space_m') if self.compact else metric('space_l')
        lead = 0 if self.compact else metric('icon_size') * 2 + metric('space_s')
        switch = QSize(metric('space_xl') * 2 + metric('space_xs'), metric('space_xl') + metric('space_s'))
        return pad, lead, switch

    def _text_width(self, width):
        pad, lead, switch = self._metrics()
        return width - pad * 2 - lead - (metric('space_l') if lead else 0) - switch.width() - metric('space_l')

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        pad, _lead, switch = self._metrics()
        inner = self._text_width(width)
        height = QFontMetrics(text_font('body', 600)).height()
        if self.detail:
            height += metric('space_xs') + wrapped_height(text_font('small'), self.detail, inner)
        if self.note:
            height += metric('space_xs') + QFontMetrics(text_font('caption', 600)).height()
        return max(height, switch.height()) + pad * 2

    def sizeHint(self):
        return QSize(metric('space_xl') * 16, self.heightForWidth(metric('space_xl') * 16))

    def minimumSizeHint(self):
        # Layouts sum minimums; the real height comes from heightForWidth.
        return QSize(metric('space_xl') * 8, self.heightForWidth(metric('space_xl') * 40))

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.apply_entrance(painter)
        pad, lead, switch = self._metrics()
        rect = QRectF(self.rect())
        radius = tokens()['radius_m'] if not self.compact else tokens()['radius_control']
        on = self.isChecked()
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('nav_selected' if on and not self.compact else 'well'))
        painter.drawRoundedRect(rect, radius, radius)
        if self.layer.amount and self.isEnabled():
            painter.setBrush(color('tint', round(14 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        left = pad
        if lead:
            badge = QRectF(pad, pad, lead - metric('space_s'), lead - metric('space_s'))
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('accent' if on else 'fill'))
            painter.drawPath(squircle(badge, .35 + .65 * (1 - self.knob.amount)))
            paint_symbol(painter, badge, self.symbol, 'on_accent' if on else 'glyph', badge.height() * .52)
            left = pad + lead + metric('space_s')
        width = self._text_width(self.width())
        y = pad
        title = text_font('body', 600)
        painter.setFont(title)
        painter.setPen(color('text_strong' if self.isEnabled() or self.locked else 'disabled'))
        height = QFontMetrics(title).height()
        painter.drawText(QRectF(left, y, width, height), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(title).elidedText(self.title, Qt.ElideRight, int(width)))
        y += height
        if self.detail:
            y += metric('space_xs')
            font = text_font('small')
            painter.setFont(font)
            painter.setPen(color('muted' if self.isEnabled() or self.locked else 'disabled'))
            block = wrapped_height(font, self.detail, width)
            painter.drawText(QRectF(left, y, width, block), Qt.AlignLeft | Qt.TextWordWrap, self.detail)
            y += block
        if self.note:
            y += metric('space_xs')
            font = text_font('caption', 600)
            painter.setFont(font)
            painter.setPen(color('accent'))
            painter.drawText(QRectF(left, y, width, QFontMetrics(font).height()), Qt.AlignLeft | Qt.AlignVCenter, self.note)
        track = QRectF(rect.right() - pad - switch.width(), (rect.height() - switch.height()) / 2,
                       switch.width(), switch.height())
        paint_switch(painter, track, self.knob.amount, self.isEnabled() or self.locked, self.locked)
        if self.hasFocus() and self.window().isActiveWindow():
            focus_ring(painter, rect, radius)


class OptionTile(Entrance, QAbstractButton):
    """Compact checkable tile (optional applications): a cookie badge that turns when chosen."""

    def __init__(self, symbol, title, detail, parent=None):
        super().__init__(parent)
        self.init_entrance()
        self.symbol, self.title, self.detail = symbol, title, detail
        self.layer = StateLayer(self)
        self.pick = StateLayer(self)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self.setAccessibleDescription(detail)
        self.setMinimumHeight(metric('space_xl') * 4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(metric('space_xl') * 4 + metric('space_s'))
        self.toggled.connect(lambda on: self.pick.to(1.0 if on else 0.0))

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.apply_entrance(painter)
        rect = QRectF(self.rect())
        radius = tokens()['radius_m']
        on = self.pick.amount
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('nav_selected' if self.isChecked() else 'well'))
        painter.drawRoundedRect(rect, radius, radius)
        if self.layer.amount and self.isEnabled():
            painter.setBrush(color('tint', round(14 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        pad = metric('space_m')
        side = metric('icon_size') * 2
        badge = QRectF(pad, pad, side, side)
        painter.setBrush(color('accent') if self.isChecked() else color('fill'))
        painter.drawPath(cookie(badge, 9, 40 * on + 12 * self.layer.amount))
        paint_symbol(painter, badge, 'check' if self.isChecked() else self.symbol,
                     'on_accent' if self.isChecked() else 'glyph', side * .5, filled=self.isChecked())
        painter.setFont(text_font('body', 600))
        painter.setPen(color('text_strong' if self.isEnabled() else 'disabled'))
        top = badge.bottom() + metric('space_s')
        painter.drawText(QRectF(pad, top, rect.width() - pad * 2, metric('font_body') * 1.5),
                         Qt.AlignLeft | Qt.AlignVCenter, self.title)
        painter.setFont(text_font('small'))
        painter.setPen(color('muted' if self.isEnabled() else 'disabled'))
        metrics = painter.fontMetrics()
        painter.drawText(QRectF(pad, top + metric('font_body') * 1.5, rect.width() - pad * 2, metrics.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(self.detail, Qt.ElideRight, int(rect.width() - pad * 2)))
        if self.hasFocus() and self.window().isActiveWindow():
            focus_ring(painter, rect, radius)


class Segmented(QWidget):
    """Single-choice pill group with an indicator that slides between options."""

    changed = Signal(str)

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.options = list(options)  # [(key, label)]
        self.current = self.options[0][0]
        self.position = 0.0
        self.hovered = -1
        self._slide = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setFont(text_font('body', 600))
        self.setFixedHeight(metric('space_xl') + metric('space_l'))
        self.setAccessibleName('Selección rápida')

    def sizeHint(self):
        metrics = self.fontMetrics()
        width = max(metrics.horizontalAdvance(text) for _, text in self.options) + metric('space_xl') * 2
        return QSize(width * len(self.options) + 8, self.height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def index(self, key=None):
        return next(i for i, (k, _) in enumerate(self.options) if k == (key or self.current))

    def set_current(self, key, animate_change=True):
        if key == self.current:
            return
        start, self.current = self.position, key
        end = float(self.index())
        self.setAccessibleDescription(dict(self.options)[key])
        if animate_change:
            self._slide = animate(self, tokens()['motion_enter'], self._move, start, end, QEasingCurve.OutBack)
        else:
            self._move(end)

    def _move(self, value):
        self.position = value
        self.update()

    def _slot(self, index):
        width = (self.width() - 8) / len(self.options)
        return QRectF(4 + width * index, 4, width, self.height() - 8)

    def mouseMoveEvent(self, event):
        width = (self.width() - 8) / len(self.options)
        hovered = int(max(0, min(len(self.options) - 1, (event.position().x() - 4) // width)))
        if hovered != self.hovered:
            self.hovered = hovered
            self.update()

    def leaveEvent(self, event):
        self.hovered = -1
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        width = (self.width() - 8) / len(self.options)
        index = int(max(0, min(len(self.options) - 1, (event.position().x() - 4) // width)))
        self._choose(index)

    def keyPressEvent(self, event):
        steps = {Qt.Key_Left: -1, Qt.Key_Right: 1}
        if event.key() in steps:
            self._choose(max(0, min(len(self.options) - 1, self.index() + steps[event.key()])))
        else:
            super().keyPressEvent(event)

    def _choose(self, index):
        key = self.options[index][0]
        if key != self.current:
            self.set_current(key)
            self.changed.emit(key)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('well'))
        painter.drawRoundedRect(rect, radius, radius)
        if 0 <= self.hovered != self.index():
            slot = self._slot(self.hovered)
            painter.setBrush(color('tint', 12))
            painter.drawRoundedRect(slot, slot.height() / 2, slot.height() / 2)
        indicator = self._slot(0)
        indicator.moveLeft(indicator.left() + indicator.width() * self.position)
        painter.setBrush(color('accent'))
        painter.drawRoundedRect(indicator, indicator.height() / 2, indicator.height() / 2)
        painter.setFont(self.font())
        for index, (_key, text) in enumerate(self.options):
            closeness = max(0.0, 1 - abs(self.position - index))
            painter.setPen(color('on_accent') if closeness > .5 else color('text'))
            painter.drawText(self._slot(index), Qt.AlignCenter, text)
        if self.hasFocus() and self.window().isActiveWindow():
            focus_ring(painter, rect, radius)


# --------------------------------------------------------------------------- status
# Glyphs that survive filling (no inner detail); others are drawn outlined.
SOLID = {'check', 'close', 'priority_high', 'pause', 'remove', 'download', 'refresh', 'sync', 'lock'}


class StatusMark(QWidget):
    """State as an M3 shape. ``active`` is a turning, breathing cookie; finishing settles it into a
    circle carrying a check (or a warning/error shape); ``celebrate()`` throws a few cookies outward."""

    LEVELS = {
        'ok': ('accent', 'on_accent', 'check'), 'done': ('accent', 'on_accent', 'check'),
        'warning': ('warning', 'on_accent', 'priority_high'), 'error': ('danger', 'on_accent', 'close'),
        'info': ('selection', 'selection_text', 'info'), 'cancelled': ('fill', 'glyph', 'pause'),
        'skipped': ('fill', 'glyph_muted', 'remove'),
    }

    def __init__(self, size=None, parent=None, halo=False):
        super().__init__(parent)
        self.side = size or metric('space_xl') + metric('space_xs')
        self.halo = halo
        self.level = 'pending'
        self.symbol = None
        self.angle = 0.0
        self.phase = 0.0
        self.settle = 1.0
        self.burst = 0.0
        self._timer = QTimer(self, interval=33)
        self._timer.timeout.connect(self._tick)
        extra = self.side * (1.6 if halo else 0)
        self.setFixedSize(round(self.side + extra), round(self.side + extra))

    def set_level(self, level, symbol=None):
        if level == self.level and symbol == self.symbol:
            return
        previous, self.level, self.symbol = self.level, level, symbol
        if previous == 'active' and level != 'active':
            animate(self, tokens()['motion_enter'] * 2, self._settle, 0.0, 1.0, QEasingCurve.OutBack)
        else:
            self.settle = 1.0
        self._sync()
        self.update()

    def celebrate(self):
        animate(self, 1100, self._burst, 0.0, 1.0, QEasingCurve.OutCubic)

    def _settle(self, value):
        self.settle = value
        self.update()

    def _burst(self, value):
        self.burst = value
        self.update()

    def _sync(self):
        if self.level == 'active' and self.isVisible() and not reduced_motion(self.window()):
            self._timer.start()
        else:
            self._timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self):
        self.angle = (self.angle + 3.2) % 360
        self.phase = (self.phase + .09) % (2 * math.pi)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        centre = QRectF(self.rect()).center()
        side = self.side
        box = QRectF(centre.x() - side / 2, centre.y() - side / 2, side, side)
        painter.setPen(Qt.NoPen)
        if 0 < self.burst < 1:
            # One short burst of small cookies flying outward and fading.
            for index in range(9):
                angle = index / 9 * 2 * math.pi + .3
                distance = side * (.55 + 1.05 * self.burst)
                size = side * .2 * (1 - self.burst * .6)
                point = QPointF(centre.x() + math.cos(angle) * distance, centre.y() + math.sin(angle) * distance)
                painter.setBrush(color('accent' if index % 2 else 'accent_muted', round(230 * (1 - self.burst))))
                painter.drawPath(cookie(QRectF(point.x() - size / 2, point.y() - size / 2, size, size), (4, 6, 9)[index % 3],
                                        self.burst * 160 + index * 40))
        if self.level == 'pending':
            painter.setPen(QPen(color('line_strong'), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(box.adjusted(side * .3, side * .3, -side * .3, -side * .3))
            return
        if self.level == 'active':
            if self.halo:
                painter.setBrush(color('accent', 28))
                painter.drawPath(blob(box.adjusted(-side * .28, -side * .28, side * .28, side * .28), 9, .07, -self.angle * .6))
            depth = .06 + .03 * math.sin(self.phase)
            painter.setBrush(color('accent'))
            painter.drawPath(blob(box, 12, depth, self.angle))
            if self.symbol:
                paint_symbol(painter, box, self.symbol, 'on_accent', side * .46, filled=self.symbol in SOLID)
            return
        fill, ink, glyph = self.LEVELS.get(self.level, self.LEVELS['info'])
        depth = .07 * (1 - self.settle) if self.settle < 1 else 0.0
        scale = .82 + .18 * min(1.0, self.settle)
        inner = QRectF(box.center().x() - side * scale / 2, box.center().y() - side * scale / 2, side * scale, side * scale)
        painter.setBrush(color(fill))
        if self.level == 'warning':
            painter.drawPath(squircle(inner, .2))
        elif self.level == 'error':
            painter.drawPath(cookie(inner, 4, 45))
        else:
            painter.drawPath(blob(inner, 12, depth, self.angle))
        painter.setOpacity(max(0.0, min(1.0, self.settle)))
        symbol = self.symbol or glyph
        paint_symbol(painter, inner, symbol, ink, side * .5 * min(1.15, max(.4, self.settle)), filled=symbol in SOLID)


class CheckRow(Entrance, QWidget):
    """One read-only check result: status shape, title, explanation."""

    def __init__(self, check, parent=None):
        super().__init__(parent)
        self.init_entrance()
        self.mark = StatusMark(metric('space_xl'), self)
        self.title, self.detail = check['title'], check.get('detail', '')
        self.mark.set_level(check['level'])
        self.level = check['level']
        self.setAccessibleName(self.title)
        self.setAccessibleDescription(self.detail)
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def hasHeightForWidth(self):
        return True

    def _width(self, width):
        return width - metric('space_xl') - metric('space_m') * 3

    def heightForWidth(self, width):
        height = QFontMetrics(text_font('body', 600)).height()
        if self.detail:
            height += metric('space_xs') + wrapped_height(text_font('small'), self.detail, self._width(width))
        return max(height, metric('space_xl')) + metric('space_m') * 2

    def sizeHint(self):
        return QSize(metric('space_xl') * 14, self.heightForWidth(metric('space_xl') * 14))

    def minimumSizeHint(self):
        return QSize(metric('space_xl') * 6, self.heightForWidth(metric('space_xl') * 40))

    def resizeEvent(self, event):
        self.mark.move(metric('space_m'), metric('space_m'))
        super().resizeEvent(event)

    def enter(self, order=0):
        Entrance.enter(self, order)
        self.mark.setVisible(True)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.apply_entrance(painter)
        rect = QRectF(self.rect())
        radius = tokens()['radius_m']
        tone = {'error': 'danger_soft', 'warning': 'warning_soft'}.get(self.level, 'well')
        painter.setPen(Qt.NoPen)
        painter.setBrush(color(tone))
        painter.drawRoundedRect(rect, radius, radius)
        left = metric('space_m') * 2 + metric('space_xl')
        width = self._width(self.width())
        y = metric('space_m')
        font = text_font('body', 600)
        painter.setFont(font)
        painter.setPen(color('text_strong'))
        height = QFontMetrics(font).height()
        painter.drawText(QRectF(left, y, width, height), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(font).elidedText(self.title, Qt.ElideRight, int(width)))
        if self.detail:
            font = text_font('small')
            painter.setFont(font)
            painter.setPen(color('muted'))
            y += height + metric('space_xs')
            painter.drawText(QRectF(left, y, width, wrapped_height(font, self.detail, width)),
                             Qt.AlignLeft | Qt.TextWordWrap, self.detail)


class Timeline(QWidget):
    """Phases joined by a thread: pending dots, a turning cookie for the current one, checks behind it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_phases(self, phases):
        while self.box.count():
            item = self.box.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.rows = []
        for phase in phases:
            self.add(phase)
        self.update()

    def add(self, phase, index=None):
        row = PhaseRow(phase, self)
        if index is None:
            self.rows.append(row)
            self.box.addWidget(row)
        else:
            self.rows.insert(index, row)
            self.box.insertWidget(index, row)
        return row

    def names(self):
        return [row.phase['name'] for row in self.rows]

    def enter(self):
        for order, row in enumerate(self.rows):
            row.enter(order)

    def mark(self, name, level, index_hint=None):
        """Set ``name``'s state; an unexpected stage is inserted where the installer reports it."""
        names = self.names()
        if name not in names:
            from journey import phase
            position = min(len(self.rows), index_hint if index_hint is not None else len(self.rows))
            row = self.add(phase(name), position)
            row.show()
        row = self.rows[self.names().index(name)]
        row.set_level(level)
        if level == 'active':
            position = self.rows.index(row)
            for earlier in self.rows[:position]:
                if earlier.level in ('pending', 'active'):
                    earlier.set_level('done' if earlier.level == 'active' else 'skipped')
        self.update()
        return row

    def finish(self, level):
        """Close the timeline: the running stage takes ``level``; stages never reached stay pending."""
        for row in self.rows:
            if row.level == 'active':
                row.set_level(level)
        self.update()

    def paintEvent(self, _event):
        if len(self.rows) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        x = self.rows[0].mark_centre().x()
        for first, second in zip(self.rows, self.rows[1:]):
            a = first.geometry().top() + first.mark_centre().y() + first.mark.side / 2 + 2
            b = second.geometry().top() + second.mark_centre().y() - second.mark.side / 2 - 2
            done = first.level in ('done', 'ok') and second.level not in ('pending',)
            painter.setPen(QPen(color('accent' if done else 'line'), 2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(x, a), QPointF(x, b))


class PhaseRow(Entrance, QWidget):
    def __init__(self, phase, parent=None):
        super().__init__(parent)
        self.init_entrance()
        self.phase = phase
        self.level = 'pending'
        self.mark = StatusMark(metric('space_xl'), self)
        self.mark.set_level('pending')
        self.setAccessibleName(phase['name'])
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def set_level(self, level):
        self.level = level
        self.mark.set_level(level, self.phase['symbol'] if level in ('active', 'pending') else None)
        self.setAccessibleDescription({'pending': 'Pendiente', 'active': 'En curso', 'done': 'Completada',
                                       'error': 'Con error', 'cancelled': 'Detenida', 'skipped': 'Omitida'}.get(level, ''))
        self.update()

    def mark_centre(self):
        return QPointF(metric('space_s') + metric('space_xl') / 2, metric('space_s') + metric('space_xl') / 2)

    def hasHeightForWidth(self):
        return True

    def _width(self, width):
        return width - metric('space_xl') - metric('space_s') - metric('space_l') * 2

    def heightForWidth(self, width):
        height = QFontMetrics(text_font('body', 600)).height()
        if self.phase.get('detail'):
            height += 2 + wrapped_height(text_font('small'), self.phase['detail'], self._width(width))
        return max(height, metric('space_xl')) + metric('space_s') * 2 + metric('space_xs')

    def sizeHint(self):
        return QSize(metric('space_xl') * 14, self.heightForWidth(metric('space_xl') * 14))

    def minimumSizeHint(self):
        return QSize(metric('space_xl') * 6, self.heightForWidth(metric('space_xl') * 40))

    def resizeEvent(self, event):
        self.mark.move(metric('space_s'), metric('space_s'))
        super().resizeEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.apply_entrance(painter)
        rect = QRectF(self.rect())
        if self.level == 'active':
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('nav_selected'))
            painter.drawRoundedRect(rect, tokens()['radius_m'], tokens()['radius_m'])
        left = metric('space_s') + metric('space_xl') + metric('space_l')
        width = self._width(self.width())
        y = metric('space_s')
        font = text_font('body', 600 if self.level == 'active' else 500)
        painter.setFont(font)
        painter.setPen(color('text_strong' if self.level in ('active', 'done', 'error') else
                             'muted' if self.level == 'pending' else 'subtle'))
        height = QFontMetrics(font).height()
        painter.drawText(QRectF(left, y, width, height), Qt.AlignLeft | Qt.AlignVCenter,
                         QFontMetrics(font).elidedText(self.phase['name'], Qt.ElideRight, int(width)))
        if self.phase.get('detail'):
            font = text_font('small')
            painter.setFont(font)
            painter.setPen(color('muted' if self.level != 'skipped' else 'subtle'))
            painter.drawText(QRectF(left, y + height + 2, width, wrapped_height(font, self.phase['detail'], width)),
                             Qt.AlignLeft | Qt.TextWordWrap, self.phase['detail'])


# --------------------------------------------------------------------------- navigation
class RailItem(QAbstractButton):
    """Navigation entry; the rail paints the moving selection pill behind it."""

    def __init__(self, symbol, title, parent=None):
        super().__init__(parent)
        self.symbol, self.title = symbol, title
        self.state = 'future'  # future | current | done
        self.compact = False
        self.layer = StateLayer(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self.setFixedHeight(metric('space_xl') + metric('space_m'))

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        if self.layer.amount and self.isEnabled() and self.state != 'current':
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('tint', round(12 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        current = self.state == 'current'
        ink = 'text_strong' if current else 'disabled' if not self.isEnabled() else 'text'
        icon = metric('icon_size') * 1.15
        if self.compact:
            symbol_rect = QRectF(0, 0, rect.width(), rect.height())
        else:
            symbol_rect = QRectF(metric('space_m'), 0, icon, rect.height())
        done = self.state == 'done'
        paint_symbol(painter, symbol_rect, self.symbol, 'accent' if current else ink, icon, filled=current)
        if not self.compact:
            painter.setFont(text_font('body', 600 if current else 500))
            painter.setPen(color(ink))
            left = symbol_rect.right() + metric('space_m')
            painter.drawText(QRectF(left, 0, rect.width() - left - metric('space_xl'), rect.height()),
                             Qt.AlignLeft | Qt.AlignVCenter, self.title)
        if done:
            side = metric('icon_size')
            dot = QRectF(rect.right() - side - metric('space_s'), (rect.height() - side) / 2, side, side)
            if self.compact:
                dot = QRectF(rect.center().x() + icon * .3, rect.center().y() - icon * .95, side * .7, side * .7)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('accent'))
            painter.drawEllipse(dot)
            paint_symbol(painter, dot, 'check', 'on_accent', dot.height() * .75, filled=True)
        if self.hasFocus() and self.window().isActiveWindow():
            focus_ring(painter, rect, radius)


class Rail(QWidget):
    """Vertical journey: items over one selection pill that glides to the current step."""

    selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.current = 0
        self.pill = QRectF()
        self._glide = None
        self.compact = False
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(2)

    def set_items(self, entries):
        for item in self.items:
            item.hide()
            item.deleteLater()
        self.items = []
        for index, (symbol, title) in enumerate(entries):
            item = RailItem(symbol, title, self)
            item.compact = self.compact
            item.clicked.connect(lambda _=False, i=index: self.selected.emit(i))
            self.box.addWidget(item)
            self.items.append(item)

    def set_compact(self, compact):
        self.compact = compact
        for item in self.items:
            item.compact = compact
            item.setToolTip(item.title if compact else '')
            item.update()
        QTimer.singleShot(0, lambda: self.set_current(self.current, False))

    def set_current(self, index, animate_change=True, reachable=None):
        self.current = index
        for i, item in enumerate(self.items):
            item.state = 'current' if i == index else 'done' if i < index else 'future'
            if reachable is not None:
                item.setEnabled(i in reachable or i == index)
            item.update()
        if not self.items:
            return
        target = QRectF(self.items[index].geometry())
        if self.pill.isNull() or not animate_change or not self.isVisible():
            self.pill = target
            self.update()
            return
        start = QRectF(self.pill)

        def step(value):
            # Stretch toward the target first, then let the trailing edge follow (launcher highlight).
            lead = min(1.0, value * 1.35)
            tail = max(0.0, value * 1.35 - .35)
            top = start.top() + (target.top() - start.top()) * (lead if target.top() < start.top() else tail)
            bottom = start.bottom() + (target.bottom() - start.bottom()) * (lead if target.top() > start.top() else tail)
            self.pill = QRectF(target.left(), top, target.width(), bottom - top)
            self.update()
        self._glide = animate(self, tokens()['motion_enter'] + 80, step)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.items:
            QTimer.singleShot(0, lambda: self.set_current(self.current, False))

    def paintEvent(self, _event):
        if self.pill.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('nav_selected'))
        radius = min(self.pill.height(), self.pill.width()) / 2
        painter.drawRoundedRect(self.pill, radius, radius)


class PageStack(QWidget):
    """Pages that slide a few pixels in the direction of travel while the previous one fades out."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pages = []
        self.index = -1
        self.ghost = QPixmap()
        self.ghost_amount = 0.0
        self.direction = 1
        self._motion = None
        self._overlay = _Ghost(self)
        self._overlay.hide()

    def add(self, page):
        page.setParent(self)
        page.hide()
        self.pages.append(page)
        return len(self.pages) - 1

    def current(self):
        return self.pages[self.index] if 0 <= self.index < len(self.pages) else None

    def set_current(self, index, direction=1, animate_change=True):
        previous = self.current()
        if index == self.index and previous is not None:
            return
        page = self.pages[index]
        motion = animate_change and previous is not None and self.isVisible() and not reduced_motion(self.window())
        if motion:
            self._overlay.pixmap = previous.grab()
            self._overlay.setGeometry(self.rect())
            self._overlay.show()
            self._overlay.raise_()
        if previous is not None:
            previous.hide()
        self.index, self.direction = index, direction
        page.setGeometry(self.rect())
        page.show()
        if not motion:
            self._overlay.hide()
            return
        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        shift = metric('space_xl') * 2
        overlay = self._overlay

        def step(value):
            if page.graphicsEffect() is effect:
                effect.setOpacity(value)
            page.move(round((1 - value) * shift * direction), 0)
            overlay.amount = 1 - value
            overlay.offset = -value * shift * direction * .5
            overlay.update()

        def done():
            page.move(0, 0)
            if page.graphicsEffect() is effect:
                page.setGraphicsEffect(None)
            overlay.hide()
        if self._motion is not None:
            self._motion.stop()
        self._motion = animate(self, tokens()['motion_enter'] + 60, step, finished=done)

    def resizeEvent(self, event):
        page = self.current()
        if page is not None:
            page.setGeometry(self.rect())
        self._overlay.setGeometry(self.rect())
        super().resizeEvent(event)


class _Ghost(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.pixmap = QPixmap()
        self.amount = 1.0
        self.offset = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _event):
        if self.pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setOpacity(max(0.0, self.amount))
        painter.drawPixmap(QPointF(self.offset, 0), self.pixmap)


class Crossfade(QWidget):
    """A snapshot of the whole window fading away: theme changes dissolve instead of flashing."""

    def __init__(self, host):
        super().__init__(host)
        self.pixmap = host.grab()
        self.amount = 1.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(host.rect())
        self.show()
        self.raise_()
        animate(self, tokens()['motion_enter'] * 2, self._step, 1.0, 0.0, QEasingCurve.InOutCubic, self.deleteLater)

    def _step(self, value):
        self.amount = value
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setOpacity(self.amount)
        painter.drawPixmap(0, 0, self.pixmap)


# --------------------------------------------------------------------------- sheet
class Sheet(QWidget):
    """Modal card over a scrim inside the window (Files' sheets). Esc closes it."""

    closed = Signal()

    def __init__(self, host, title, width=None):
        super().__init__(host)
        self.host = host
        self.amount = 0.0
        self.closing = False
        self.card = Card('surface_raised', self)
        self.card.setAttribute(Qt.WA_StyledBackground, False)
        self.body = QVBoxLayout(self.card)
        pad = metric('space_xl')
        self.body.setContentsMargins(pad, pad, pad, metric('space_l'))
        self.body.setSpacing(metric('space_m'))
        heading = label(title, 'section')
        heading.setAccessibleName(title)
        self.body.addWidget(heading)
        self.card_width = width or metric('space_xl') * 20
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        host.installEventFilter(self)

    def open(self):
        self.setGeometry(self.host.rect())
        self._layout()
        self.show()
        self.raise_()
        self.previous_focus = self.host.focusWidget()
        animate(self, tokens()['motion_enter'], self._step)
        candidates = [w for w in self.card.findChildren(QAbstractButton) if w.isEnabled() and w.focusPolicy() != Qt.NoFocus]
        (candidates[-1] if candidates else self).setFocus(Qt.PopupFocusReason)
        return self

    def close_sheet(self):
        if self.closing:
            return
        self.closing = True
        animate(self, tokens()['motion_exit'], self._step, self.amount, 0.0, QEasingCurve.InCubic, self._closed)

    def _closed(self):
        self.hide()
        self.closed.emit()
        if getattr(self, 'previous_focus', None) is not None:
            try:
                self.previous_focus.setFocus()
            except RuntimeError:
                pass
        self.deleteLater()

    def _step(self, value):
        self.amount = value
        self._layout()
        self.update()

    def _layout(self):
        width = min(self.card_width, self.width() - metric('space_xl') * 2)
        self.card.setFixedWidth(width)
        height = min(self.card.sizeHint().height(), self.height() - metric('space_xl') * 2)
        self.card.setFixedHeight(max(height, metric('space_xl') * 4))
        x = (self.width() - width) / 2
        y = (self.height() - self.card.height()) / 2 + (1 - self.amount) * metric('space_xl')
        self.card.move(round(x), round(y))

    def eventFilter(self, watched, event):
        if watched is self.host and event.type() == QEvent.Resize and self.isVisible():
            self.setGeometry(self.host.rect())
            self._layout()
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_sheet()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if not self.card.geometry().contains(event.position().toPoint()):
            self.close_sheet()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), color('scrim', round(color('scrim').alpha() * .8 * self.amount)))
        painter.setOpacity(self.amount)


# --------------------------------------------------------------------------- progress
class WaveBar(QWidget):
    """Progress as Music's wavy line: the wave runs while work runs and flattens when it stops.
    ``value`` None is indeterminate: a short wave segment sweeps along the track."""

    WAVE_LENGTH = 26.0
    WAVE_AMPLITUDE = 2.6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = None
        self.shown = 0.0
        self.running = False
        self.phase = 0.0
        self.wave = 0.0
        self.sweep = 0.0
        self._timer = QTimer(self, interval=33)
        self._timer.timeout.connect(self._tick)
        self.setFixedHeight(metric('space_l') + metric('space_xs'))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName('Progreso de la instalación')

    def set_progress(self, value, running=True):
        self.value = None if value is None else max(0.0, min(1.0, value))
        self.running = running
        if value is not None and reduced_motion(self.window()):
            self.shown = self.value
        self.setAccessibleDescription('' if value is None else f'{round(value * 100)} %')
        self._sync()
        self.update()

    def _sync(self):
        if self.isVisible() and not reduced_motion(self.window()) and (self.running or self.wave > 0 or
                                                                       (self.value is not None and abs(self.shown - self.value) > .001)):
            self._timer.start()
        else:
            self._timer.stop()
            if reduced_motion(self.window()):
                self.wave = 1.0 if self.running else 0.0
            if self.value is not None:
                self.shown = self.value

    def showEvent(self, event):
        super().showEvent(event)
        self._sync()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self):
        target = 1.0 if self.running else 0.0
        self.wave += (target - self.wave) * .12
        if abs(target - self.wave) < .02:
            self.wave = target
        if self.value is not None:
            self.shown += (self.value - self.shown) * .12
        self.phase = (self.phase + .19) % (2 * math.pi)
        self.sweep = (self.sweep + .011) % 1.0
        self.update()
        if not self.running and not self.wave and (self.value is None or abs(self.shown - self.value) < .001):
            self._timer.stop()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        thickness = 4
        y = self.height() / 2
        start, end = thickness, self.width() - thickness
        span = end - start
        if self.value is None:
            head = start + span * self.sweep
            tail = max(start, head - span * .28)
            segments = [(tail, head)]
            painter.setPen(QPen(color('track'), thickness, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(start, y), QPointF(end, y))
        else:
            x = start + span * self.shown
            segments = [(start, x)] if x > start + .5 else []
            if x + 6 < end:
                painter.setPen(QPen(color('track'), thickness, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(QPointF(min(end, x + 6), y), QPointF(end, y))
            # M3 stop indicator at the end of the track.
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('accent'))
            painter.drawEllipse(QPointF(end, y), 2, 2)
        amplitude = self.WAVE_AMPLITUDE * (self.wave if self.value is not None else 1.0)
        painter.setPen(QPen(color('accent'), thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        for a, b in segments:
            if amplitude > .05:
                path = QPainterPath(QPointF(a, y + math.sin((a - start) / self.WAVE_LENGTH * 2 * math.pi - self.phase) * amplitude))
                position = a
                while position < b:
                    position = min(b, position + 2)
                    angle = (position - start) / self.WAVE_LENGTH * 2 * math.pi - self.phase
                    path.lineTo(position, y + math.sin(angle) * amplitude)
                painter.drawPath(path)
            else:
                painter.drawLine(QPointF(a, y), QPointF(b, y))


class LogView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(4000)
        self.setAccessibleName('Registro de la operación')
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)


class Keycaps(QWidget):
    """Key chord drawn as caps (launcher Keycaps.qml)."""

    def __init__(self, keys, parent=None):
        super().__init__(parent)
        self.keys = list(keys)
        self.setFont(text_font('small', 600))
        self.setAccessibleName(' + '.join(self.keys))
        self.setFixedHeight(metric('space_xl') + metric('space_xs'))

    def sizeHint(self):
        metrics = self.fontMetrics()
        pad = metric('space_s')
        width = sum(max(metrics.horizontalAdvance(key) + pad * 2, self.height()) for key in self.keys)
        return QSize(round(width + metric('space_xs') * (len(self.keys) - 1)), self.height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self.font())
        metrics = self.fontMetrics()
        pad = metric('space_s')
        x = 0.0
        for key in self.keys:
            width = max(metrics.horizontalAdvance(key) + pad * 2, self.height())
            cap = QRectF(x, 0, width, self.height() - 3)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('line_strong'))
            painter.drawRoundedRect(cap.translated(0, 3), tokens()['radius_s'], tokens()['radius_s'])
            painter.setBrush(color('surface_raised'))
            painter.drawRoundedRect(cap, tokens()['radius_s'], tokens()['radius_s'])
            painter.setPen(color('text'))
            painter.drawText(cap, Qt.AlignCenter, key)
            x += width + metric('space_xs')


# --------------------------------------------------------------------------- cards and art
@lru_cache(maxsize=8)
def thumbnail(path, width=720):
    """A wallpaper decoded at preview size once, shared by every tile and window."""
    from PySide6.QtGui import QImageReader
    reader = QImageReader(path)
    size = reader.size()
    if size.isValid() and size.width() > width:
        reader.setScaledSize(QSize(width, round(size.height() * width / size.width())))
    image = reader.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


def wallpaper_path(source, values):
    for root in (Path(source) / 'assets/backgrounds', RUNTIME / 'backgrounds'):
        if (root / values['wallpaper']).is_file():
            return str(root / values['wallpaper'])
    return None


class ActionCard(QAbstractButton):
    """Music's feature card: eyebrow, title, line, and a cookie badge that turns with the hover."""

    def __init__(self, symbol, eyebrow, title, subtitle, accent=False, parent=None):
        super().__init__(parent)
        self.symbol, self.eyebrow, self.title, self.subtitle, self.accent = symbol, eyebrow, title, subtitle, accent
        self.layer = StateLayer(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)
        self.setMinimumHeight(metric('space_xl') * 6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = tokens()['radius_l']
        if self.isDown():
            painter.translate(rect.center())
            painter.scale(.985, .985)
            painter.translate(-rect.center())
        shape = QPainterPath()
        shape.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(shape)
        ink, soft = ('on_accent', 'on_accent') if self.accent else ('text_strong', 'muted')
        painter.fillRect(rect, color('accent' if self.accent else 'nav_selected'))
        painter.fillRect(rect, color('tint', round(10 * self.layer.amount)))
        pad = metric('space_l')
        side = min(self.height() * .62, self.width() * .42)
        badge = QRectF(self.width() - side - pad * .6, self.height() - side - pad * .6, side, side)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('on_accent' if self.accent else 'accent', 40 if self.accent else 52))
        painter.drawPath(cookie(badge, 12 if self.accent else 7, 20 * self.layer.amount))
        paint_symbol(painter, badge, self.symbol, ink, side * .42, filled=self.symbol in SOLID)
        painter.restore()
        width = self.width() - pad * 2
        y = pad
        font = text_font('caption', 700)
        font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1.1)
        painter.setFont(font)
        painter.setPen(color(soft))
        painter.drawText(QRectF(pad, y, width, 18), Qt.AlignLeft | Qt.AlignVCenter, self.eyebrow.upper())
        y += 22
        painter.setFont(text_font('title', 750, .95))
        painter.setPen(color(ink))
        metrics = painter.fontMetrics()
        title = QRectF(pad, y, width - side * .35, metrics.height() * 2 + 4)
        painter.drawText(title, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.title)
        bounds = metrics.boundingRect(title.toRect(), Qt.AlignLeft | Qt.TextWordWrap, self.title)
        painter.setFont(text_font('small', 500))
        painter.setPen(color(soft))
        block = QRectF(pad, min(bounds.bottom(), title.bottom()) + metric('space_xs'), width - side * .55,
                       self.height() - bounds.bottom() - pad)
        painter.drawText(block, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.subtitle)
        if self.hasFocus() and self.window().isActiveWindow():
            focus_ring(painter, rect, radius)


class Hero(QWidget):
    """Welcome art: the active wallpaper softened, Music's drifting shapes and a turning cookie
    with the W; the shapes lean toward the pointer."""

    def __init__(self, source, parent=None, compact=False):
        super().__init__(parent)
        self.source = source
        self.compact = compact
        self.drift = Drift(count=13, seed=11)
        self.angle = 0.0
        self.lean = QPointF()
        self.target = QPointF()
        self._timer = QTimer(self, interval=40)
        self._timer.timeout.connect(self._tick)
        self.setMouseTracking(True)
        self.setMinimumHeight(metric('space_xl') * (7 if compact else 9))
        self.setAccessibleName('Wysun')

    def showEvent(self, event):
        super().showEvent(event)
        if not reduced_motion(self.window()):
            self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def mouseMoveEvent(self, event):
        point = event.position()
        self.target = QPointF((point.x() / max(1, self.width()) - .5), (point.y() / max(1, self.height()) - .5))

    def leaveEvent(self, event):
        self.target = QPointF()
        super().leaveEvent(event)

    def _tick(self):
        self.drift.step(.04)
        self.angle = (self.angle - 360 * .04 / 23.5) % 360
        self.lean += (self.target - self.lean) * .08
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        values = tokens()
        rect = QRectF(self.rect())
        radius = values['radius_l']
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)
        painter.fillRect(rect, color('surface_raised'))
        path = wallpaper_path(self.source, values)
        backdrop = blurred(path, self.width(), self.height()) if path else None
        if backdrop is not None:
            painter.drawPixmap(self.rect(), backdrop)
        painter.fillRect(rect, color('surface', 120))
        painter.drawTiledPixmap(self.rect(), grain_tile())
        painter.save()
        painter.translate(self.lean.x() * metric('space_xl'), self.lean.y() * metric('space_xl'))
        self.drift.paint(painter, rect.adjusted(-40, -40, 40, 40), color('accent', 120), .55)
        painter.restore()
        side = min(self.height() * .58, self.width() * .34)
        centre = rect.center() + QPointF(self.lean.x() * metric('space_m'), self.lean.y() * metric('space_m'))
        mark = QRectF(centre.x() - side / 2, centre.y() - side / 2, side, side)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('shadow'))
        painter.drawPath(cookie(mark.translated(0, side * .05), 12, self.angle))
        painter.setBrush(color('accent'))
        painter.drawPath(cookie(mark, 12, self.angle))
        font = text_font('title', 800, side / max(1, metric('font_title')) * .42)
        painter.setFont(font)
        painter.setPen(color('on_accent'))
        painter.drawText(mark, Qt.AlignCenter, 'W')


class FlowGrid(QWidget):
    """Equal-width cells in as many columns as fit (``minimum`` each), heights by heightForWidth."""

    def __init__(self, minimum, parent=None, maximum_columns=3):
        super().__init__(parent)
        self.cells = []
        self.minimum = minimum
        self.maximum_columns = maximum_columns
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def add(self, widget):
        widget.setParent(self)
        self.cells.append(widget)
        self.updateGeometry()

    def _columns(self, width):
        gap = metric('space_m')
        return max(1, min(self.maximum_columns, int((width + gap) // (self.minimum + gap))))

    def _cell(self, width):
        gap = metric('space_m')
        columns = self._columns(width)
        return (width - gap * (columns - 1)) / columns

    def _row_height(self, width):
        cell = self._cell(width)
        return max((w.heightForWidth(int(cell)) if w.hasHeightForWidth() else max(w.sizeHint().height(), w.minimumHeight()))
                   for w in self.cells) if self.cells else 0

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        if not self.cells:
            return 0
        rows = math.ceil(len(self.cells) / self._columns(width))
        return round(rows * self._row_height(width) + (rows - 1) * metric('space_m'))

    def sizeHint(self):
        return QSize(self.minimum * 2, self.heightForWidth(self.minimum * 2))

    def minimumSizeHint(self):
        return QSize(self.minimum, self.heightForWidth(self.minimum * self.maximum_columns + metric('space_m') * 2))

    def resizeEvent(self, event):
        width = self.width()
        gap = metric('space_m')
        columns = self._columns(width)
        cell = self._cell(width)
        height = self._row_height(width)
        for index, widget in enumerate(self.cells):
            row, column = divmod(index, columns)
            widget.setGeometry(round(column * (cell + gap)), round(row * (height + gap)), round(cell), round(height))
        super().resizeEvent(event)


class StatTile(Card):
    """A figure and its caption (plan summary)."""

    def __init__(self, value, caption, parent=None):
        super().__init__('well', parent, 'radius_m')
        self.value, self.caption = str(value), caption
        self.setMinimumWidth(metric('space_xl') * 4)
        self.setFixedHeight(metric('space_xl') * 3 + metric('space_s'))
        self.setAccessibleName(f'{value} {caption}')

    def set_value(self, value):
        self.value = str(value)
        self.setAccessibleName(f'{value} {self.caption}')
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pad = metric('space_m')
        painter.setFont(text_font('title', 750, 1.1))
        painter.setPen(color('text_strong'))
        top = QRectF(pad, pad, self.width() - pad * 2, self.height() * .55 - pad / 2)
        painter.drawText(top, Qt.AlignLeft | Qt.AlignBottom, self.value)
        painter.setFont(text_font('small', 500))
        painter.setPen(color('muted'))
        painter.drawText(QRectF(pad, top.bottom() + 2, self.width() - pad * 2, metric('space_l') + 2),
                         Qt.AlignLeft | Qt.AlignVCenter, self.caption)


class IdentityCard(Card):
    """The detected system: a cookie with its initial, name, architecture and compatibility."""

    def __init__(self, parent=None):
        super().__init__('nav_selected', parent)
        self.name, self.detail, self.initial, self.ok = '', '', '', None
        self.setFixedHeight(metric('space_xl') * 4 + metric('space_s'))

    def set_system(self, name, detail, initial, ok):
        self.name, self.detail, self.initial, self.ok = name, detail, initial, ok
        self.setAccessibleName(name)
        self.setAccessibleDescription(detail)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pad = metric('space_l')
        side = self.height() - pad * 2
        badge = QRectF(pad, pad, side, side)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('accent'))
        painter.drawPath(cookie(badge, 9))
        painter.setFont(text_font('title', 800, 1.2))
        painter.setPen(color('on_accent'))
        painter.drawText(badge, Qt.AlignCenter, self.initial)
        left = badge.right() + pad
        chip_text = {True: 'Compatible', False: 'No compatible', None: 'Comprobando'}[self.ok]
        painter.setFont(text_font('small', 650))
        chip_width = painter.fontMetrics().horizontalAdvance(chip_text) + pad * 2
        chip = QRectF(self.width() - pad - chip_width, (self.height() - metric('space_xl')) / 2, chip_width, metric('space_xl'))
        painter.setBrush(color({True: 'accent', False: 'danger', None: 'fill'}[self.ok]))
        painter.drawRoundedRect(chip, chip.height() / 2, chip.height() / 2)
        painter.setPen(color('on_accent' if self.ok is not None else 'text'))
        painter.drawText(chip, Qt.AlignCenter, chip_text)
        width = chip.left() - left - pad
        painter.setFont(text_font('heading', 700, 1.15))
        painter.setPen(color('text_strong'))
        metrics = painter.fontMetrics()
        painter.drawText(QRectF(left, pad, width, side * .55), Qt.AlignLeft | Qt.AlignBottom,
                         metrics.elidedText(self.name, Qt.ElideRight, int(width)))
        painter.setFont(text_font('body'))
        painter.setPen(color('muted'))
        metrics = painter.fontMetrics()
        painter.drawText(QRectF(left, pad + side * .58, width, side * .42), Qt.AlignLeft | Qt.AlignTop,
                         metrics.elidedText(self.detail, Qt.ElideRight, int(width)))


class InstalledCard(QAbstractButton):
    """Maintenance hero, Music's «resume» card: wallpaper backdrop, the W cookie and a round action."""

    def __init__(self, source, title, subtitle, parent=None):
        super().__init__(parent)
        self.source, self.title, self.subtitle = source, title, subtitle
        self.layer = StateLayer(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('Actualizar Wysun')
        self.setAccessibleDescription(subtitle)
        self.setFixedHeight(metric('space_xl') * 8)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def enterEvent(self, event):
        self.layer.to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.layer.to(0.0)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.click()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        radius = tokens()['radius_l']
        shape = QPainterPath()
        shape.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(shape)
        painter.fillRect(rect, color('surface_raised'))
        path = wallpaper_path(self.source, tokens())
        backdrop = blurred(path, self.width(), self.height()) if path else None
        if backdrop is not None:
            painter.drawPixmap(self.rect(), backdrop)
        painter.fillRect(rect, color('surface', 150))
        painter.restore()
        pad = metric('space_l')
        side = self.height() - pad * 2
        art = QRectF(pad, pad, side, side)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('shadow'))
        painter.drawRoundedRect(art.translated(0, 4), tokens()['radius_m'], tokens()['radius_m'])
        painter.setBrush(color('accent'))
        painter.drawRoundedRect(art, tokens()['radius_m'], tokens()['radius_m'])
        painter.setBrush(color('on_accent', 40))
        painter.drawPath(cookie(art.adjusted(side * .16, side * .16, -side * .16, -side * .16), 12, 15 * self.layer.amount))
        painter.setFont(text_font('title', 800, side / max(1, metric('font_title')) * .3))
        painter.setPen(color('on_accent'))
        painter.drawText(art, Qt.AlignCenter, 'W')
        left = art.right() + pad
        width = self.width() - left - pad - metric('space_xl') * 2
        font = text_font('caption', 700)
        font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1.1)
        painter.setFont(font)
        painter.setPen(color('text'))
        painter.drawText(QRectF(left, pad, width, 18), Qt.AlignLeft | Qt.AlignVCenter, 'INSTALADO')
        painter.setFont(text_font('title', 800, 1.05))
        painter.setPen(color('text_strong'))
        title = QRectF(left, pad + 22, width, painter.fontMetrics().height() * 2 + 4)
        painter.drawText(title, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.title)
        bounds = painter.fontMetrics().boundingRect(title.toRect(), Qt.AlignLeft | Qt.TextWordWrap, self.title)
        painter.setFont(text_font('body', 500))
        painter.setPen(color('text'))
        painter.drawText(QRectF(left, bounds.bottom() + metric('space_xs'), width, self.height() - bounds.bottom() - pad),
                         Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.subtitle)
        button = QRectF(self.width() - pad - 52, self.height() - pad - 52, 52, 52)
        painter.setBrush(color('accent'))
        painter.drawEllipse(button)
        if self.layer.amount:
            painter.setBrush(color('tint', round(18 * self.layer.amount)))
            painter.drawEllipse(button)
        painter.save()
        painter.translate(button.center())
        painter.rotate(-180 * self.layer.amount)
        painter.translate(-button.center())
        paint_symbol(painter, button, 'refresh', 'on_accent', button.height() * .5, filled=True)
        painter.restore()
        if self.hasFocus() and self.window().isActiveWindow():
            focus_ring(painter, rect, radius)


class ShortcutRow(QWidget):
    def __init__(self, keys, action, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(metric('space_m'))
        row.addWidget(Keycaps(keys))
        row.addWidget(label(action, 'strong', False), 1)

    def hasHeightForWidth(self):
        return False


class Expander(QWidget):
    """A tonal toggle that unfolds its content with a height animation."""

    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self.title = title
        self.content = content
        self.open = False
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(metric('space_m'))
        self.toggle = Button(title, self.flip, symbol='expand_more', height=metric('space_xl') + metric('space_m'))
        self.toggle.setAccessibleDescription('Plegado')
        from PySide6.QtWidgets import QHBoxLayout
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.toggle)
        row.addStretch()
        box.addLayout(row)
        box.addWidget(content)
        content.setMaximumHeight(0)
        content.hide()

    def flip(self):
        self.set_open(not self.open)

    def set_open(self, value):
        if value == self.open:
            return
        self.open = value
        self.toggle.set_content('expand_less' if value else 'expand_more', self.title)
        self.toggle.setAccessibleDescription('Desplegado' if value else 'Plegado')
        content = self.content
        if value:
            content.show()
        target = content.sizeHint().height() if value else 0
        start = content.height() if content.isVisible() else 0

        def step(height):
            content.setMaximumHeight(round(height))

        def done():
            if self.open:
                content.setMaximumHeight(16777215)
            else:
                content.hide()
        animate(self, tokens()['motion_enter'], step, start, target, finished=done)


class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, _event):
        QPainter(self).fillRect(self.rect(), color('divider'))


def reveal(widget):
    """Compatibility: pages now animate through PageStack."""
    return None

"""Restrained file-manager motion without geometry or focus changes.

SoftButton expects transparent default/hover/pressed QSS surfaces. Native button
painting still owns text, icons, checked state, borders and keyboard focus.
Menus fade in only: delaying QMenu dismissal can interfere with native input
and action delivery, so closing deliberately retains Qt's immediate behavior.
"""
import configparser
import os
from pathlib import Path
import time

from PySide6.QtCore import QEvent, QEasingCurve, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QPushButton

from ui_appearance import read_appearance
from files_visuals import TOKENS, COLORS

_gtk_cache = (0.0, False)


def reduced_motion():
    """Cheap, cached reads of local preferences; never launch desktop processes."""
    global _gtk_cache
    if any(os.environ.get(key, '').lower() in ('1', 'true', 'yes')
           for key in ('QT_REDUCE_MOTION', 'ORBIT_REDUCED_MOTION')):
        return True
    app = QApplication.instance()
    if read_appearance().get('reduced_motion') or (app and app.property('orbitReducedMotion')):
        return True
    now = time.monotonic()
    if now - _gtk_cache[0] > 2:
        root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
        disabled = False
        for version in ('gtk-3.0', 'gtk-4.0'):
            parser = configparser.ConfigParser(interpolation=None)
            try:
                parser.read(root / version / 'settings.ini')
                if parser.has_option('Settings', 'gtk-enable-animations'):
                    disabled |= not parser.getboolean('Settings', 'gtk-enable-animations')
            except (OSError, ValueError, configparser.Error):
                pass
        _gtk_cache = (now, disabled)
    return _gtk_cache[1]


class SoftButton(QPushButton):
    """A native QPushButton with interruptible light-only hover and press states."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._soft_hover = 0.0
        self._soft_press = 0.0
        self._hover_animation = self._animation('_soft_hover')
        self._press_animation = self._animation('_soft_press')
        self.pressed.connect(lambda: self._tween(self._press_animation, '_soft_press', 1.0, TOKENS["motion"]["fast"]))
        self.released.connect(lambda: self._tween(self._press_animation, '_soft_press', 0.0, TOKENS["motion"]["fast"]))

    def _animation(self, attribute):
        animation = QVariantAnimation(self)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.valueChanged.connect(lambda value: self._set_amount(attribute, value))
        return animation

    def _set_amount(self, attribute, value):
        setattr(self, attribute, float(value))
        self.update()

    def _tween(self, animation, attribute, target, duration):
        animation.stop()
        if not self.isEnabled() or reduced_motion():
            self._set_amount(attribute, target if self.isEnabled() else 0.0)
            return
        animation.setDuration(duration)
        animation.setStartValue(getattr(self, attribute))
        animation.setEndValue(target)
        animation.start()

    def enterEvent(self, event):
        self._tween(self._hover_animation, '_soft_hover', 1.0, TOKENS["motion"]["duration"])
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._tween(self._hover_animation, '_soft_hover', 0.0, TOKENS["motion"]["duration"])
        super().leaveEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.EnabledChange and not self.isEnabled() and hasattr(self, '_hover_animation'):
            self._hover_animation.stop()
            self._press_animation.stop()
            self._soft_hover = self._soft_press = 0.0
            self.update()
        super().changeEvent(event)

    def hideEvent(self, event):
        self._hover_animation.stop()
        self._press_animation.stop()
        self._soft_hover = self._soft_press = 0.0
        super().hideEvent(event)

    def paintEvent(self, event):
        if self.isEnabled() and (self._soft_hover or self._soft_press):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            color = QColor(COLORS["accent"])
            color.setAlpha(round(15 * self._soft_hover + 18 * self._soft_press))
            painter.setBrush(color)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), TOKENS["radii"]["small"], TOKENS["radii"]["small"])
            painter.end()
        super().paintEvent(event)


def animate_popup(widget):
    """Call immediately before QMenu.exec()/popup(); never delay or take focus."""
    animation = getattr(widget, '_soft_popup_animation', None)
    if animation is not None:
        animation.stop()
    if reduced_motion() or QApplication.platformName() in ('offscreen', 'minimal'):
        widget.setWindowOpacity(1.0)
        return
    if animation is None:
        animation = QVariantAnimation(widget)
        animation.setDuration(TOKENS["motion"]["fast"])
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.valueChanged.connect(widget.setWindowOpacity)
        widget._soft_popup_animation = animation
        if hasattr(widget, 'aboutToHide'):
            def restore_opacity():
                animation.stop()
                widget.setWindowOpacity(1.0)
            widget.aboutToHide.connect(restore_opacity)
    widget.setWindowOpacity(0.88)
    animation.setStartValue(0.88)
    animation.setEndValue(1.0)
    animation.start()

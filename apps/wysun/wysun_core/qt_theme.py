"""Qt side of the Wysun theme: stylesheet templates, colours, fonts and live refresh.

Stylesheets are templates. ``@token`` becomes the token value, ``@token/40`` the same
colour with alpha 40 (0-255) and ``@svg(name,token)`` a tinted copy of an asset SVG.
Metric tokens render as pixels and ``@font_family`` as a quoted family list.
``apply_style`` keeps the template on the widget, so a mode or wallpaper change
re-renders every widget, including widgets created later. Painters call
``color()``/``font()`` while painting; other caches register with ``on_theme_changed``.
"""
import os
import re
import sys
import time
import weakref
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

from . import paths, theme
from .jsonio import atomic_write_text

MARKER = re.compile(r'@svg\(([\w-]+),\s*([a-z][a-z0-9_]*)\)|@([a-z][a-z0-9_]*)(?:/(\d{1,3}))?')
PIXELS = ('radius_', 'corner_', 'space_', 'font_caption', 'font_small', 'font_body', 'font_heading', 'font_title',
          'border', 'focus_width', 'icon_size', 'shadow_')
TEMPLATE = 'wysunThemeTemplate'          # widget property holding the unrendered stylesheet
ASSET_DIRS = [Path(__file__).resolve().parents[1] / 'assets']   # apps/wysun/assets; apps may add theirs
_listeners = []

# Painters call color() hundreds of times per frame; resolving stats two files each
# time. Reuse the result briefly: the watcher invalidates on every change.
_MEMO_SECONDS = .1
_memo = [0.0, None]


def tokens(home=None):
    if home is not None:
        return theme.resolve_active(home)
    now = time.monotonic()
    if _memo[1] is None or now - _memo[0] > _MEMO_SECONDS:
        _memo[:] = [now, theme.resolve_active()]
    return _memo[1]


def invalidate():
    _memo[1] = None
    theme.invalidate()


def is_light(values=None):
    values = values or tokens()
    return QColor(values['canvas'][:7]).lightnessF() > .5


def _hex(value):
    """Token hex is CSS order (#RRGGBB or #RRGGBBAA)."""
    return value[:7], int(value[7:9], 16) if len(value) == 9 else 255


def color(name, alpha=None, values=None):
    """QColor for a colour token; ``alpha`` overrides the token's own alpha."""
    rgb, own = _hex((values or tokens())[name])
    result = QColor(rgb)
    result.setAlpha(own if alpha is None else max(0, min(255, int(alpha))))
    return result


def paint_color(value, fallback='glyph'):
    """Colour for data that may hold a token name or an explicit user colour."""
    values = tokens()
    if not value:
        return color(fallback, values=values)
    if isinstance(value, str) and isinstance(values.get(value), str) and values[value].startswith('#'):
        return color(value, values=values)
    return QColor(value)


def css(name, alpha=None, values=None):
    rgb, own = _hex((values or tokens())[name])
    alpha = own if alpha is None else max(0, min(255, int(alpha)))
    if alpha == 255:
        return rgb.lower()
    value = QColor(rgb)
    return f'rgba({value.red()},{value.green()},{value.blue()},{alpha})'  # theme-exception: conversion a sintaxis CSS


def family(values=None):
    """First installed family of the theme's list."""
    available = set(QFontDatabase.families())
    names = (values or tokens())['font_family']
    return next((name for name in names if name in available), names[-1])


def font(size=None, weight=None, role=None, values=None):
    """QFont in the theme family. ``size`` is points; ``role`` (body/small/caption/heading/title) a pixel token."""
    values = values or tokens()
    result = QFont(family(values))
    if role:
        result.setPixelSize(int(values['font_' + role]))
    elif size:
        result.setPointSizeF(size)
    if weight is not None:
        result.setWeight(QFont.Weight(int(weight)))
    return result


def svg_asset(name, token, values=None):
    """Tinted copy of <asset dir>/<name>.svg for QSS url(); cached per colour."""
    rgb, _ = _hex((values or tokens())[token])
    target = paths.runtime(f'orbit-theme-{os.getuid()}', f'{name}-{rgb[1:].lower()}.svg')
    if not target.is_file():
        source = next(directory / (name + '.svg') for directory in ASSET_DIRS if (directory / (name + '.svg')).is_file())
        text = re.sub(r'stroke="#[0-9a-fA-F]{6}"', f'stroke="{rgb}"', source.read_text())
        atomic_write_text(target, text)
    return target.as_posix()


def _render(match, values):
    if match[1]:
        return svg_asset(match[1], match[2], values)
    name, alpha = match[3], match[4]
    if name not in values:
        return match[0]
    value = values[name]
    if isinstance(value, str) and value.startswith('#'):
        return css(name, alpha, values)
    if name in ('font_family', 'font_mono'):
        return ', '.join(f'"{item}"' for item in value)
    if isinstance(value, (int, float)) and name.startswith(PIXELS):
        return f'{value:g}px'
    return str(value)


def qss(template, values=None):
    values = values or tokens()
    return MARKER.sub(lambda match: _render(match, values), template)


def apply_style(widget, template):
    """Set a themed stylesheet that follows every later theme change."""
    widget.setProperty(TEMPLATE, template)
    widget.setStyleSheet(qss(template))


def extend_style(widget, template):
    """Append template rules to the widget's existing themed template."""
    base = widget.property(TEMPLATE)
    apply_style(widget, (base if base is not None else widget.styleSheet()) + template)


def palette(values=None):
    """QPalette matching the tokens, for unstyled native parts."""
    values = values or tokens()
    result = QPalette()
    roles = [(QPalette.Window, 'canvas'), (QPalette.Base, 'surface'), (QPalette.AlternateBase, 'well'),
             (QPalette.WindowText, 'text'), (QPalette.Text, 'text'), (QPalette.Button, 'surface'),
             (QPalette.ButtonText, 'text'), (QPalette.Highlight, 'accent'), (QPalette.HighlightedText, 'on_accent'),
             (QPalette.ToolTipBase, 'tooltip'), (QPalette.ToolTipText, 'on_tooltip'), (QPalette.PlaceholderText, 'muted'),
             (QPalette.Link, 'accent'), (QPalette.BrightText, 'text_strong'), (QPalette.Mid, 'line'), (QPalette.Dark, 'line_strong')]
    for role, name in roles:
        result.setColor(role, color(name, 255, values))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        result.setColor(QPalette.Disabled, role, color('disabled', 255, values))
    return result


def apply_palette(app=None):
    from PySide6.QtWidgets import QApplication
    app = app or QApplication.instance()
    if app:
        app.setPalette(palette(tokens()))


def on_theme_changed(callback):
    """Register ``callback()`` for caches that are not stylesheets or painters.
    Bound methods are held weakly, so closed windows are not kept alive."""
    reference = weakref.WeakMethod(callback) if hasattr(callback, '__self__') else (lambda: callback)
    _listeners.append(reference)
    return callback


def refresh_widgets():
    """Re-render the palette, every themed stylesheet and every registered cache."""
    from PySide6.QtWidgets import QApplication, QWidget
    invalidate()
    app = QApplication.instance()
    if not app:
        return
    apply_palette(app)
    if app.property(TEMPLATE) is not None:
        app.setStyleSheet(qss(app.property(TEMPLATE)))
    for widget in QApplication.allWidgets():
        template = widget.property(TEMPLATE)
        if template is not None:
            widget.setStyleSheet(qss(template))
    for reference in list(_listeners):
        callback = reference()
        if callback is None:
            _listeners.remove(reference)
            continue
        try:
            callback()
        except Exception as error:  # A broken listener must not stop the others.
            print('Wysun: no se pudo actualizar el tema en', callback, error, file=sys.stderr)
    for widget in QApplication.allWidgets():
        QWidget.update(widget)


def watch_theme(home=None):
    """Follow theme.json and scheme.json, including atomic replacement and late creation."""
    from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if not app or hasattr(app, 'wysunThemeWatcher'):
        return
    apply_palette(app)

    class ThemeWatcher(QObject):
        def __init__(self):
            super().__init__(app)
            self.watcher = QFileSystemWatcher(self)
            self.timer = QTimer(self, singleShot=True, interval=40)
            self.revision = theme.revision(home)
            self.watcher.fileChanged.connect(self.timer.start)
            self.watcher.directoryChanged.connect(self.timer.start)
            self.timer.timeout.connect(self.refresh)
            self.arm()

        def arm(self):
            targets = set()
            for path in (theme.selection_path(home), theme.scheme_path(home)):
                if path.exists():
                    targets.add(str(path))
                parent = path.parent
                while not parent.exists() and parent != parent.parent:
                    parent = parent.parent
                targets.add(str(parent))
            current = set(self.watcher.files() + self.watcher.directories())
            if current - targets:
                self.watcher.removePaths(list(current - targets))
            if targets - current:
                self.watcher.addPaths(list(targets - current))

        def refresh(self):
            self.arm()
            invalidate()
            revision = theme.revision(home)
            if revision != self.revision:
                self.revision = revision
                refresh_widgets()

    app.wysunThemeWatcher = ThemeWatcher()

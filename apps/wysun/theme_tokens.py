"""Qt adapter for Wysun's semantic theme tokens (source: wysun_theme.json).

Stylesheets are templates. ``@token`` becomes the token value, ``@token/40``
the same colour with alpha 40 (0-255), and ``@svg(name,token)`` a tinted copy
of assets/<name>.svg. Metric tokens render as pixels and ``@font_family`` as
a quoted family list. ``apply_style`` keeps the template on the widget, so a
style or variant change re-renders every widget, including widgets created
later. Painters call ``color()``/``font()`` while painting and need no hook;
other caches can register with ``on_theme_changed``.
"""
import os
import re
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

import theme_core

ROOT = Path(__file__).resolve().parent
MARKER = re.compile(r'@svg\(([\w-]+),\s*([a-z][a-z0-9_]*)\)|@([a-z][a-z0-9_]*)(?:/(\d{1,3}))?')
PIXELS = ('radius_', 'space_', 'font_caption', 'font_small', 'font_body', 'font_heading', 'font_title', 'border', 'focus_width', 'icon_size', 'shadow_')
_listeners = []


def theme_id(home=None):
    """Active selection as 'style:variant'."""
    return theme_core.key(*theme_core.selection(home))


def tokens(home=None):
    return _resolved(*theme_core.selection(home))


@lru_cache(maxsize=8)
def _resolved(style, variant):
    return theme_core.resolve(style, variant)


def invalidate():
    theme_core.invalidate()


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
    """First installed family of the active style."""
    available = set(QFontDatabase.families())
    names = (values or tokens())['font_family']
    return next((name for name in names if name in available), names[-1])


def font(size=None, weight=None, role=None, values=None):
    """QFont in the theme family. ``size`` is points (as QFont('Inter', n));
    ``role`` (body/small/caption/heading/title) uses a pixel-size token."""
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
    """Tinted copy of assets/<name>.svg for QSS url(); cached per colour."""
    rgb, _ = _hex((values or tokens())[token])
    cache = Path(os.environ.get('XDG_RUNTIME_DIR') or Path.home() / '.cache') / f'orbit-theme-{os.getuid()}'
    target = cache / f'{name}-{rgb[1:].lower()}.svg'
    if not target.is_file():
        source = (ROOT / 'assets' / (name + '.svg')).read_text()
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        text = re.sub(r'stroke="#[0-9a-fA-F]{6}"', f'stroke="{rgb}"', source)
        temporary = target.with_suffix('.tmp' + str(os.getpid()))
        temporary.write_text(text)
        os.replace(temporary, target)
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
    if name == 'font_family' or name == 'font_mono':
        return ', '.join(f'"{item}"' for item in value)
    if isinstance(value, (int, float)) and name.startswith(PIXELS):
        return f'{value:g}px'
    return str(value)


def qss(template, values=None):
    values = values or tokens()
    return MARKER.sub(lambda match: _render(match, values), template)


def apply_style(widget, template):
    """Set a themed stylesheet that follows every later theme change."""
    widget.setProperty('orbitOriginalStyle', template)
    widget.setStyleSheet(qss(template))


def extend_style(widget, template):
    """Append template rules to the widget's existing themed template."""
    base = widget.property('orbitOriginalStyle')
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
    """Fluent sets a full palette; Space Black keeps the platform palette it always used,
    unless the app opts in with the ``orbitThemePalette`` property (Files)."""
    from PySide6.QtWidgets import QApplication
    app = app or QApplication.instance()
    if not app:
        return
    if app.property('orbitPlatformPalette') is None:
        app.setProperty('orbitPlatformPalette', QPalette(app.palette()))
    values = tokens()
    themed = values['style'] != 'space-black' or bool(app.property('orbitThemePalette'))
    app.setPalette(palette(values) if themed else app.property('orbitPlatformPalette'))


def on_theme_changed(callback):
    """Register ``callback()`` for caches that are not stylesheets or painters.
    Bound methods are held weakly, so closed windows are not kept alive."""
    import weakref
    reference = weakref.WeakMethod(callback) if hasattr(callback, '__self__') else (lambda: callback)
    _listeners.append(reference)
    return callback


def refresh_widgets():
    from PySide6.QtWidgets import QApplication, QWidget
    invalidate()
    from icons import glyph, badge, refresh_icons
    glyph.cache_clear()
    badge.cache_clear()
    app = QApplication.instance()
    if not app:
        return
    apply_palette(app)
    if app.property('orbitOriginalStyle') is not None:
        app.setStyleSheet(qss(app.property('orbitOriginalStyle')))
    for widget in QApplication.allWidgets():
        template = widget.property('orbitOriginalStyle')
        if template is not None:
            widget.setStyleSheet(qss(template))
    refresh_icons()
    for reference in list(_listeners):
        callback = reference()
        if callback is None:
            _listeners.remove(reference)
            continue
        try:
            callback()
        except Exception as error:  # A broken listener must not stop the others.
            print('Wysun: no se pudo actualizar el tema en', callback, error)
    for widget in QApplication.allWidgets():
        QWidget.update(widget)


def watch_theme(home=None):
    """Follow ~/.config/orbit/theme.json (atomic replace and late creation included)."""
    from PySide6.QtCore import QFileSystemWatcher, QTimer, QObject
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if not app or hasattr(app, 'orbitThemeWatcher'):
        return
    try:
        theme_core.migrate(home)
    except OSError as error:
        print('Wysun: no se pudo migrar theme.json:', error)
    apply_palette(app)

    class ThemeWatcher(QObject):
        def __init__(self):
            super().__init__(app)
            self.watcher = QFileSystemWatcher(self)
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.setInterval(40)
            self.key = theme_id(home)
            self.watcher.fileChanged.connect(self.changed)
            self.watcher.directoryChanged.connect(self.changed)
            self.timer.timeout.connect(self.refresh)
            self.arm()

        def arm(self):
            targets = set()
            path = theme_core.selection_path(home)
            if path.exists():
                targets.add(str(path))
            parent = path.parent
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            if parent.exists():
                targets.add(str(parent))
            current = set(self.watcher.files() + self.watcher.directories())
            if current - targets:
                self.watcher.removePaths(list(current - targets))
            if targets - current:
                self.watcher.addPaths(list(targets - current))

        def changed(self, *_):
            self.timer.start()

        def refresh(self):
            self.arm()
            invalidate()
            key = theme_id(home)
            if key != self.key:
                self.key = key
                refresh_widgets()

    app.orbitThemeWatcher = ThemeWatcher()

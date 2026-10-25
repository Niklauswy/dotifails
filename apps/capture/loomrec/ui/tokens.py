"""Wysun theme for Recorder and Screenshot (Material You).

Capture releases are installed apart from the launcher, so they carry their own
byte-identical copies of theme_core.py and wysun_theme.json and read the palette
mode from ~/.config/orbit/theme.json plus the Material scheme from
$XDG_STATE_HOME/wysun/scheme.json. Stylesheets are templates: ``@token``,
``@token/alpha`` (0-255). ``apply_theme`` installs the palette and stylesheet and
follows later mode and wallpaper changes live.
"""
import re
from collections.abc import Mapping

from PySide6.QtGui import QColor, QPalette, QFont, QFontDatabase

from . import theme_core

MARKER = re.compile(r'@([a-z][a-z0-9_]*)(?:/(\d{1,3}))?')
PIXELS = ('radius_', 'corner_', 'space_', 'font_caption', 'font_small', 'font_body', 'font_heading', 'font_title', 'border', 'focus_width', 'icon_size')
# Historic Recorder names kept for callers; values come from the active theme.
LEGACY = {'blue': 'accent', 'blue_hover': 'accent_hover'}
_listeners = []
_cache = {}


def tokens():
    selection = theme_core.selection()
    if selection not in _cache:
        _cache[selection] = theme_core.resolve(*selection)
    return theme_core.resolve_active(*selection)


class _Tokens(Mapping):
    """Live view with Recorder's historic keys: colours, space, radius, motion_ms."""
    def __getitem__(self, key):
        values = tokens()
        if key == 'space':
            return tuple(values['space_' + n] for n in ('xs', 's', 'm', 'l', 'xl'))
        if key == 'radius':
            return values['radius_s'], values['radius_m'], values['radius_l']
        if key == 'motion_ms':
            return values['motion_fast']
        value = values[LEGACY.get(key, key)]
        return value[:7] if isinstance(value, str) and value.startswith('#') else value
    def __iter__(self):
        return iter(tokens())
    def __len__(self):
        return len(tokens())


TOKENS = _Tokens()


def color(name, alpha=None, values=None):
    value = (values or tokens())[LEGACY.get(name, name)]
    result = QColor(value[:7])
    own = int(value[7:9], 16) if len(value) == 9 else 255
    result.setAlpha(own if alpha is None else max(0, min(255, int(alpha))))
    return result


def css(name, alpha=None, values=None):
    value = color(name, alpha, values)
    if value.alpha() == 255:
        return value.name()
    return f'rgba({value.red()},{value.green()},{value.blue()},{value.alpha()})'  # theme-exception: conversion a sintaxis CSS


def tint(value):
    """Icon colour: a token name or an explicit '#rrggbb'."""
    if isinstance(value, str) and value.startswith('#'):
        return value
    return color(value or 'muted').name()


def family(values=None):
    available = set(QFontDatabase.families())
    from .material import load_fonts
    load_fonts()
    available = set(QFontDatabase.families())
    names = ['Rubik', *(values or tokens())['font_family']]
    return next((name for name in names if name in available), 'Sans Serif')


def _render(match, values):
    name, alpha = match[1], match[2]
    key = LEGACY.get(name, name)
    if key not in values:
        return match[0]
    value = values[key]
    if isinstance(value, str) and value.startswith('#'):
        return css(key, alpha, values)
    if key in ('font_family', 'font_mono'):
        return ', '.join(f'"{item}"' for item in value)
    if isinstance(value, (int, float)) and key.startswith(PIXELS):
        return f'{value:g}px'
    return str(value)


def qss(template, values=None):
    values = values or tokens()
    return MARKER.sub(lambda match: _render(match, values), template)


def apply_style(widget, template):
    """Themed stylesheet that follows later theme changes."""
    widget.setProperty('wysunThemeStyle', template)
    widget.setStyleSheet(qss(template))


def on_theme_changed(callback):
    import weakref
    _listeners.append(weakref.WeakMethod(callback) if hasattr(callback, '__self__') else (lambda: callback))
    return callback


STYLE = '''
  QWidget { color:@text; }
  QMainWindow,QDialog { background:@canvas; }
  QLabel { background:transparent; }
  QLabel[role="title"] { font-size:@font_title; font-weight:600; letter-spacing:-0.5px; }
  QLabel[role="subtitle"] { color:@muted; font-size:@font_body; }
  QLabel[role="eyebrow"] { color:@muted; font-size:@font_small; font-weight:600; letter-spacing:1px; }
  QLabel[role="section"] { font-size:@font_heading; font-weight:600; }
  QFrame[role="surface"] { background:@surface; border:1px solid @material_edge; border-radius:@radius_l; }
  QFrame[role="well"] { background:@inset; border:1px solid @divider; border-radius:@radius_m; }
  QFrame[role="rule"] { background:@divider; max-height:1px; border:0; }
  QPushButton { background:@surface; border:1px solid @line; border-radius:@radius_l; padding:@space_s @space_m; min-height:20px; }
  QPushButton:hover { background:@hover; border-color:@line_strong; }
  QPushButton:pressed { background:@pressed; }
  QPushButton:focus { border:@focus_width solid @focus; }
  QPushButton:disabled { color:@disabled; background:@disabled_surface; border-color:@divider; }
  QPushButton[primary="true"] { background:@accent; border-radius:@radius_l; color:@on_accent; border-color:@accent; font-weight:600; }
  QPushButton[primary="true"]:hover { background:@accent_hover; }
  QPushButton[primary="true"]:pressed { background:@accent_pressed; }
  QPushButton[primary="true"]:focus { border:@focus_width solid @accent_focus; }
  QPushButton[primary="true"]:disabled { background:@accent_disabled; border-color:@accent_disabled; color:@on_accent; }
  QPushButton[dropdown="true"] { padding-right:22px; }
  QPushButton[quiet="true"] { background:transparent; border-color:transparent; }
  QPushButton[quiet="true"]:hover { background:@hover; }
  QPushButton[quiet="true"]:pressed { background:@pressed; }
  QPushButton[quiet="true"]:focus { border:@focus_width solid @focus; }
  QPushButton:checked { background:@selection; color:@selection_text; border-color:@selection_line; }
  QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:@well; border:1px solid @line; border-radius:@radius_s; padding:@space_s @space_m; min-height:18px; color:@text; selection-background-color:@accent; selection-color:@on_accent; }
  QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus { border:1px solid @focus_input; background:@surface; }
  QSpinBox,QDoubleSpinBox { padding-right:26px; }
  QSpinBox::up-button,QDoubleSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:22px; height:18px; border:0; background:transparent; }
  QSpinBox::down-button,QDoubleSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:22px; height:18px; border:0; background:transparent; }
  QSpinBox::up-arrow,QDoubleSpinBox::up-arrow,QSpinBox::down-arrow,QDoubleSpinBox::down-arrow { image:none; width:0; height:0; }
  QComboBox::drop-down { border:0; width:24px; }
  QComboBox QAbstractItemView { background:@surface_raised; border:1px solid @line; padding:5px; color:@text; selection-background-color:@selection; selection-color:@text; }
  QListWidget { background:@surface; border:0; border-radius:@radius_m; outline:0; padding:4px; }
  QListWidget::item { padding:10px; border-radius:@radius_s; margin:2px; }
  QListWidget::item:selected { background:@selection; color:@selection_text; }
  QListWidget::item:hover { background:@row_hover; }
  QScrollArea { border:0; background:transparent; }
  QScrollArea > QWidget > QWidget { background:transparent; }
  QScrollBar:vertical { background:transparent; width:8px; margin:2px; }
  QScrollBar::handle:vertical { background:@scrollbar; min-height:28px; border-radius:@space_xs; }
  QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
  QScrollBar:horizontal { background:transparent; height:8px; }
  QScrollBar::handle:horizontal { background:@scrollbar; min-width:28px; border-radius:@space_xs; }
  QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal { width:0; }
  QProgressBar { background:@track; border:0; border-radius:@space_xs; min-height:8px; text-align:center; color:@muted; font-size:@font_small; }
  QProgressBar::chunk { background:@accent_muted; border-radius:@space_xs; }
  QSlider::groove:horizontal { height:4px; background:@track; border-radius:2px; }
  QSlider::sub-page:horizontal { background:@accent_muted; border-radius:2px; }
  QSlider::handle:horizontal { width:12px; height:12px; margin:-5px 0; background:@surface; border:2px solid @accent; border-radius:7px; }
  QSlider::handle:horizontal:focus { border-color:@focus; background:@selection; }
  QTabWidget::pane { background:@surface; border:1px solid @divider; border-radius:@radius_m; top:-1px; }
  QTabBar::tab { padding:10px 14px; margin:0 2px 5px 0; background:transparent; color:@muted; border-radius:@radius_s; }
  QTabBar::tab:selected { background:@selection; color:@selection_text; }
  QTabBar::tab:hover { background:@hover; }
  QTabBar::tab:focus { color:@text_strong; }
  QMenu { background:@menu; color:@text; border:1px solid @line; border-radius:@radius_l; padding:6px; }
  QMenu::item { padding:9px 22px; border-radius:@radius_s; }
  QMenu::item:selected { background:@menu_selected; }
  QMenu::item:disabled { color:@disabled; }
  QToolTip { background:@tooltip; color:@on_tooltip; border:0; padding:7px; }
  QCheckBox { spacing:8px; }
  QCheckBox::indicator { width:16px; height:16px; border:1px solid @check_line; border-radius:@radius_s; background:@check; }
  QCheckBox::indicator:checked { background:@check_on; border-color:@check_on_line; }
  QCheckBox::indicator:disabled { border-color:@disabled; background:@disabled_surface; }
  QCheckBox:focus { color:@selection_text; }
  QCheckBox::indicator:focus { border-color:@check_focus; }
  QSplitter::handle { background:transparent; width:10px; }
  QStatusBar { background:transparent; color:@muted; font-size:@font_small; }
'''


def palette(values=None):
    values = values or tokens()
    result = QPalette()
    for role, key in [(QPalette.Window, 'canvas'), (QPalette.Base, 'surface'), (QPalette.AlternateBase, 'well'),
                      (QPalette.WindowText, 'text'), (QPalette.Text, 'text'), (QPalette.Button, 'surface'),
                      (QPalette.ButtonText, 'text'), (QPalette.Highlight, 'accent'), (QPalette.HighlightedText, 'on_accent'),
                      (QPalette.ToolTipBase, 'tooltip'), (QPalette.ToolTipText, 'on_tooltip'),
                      (QPalette.PlaceholderText, 'muted'), (QPalette.Link, 'accent')]:
        result.setColor(role, color(key, 255, values))
    for role in [QPalette.WindowText, QPalette.Text, QPalette.ButtonText]:
        result.setColor(QPalette.Disabled, role, color('disabled', 255, values))
    return result


def _install(app):
    values = tokens()
    font = QFont(family(values))
    font.setPixelSize(int(values['font_body']))
    app.setFont(font)
    app.setPalette(palette(values))
    app.setStyleSheet(qss(STYLE, values))


def refresh(app=None):
    """Re-render palette, stylesheets, icons and painters for the new theme."""
    from PySide6.QtWidgets import QApplication, QWidget
    app = app or QApplication.instance()
    if not app:
        return
    _cache.clear()
    theme_core.invalidate()
    _install(app)
    for widget in QApplication.allWidgets():
        template = widget.property('wysunThemeStyle')
        if template is not None:
            widget.setStyleSheet(qss(template))
    from .icons import refresh_icons
    refresh_icons()
    for reference in list(_listeners):
        callback = reference()
        if callback is None:
            _listeners.remove(reference)
            continue
        try:
            callback()
        except Exception as error:
            print('Wysun: no se pudo actualizar el tema en', callback, error)
    for widget in QApplication.allWidgets():
        QWidget.update(widget)


def watch(app):
    """Follow theme.json, including atomic replacement and late creation."""
    from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer
    if getattr(app, '_wysun_theme_watcher', None):
        return
    try:
        theme_core.migrate()
    except OSError:
        pass

    class Watcher(QObject):
        def __init__(self):
            super().__init__(app)
            self.files = QFileSystemWatcher(self)
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.setInterval(40)
            self.key = theme_core.visual_key()
            self.files.fileChanged.connect(self.timer.start)
            self.files.directoryChanged.connect(self.timer.start)
            self.timer.timeout.connect(self.check)
            self.arm()

        def arm(self):
            targets = set()
            for path in (theme_core.selection_path(), theme_core.scheme_path()):
                if path.exists():
                    targets.add(str(path))
                parent = path.parent
                while not parent.exists() and parent != parent.parent:
                    parent = parent.parent
                if parent.exists():
                    targets.add(str(parent))
            current = set(self.files.files() + self.files.directories())
            if current - targets:
                self.files.removePaths(list(current - targets))
            if targets - current:
                self.files.addPaths(list(targets - current))

        def check(self):
            self.arm()
            theme_core.invalidate()
            key = theme_core.visual_key()
            if key != self.key:
                self.key = key
                refresh(app)

    app._wysun_theme_watcher = Watcher()


def apply_theme(app):
    app.setStyle('Fusion')
    _install(app)
    watch(app)

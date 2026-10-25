"""Recorder's own theme pieces: its global stylesheet, its bundled font and ``apply_theme``.

Tokens, colours, templates and the live watcher come from ``wysun_core.qt_theme``,
which every Recorder release carries inside its own ``wysun_core`` copy.
"""
from PySide6.QtGui import QFont

from wysun_core.qt_theme import apply_palette, apply_style, color, on_theme_changed, tokens, watch_theme


def tint(value):
    """Icon colour: a token name or an explicit '#rrggbb'."""
    if isinstance(value, str) and value.startswith('#'):
        return value
    return color(value or 'muted').name()


def family(values=None):
    """Rubik (bundled in wysun_core) first, then the theme's families."""
    from wysun_core.ui.fonts import display_family, load_fonts
    load_fonts()
    return display_family()


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


def _apply_font(app):
    font = QFont(family())
    font.setPixelSize(int(tokens()['font_body']))
    app.setFont(font)


def apply_theme(app):
    app.setStyle('Fusion')
    apply_palette(app)
    apply_style(app, STYLE)
    _apply_font(app)
    on_theme_changed(lambda: _apply_font(app))
    watch_theme()

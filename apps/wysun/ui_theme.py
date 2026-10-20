"""Native surface and control tokens shared by every Wysun module."""
from theme_tokens import apply_style, color, tokens

from ui_appearance import read_appearance
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QLinearGradient, QRadialGradient

# Templates: @token markers are resolved by theme_tokens.qss on every theme change.
PANEL_STYLE = '''
QWidget { background:transparent; color:@text; font-family:@font_family; font-size:@font_body; }
QWidget#page { background:transparent; }
QLabel#title {font-size:@font_title;font-weight:600;}
QLabel#subtitle, QLabel#muted {color:@muted;font-size:12px;}
QLabel#eyebrow {color:@subtle;font-size:10px;font-weight:600;letter-spacing:2px;}
QPushButton {padding:9px 13px;border-radius:@radius_control;background:@fill;border:@border solid transparent;color:@control_text;}
QPushButton:hover {background:@hover;color:@text_strong;}
QPushButton:focus {border:@focus_width solid @focus;}
QPushButton:pressed {background:@pressed;}
QPushButton:checked {background:@selection;color:@selection_text;border-color:@selection_line;}
QPushButton:disabled {color:@disabled;background:@disabled_surface;}
QPushButton#primary {background:@accent;color:@on_accent;font-weight:600;}
QPushButton#primary:hover {background:@accent_hover;}
QPushButton#primary:pressed {background:@accent_pressed;}
QPushButton#danger {color:@danger;background:@danger_soft;}
QPushButton#danger:hover {background:@danger_hover;}
QPushButton#danger:disabled,QPushButton#primary:disabled {color:@disabled;background:@disabled_surface;}
QLineEdit,QPlainTextEdit,QTextEdit,QSpinBox,QDoubleSpinBox,QComboBox {background:@well;border:@border solid @line;border-radius:@radius_control;padding:9px;selection-background-color:@text_selection;}
QLineEdit:focus,QPlainTextEdit:focus,QTextEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus {border-color:@focus_input;}
QComboBox::drop-down {border:0;width:25px;background:transparent;}
QComboBox::down-arrow {image:url(@svg(chevron-down,chevron));width:12px;height:12px;}
QComboBox {padding-right:30px;}
QSpinBox::up-button,QDoubleSpinBox::up-button {subcontrol-origin:border;subcontrol-position:top right;width:22px;border:0;background:transparent;}
QSpinBox::down-button,QDoubleSpinBox::down-button {subcontrol-origin:border;subcontrol-position:bottom right;width:22px;border:0;background:transparent;}
QSpinBox::up-arrow,QDoubleSpinBox::up-arrow {image:url(@svg(chevron-up,chevron));width:10px;height:10px;}
QSpinBox::down-arrow,QDoubleSpinBox::down-arrow {image:url(@svg(chevron-down,chevron));width:10px;height:10px;}
QComboBox QAbstractItemView {background:@surface_raised;color:@text;selection-background-color:@menu_selected;selection-color:@text;}
QListWidget,QTableWidget,QScrollArea {background:transparent;border:none;outline:0;}
QListWidget::item {padding:10px;border-radius:@radius_control;}
QListWidget::item:selected {background:@selection;color:@selection_text;}
QListWidget::item:hover {background:@hover;}
QHeaderView::section {background:@header;color:@muted;border:0;padding:9px;text-align:left;}
QTableWidget {gridline-color:@grid;selection-background-color:@selection;selection-color:@selection_text;}
QCheckBox {spacing:10px;padding:7px 0;}
QCheckBox::indicator {width:18px;height:18px;border:@border solid @check_line;border-radius:6px;background:@check;}
QCheckBox::indicator:checked {background:@check_on;border-color:@check_on_line;image:url(@svg(check-dark,check_mark));}
QCheckBox::indicator:disabled {border-color:@disabled;background:@disabled_surface;}
QCheckBox:focus {color:@text_strong;}
QCheckBox::indicator:focus {border-color:@check_focus;}
QDialog {background:@surface;}
QSlider::groove:horizontal {height:5px;background:@track;border-radius:2px;}
QSlider::sub-page:horizontal {background:@accent;border-radius:2px;}
QSlider::handle:horizontal {background:@slider_handle;width:14px;margin:-5px 0;border-radius:7px;}
QSlider::handle:focus {background:@slider_focus;}
QScrollBar:vertical {background:transparent;width:6px;}
QScrollBar::handle:vertical {background:@scrollbar;border-radius:3px;min-height:25px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QToolTip {background:@tooltip;color:@on_tooltip;border:@border solid @tooltip_line;padding:7px;}
'''
PALETTE_STYLE = PANEL_STYLE + '''
QLineEdit {background:transparent;border:none;padding:10px 4px;font-size:19px;}
QLabel#section {color:@section;font-size:11px;font-weight:600;letter-spacing:1px;}
QLabel#previewTitle {font-size:21px;font-weight:600;}
QPlainTextEdit {background:transparent;border:0;padding:0;}
QListWidget {padding:4px;}
QDialog QLineEdit,QDialog QPlainTextEdit {background:@well;border:@border solid @line;padding:10px;}
QMenu {background:@menu;color:@text;border:@border solid @line_strong;border-radius:@radius_m;padding:6px;}
QMenu::item {padding:10px 28px 10px 12px;border-radius:@radius_s;}
QMenu::item:selected {background:@menu_selected;}
QMenu::item:disabled {color:@disabled;}
'''


def surface_alpha(values=None):
    """Window material opacity: the user's preference for glass, solid for Fluent."""
    values = values or tokens()
    return round(read_appearance()['opacity']*2.55) if values['translucent'] else 255


def paint_surface(widget, radius=None):
    """Window material. Space Black: tinted glass; Fluent: pearl or mica, opaque."""
    values=tokens();radius=values['radius_l']
    p=QPainter(widget);p.setRenderHint(QPainter.Antialiasing)
    rect=QRectF(.5,.5,widget.width()-1,widget.height()-1)
    alpha=surface_alpha(values)
    if values['material']=='glass':
        base=QLinearGradient(0,0,widget.width()*.5,widget.height())
        base.setColorAt(0,color('material_top',alpha));base.setColorAt(.52,color('material_mid',alpha));base.setColorAt(1,color('material_bottom',min(255,alpha+12)))
    else:
        base=QLinearGradient(0,0,0,widget.height())
        base.setColorAt(0,color('material_top',alpha));base.setColorAt(.52,color('material_mid',alpha));base.setColorAt(1,color('material_bottom',alpha))
    p.setBrush(base);p.setPen(QPen(color('material_edge'),values['border']));p.drawRoundedRect(rect,radius,radius)
    if color('material_glow').alpha():
        glow=QRadialGradient(widget.width()*.8,-80,widget.width()*.7)
        glow.setColorAt(0,color('material_glow'));glow.setColorAt(1,color('material_glow',0))
        p.setBrush(glow);p.setPen(Qt.NoPen);p.drawRoundedRect(rect.adjusted(1,1,-1,-1),radius-1,radius-1)
    if color('material_highlight').alpha():
        # Thin inner reflection gives the glass an edge without whitening the content.
        p.setPen(QPen(color('material_highlight'),1));p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect.adjusted(1,1,-1,-1),radius-1,radius-1)
    p.end()

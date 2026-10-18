"""Native surface and control tokens shared by every Wysun module."""
from theme_tokens import ThemeColor, apply_style

from pathlib import Path
from ui_appearance import read_appearance
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QRadialGradient

ACCENT = '#B8CBF2'
PANEL_STYLE = '''
QWidget { background:transparent; color:#E8EDF7; font-family:Inter; font-size:13px; }
QWidget#page { background:transparent; }
QLabel#title {font-size:23px;font-weight:600;}
QLabel#subtitle, QLabel#muted {color:#A0ACC0;font-size:12px;}
QLabel#eyebrow {color:#8596B2;font-size:10px;font-weight:600;letter-spacing:2px;}
QPushButton {padding:9px 13px;border-radius:10px;background:rgba(255,255,255,4);border:1px solid transparent;color:#BBC8DC;}
QPushButton:hover {background:#263449;color:#F4F7FC;}
QPushButton:focus {border-color:#ADC9F7;}
QPushButton:pressed {background:#35465F;}
QPushButton:checked {background:#2C3D57;color:#E6F0FF;border-color:#486082;}
QPushButton:disabled {color:#667389;background:rgba(255,255,255,2);}
QPushButton#primary {background:#B8CBF2;color:#101D32;font-weight:600;}
QPushButton#primary:hover {background:#D0DFFA;}
QPushButton#danger {color:#F0A6AF;background:rgba(222,108,129,12);}
QPushButton#danger:hover {background:#422A39;}
QPushButton#danger:disabled,QPushButton#primary:disabled {color:#6E7D93;background:rgba(255,255,255,3);}
QLineEdit,QPlainTextEdit,QTextEdit,QSpinBox,QDoubleSpinBox,QComboBox {background:rgba(8,13,22,90);border:1px solid rgba(180,203,239,38);border-radius:10px;padding:9px;selection-background-color:#3F587F;}
QLineEdit:focus,QPlainTextEdit:focus,QTextEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus {border-color:#91B5ED;}
QComboBox::drop-down {border:0;width:25px;background:transparent;}
QComboBox::down-arrow {image:url(__CHEVRON__);width:12px;height:12px;}
QComboBox {padding-right:30px;}
QSpinBox::up-button,QDoubleSpinBox::up-button {subcontrol-origin:border;subcontrol-position:top right;width:22px;border:0;background:transparent;}
QSpinBox::down-button,QDoubleSpinBox::down-button {subcontrol-origin:border;subcontrol-position:bottom right;width:22px;border:0;background:transparent;}
QSpinBox::up-arrow,QDoubleSpinBox::up-arrow {image:url(__UP__);width:10px;height:10px;}
QSpinBox::down-arrow,QDoubleSpinBox::down-arrow {image:url(__CHEVRON__);width:10px;height:10px;}
QComboBox QAbstractItemView {background:#1D293B;selection-background-color:#344966;}
QListWidget,QTableWidget,QScrollArea {background:transparent;border:none;outline:0;}
QListWidget::item {padding:10px;border-radius:10px;}
QListWidget::item:selected {background:#2C3D57;}
QListWidget::item:hover {background:#233047;}
QHeaderView::section {background:#162133;color:#A5B4CB;border:0;padding:9px;text-align:left;}
QTableWidget {gridline-color:#2A3649;selection-background-color:#2C3D57;}
QCheckBox {spacing:10px;padding:7px 0;}
QCheckBox::indicator {width:18px;height:18px;border:1px solid #617493;border-radius:6px;background:#152033;}
QCheckBox::indicator:checked {background:#ADC7F0;border-color:#C7D9F5;image:url(__CHECK__);}
QCheckBox:focus {color:#D4E5FF;}
QDialog {background:#162032;}
QSlider::groove:horizontal {height:5px;background:#2C3A50;border-radius:2px;}
QSlider::sub-page:horizontal {background:#B8CBF2;border-radius:2px;}
QSlider::handle:horizontal {background:#D3E3FF;width:14px;margin:-5px 0;border-radius:7px;}
QSlider::handle:focus {background:#FFFFFF;}
QScrollBar:vertical {background:transparent;width:6px;}
QScrollBar::handle:vertical {background:#41536F;border-radius:3px;min-height:25px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QToolTip {background:#24344C;color:#EDF3FE;border:1px solid #4A6388;padding:7px;}
'''.replace('__CHEVRON__',(Path(__file__).parent/'assets/chevron-down.svg').as_posix()).replace('__CHECK__',(Path(__file__).parent/'assets/check-dark.svg').as_posix()).replace('__UP__',(Path(__file__).parent/'assets/chevron-up.svg').as_posix())
PALETTE_STYLE = PANEL_STYLE + '''
QLineEdit {background:transparent;border:none;padding:10px 4px;font-size:19px;}
QLabel#section {color:#94A8C8;font-size:11px;font-weight:600;letter-spacing:1px;}
QLabel#previewTitle {font-size:21px;font-weight:600;}
QPlainTextEdit {background:transparent;border:0;padding:0;}
QListWidget {padding:4px;}
QDialog QLineEdit,QDialog QPlainTextEdit {background:rgba(8,13,22,90);border:1px solid rgba(180,203,239,38);padding:10px;}
QMenu {background:#1C293D;border:1px solid #415574;border-radius:12px;padding:6px;}
QMenu::item {padding:10px 28px 10px 12px;border-radius:7px;}
QMenu::item:selected {background:#304766;}
'''


def paint_surface(widget, radius=22):
    from theme_tokens import tokens
    radius=tokens()['radius']
    p=QPainter(widget);p.setRenderHint(QPainter.Antialiasing)
    rect=QRectF(.5,.5,widget.width()-1,widget.height()-1)
    base=QLinearGradient(0,0,widget.width()*.5,widget.height())
    alpha=round(read_appearance()['opacity']*2.55)
    base.setColorAt(0,ThemeColor(21,29,43,alpha));base.setColorAt(.52,ThemeColor(14,20,31,alpha));base.setColorAt(1,ThemeColor(10,15,24,min(255,alpha+12)))
    p.setBrush(base);p.setPen(QPen(ThemeColor(209,227,255,72),1));p.drawRoundedRect(rect,radius,radius)
    glow=QRadialGradient(widget.width()*.8,-80,widget.width()*.7)
    glow.setColorAt(0,ThemeColor(155,190,248,18));glow.setColorAt(1,ThemeColor(112,159,234,0))
    p.setBrush(glow);p.setPen(Qt.NoPen);p.drawRoundedRect(rect.adjusted(1,1,-1,-1),radius-1,radius-1)
    # Thin inner reflection gives the glass an edge without whitening the content.
    p.setPen(QPen(ThemeColor(255,255,255,12),1));p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(rect.adjusted(1,1,-1,-1),radius-1,radius-1)
    p.end()

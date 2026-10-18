"""Solid pearl Fluent-inspired native materials; no compositor blur dependency."""
from PySide6.QtGui import QColor,QPalette,QFont,QFontDatabase
TOKENS={
 'canvas':'#F3F6FB','surface':'#FCFDFF','well':'#EDF3FA','line':'#DDE5EF',
 'text':'#1C2A3B','muted':'#596A80','blue':'#2165D5','blue_hover':'#1958BE',
 'selection':'#E3EDFD','disabled':'#8B98A9','danger':'#AA3547',
 'space':(4,8,12,16,24),'radius':(8,12,20),'motion_ms':150,
}

def apply_theme(app):
    app.setStyle('Fusion')
    fonts=QFontDatabase.families()
    family=next((f for f in ['Segoe UI Variable','Inter','Noto Sans','DejaVu Sans'] if f in fonts),'Sans Serif')
    font=QFont(family);font.setPixelSize(14);app.setFont(font)
    palette=QPalette()
    for role,key in [(QPalette.Window,'canvas'),(QPalette.Base,'surface'),(QPalette.AlternateBase,'well'),(QPalette.WindowText,'text'),(QPalette.Text,'text'),(QPalette.Button,'surface'),(QPalette.ButtonText,'text'),(QPalette.Highlight,'blue'),(QPalette.HighlightedText,None),(QPalette.ToolTipBase,'text'),(QPalette.ToolTipText,None)]:
        palette.setColor(role,QColor(TOKENS[key] if key else '#FFFFFF'))
    for role in [QPalette.WindowText,QPalette.Text,QPalette.ButtonText]:palette.setColor(QPalette.Disabled,role,QColor(TOKENS['disabled']))
    app.setPalette(palette)
    app.setStyleSheet('''
      QWidget { color:#1C2A3B; }
      QMainWindow,QDialog { background:#F3F6FB; }
      QLabel { background:transparent; }
      QLabel[role="title"] { font-size:24px; font-weight:600; letter-spacing:-0.5px; }
      QLabel[role="subtitle"] { color:#596A80; font-size:13px; }
      QLabel[role="eyebrow"] { color:#596A80; font-size:11px; font-weight:600; letter-spacing:1px; }
      QLabel[role="section"] { font-size:15px; font-weight:600; }
      QFrame[role="surface"] { background:#FCFDFF; border:1px solid #FFFFFF; border-radius:20px; }
      QFrame[role="well"] { background:#EDF3FA; border:1px solid #E2EAF4; border-radius:12px; }
      QFrame[role="rule"] { background:#E2E8F0; max-height:1px; border:0; }
      QPushButton { background:#FCFDFF; border:1px solid #DDE5EF; border-radius:10px; padding:8px 12px; min-height:20px; }
      QPushButton:hover { background:#EAF1FB; border-color:#C5D4E8; }
      QPushButton:pressed { background:#DCE8F8; }
      QPushButton:focus { border:2px solid #2165D5; }
      QPushButton:disabled { color:#8B98A9; background:#EFF3F8; border-color:#E5EBF3; }
      QPushButton[primary="true"] { background:#2165D5; border-radius:12px; color:white; border-color:#2165D5; font-weight:600; }
      QPushButton[primary="true"]:hover { background:#1958BE; }
      QPushButton[primary="true"]:pressed { background:#164EAD; }
      QPushButton[primary="true"]:focus { border:2px solid #123C82; }
      QPushButton[primary="true"]:disabled { background:#ADC4E7; border-color:#ADC4E7; color:#F5F8FD; }
      QPushButton[dropdown="true"] { padding-right:22px; }
      QPushButton[quiet="true"] { background:transparent; border-color:transparent; }
      QPushButton[quiet="true"]:hover { background:#E7EEF8; }
      QPushButton[quiet="true"]:pressed { background:#DCE8F8; }
      QPushButton[quiet="true"]:focus { border:2px solid #2165D5; }
      QPushButton:checked { background:#E3EDFD; color:#164EAD; border-color:#B9CFED; }
      QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#F5F8FC; border:1px solid #DEE6F0; border-radius:8px; padding:7px 9px; min-height:18px; selection-background-color:#2165D5; }
      QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus { border:1px solid #2165D5; background:#FFFFFF; }
      QSpinBox,QDoubleSpinBox { padding-right:26px; }
      QSpinBox::up-button,QDoubleSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:22px; height:18px; border:0; background:transparent; }
      QSpinBox::down-button,QDoubleSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:22px; height:18px; border:0; background:transparent; }
      QSpinBox::up-arrow,QDoubleSpinBox::up-arrow,QSpinBox::down-arrow,QDoubleSpinBox::down-arrow { image:none; width:0; height:0; }
      QComboBox::drop-down { border:0; width:24px; }
      QComboBox QAbstractItemView { background:#FCFDFF; border:1px solid #DDE5EF; padding:5px; selection-background-color:#E3EDFD; selection-color:#1C2A3B; }
      QListWidget { background:#FCFDFF; border:0; border-radius:12px; outline:0; padding:4px; }
      QListWidget::item { padding:10px; border-radius:8px; margin:2px; }
      QListWidget::item:selected { background:#E3EDFD; color:#164EAD; }
      QListWidget::item:hover { background:#EFF4FB; }
      QScrollArea { border:0; background:transparent; }
      QScrollArea > QWidget > QWidget { background:transparent; }
      QScrollBar:vertical { background:transparent; width:8px; margin:2px; }
      QScrollBar::handle:vertical { background:#C6D3E3; min-height:28px; border-radius:4px; }
      QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
      QScrollBar:horizontal { background:transparent; height:8px; }
      QScrollBar::handle:horizontal { background:#C6D3E3; min-width:28px; border-radius:4px; }
      QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal { width:0; }
      QProgressBar { background:#E6EDF6; border:0; border-radius:4px; min-height:8px; text-align:center; color:#596A80; font-size:11px; }
      QProgressBar::chunk { background:#79A5E1; border-radius:4px; }
      QSlider::groove:horizontal { height:4px; background:#DCE5F1; border-radius:2px; }
      QSlider::sub-page:horizontal { background:#6394D9; border-radius:2px; }
      QSlider::handle:horizontal { width:12px; height:12px; margin:-5px 0; background:#FCFDFF; border:2px solid #2165D5; border-radius:7px; }
      QTabWidget::pane { background:#FCFDFF; border:1px solid #E2E8F0; border-radius:12px; top:-1px; }
      QTabBar::tab { padding:10px 14px; margin:0 2px 5px 0; background:transparent; color:#596A80; border-radius:8px; }
      QTabBar::tab:selected { background:#E3EDFD; color:#164EAD; }
      QTabBar::tab:hover { background:#EAF1FA; }
      QMenu { background:#FCFDFF; border:1px solid #DDE5EF; border-radius:10px; padding:6px; }
      QMenu::item { padding:9px 22px; border-radius:6px; }
      QMenu::item:selected { background:#E3EDFD; }
      QToolTip { background:#26364C; color:white; border:0; padding:7px; }
      QCheckBox { spacing:8px; }
      QCheckBox::indicator { width:16px; height:16px; border:1px solid #B8C7D9; border-radius:5px; background:white; }
      QCheckBox::indicator:checked { background:#2165D5; border-color:#2165D5; }
      QCheckBox:focus { color:#164EAD; }
      QSplitter::handle { background:transparent; width:10px; }
      QStatusBar { background:transparent; color:#596A80; font-size:12px; }
    ''')

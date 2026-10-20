"""Reference theme-aware widget (Qt). See docs/themes.md.

Everything visual comes from tokens: colours through ``color()``, stylesheet
templates through ``apply_style()`` (re-rendered on every theme change), fonts
through ``font()``. Text derived from the theme (the caption) refreshes through
``on_theme_changed``; painters just ask ``color()`` while painting.
"""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from theme_tokens import apply_style, color, on_theme_changed, tokens

STYLE = '''
QFrame#themeDemo { background:@surface; border:@border solid @line; border-radius:@radius_m; }
QLabel#demoTitle { color:@text; font-size:@font_heading; font-weight:600; }
QLabel#demoMuted { color:@muted; font-size:@font_small; }
QPushButton#demoAction { background:@accent; color:@on_accent; border-radius:@radius_control; padding:8px 14px; }
QPushButton#demoAction:hover { background:@accent_hover; }
QPushButton#demoAction:focus { border:@focus_width solid @focus; }
'''


class ThemeDemo(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('themeDemo')
        apply_style(self, STYLE)
        layout = QVBoxLayout(self)
        title = QLabel('Tema de Wysun')
        title.setObjectName('demoTitle')
        self.caption = QLabel()
        self.caption.setObjectName('demoMuted')
        row = QHBoxLayout()
        self.action = QPushButton('Acción')
        self.action.setObjectName('demoAction')
        row.addWidget(self.action)
        row.addStretch(1)
        for widget in (title, self.caption):
            layout.addWidget(widget)
        layout.addLayout(row)
        self.refresh_caption()
        on_theme_changed(self.refresh_caption)  # weak: dies with the widget

    def refresh_caption(self):
        values = tokens()
        self.caption.setText(f"{values['style_name']} · {values['name']}")

    def paintEvent(self, event):
        super().paintEvent(event)
        # A custom-painted element: ask for the colour while painting.
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(color('accent'))
        p.drawRoundedRect(QRectF(self.width() - 90, 14, 72, 6), 3, 3)
        p.end()

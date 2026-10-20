"""Lightweight Fluent quick look, isolated from the shared desktop viewer."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QDialog

from file_viewer import FileViewer
from files_visuals import STYLE
from icons import _icon_specs, icon
from theme_tokens import apply_style, color


class FluentFileViewer(FileViewer):
    """Retain the existing media loaders and controls with a native light shell."""

    def __init__(self, path, parent=None):
        super().__init__(path, parent)
        self.setWindowFlags(Qt.Window)
        self.setWindowModality(Qt.WindowModal)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setObjectName('fluentPreview')
        apply_style(self, STYLE + '''
            QDialog#fluentPreview { background: @canvas; }
            QLabel#title { color: @text; font-size: 16px; font-weight: 600; }
            QLabel#subtitle { color: @muted; font-size: 12px; }
            QScrollArea { background: @inset; border: 1px solid @line;
                          border-radius: 8px; }
            QScrollArea QWidget { background: @inset; }
            QPlainTextEdit { background: @surface; color: @text;
                border: 1px solid @line; border-radius: 8px; padding: 12px;
                selection-background-color: @selection; selection-color: @selection_text; }
            QPlainTextEdit:focus { border-color: @focus; }
            QPushButton { padding: 6px 12px; min-height: 20px; }
            QPushButton:default { background: @surface; color: @text;
                                  border-color: @line; }
            QPushButton:default:hover { background: @hover; }
            QPushButton:default:pressed { background: @pressed; }
            QPushButton:default:focus { border-color: @focus; }
            QSlider::groove:horizontal { height: 4px; background: @track;
                                        border-radius: 2px; }
            QSlider::sub-page:horizontal { background: @accent; border-radius: 2px; }
            QSlider::handle:horizontal { background: @accent; border: 3px solid @surface;
                width: 12px; height: 12px; margin: -7px 0; border-radius: 9px; }
            QSlider::handle:horizontal:focus { border-color: @focus; }
        ''')
        self.layout().setContentsMargins(20, 16, 20, 16)
        self.setMinimumSize(480, 320)
        self._refresh_button_icons()
        if self.player:
            # Only the actual playback surface stays black. Controls remain light.
            apply_style(self.player.surface, 'background: #090a0e;')  # theme-exception: lienzo negro de vídeo
            self.player.poll.timeout.connect(self._refresh_button_icons)

    def _refresh_button_icons(self):
        for button in self.findChildren(QAbstractButton):
            spec = _icon_specs.get(button.icon().cacheKey())
            if spec:
                button.setIcon(spec[0](*spec[1]))
            if not button.accessibleName():
                button.setAccessibleName(button.text() or button.toolTip())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), color('canvas'))

    def show(self):
        # Bypass WindowMotion's desktop-theme lift; keep window manager placement.
        QDialog.show(self)

    def showEvent(self, event):
        QDialog.showEvent(self, event)
        self._animate_window(True)

    def hideEvent(self, event):
        QDialog.hideEvent(self, event)

    def _animate_window(self, entering):
        if entering:
            from files_motion import animate_popup
            animate_popup(self)
        else:
            self.hide()

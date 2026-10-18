"""Lightweight Fluent quick look, isolated from the shared desktop viewer."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton, QDialog

from file_viewer import FileViewer
from files_visuals import STYLE
from icons import _icon_specs, icon


class FluentFileViewer(FileViewer):
    """Retain the existing media loaders and controls with a native light shell."""

    def __init__(self, path, parent=None):
        super().__init__(path, parent)
        self.setWindowFlags(Qt.Window)
        self.setWindowModality(Qt.WindowModal)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        # The desktop theme watcher must not restore PANEL_STYLE on this window.
        self.setProperty('orbitOriginalStyle', None)
        self.setObjectName('fluentPreview')
        self.setStyleSheet(STYLE + '''
            QDialog#fluentPreview { background: #f5f7fa; }
            QLabel#title { color: #253345; font-size: 16px; font-weight: 600; }
            QLabel#subtitle { color: #58677a; font-size: 12px; }
            QScrollArea { background: #edf1f6; border: 1px solid #dbe2eb;
                          border-radius: 8px; }
            QScrollArea QWidget { background: #edf1f6; }
            QPlainTextEdit { background: #ffffff; color: #253345;
                border: 1px solid #dbe2eb; border-radius: 8px; padding: 12px;
                selection-background-color: #d9eaff; selection-color: #163e6e; }
            QPlainTextEdit:focus { border-color: #2563b4; }
            QPushButton { padding: 6px 12px; min-height: 20px; }
            QPushButton:default { background: #fcfdff; color: #253345;
                                  border-color: #dbe2eb; }
            QPushButton:default:hover { background: #e6edf6; }
            QPushButton:default:pressed { background: #d9e4f2; }
            QPushButton:default:focus { border-color: #2677c7; }
            QSlider::groove:horizontal { height: 4px; background: #d2dbe6;
                                        border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #2563b4; border-radius: 2px; }
            QSlider::handle:horizontal { background: #2563b4; border: 3px solid white;
                width: 12px; height: 12px; margin: -7px 0; border-radius: 9px; }
            QSlider::handle:horizontal:focus { border-color: #a7ccf4; }
        ''')
        self.layout().setContentsMargins(20, 16, 20, 16)
        self.setMinimumSize(480, 320)
        self._refresh_button_icons()
        if self.player:
            # Only the actual playback surface stays black. Controls remain light.
            self.player.surface.setProperty('orbitOriginalStyle', None)
            self.player.surface.setStyleSheet('background: #090a0e;')
            self.player.poll.timeout.connect(self._refresh_button_icons)

    def _refresh_button_icons(self):
        for button in self.findChildren(QAbstractButton):
            spec = _icon_specs.get(button.icon().cacheKey())
            if spec:
                button.setIcon(icon(spec[0], spec[1], '#3d4b5d'))
            if not button.accessibleName():
                button.setAccessibleName(button.text() or button.toolTip())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#f5f7fa'))

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

#!/usr/bin/python3
"""sudo askpass: the password travels only to sudo's anonymous stdout pipe."""
import sys
import os
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout


def main():
    app = QApplication(['dotifails-authorization'])
    app.setApplicationName('Autorización de Wysun')
    dialog = QDialog()
    dialog.setWindowTitle('Autorizar instalación · Wysun')
    dialog.setMinimumWidth(420)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(16)
    title = QLabel('Autorización de administrador')
    title.setStyleSheet('font-size:19px;font-weight:600;')
    layout.addWidget(title)
    message = QLabel('El instalador necesita permiso para cambiar paquetes o archivos del sistema. Introduce tu contraseña de sudo.')
    message.setWordWrap(True)
    layout.addWidget(message)
    password = QLineEdit()
    password.setEchoMode(QLineEdit.Password)
    password.setAccessibleName('Contraseña de sudo')
    password.setPlaceholderText('Contraseña')
    layout.addWidget(password)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setText('Autorizar')
    buttons.button(QDialogButtonBox.Cancel).setText('Cancelar')
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    password.returnPressed.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.setStyleSheet('QDialog{background:#111923;color:#edf3fc} QLabel{color:#edf3fc} QLineEdit{background:#1d2938;color:white;border:1px solid #536980;border-radius:8px;padding:12px} QPushButton{padding:10px 20px}')
    password.setFocus(Qt.OtherFocusReason)
    cancel_path=os.environ.get('DOTIFAILS_CANCEL_FILE')
    cancel_timer=QTimer(dialog)
    if cancel_path:
        cancel_timer.timeout.connect(lambda:dialog.reject() if Path(cancel_path).is_file() else None)
        cancel_timer.start(250)
    if dialog.exec() != QDialog.Accepted:
        return 1
    sys.stdout.write(password.text() + '\n')
    sys.stdout.flush()
    password.clear()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

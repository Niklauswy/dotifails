"""Privileged boot recovery remains separate from ordinary home backups."""
from pathlib import Path

from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QMessageBox, QPlainTextEdit, QVBoxLayout

from process_runner import InstallerProcess
from visual_widgets import Button, label


class BootRecoveryDialog(QDialog):
    def __init__(self, home, parent=None):
        super().__init__(parent)
        self.home = Path(home)
        self.items = []
        self.latest = None
        self.kind = None
        self.runner = InstallerProcess(home, self)
        self.runner.line.connect(self.log_line)
        self.runner.event.connect(self.event_received)
        self.runner.finished.connect(self.finished_operation)
        self.setWindowTitle('Recuperación de Blue CRT')
        self.resize(700, 550)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(14)
        layout.addWidget(label('Arranque y acceso', 'heading'))
        layout.addWidget(label('Consulta los respaldos del sistema, comprueba los archivos instalados o recupera el aspecto anterior. Se solicitará autorización de administrador.'))
        self.listing = QListWidget()
        self.listing.currentRowChanged.connect(self.selection_changed)
        self.listing.setAccessibleName('Respaldos del arranque del sistema')
        layout.addWidget(self.listing, 1)
        self.status = label('Pulsa «Consultar respaldos» para cargar la lista.', 'small')
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setMaximumHeight(130)
        layout.addWidget(self.log)
        row = QHBoxLayout()
        self.load = Button('Consultar respaldos', lambda:self.run('list'))
        self.verify = Button('Verificar arranque', lambda:self.run('verify'))
        self.restore = Button('Restaurar', self.restore_selected, 'primary')
        self.restore.setEnabled(False)
        row.addWidget(self.load)
        row.addWidget(self.verify)
        row.addStretch()
        row.addWidget(self.restore)
        layout.addLayout(row)

    def run(self, kind, ident=None):
        self.kind = kind
        arguments = ['-A', '/usr/bin/python3', str(Path(__file__).with_name('boot.py')), '--events']
        arguments += ['--restore', ident] if kind == 'restore' else ['--'+kind]
        self.log.clear()
        self.status.setText('Operación en curso. Espera a que termine.')
        for button in (self.load, self.verify, self.restore):
            button.setEnabled(False)
        try:
            self.runner.start('sudo', arguments, Path(__file__).parent)
        except OSError as error:
            self.log_line(str(error))
            self.finished_operation(1, {})

    def log_line(self, text):
        self.log.appendPlainText(text)

    def event_received(self, event):
        if event.get('event') != 'backups':
            return
        self.items = event['items']
        self.listing.clear()
        for item in self.items:
            groups = ', '.join(item.get('groups') or [])
            self.listing.addItem(f"{item['id']}  ·  {item['status']}\n{groups}")
        self.latest = next((i for i,item in enumerate(self.items) if item['status'] != 'restored'), None)
        if self.latest is not None:
            self.listing.setCurrentRow(self.latest)

    def selection_changed(self):
        self.restore.setEnabled(not self.runner.running and self.latest is not None and self.listing.currentRow() == self.latest)

    def finished_operation(self, code, result):
        self.load.setEnabled(True)
        self.verify.setEnabled(True)
        self.selection_changed()
        if code:
            self.status.setText('No se completó la operación. Revisa el registro.')
        elif self.kind == 'restore':
            self.status.setText('Restaurado. El cambio se verá en el próximo inicio. Consulta la lista para continuar.')
            self.restore.setEnabled(False)
        elif self.kind == 'verify':
            self.status.setText('Verificación terminada. Consulta el resultado en el registro.')
        else:
            self.status.setText(f'{len(self.items)} respaldos. Se recuperan del más reciente al más antiguo.')

    def restore_selected(self):
        index = self.listing.currentRow()
        if index != self.latest or index < 0:
            return
        ident = self.items[index]['id']
        answer = QMessageBox.question(self, 'Restaurar el arranque', f'Se restaurará el respaldo {ident} y se reconstruirá la imagen de inicio si corresponde. La sesión permanecerá abierta. ¿Continuar?', QMessageBox.Yes|QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.run('restore', ident)

    def reject(self):
        if not self.runner.running:
            super().reject()

    def closeEvent(self, event):
        if self.runner.running:
            event.ignore()
            self.status.setText('Espera a que termine la operación antes de cerrar.')
        else:
            event.accept()

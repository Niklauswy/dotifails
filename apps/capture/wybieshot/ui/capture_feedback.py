"""GUI-thread consent instructions; no progress window is present in captured pixels."""
import threading
import time
from PySide6.QtCore import QObject,Signal,QTimer
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton
from loomrec.portal import PortalCancelled


class CaptureFeedback(QObject):
    requested=Signal(object)
    def __init__(self,parent):
        super().__init__(parent);self.cancelled=threading.Event();self.dialog=None
        self.requested.connect(self.present)
    def check(self):
        if self.cancelled.is_set():raise PortalCancelled('Captura completa cancelada; no se guardó ningún monitor parcial.')
    def report(self,state):
        self.check()
        if state['stage']!='select':return
        ack=threading.Event();self.requested.emit((state,ack));deadline=time.monotonic()+120
        while not ack.wait(.05):
            self.check()
            if time.monotonic()>=deadline:raise TimeoutError('Se agotó el tiempo para continuar la captura. No se guardó un escritorio parcial.')
        self.check()
    def present(self,request):
        state,ack=request
        if self.cancelled.is_set():ack.set();return
        if self.dialog:self.dialog.deleteLater()
        dialog=self.dialog=QDialog(None);dialog.setWindowTitle('Wysun · Escritorio con cursor')
        layout=QVBoxLayout(dialog)
        text=QLabel(f"Monitor {state['index']} de {state['total']} · faltan: {', '.join(state['remaining'])}\n\nSelecciona uno de estos monitores en el portal. Cada monitor necesita su propio permiso.\nLas imágenes se capturan en secuencia, no al mismo instante.\nCancelar aquí o en cualquier portal descarta toda la captura.")
        text.setWordWrap(True);layout.addWidget(text);row=QHBoxLayout();layout.addLayout(row)
        cancel=QPushButton('Cancelar todo');proceed=QPushButton('Continuar al portal');row.addWidget(cancel);row.addWidget(proceed);proceed.setDefault(True)
        def advance():
            # Acknowledge only after hiding and allowing the compositor to commit.
            dialog.hide();QTimer.singleShot(180,ack.set)
        def stop():self.cancel();ack.set()
        cancel.clicked.connect(stop);dialog.rejected.connect(stop);proceed.clicked.connect(advance)
        dialog.resize(460,220);dialog.show();proceed.setFocus()
    def cancel(self):
        self.cancelled.set()
        if self.dialog:self.dialog.hide()
    def close(self):
        if self.dialog:self.dialog.hide();self.dialog.deleteLater();self.dialog=None
        self.deleteLater()

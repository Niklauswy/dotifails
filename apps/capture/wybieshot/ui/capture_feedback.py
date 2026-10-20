"""GUI-thread consent instructions; no progress window is present in captured pixels."""
import threading
import time
from PySide6.QtCore import QObject,Signal,Slot,QTimer,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton
from loomrec.portal import PortalCancelled


class CaptureWaitDialog(QDialog):
    def reject(self):
        # Escape/WM close requests cancellation, not successful teardown. Keep
        # progress visible until the worker acknowledges portal/session close.
        self.rejected.emit()


class CaptureWaitFeedback(QObject):
    """Cancellable portal wait. Its owner retains the lease until Work finishes."""
    frame_requested=Signal(object)
    defer_release=True
    def __init__(self,parent,*,delay_ms=0,screen_cast=False):
        super().__init__(parent);self.cancelled=threading.Event()
        self.frame_requested.connect(self.before_frame,Qt.QueuedConnection)
        self._frame_ack=None;self.hide_timer=QTimer(self);self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.acknowledge_frame)
        self.show_timer=QTimer(self);self.show_timer.setSingleShot(True);self.show_timer.timeout.connect(self.show_dialog)
        self.dialog=CaptureWaitDialog(None);self.dialog.setWindowTitle('Wysun Screenshot · Preparando selección')
        layout=QVBoxLayout(self.dialog)
        hint=('Esperando la selección del monitor en el portal…\nDespués podrás marcar una región de la imagen autorizada.' if screen_cast
              else 'Preparando la captura del escritorio…\nLa selección de región aparecerá en cuanto el portal entregue la imagen.')
        self.text=QLabel(hint)
        self.text.setWordWrap(True);layout.addWidget(self.text)
        self.cancel_button=QPushButton('Cancelar');layout.addWidget(self.cancel_button)
        self.cancel_button.clicked.connect(parent.cancel_capture);self.dialog.rejected.connect(parent.cancel_capture)
        self.dialog.resize(420,160)
        if delay_ms>0:self.show_timer.start(delay_ms)
        else:self.show_dialog()
    def show_dialog(self):
        if self.dialog and not self.dialog.isVisible() and not self.cancelled.is_set():
            self.dialog.show();self.cancel_button.setFocus()
    def check(self):
        if self.cancelled.is_set():raise PortalCancelled('Selección cancelada en el portal')
    def report(self,state):
        self.check()
        if state['stage']!='frame':return
        ack=threading.Event();self.frame_requested.emit(ack)
        while not ack.wait(.05):self.check()
        self.check()
    @Slot(object)
    def before_frame(self,ack):
        # No progress dialog may appear in the authorized monitor frame. Hide
        # and commit before connecting the PipeWire consumer, not afterwards.
        self.show_timer.stop()
        if self.dialog:self.dialog.hide()
        self._frame_ack=ack;self.hide_timer.start(180)
    @Slot()
    def acknowledge_frame(self):
        ack,self._frame_ack=self._frame_ack,None
        if ack:ack.set()
    def cancel(self):
        self.cancelled.set()
        if self.dialog:
            self.text.setText('Cancelando la petición del portal…\nSi el selector del portal sigue abierto, ciérralo también para terminar. La aplicación sigue esperando la respuesta del portal.')
            self.cancel_button.setEnabled(False)
    def close(self):
        self.hide_timer.stop();self.show_timer.stop()
        if self.dialog:self.dialog.hide();self.dialog.deleteLater();self.dialog=None
        self.deleteLater()


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

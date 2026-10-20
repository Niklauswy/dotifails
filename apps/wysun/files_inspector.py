"""Bounded asynchronous selection preview and unambiguous breadcrumb gestures."""
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit
from files_motion import SoftButton
from files_zoom import ZoomCanvas
from file_media import FilePreviewJob, file_kind, duration_label

class BreadcrumbButton(SoftButton):
    navigateRequested=Signal(str)
    copyRequested=Signal()
    def __init__(self,label,path,parent=None):
        super().__init__(label,parent)
        self.path=path
        self.timer=QTimer(self);self.timer.setSingleShot(True)
        from PySide6.QtWidgets import QApplication
        self.timer.setInterval(QApplication.doubleClickInterval())
        self.timer.timeout.connect(lambda:self.navigateRequested.emit(self.path))
        self.clicked.connect(lambda:self.timer.start())
        self.suppress_release=False
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.timer.stop();self.suppress_release=True;self.setDown(False)
            self.copyRequested.emit();event.accept()
        else:super().mouseDoubleClickEvent(event)
    def mouseReleaseEvent(self,event):
        if self.suppress_release:
            self.suppress_release=False;self.setDown(False);event.accept()
        else:super().mouseReleaseEvent(event)

class SelectionPreview(QWidget):
    fullscreenRequested=Signal(bool)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.player=None
        self.path='';self.page=1;self.pages=1;self.image=None;self.job=None;self.request=None
        self.setObjectName('selectionPreview');self.setMinimumHeight(170)
        layout=QVBoxLayout(self);layout.setContentsMargins(8,8,8,8)
        self.canvas=ZoomCanvas();self.canvas.setText('Selecciona un archivo');self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setWordWrap(True);self.canvas.setMinimumSize(80,100)
        from PySide6.QtWidgets import QSizePolicy
        self.canvas.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Ignored)
        layout.addWidget(self.canvas,1)
        self.text=QPlainTextEdit();self.text.setReadOnly(True);self.text.setAccessibleName('Contenido del documento')
        self.text.setStyleSheet('QPlainTextEdit { background: #f5f6f8; color: #243247; border: 1px solid #dce4ee; border-radius: 8px; padding: 10px; selection-background-color: #dceaff; }')
        layout.addWidget(self.text,1);self.text.hide()
        self.metadata=QLabel();self.metadata.setWordWrap(True);layout.addWidget(self.metadata)
        row=QHBoxLayout();self.previous=SoftButton('Anterior');self.next=SoftButton('Siguiente');self.counter=QLabel()
        self.previous.clicked.connect(lambda:self.turn(-1));self.next.clicked.connect(lambda:self.turn(1))
        for w in (self.previous,self.counter,self.next):row.addWidget(w)
        layout.addLayout(row)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(120);self.timer.timeout.connect(self.start)
        self.set_path('')
    @staticmethod
    def supported(path):
        return bool(path) and Path(path).is_file() and (file_kind(path) in ('image','video','audio','code') or Path(path).suffix.lower() in ('.pdf','.txt','.md','.rst','.csv','.log','.tex','.srt','.vtt'))
    def set_path(self,path):
        if path==self.path:return
        if self.player:
            self.player.stop();self.player.hide();self.layout().removeWidget(self.player);self.player.deleteLater();self.player=None
        self.text.clear();self.text.hide();self.canvas.show()
        self.path=path;self.page=1;self.pages=1;self.image=None;self.request=(path,1) if path else None
        self.canvas.clear();self.canvas.setText('Cargando vista previa…' if path else 'Sin vista previa');self.metadata.clear();self.metadata.hide()
        self.controls();self.timer.stop()
        if path and file_kind(path) in ('video','audio'):
            from files_player import InlinePlayer
            self.player=InlinePlayer(path,self,audio=file_kind(path)=='audio')
            self.player.fullscreenRequested.connect(self.fullscreenRequested)
            self.layout().insertWidget(0,self.player,1);self.canvas.hide();self.request=None
            self.metadata.clear()
        elif path:self.timer.start()
    def controls(self):
        pdf=Path(self.path).suffix.lower()=='.pdf'
        for w in (self.previous,self.counter,self.next):w.setVisible(pdf)
        self.previous.setEnabled(self.page>1);self.next.setEnabled(self.page<self.pages);self.counter.setText(f'{self.page} / {self.pages}')
    def turn(self,step):
        self.page=max(1,min(self.pages,self.page+step));self.request=(self.path,self.page);self.controls();self.start()
    def start(self):
        if self.job is not None or not self.request:return
        path,page=self.request;self.request=None
        self.job=FilePreviewJob(path,page)
        self.job.ready.connect(lambda _,data,p=path,n=page:self.loaded(p,n,data))
        self.job.finished.connect(self.finished);self.job.start()
    def finished(self):
        self.job.deleteLater();self.job=None
        if self.request:self.start()
    def loaded(self,path,page,data):
        if path!=self.path or page!=self.page:return
        self.image=data.get('image');meta=data.get('meta',{});self.pages=meta.get('pages',1)
        parts=[]
        if meta.get('width'):parts.append(f"{meta['width']} × {meta.get('height',0)} px")
        if meta.get('duration'):parts.append(duration_label(meta['duration']))
        if meta.get('pages'):parts.append(f"{meta['pages']} páginas")
        self.metadata.setText(' · '.join(parts));self.controls()
        if self.image is not None and not self.image.isNull():self.canvas.set_image(self.image)
        elif file_kind(path) in ('code','document') and Path(path).suffix.lower()!='.pdf' or Path(path).suffix.lower() in ('.srt','.vtt'):
            self.canvas.hide();self.text.show()
            content=data.get('text','')
            self.text.setPlainText(data.get('error') or content or 'Documento vacío o sin texto legible.')
            if meta.get('size',0)>=8*1024*1024:
                self.text.setPlainText('Documento demasiado grande para la vista previa. Usa Abrir para verlo completo.')
            elif meta.get('size',0)>50000:self.metadata.setText('Vista parcial · primeros 50 KB; usa Abrir para el documento completo.')
        else:self.canvas.setText(data.get('error') or data.get('text') or 'Vista previa no disponible')
        self.metadata.setVisible(bool(self.metadata.text()))
    def render(self):
        if self.image is not None and not self.image.isNull():
            self.canvas.update()
    def resizeEvent(self,event):
        super().resizeEvent(event);self.render()

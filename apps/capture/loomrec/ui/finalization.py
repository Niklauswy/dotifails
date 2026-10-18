"""Recording publication status: automatic MP4 without exposing project internals."""
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QProgressBar
from .components import SoftButton

class FinalizationPanel(QWidget):
    def __init__(self,cancel,retry,parent=None):
        super().__init__(parent)
        self.setObjectName('currentJob')
        layout=QHBoxLayout(self);layout.setContentsMargins(20,10,20,10)
        text=QVBoxLayout();layout.addLayout(text,1)
        self.title=QLabel();self.title.setProperty('role','section');text.addWidget(self.title)
        self.detail=QLabel();self.detail.setWordWrap(True);text.addWidget(self.detail)
        self.progress=QProgressBar();self.progress.setRange(0,100);self.progress.setMaximumWidth(180);layout.addWidget(self.progress)
        self.cancel=SoftButton(self.tr('Cancelar preparación'));self.cancel.clicked.connect(cancel);layout.addWidget(self.cancel)
        self.retry=SoftButton(self.tr('Preparar MP4'));self.retry.clicked.connect(retry);layout.addWidget(self.retry)
        self.hide()

    def update_status(self,status):
        state=status.get('state','pending');active=state in ('pending','running')
        titles={'pending':'Preparando MP4…','running':'Preparando MP4…','ready':'MP4 listo para enviar','error':'No se pudo preparar el MP4','cancelled':'Preparación cancelada'}
        self.title.setText(self.tr(titles.get(state,'Grabación conservada')))
        detail=status.get('error') if state=='error' else None
        self.detail.setText(detail or self.tr('La grabación está guardada. Puedes cancelar sin perderla.' if active else 'Puedes reproducir el video o copiar su ruta desde la biblioteca.' if state=='ready' else 'La grabación está guardada. Pulsa Preparar MP4 para intentarlo de nuevo.'))
        self.progress.setValue(round(100*max(0,min(1,status.get('progress',0) or 0))))
        self.progress.setVisible(active);self.cancel.setVisible(active);self.cancel.setEnabled(active)
        self.retry.setVisible(state in ('error','cancelled'));self.show()

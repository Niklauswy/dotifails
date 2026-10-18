"""One visible operation; no fictional job queue."""
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QProgressBar,QPushButton

class JobPanel(QWidget):
    def __init__(self,cancel,parent=None):
        super().__init__(parent);self.setObjectName('currentJob')
        layout=QHBoxLayout(self);layout.setContentsMargins(20,10,20,10)
        text=QVBoxLayout();layout.addLayout(text,1)
        self.title=QLabel();self.title.setProperty('role','section');text.addWidget(self.title)
        self.detail=QLabel();self.detail.setWordWrap(True);text.addWidget(self.detail)
        self.progress=QProgressBar();self.progress.setRange(0,100);self.progress.setMaximumWidth(180);layout.addWidget(self.progress)
        self.cancel=QPushButton('Cancelar tarea');self.cancel.clicked.connect(cancel);layout.addWidget(self.cancel)
        self.hide()
    def update_job(self,kind,status,cancelling=False):
        state=status['state'];active=state in ('idle','running')
        labels={'preview':'Vista previa','export':'Exportación MP4','silence':'Detección de silencios','transcription':'Transcripción local'}
        states={'idle':'Preparando','running':'En curso','done':'Completada','error':'Falló','cancelled':'Cancelada'}
        self.title.setText(labels.get(kind,kind)+' · '+('Cancelando…' if cancelling and active else states.get(state,state)))
        detail=status.get('error') or ('Proyecto y originales conservados.' if state=='cancelled' else status.get('phase') or ('Espera o cancela esta tarea para editar o abrir otro proyecto.' if active else 'Puedes continuar editando.'))
        self.detail.setText(detail);self.progress.setValue(round(100*status.get('progress',0)))
        self.cancel.setEnabled(active and not cancelling);self.cancel.setText('Cancelando…' if cancelling and active else 'Cancelar tarea')
        self.show()

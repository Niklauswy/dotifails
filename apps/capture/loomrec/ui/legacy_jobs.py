"""Explicit compatibility controls for a render owned by an older running GUI."""
import json,os,signal,time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QDialog,QVBoxLayout,QLabel,QPushButton,QProgressBar
from .activation import show_and_focus,focus_window


def process_identity(pid,proc=Path('/proc')):
    return (proc/str(pid)/'stat').read_text().rsplit(')',1)[1].split()[19]


def owned_render(gui_pid,proc=Path('/proc')):
    children=set()
    try:
        for task in (proc/str(gui_pid)/'task').iterdir():children.update((task/'children').read_text().split())
    except OSError:return None
    matches=[]
    for pid in children:
        p=proc/pid
        try:
            if p.stat().st_uid!=os.getuid() or (p/'comm').read_text().strip()!='ffmpeg':continue
            args=(p/'cmdline').read_bytes().split(b'\0')
            if not any(b'.loom-export-' in arg for arg in args):continue
            matches.append({'pid':int(pid),'identity':process_identity(pid,proc),'kind':'Vista previa' if any(b'/.preview/' in arg for arg in args) else 'Exportación MP4'})
        except OSError:continue
    return matches[0] if len(matches)==1 else None


def interrupt_render(gui_pid,target):
    current=owned_render(gui_pid)
    if not current or (current['pid'],current['identity'])!=(target['pid'],target['identity']):
        raise RuntimeError('La tarea cambió; no se interrumpió ningún proceso.')
    os.kill(current['pid'],signal.SIGTERM)


class LegacyJobPanel(QDialog):
    def __init__(self,gui_pid,target):
        super().__init__();self.gui_pid=gui_pid;self.target=target;self.pending=False;self.started=time.monotonic()
        self.setWindowTitle('Wysun Recorder · Tarea actual');self.resize(480,250)
        layout=QVBoxLayout(self);self.title=QLabel(target['kind']+' · En curso');self.title.setProperty('role','title');layout.addWidget(self.title)
        self.message=QLabel('La ventana anterior sigue procesando. No publica porcentaje en tiempo real. El proyecto y los originales se conservan.');self.message.setWordWrap(True);layout.addWidget(self.message)
        self.progress=QProgressBar();self.progress.setRange(0,0);layout.addWidget(self.progress)
        self.cancel=QPushButton('Detener render anterior');self.cancel.clicked.connect(self.cancel_requested);layout.addWidget(self.cancel)
        note=QLabel('Al detenerlo, la versión anterior puede mostrar un error de FFmpeg. No se detiene ninguna grabación.');note.setWordWrap(True);layout.addWidget(note)
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(300)
    def cancel_requested(self):
        try:interrupt_render(self.gui_pid,self.target)
        except Exception as exc:self.message.setText(str(exc));return
        self.pending=True;self.cancel.setEnabled(False);self.title.setText(self.target['kind']+' · Interrumpiendo…')
    def activate(self,action):
        if action!='status':show_and_focus(self)
        return {'pid':os.getpid(),'window':int(self.winId()),'job_panel':True,'cancel_requested':self.pending}
    def poll(self):
        current=owned_render(self.gui_pid)
        if current:
            self.progress.setRange(0,0)
            elapsed=int(time.monotonic()-self.started)
            if not self.pending:self.message.setText(f'Seguimiento: {elapsed//60:02}:{elapsed%60:02}. La versión anterior no publica porcentaje. Proyecto y originales conservados.')
            if self.pending and current['identity']!=self.target['identity']:
                self.message.setText('La versión anterior inició otra fase; no se interrumpirá automáticamente.');self.pending=False
            self.target=current
            if not self.pending:self.title.setText(current['kind']+' · En curso');self.cancel.setEnabled(True)
            return
        self.progress.setRange(0,1);self.progress.setValue(1);self.cancel.setEnabled(False)
        self.title.setText('Render anterior interrumpido' if self.pending else 'Proceso de render finalizado')
        self.message.setText('Proyecto y originales conservados. La ventana anterior muestra el resultado o error; ya puedes volver a ella.')


def show_legacy_job(gui_pid,target):
    from .instance import Instance
    channel=Instance(name='job')
    if not channel.claim():
        state=channel.request('focus');focus_window(state['window']);return 0
    try:
        app=QApplication.instance() or QApplication([])
        from .tokens import apply_theme
        apply_theme(app);window=LegacyJobPanel(gui_pid,target);show_and_focus(window)
        timer=QTimer(window);timer.timeout.connect(lambda:channel.poll(window.activate));timer.start(50)
        return app.exec()
    finally:channel.close()

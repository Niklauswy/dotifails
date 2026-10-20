"""Explicit launcher activation, including safe controls for a legacy live recorder."""
import os
import json
from pathlib import Path
import subprocess
import time
from PySide6.QtCore import QTimer,Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QInputDialog,QMessageBox


def focus_window(window_id):
    """Qt already requested focus; the compositor decides whether to grant it."""
    return False


def show_and_focus(widget):
    widget.showNormal();widget.raise_();widget.activateWindow()
    # WM must first manage/remap a newly shown window; retry without global rules.
    for delay in (0,100,300):QTimer.singleShot(delay,widget,lambda:focus_window(int(widget.winId())) if widget.isVisible() else None)


def owned_capture(gui_pid,proc=Path('/proc')):
    """Only a direct recorder child of this GUI, never another detached session."""
    candidates=[]
    children=(proc/str(gui_pid)/'task'/str(gui_pid)/'children').read_text().split()
    for pid in children:
        child=proc/pid
        try:
            if child.stat().st_uid!=os.getuid():continue
            args=(child/'cmdline').read_bytes().split(b'\0')
            index=args.index(b'loomrec.worker');root=Path(os.fsdecode(args[index+1]))
            candidates.append(root)
        except (OSError,ValueError,IndexError):continue
    if len(candidates)!=1:raise RuntimeError('No se pudo identificar de forma inequívoca la captura de esta ventana.')
    return candidates[0]


def live_recordings(proc=Path('/proc')):
    """Discover live same-user recorders by process/status identity, not GUI ownership."""
    found=[]
    for child in proc.glob('[0-9]*'):
        try:
            if child.stat().st_uid!=os.getuid():continue
            args=(child/'cmdline').read_bytes().split(b'\0');index=args.index(b'loomrec.worker')
            root=Path(os.fsdecode(args[index+1]));status=json.loads((root/'status.json').read_text())
            if status.get('pid')!=int(child.name) or time.time()-status.get('heartbeat',0)>15:continue
            if status.get('state') not in ('starting','recording','paused','stopping'):continue
            found.append(root)
        except (OSError,ValueError,IndexError):continue
    return found


class RecordingController(QDialog):
    """Map controls only after a finalized paused acknowledgement from the recorder."""
    def __init__(self,session,owner,target_label="Grabación de esta ventana"):
        super().__init__();self.session=session;self.owner=owner;self.pending=None;self.failure=None;self.deadline=0
        from .components import surface,SoftButton
        self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground);self.setWindowTitle('Wysun Recorder · Controles')
        panel=self;layout=QVBoxLayout(self);layout.setContentsMargins(22,18,22,18)
        row=QHBoxLayout();layout.addLayout(row)
        self.title=QLabel('En pausa');self.title.setProperty('role','title');row.addWidget(self.title)
        self.timer_label=QLabel();row.addWidget(self.timer_label);row.addStretch()
        self.pause_button=SoftButton('Reanudar','play',primary=True);self.pause_button.clicked.connect(self.pause_requested);row.addWidget(self.pause_button)
        self.stop_button=SoftButton('Terminar','stop');self.stop_button.clicked.connect(self.stop_requested);row.addWidget(self.stop_button)
        hide=SoftButton('×',quiet=True);hide.setToolTip('Ocultar controles · mantener pausa');hide.clicked.connect(self.hide);row.addWidget(hide)
        self.warning=QLabel('Al reanudar, los controles se ocultan antes de continuar.');self.warning.setWordWrap(True);layout.addWidget(self.warning)
        self.warning.setProperty('role','subtitle');self.title.setProperty('role','section');self.timer_label.setProperty('role','subtitle')
        from .materials import apply_material
        apply_material(self,kind='controller',radius=28)
        self.setToolTip(target_label)
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(100);self.poll()

    def dock(self):
        screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();geo=screen.availableGeometry()
        self.setFixedWidth(min(620,max(120,geo.width()-24)));self.adjustSize()
        self.move(max(geo.left(),geo.center().x()-self.width()//2),max(geo.top(),geo.bottom()-self.height()-28))

    def prepare_show(self):
        state=self.session.status()['state']
        if state=='paused':
            self.pending=None;self.failure=None;self.pause_button.setEnabled(True);self.stop_button.setEnabled(True);self.poll();self.dock();show_and_focus(self)
        elif state in ('starting','recording'):
            self.hide()
            if self.pending!='show_paused':
                try:self.session.pause()
                except (OSError,ValueError,RuntimeError) as exc:self.fail('No se pudo solicitar la pausa: '+str(exc));return
                self.pending='show_paused';self.deadline=time.monotonic()+15
        elif state in ('stopped','error','interrupted'):
            self.fail('La sesión ya no está grabando. Abre el proyecto desde la biblioteca.')

    def fail(self,message):
        self.hide();self.pending=None;self.failure=message
        # Never post a desktop popup into a potentially active full-screen capture.
        # A safe external badge is used only when its complete rectangle is outside.
        from .capture_feedback import RecordingIndicator
        self.error_indicator=getattr(self,'error_indicator',RecordingIndicator())
        try:
            config=json.loads((self.session.root/'capture.json').read_text())
            self.error_indicator.present(config['rect'],[s.geometry().getRect() for s in QApplication.screens()])
            if self.error_indicator.badge:self.error_indicator.badge.setText('No se pudo pausar');self.error_indicator.badge.setToolTip(message)
            QTimer.singleShot(5000,self,self.error_indicator.hide)
        except (OSError,ValueError,KeyError):pass
        root=Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'loomrec';root.mkdir(parents=True,exist_ok=True)
        from ..schema import atomic_json
        atomic_json(root/'controls-status.json',{'error':message,'time':time.time()})
        print('Wysun Recorder: '+message,file=__import__('sys').stderr,flush=True)

    def pause_requested(self):
        if self.session.status()['state']!='paused':self.prepare_show();return
        try:
            owner=self.owner.request('status',timeout=.7)
            if owner.get('project_path') and Path(owner['project_path']).parent.resolve()!=self.session.root.resolve():raise RuntimeError('La ventana controla otra sesión.')
            if owner.get('controls_protocol')==1:
                if not self.owner.request('hide_controls',timeout=.7).get('hidden'):raise RuntimeError('Los controles siguen visibles.')
            else:
                raise RuntimeError('Los controles antiguos no permiten comprobar la ocultación; usa los controles de la ventana actual.')
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
            self.warning.setText('No se reanudó: '+str(exc));return
        self.pending='recording';self.deadline=time.monotonic()+15;self.pause_button.setEnabled(False);self.stop_button.setEnabled(False);self.hide()
        if hasattr(self,'error_indicator'):self.error_indicator.hide()
        QTimer.singleShot(500,self,self.resume_after_hidden)

    def resume_after_hidden(self):
        if self.pending=='recording' and not self.isVisible() and self.session.status()['state']=='paused':self.session.resume()

    def stop_requested(self):
        if self.session.status()['state']!='paused':self.prepare_show();return
        self.session.stop();self.pending='stopped';self.deadline=time.monotonic()+15;self.stop_button.setEnabled(False);self.pause_button.setEnabled(False)

    def activate(self,action):
        if action!='status':self.prepare_show()
        return {'pid':os.getpid(),'window':int(self.winId()) if self.isVisible() else None,'controller':True,'state':self.session.status()['state'],'pending':self.pending,'error':self.failure}

    def poll(self):
        status=self.session.status();state=status['state'];elapsed=max(0,int(status.get('duration',0)))
        self.timer_label.setText(f'{elapsed//60:02}:{elapsed%60:02} · En pausa')
        if state in ('starting','recording','stopping') and self.isVisible():self.hide()
        if self.pending=='show_paused' and state=='paused':self.prepare_show();return
        if self.pending=='recording' and state=='recording':self.pending=None;self.close();return
        if self.pending=='stopped' and state in ('stopped','error','interrupted'):
            try:
                response=self.owner.request('focus',timeout=.7)
                if response.get('window'):focus_window(response['window'])
            except (OSError,ValueError,RuntimeError):return
            self.pending=None;self.close();return
        if not self.pending and not self.isVisible() and state in ('stopped','error','interrupted','cleared'):
            # The capture ended elsewhere (tray, shortcut or owner): nothing is left to control.
            self.close();QApplication.quit();return
        if self.pending and (state in ('error','interrupted') or time.monotonic()>self.deadline):
            self.fail('No se confirmó la pausa o la operación. La barra permanece oculta; usa el atajo de pausa y vuelve a abrir los controles.')

    def closeEvent(self,event):
        if hasattr(self,'error_indicator'):self.error_indicator.hide()
        super().closeEvent(event)

def activate_response(response,owner):
    if 'job' not in response and response.get('state')=='idle':
        from .legacy_jobs import owned_render,show_legacy_job
        target=owned_render(response['pid'])
        if target:return show_legacy_job(response['pid'],target)
    if response.get('state')=='paused' and response.get('project_path'):
        response={**response,'result':'capture_kept_hidden'}
    if response.get('result')!='capture_kept_hidden':
        if response.get('window'):focus_window(response['window'])
        return 0
    from .instance import Instance
    from ..capture import CaptureSession
    controller=Instance(name='controller')
    if not controller.claim():
        controller.request('focus');return 0
    try:
        # Preserve the legacy GUI, its editor and service; only explicit buttons send commands.
        app=QApplication.instance() or QApplication([])
        if response.get('project_path'):
            root=Path(response['project_path']).parent;label='Grabación de esta ventana'
        else:
            candidates=live_recordings()
            if not candidates:
                QMessageBox.information(None,'Wysun Recorder','No hay una grabación activa con estado reciente.');return 0
            if len(candidates)==1:root=candidates[0]
            else:
                choices=[path.name for path in candidates]
                selected,accepted=QInputDialog.getItem(None,'Wysun Recorder · Grabaciones activas','Elige qué grabación quieres controlar:',choices,0,False)
                if not accepted:return 0
                root=candidates[choices.index(selected)]
            label='Grabación activa detectada: '+root.name
        session=CaptureSession.attach(root)
        from .tokens import apply_theme
        apply_theme(app);window=RecordingController(session,owner,label);window.prepare_show()
        activation=QTimer(window);activation.timeout.connect(lambda:controller.poll(window.activate));activation.start(50)
        return app.exec()
    finally:controller.close()

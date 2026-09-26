"""Native image/PDF quick look and an embedded, explicitly controlled mpv player."""
import json,os,socket,tempfile
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QProcess,QSize
from PySide6.QtGui import QPixmap,QKeySequence,QShortcut,QDesktopServices,QFont
from PySide6.QtWidgets import QDialog,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QScrollArea,QSlider,QPlainTextEdit,QApplication
from desktop_common import PANEL_STYLE,button,text_label
from file_media import FilePreviewJob,file_kind,duration_label,human_size
from icons import icon,badge

class VideoPlayer(QWidget):
    def __init__(self,path,parent=None):
        super().__init__(parent);self.path=str(path);self.process=None;self.sock=None;self.buffer=b'';self.props={};self.root=None;self.stopped=False
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);self.surface=QWidget();self.surface.setAttribute(Qt.WA_NativeWindow);self.surface.setStyleSheet('background:#090A0E;');self.surface.setMinimumHeight(250);layout.addWidget(self.surface,1)
        controls=QHBoxLayout();self.play_button=button('Reproducir',self.toggle,symbol='circle-play');controls.addWidget(self.play_button);self.position=QSlider(Qt.Horizontal);self.position.setRange(0,1000);self.position.sliderReleased.connect(self.seek);controls.addWidget(self.position,1);self.time_label=text_label('0:00 / 0:00','subtitle');controls.addWidget(self.time_label);self.mute=button('',lambda:self.send(['cycle','mute']),symbol='volume-2');controls.addWidget(self.mute);layout.addLayout(controls);self.status=text_label('Preparando vídeo…','subtitle');layout.addWidget(self.status)
        self.poll=QTimer(self);self.poll.setInterval(120);self.poll.timeout.connect(self.read_ipc);QTimer.singleShot(0,self.start)
    def start(self):
        if self.stopped:return
        if QApplication.platformName()=='offscreen':self.status.setText('Reproducción disponible en la sesión gráfica.');return
        self.root=tempfile.TemporaryDirectory(prefix='orbit-video-',dir=os.environ.get('XDG_RUNTIME_DIR','/tmp'));self.socket_path=str(Path(self.root.name)/'mpv.sock');self.process=QProcess(self)
        self.process.setStandardOutputFile(os.devnull);self.process.setStandardErrorFile(os.devnull);self.process.errorOccurred.connect(lambda *_:self.status.setText('No se pudo iniciar el reproductor.'));self.process.finished.connect(self.player_finished)
        args=['--no-config','--no-terminal','--load-scripts=no','--ytdl=no','--access-references=no','--audio-file-auto=no','--sub-auto=no','--osc=no','--input-default-bindings=no','--input-vo-keyboard=no','--idle=yes','--keep-open=yes','--pause=yes','--volume=65','--force-window=yes','--vo=x11','--hwdec=no','--vd-lavc-threads=2','--wid='+str(int(self.surface.winId())),'--input-ipc-server='+self.socket_path,'--',self.path]
        self.process.start('mpv',args);self.poll.start()
    def send(self,command):
        if not self.sock:return
        try:self.sock.sendall((json.dumps({'command':command})+'\n').encode())
        except OSError:pass
    def read_ipc(self):
        if not self.sock:
            if not Path(self.socket_path).exists():return
            try:
                s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(.025);s.connect(self.socket_path);s.setblocking(False);self.sock=s
                for i,name in enumerate(('time-pos','duration','pause','mute','eof-reached')):self.send(['observe_property',i,name])
                self.status.setText('Espacio reproduce o pausa · el audio se activa al reproducir.')
            except OSError:return
        try:
            while True:
                chunk=self.sock.recv(65536)
                if not chunk:break
                self.buffer+=chunk
        except BlockingIOError:pass
        except OSError:return
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:
                data=json.loads(line)
                if data.get('event')=='property-change':self.props[data['name']]=data.get('data')
            except (ValueError,KeyError):continue
        duration=self.props.get('duration') or 0;position=self.props.get('time-pos') or 0
        if not self.position.isSliderDown():self.position.setValue(int(position/duration*1000) if duration else 0)
        self.time_label.setText(duration_label(position)+' / '+duration_label(duration));paused=self.props.get('pause',True);self.play_button.setText('Reproducir' if paused else 'Pausar');self.play_button.setIcon(icon('circle-play' if paused else 'circle-pause'));self.mute.setIcon(icon('volume-x' if self.props.get('mute') else 'volume-2'))
    def toggle(self):
        if self.props.get('eof-reached'):self.send(['seek',0,'absolute'])
        self.send(['cycle','pause'])
    def seek(self):self.send(['seek',self.position.value()/10,'absolute-percent+exact'])
    def player_finished(self,code,*_):
        if not self.stopped:self.status.setText('No se pudo reproducir el archivo.' if code else 'Reproducción finalizada.')
    def stop(self):
        self.stopped=True;self.poll.stop();self.send(['quit'])
        if self.process and self.process.state()!=QProcess.NotRunning:
            if not self.process.waitForFinished(120):self.process.kill();self.process.waitForFinished(120)
        if self.sock:self.sock.close();self.sock=None
        if self.root:self.root.cleanup();self.root=None

class FileViewer(QDialog):
    def __init__(self,path,parent=None):
        super().__init__(parent);self.path=str(path);self.kind=file_kind(path);self.page=1;self.pages=1;self.job=None;self.image=None;self.zoom=1.;self.player=None;self.pending_page=1
        self.setWindowTitle('Vista previa · '+Path(path).name);self.setWindowModality(Qt.WindowModal);self.setStyleSheet(PANEL_STYLE);self.resize(980,680)
        outer=QVBoxLayout(self);outer.setContentsMargins(20,18,20,16);outer.setSpacing(12);header=QHBoxLayout();names=QVBoxLayout();names.addWidget(text_label(Path(path).name,'title'));self.summary=text_label(str(Path(path).parent),'subtitle');names.addWidget(self.summary);header.addLayout(names,1);header.addWidget(button('Cerrar',self.reject,symbol='x'));outer.addLayout(header)
        if self.kind in ('video','audio'):
            self.player=VideoPlayer(path,self);outer.addWidget(self.player,1);QShortcut(QKeySequence('Space'),self).activated.connect(self.player.toggle)
        else:
            self.scroll=QScrollArea();self.scroll.setWidgetResizable(False);self.scroll.setAlignment(Qt.AlignCenter);self.image_label=QLabel();self.image_label.setAlignment(Qt.AlignCenter);self.scroll.setWidget(self.image_label);outer.addWidget(self.scroll,1);self.text=QPlainTextEdit();self.text.setReadOnly(True);self.text.setFont(QFont('DejaVu Sans Mono',11));outer.addWidget(self.text,1);self.text.hide()
            controls=QHBoxLayout();self.previous=button('Anterior',lambda:self.turn_page(-1),symbol='arrow-left');self.next=button('Siguiente',lambda:self.turn_page(1),symbol='chevron-right');self.page_label=text_label('');controls.addWidget(self.previous);controls.addWidget(self.page_label);controls.addWidget(self.next);controls.addStretch();controls.addWidget(button('−',lambda:self.scale(.8)));controls.addWidget(button('Ajustar',self.fit));controls.addWidget(button('+',lambda:self.scale(1.25)));outer.addLayout(controls)
            for w in (self.previous,self.next,self.page_label):w.setVisible(Path(path).suffix.lower()=='.pdf')
            self.load()
        QShortcut(QKeySequence('Escape'),self).activated.connect(self.reject)
    def load(self):
        if self.job and self.job.isRunning():self.pending_page=self.page;return
        self.pending_page=self.page;self.job=FilePreviewJob(self.path,self.page);page=self.page;self.job.ready.connect(lambda path,data,p=page:self.loaded(p,data));self.job.finished.connect(lambda p=page:self.load() if self.page!=p else None);self.job.start()
    def loaded(self,page,data):
        if page!=self.page:return
        meta=data.get('meta',{});self.pages=meta.get('pages',1);self.page_label.setText(f'{page} / {self.pages}');self.previous.setEnabled(page>1);self.next.setEnabled(page<self.pages)
        self.summary.setText(human_size(meta.get('size',0))+' · '+meta.get('mime','')+' · '+str(Path(self.path).parent));self.image=data.get('image')
        if self.image is not None and not self.image.isNull():self.scroll.show();self.text.hide();self.fit()
        else:self.scroll.hide();self.text.setPlainText(data.get('text') or data.get('error','Sin vista previa.'));self.text.show()
    def fit(self):
        if self.image is None or self.image.isNull():return
        available=self.scroll.viewport().size()-QSize(12,12);self.zoom=min(available.width()/self.image.width(),available.height()/self.image.height(),1.);self.render_image()
    def scale(self,factor):self.zoom=max(.1,min(4,self.zoom*factor));self.render_image()
    def render_image(self):
        if self.image is None or self.image.isNull():return
        pix=QPixmap.fromImage(self.image).scaled(self.image.size()*self.zoom,Qt.KeepAspectRatio,Qt.SmoothTransformation);self.image_label.setPixmap(pix);self.image_label.resize(pix.size())
    def turn_page(self,step):self.page=max(1,min(self.pages,self.page+step));self.load()
    def done(self,result):
        if self.player:self.player.stop()
        super().done(result)
    def closeEvent(self,event):
        if self.player:self.player.stop()
        super().closeEvent(event)

"""One local camera preview, bounded in-memory frames and asynchronous release.

set_device(device) starts immediately; stop(callback) is the capture handoff fence.
The callback runs only when the child has exited (or no child ever opened). Owners
must call stop before capture/application teardown. Reparent this widget instead
of creating another preview for the same selected camera. No frames go to disk.
"""
import re
from PySide6.QtCore import Qt,QProcess,QTimer,Signal,QRectF
from PySide6.QtGui import QImage,QPainter,QColor,QPainterPath
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel


class _Canvas(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.image=QImage();self.setMinimumSize(160,90)
        self.setAccessibleName(self.tr('Vista previa de cámara'))
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        path=QPainterPath();path.addRoundedRect(QRectF(self.rect()),10,10);painter.setClipPath(path)
        painter.fillRect(self.rect(),QColor('#18263A'))
        if not self.image.isNull():
            size=self.image.size().scaled(self.size(),Qt.KeepAspectRatio)
            target=QRectF((self.width()-size.width())/2,(self.height()-size.height())/2,size.width(),size.height())
            painter.drawImage(target,self.image)
        else:
            painter.setPen(QColor('#BAC9DD'));painter.drawText(self.rect(),Qt.AlignCenter,self.tr('Cámara'))


class CameraPreview(QWidget):
    stateChanged=Signal(str)
    frameReady=Signal(QImage)
    released=Signal()
    WIDTH=320
    HEIGHT=180
    FRAME_BYTES=WIDTH*HEIGHT*3
    MAX_STDERR=4096

    def __init__(self,parent=None):
        super().__init__(parent)
        self.state='off';self.device=None;self._desired=None;self._process=None
        self._buffer=bytearray();self._stderr=bytearray();self._callbacks=[]
        self._stopping=False;self._failure=None;self._drain_pending=False
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(6)
        self.canvas=_Canvas(self);self.canvas.setMinimumHeight(112);self.canvas.setMaximumHeight(180);layout.addWidget(self.canvas)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setProperty('role','subtitle');layout.addWidget(self.status)
        self.setAccessibleName(self.tr('Vista previa local de cámara'))
        self._kill_timer=QTimer(self);self._kill_timer.setSingleShot(True);self._kill_timer.timeout.connect(self._kill)
        self._watchdog=QTimer(self);self._watchdog.setSingleShot(True);self._watchdog.timeout.connect(self._timeout)
        self._set_state('off')

    @property
    def is_running(self):
        return self._process is not None and self._process.state()!=QProcess.NotRunning

    def _set_state(self,state,detail=None):
        self.state=state
        messages={'off':self.tr('Cámara apagada'),'loading':self.tr('Abriendo cámara…'),
                  'live':self.tr('Vista previa en directo · solo en este equipo'),
                  'stopping':self.tr('Liberando cámara…'),'error':detail or self.tr('No se pudo abrir la cámara.')}
        self.status.setText(messages[state]);self.status.setAccessibleName(messages[state])
        self._reserve_status_space()
        QTimer.singleShot(0,self,self._resize_popup)
        self.stateChanged.emit(state)

    def _reserve_status_space(self):
        # Reserve the two-line live caption while loading so the first frame never
        # changes the canvas/caption boundary in a compact camera popup.
        height=max(self.status.fontMetrics().lineSpacing()*2+2,
                   self.status.heightForWidth(max(160,self.width())))
        self.status.setMinimumHeight(height)
        self.setMinimumHeight(self.canvas.minimumHeight()+self.layout().spacing()+height)
        self.updateGeometry()

    def _resize_popup(self):
        self._reserve_status_space()
        popup=self.window()
        if popup is self or popup.windowType()!=Qt.Popup or not popup.isVisible():return
        before=popup.geometry();popup.adjustSize()
        screen=popup.screen()
        if screen:
            area=screen.availableGeometry()
            popup.move(max(area.left(),min(before.x(),area.right()-popup.width()+1)),
                       max(area.top(),min(before.bottom()-popup.height()+1,area.bottom()-popup.height()+1)))

    def set_device(self,device):
        """Select /dev/videoN or None. Switches wait for the old process to exit."""
        if device is not None and not re.fullmatch(r'/dev/video\d+',str(device)):
            self.stop();self._failure=self.tr('Selecciona un dispositivo de cámara válido.');self._set_state('error',self._failure);return
        device=str(device) if device is not None else None
        if device==self._desired and self.state in ('loading','live'):return
        self._desired=device;self._failure=None
        self._clear_frame()
        if self._process is not None:
            self._begin_stop()
        elif device:
            self._start()
        else:self._set_state('off')

    def stop(self,on_stopped=None):
        """Nonblocking release fence; callback executes after process exit, never early."""
        if on_stopped is not None:self._callbacks.append(on_stopped)
        self._desired=None;self._failure=None;self._clear_frame()
        if self._process is not None:self._begin_stop()
        else:
            self.device=None;self._set_state('off')
            QTimer.singleShot(0,self,self._release_callbacks)

    def _command(self,device):
        # One decode/filter thread; low-rate RGB frames flow only through a local pipe.
        return 'ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-threads','1',
            '-f','v4l2','-i',device,'-an','-filter_threads','1',
            '-vf',f'fps=10,scale={self.WIDTH}:{self.HEIGHT}:force_original_aspect_ratio=decrease,pad={self.WIDTH}:{self.HEIGHT}:(ow-iw)/2:(oh-ih)/2',
            '-pix_fmt','rgb24','-threads','1','-f','rawvideo','pipe:1']

    def _start(self):
        if not self._desired or self._process is not None:return
        self.device=self._desired;self._buffer.clear();self._stderr.clear();self._stopping=False;self._failure=None
        process=QProcess(self);self._process=process
        process.setProcessChannelMode(QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(lambda:self._drain(process))
        process.readyReadStandardError.connect(lambda:self._read_error(process))
        process.finished.connect(lambda code,status:self._finished(process,code))
        process.errorOccurred.connect(lambda error:self._process_error(process,error))
        self._set_state('loading');self._watchdog.start(7000)
        try:program,args=self._command(self.device);process.start(program,args)
        except Exception:
            self._failure=self.tr('No se pudo iniciar la vista previa. Comprueba FFmpeg.');self._finished(process,-1)

    def _read_error(self,process):
        if process is not self._process:return
        self._stderr.extend(bytes(process.readAllStandardError()));self._stderr=self._stderr[-self.MAX_STDERR:]

    def _drain(self,process):
        if process is not self._process:return
        process.setReadChannel(QProcess.StandardOutput)
        # Bound each event-loop turn; retain only one complete frame plus a partial.
        budget=self.FRAME_BYTES*4
        latest=None
        while process.bytesAvailable()>0 and budget>0:
            data=bytes(process.read(min(65536,budget)));budget-=len(data)
            if not data:break
            if self._stopping:continue
            self._buffer.extend(data)
            while len(self._buffer)>=self.FRAME_BYTES:
                latest=bytes(self._buffer[:self.FRAME_BYTES]);del self._buffer[:self.FRAME_BYTES]
        if latest is not None and not self._stopping:
            image=QImage(latest,self.WIDTH,self.HEIGHT,self.WIDTH*3,QImage.Format_RGB888).copy()
            self.canvas.image=image;self.canvas.update();self._watchdog.start(5000)
            if self.state!='live':self._set_state('live')
            self.frameReady.emit(image)
        if process.bytesAvailable()>0 and not self._drain_pending:
            self._drain_pending=True
            def again():
                self._drain_pending=False;self._drain(process)
            QTimer.singleShot(0,self,again)

    def _process_error(self,process,error):
        if process is not self._process:return
        if error==QProcess.FailedToStart:
            self._failure=self.tr('No se pudo iniciar FFmpeg. Comprueba su instalación.');self._finished(process,-1)

    def _timeout(self):
        if not self._process:return
        self._failure=self.tr('La cámara no entrega imágenes. Comprueba la conexión o elige otra cámara.')
        self._desired=None;self._begin_stop()

    def _begin_stop(self):
        if self._stopping:return
        self._stopping=True;self._watchdog.stop();self._set_state('stopping')
        if self._process.state()==QProcess.NotRunning:self._finished(self._process,0);return
        self._process.terminate();self._kill_timer.start(800)

    def _kill(self):
        if self.is_running:self._process.kill()

    def _finished(self,process,code):
        if process is not self._process:return
        self._read_error(process);was_stopping=self._stopping
        self._kill_timer.stop();self._watchdog.stop();self._process=None;self.device=None;self._stopping=False
        process.deleteLater();self._clear_frame()
        if not was_stopping and not self._failure:
            diagnostic=bytes(self._stderr).decode('utf-8','replace').lower()
            if 'busy' in diagnostic:
                self._failure=self.tr('La cámara está ocupada por otra aplicación. Ciérrala allí y vuelve a seleccionar la cámara.')
            elif 'permission denied' in diagnostic:
                self._failure=self.tr('No hay permiso para abrir la cámara. Comprueba los permisos del dispositivo.')
            elif any(word in diagnostic for word in ('invalid argument','not supported','unsupported','pixel format')):
                self._failure=self.tr('El formato de esta cámara no es compatible. Elige otro dispositivo de vídeo de la cámara.')
            else:
                self._failure=self.tr('La cámara dejó de responder. Comprueba si otra aplicación la usa, reconéctala o elige otra cámara.')
        if self._failure:
            failure=self._failure;self._desired=None;self._set_state('error',failure)
        elif not self._desired:self._set_state('off')
        self._release_callbacks()
        if self._desired:self._start()

    def _release_callbacks(self):
        if self._process is not None:return
        callbacks,self._callbacks=self._callbacks,[]
        self.released.emit()
        for callback in callbacks:callback()

    def _clear_frame(self):
        self._buffer.clear();self.canvas.image=QImage();self.canvas.update()

    def hideEvent(self,event):
        # Popup dismissal must never leave an invisible camera consumer running.
        if self._process is not None or self._desired is not None:self.stop()
        super().hideEvent(event)

"""Pre-capture countdown and strictly out-of-crop recording feedback."""
import json,os,subprocess,time
from pathlib import Path
from ..portal import is_wayland
from PySide6.QtCore import Qt,QRect,QRectF,QTimer
from PySide6.QtGui import QShortcut,QKeySequence,QPainter,QColor,QLinearGradient,QPainterPath,QRegion,QPen
from PySide6.QtWidgets import QWidget,QLabel,QVBoxLayout,QHBoxLayout,QPushButton


def control_hints():
    from ..integration import shortcut_settings
    try:
        keys=shortcut_settings()
        return f"Abrir controles pausa la grabación: Super+Shift+L · Pausa: {keys['pause']} · Terminar: {keys['stop']}"
    except (OSError,ValueError,TypeError) as exc:return 'Revisa la configuración de atajos: '+str(exc)


def preference_path():
    return Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'loomrec'/'capture-ui.json'


def load_countdown():
    try:return max(0,min(30,int(json.loads(preference_path().read_text()).get('countdown',3))))
    except (OSError,ValueError,TypeError,AttributeError):return 3


def save_countdown(value):
    path=preference_path();path.parent.mkdir(parents=True,exist_ok=True)
    try:data=json.loads(path.read_text())
    except (OSError,ValueError):data={}
    if not isinstance(data,dict):data={}
    data['countdown']=max(0,min(30,int(value)))
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data));os.replace(temp,path)


def indicator_geometry(rect,screens,badge_size=(224,40)):
    """Native rectangles wholly outside the crop; prefer an uncaptured monitor."""
    area=QRect(*rect);bounds=[QRect(*s) for s in screens if s[2]>0 and s[3]>0]
    if area.isEmpty():return [],None
    x,y,w,h=rect;t=3
    candidates=[QRect(x-t,y-t,w+2*t,t),QRect(x-t,y+h,w+2*t,t),QRect(x-t,y,t,h),QRect(x+w,y,t,h)]
    borders=[]
    for candidate in candidates:
        for screen in bounds:
            piece=candidate.intersected(screen)
            if not piece.isEmpty() and not piece.intersects(area) and piece not in borders:borders.append(piece)
    bw,bh=badge_size
    for screen in sorted(bounds,key=lambda s:s.intersects(area)):
        nearby=[QRect(x,y-bh-10,bw,bh),QRect(x,y+h+10,bw,bh),QRect(x+w+10,y,bw,bh),QRect(x-bw-10,y,bw,bh)]
        corners=[QRect(screen.right()-bw-11,screen.top()+12,bw,bh),QRect(screen.left()+12,screen.top()+12,bw,bh),QRect(screen.left()+12,screen.bottom()-bh-11,bw,bh),QRect(screen.right()-bw-11,screen.bottom()-bh-11,bw,bh)]
        for place in (nearby+corners if screen.intersects(area) else corners):
            if screen.contains(place) and not place.intersects(area):return borders,place
    return borders,None


class Countdown(QWidget):
    """Dark compact card: big number inside a ring that drains each second."""
    def __init__(self,cancel):
        super().__init__(None,Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.setWindowTitle('Wysun Recorder · Cuenta atrás');self.setAttribute(Qt.WA_TranslucentBackground);self.setFixedSize(300,372)
        self.fraction=1.;self.total=0
        box=QVBoxLayout(self);box.setContentsMargins(28,34,28,22);box.setSpacing(10)
        self.number=QLabel();self.number.setAlignment(Qt.AlignCenter);self.number.setFixedHeight(176)
        self.number.setStyleSheet('font-size:88px;font-weight:700;color:#FFFFFF;background:transparent;');box.addWidget(self.number)
        caption=QLabel('La grabación empieza en');caption.setAlignment(Qt.AlignCenter);caption.setStyleSheet('font-size:13px;color:#AEB8C8;background:transparent;')
        box.insertWidget(0,caption)
        button=QPushButton('Cancelar  ·  Esc');button.setCursor(Qt.PointingHandCursor);button.clicked.connect(cancel)
        button.setStyleSheet('QPushButton{background:rgba(255,255,255,18);color:#E6EBF3;border:1px solid rgba(255,255,255,30);border-radius:16px;padding:7px 18px;font-size:13px;} QPushButton:hover{background:rgba(255,255,255,34);}')
        row=QHBoxLayout();row.addStretch();row.addWidget(button);row.addStretch();box.addLayout(row)
        self.hints=QLabel(control_hints().replace('Abrir controles pausa la grabación: ','Controles ').replace(' · ','  ·  '));self.hints.setWordWrap(True);self.hints.setAlignment(Qt.AlignCenter);self.hints.setStyleSheet('font-size:11px;color:#8A95A8;background:transparent;');box.addWidget(self.hints)
        self.tick=QTimer(self);self.tick.setInterval(30);self.tick.timeout.connect(self._advance);self._started=0.
        QShortcut(QKeySequence('Escape'),self,activated=cancel)
    def _advance(self):
        self.fraction=max(0.,1.-(time.monotonic()-self._started));self.update()
        if self.fraction<=0:self.tick.stop()
    def present(self,seconds,rect):
        self.number.setText(str(seconds));self.fraction=1.;self._started=time.monotonic();self.tick.start()
        area=QRect(*rect);self.move(area.center().x()-self.width()//2,area.center().y()-self.height()//2)
        from .activation import show_and_focus
        show_and_focus(self)
    def hideEvent(self,event):
        self.tick.stop();super().hideEvent(event)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        card=QRectF(self.rect()).adjusted(1,1,-1,-1)
        p.setPen(QPen(QColor(255,255,255,26),1));p.setBrush(QColor(14,18,27,236));p.drawRoundedRect(card,28,28)
        ring=QRectF(0,0,148,148);ring.moveCenter(QRectF(self.number.geometry()).center())
        p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor(255,255,255,28),8,Qt.SolidLine,Qt.RoundCap));p.drawEllipse(ring)
        p.setPen(QPen(QColor('#E5484D'),8,Qt.SolidLine,Qt.RoundCap));p.drawArc(ring,90*16,int(-360*16*self.fraction))


COLORS={
    'selected':('#2569CA','#B8DBFF'),
    'countdown':('#2569CA','#B8DBFF'),
    'starting':('#2569CA','#B8DBFF'),
    'recording':('#D2384D','#FFD7DD'),
    'paused':('#A96815','#FFDE9E'),
    'stopping':('#52647B','#CBD5E1'),
}
TERMINAL={'stopped','error','interrupted','cleared'}


def elapsed_text(seconds):
    seconds=max(0,int(seconds));hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
    return f'{hours:02}:{minutes:02}:{seconds:02}' if hours else f'{minutes:02}:{seconds:02}'


class RecordingBorder(QWidget):
    """A quiet moving light on a solid strip, with no pixels inside the crop."""
    def __init__(self):
        super().__init__();self.phase=0.;self.state='selected';self.motion=True
    def paintEvent(self,event):
        painter=QPainter(self);base,light=COLORS.get(self.state,COLORS['starting'])
        painter.fillRect(self.rect(),QColor(base))
        if self.state not in ('selected','countdown','recording'):return
        if not self.motion:return
        horizontal=self.width()>self.height();length=self.width() if horizontal else self.height()
        span=min(120,max(32,length//4));position=self.phase*(length+2*span)-span
        gradient=QLinearGradient(position-span if horizontal else 0,0 if horizontal else position-span,position+span if horizontal else 0,0 if horizontal else position+span)
        gradient.setColorAt(0,QColor(base));gradient.setColorAt(.5,QColor(light));gradient.setColorAt(1,QColor(base))
        painter.fillRect(self.rect(),gradient)


class RecordingBadge(QWidget):
    """A compact opaque pearl capsule; colored status is an accent, not a slab."""
    def __init__(self,on_pause=None,on_stop=None):
        super().__init__();self.setAttribute(Qt.WA_TranslucentBackground);self._rendered_state=None;self._text='';self.state='starting'
        self.dot=QLabel('●');self.dot.setFixedWidth(12);self.dot.setAlignment(Qt.AlignCenter)
        self.caption=QLabel();row=QHBoxLayout(self);row.setContentsMargins(12,0,10,0);row.setSpacing(7);row.addWidget(self.dot);row.addWidget(self.caption,1)
        self.pause_button=None;self.stop_button=None;self._pending=False
        self.setStyleSheet('QLabel {background:transparent;color:#29435E;font-size:13px;font-weight:600;} QPushButton {background:transparent;color:#365776;border:0;border-radius:14px;padding:0 8px;min-width:44px;font-size:12px;font-weight:600;} QPushButton:hover {background:#DAE7F5;} QPushButton:pressed {background:#CBDDF0;} QPushButton:disabled {color:#8394A7;}')
        for name,callback,attribute in [('Pausar',on_pause,'pause_button'),('Terminar',on_stop,'stop_button')]:
            if callback is None:continue
            button=QPushButton(name);button.setFocusPolicy(Qt.NoFocus);button.setCursor(Qt.PointingHandCursor);button.setFixedHeight(44);button.setMinimumWidth(44)
            button.clicked.connect(lambda _,callback=callback:self.dispatch(callback));row.addWidget(button);setattr(self,attribute,button)
    def resizeEvent(self,event):
        path=QPainterPath();path.addRoundedRect(QRectF(self.rect()),18,18);self.setMask(QRegion(path.toFillPolygon().toPolygon()));super().resizeEvent(event)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
        gradient=QLinearGradient(0,0,0,self.height());gradient.setColorAt(0,QColor('#F7FAFE'));gradient.setColorAt(1,QColor('#E8F0F9'))
        painter.setBrush(gradient);painter.setPen(QPen(QColor('#B7CADE'),1));painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),18,18)
    def dispatch(self,callback):
        if self._pending:return
        self._pending=True
        for button in (self.pause_button,self.stop_button):
            if button:button.setEnabled(False)
        # The owner retains pause/ACK/resume/stop sequencing. Never command a worker here.
        try:callback()
        except Exception:
            self._pending=False;raise
    def text(self):return self._text
    def setText(self,text):
        if text!=self._text:
            self._text=text;self.caption.setText(text.removeprefix('● ').removeprefix('Ⅱ '));self.setAccessibleName(text)
    def render_state(self,state,text,changed):
        if self._rendered_state!=state:
            self.state=state;accent=COLORS.get(state,COLORS['starting'])[0]
            self.dot.setStyleSheet('color:'+accent+';background:transparent;font-size:13px;')
            self.caption.setStyleSheet('color:'+('#35608D' if state in ('selected','countdown','starting') else '#29435E')+';background:transparent;');self._rendered_state=state;self.update()
        if changed:self._pending=False
        self.setText(text)
        for button in (self.pause_button,self.stop_button):
            if button:button.setEnabled(state in ('recording','paused') and not self._pending)
        if self.pause_button:self.pause_button.setText('Reanudar' if state=='paused' else 'Pausar')


class RecordingIndicator:
    """Presentation only: the owner supplies state and owns every capture command."""
    def __init__(self,clock=None):
        self.windows=[];self.badge=None;self.borders=[];self.state='stopped';self.phase=0.
        self.rect=None;self.screens=[];self.on_pause=None;self.on_stop=None;self.remaining=None
        self._clock=clock or time.monotonic;self._elapsed=0.;self._running_since=None
        self.timer=QTimer();self.timer.setInterval(70);self.timer.timeout.connect(self.animate)
    @property
    def elapsed(self):
        return self._elapsed+(max(0,self._clock()-self._running_since) if self._running_since is not None else 0)
    def animate(self):
        from .motion import reduced_motion
        if reduced_motion():self.timer.stop()
        else:self.phase=(self.phase+.012)%1
        for border in self.borders:border.phase=self.phase;border.update()
        self._caption()
    def _clear_windows(self):
        self.timer.stop()
        for widget in self.windows:widget.hide();widget.deleteLater()
        self.windows=[];self.badge=None;self.borders=[]
    def hide(self):
        self._clear_windows();self.state='stopped';self.rect=None;self._elapsed=0.;self._running_since=None;self.remaining=None;self.on_pause=None;self.on_stop=None
    def select(self,rect,screens):
        return self.present(rect,screens,state='selected')
    def present(self,rect,screens,*,state='starting',on_pause=None,on_stop=None):
        self.hide();self.rect=list(rect);self.screens=[list(s) for s in screens];self.on_pause=on_pause;self.on_stop=on_stop
        self._build();self.update(state)
        return bool(self.windows)
    def relayout(self,rect,screens):
        """Recompute safe geometry without restarting the elapsed recording clock."""
        self._clear_windows();self.rect=list(rect);self.screens=[list(s) for s in screens]
        self._build();self.update(self.state)
        return bool(self.windows)
    def _build(self):
        # Wayland clients cannot place top-level windows: the compositor would
        # tile these strips and the badge over the desktop. The countdown, the
        # tray and the portal's own screen-share indicator remain.
        if is_wayland():return
        controls=bool(self.on_pause or self.on_stop)
        borders,badge=indicator_geometry(self.rect,self.screens,(390,44) if controls else (224,40))
        if controls and badge is None:
            borders,badge=indicator_geometry(self.rect,self.screens);controls=False
        for geometry in borders:
            widget=RecordingBorder();self.borders.append(widget);self._show(widget,geometry,False)
        if badge:
            self.badge=RecordingBadge(self.on_pause if controls else None,self.on_stop if controls else None)
            self._show(self.badge,badge,controls)
    def _show(self,widget,geometry,interactive):
        flags=Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus|Qt.NoDropShadowWindowHint
        if not is_wayland():flags|=Qt.X11BypassWindowManagerHint
        if not interactive:flags|=Qt.WindowTransparentForInput
        widget.setWindowFlags(flags);widget.setAttribute(Qt.WA_ShowWithoutActivating);widget.setFocusPolicy(Qt.NoFocus)
        widget.setGeometry(geometry);widget.setWindowTitle('Wysun Recorder · Indicador seguro')
        if not is_wayland() and os.environ.get('QT_QPA_PLATFORM')!='offscreen':
            try:subprocess.run(['xprop','-id',str(int(widget.winId())),'-f','_COMPTON_SHADOW','32c','-set','_COMPTON_SHADOW','0'],capture_output=True,timeout=.5)
            except (OSError,subprocess.SubprocessError):pass
        widget.show();self.windows.append(widget)
    def _caption(self,changed=False):
        if not self.badge:return
        text={'selected':'Área seleccionada','countdown':f'Comienza en {max(0,int(self.remaining or 0))} s','starting':'Preparando…','recording':'● Grabando · '+elapsed_text(self.elapsed),'paused':'Ⅱ En pausa · '+elapsed_text(self.elapsed),'stopping':'Finalizando…'}.get(self.state,'')
        self.badge.render_state(self.state,text,changed)
    def update(self,state,*,remaining=None):
        if state in TERMINAL:self.hide();return
        if state not in COLORS:raise ValueError('Unknown recording indicator state: '+str(state))
        changed=state!=self.state
        if changed:
            if self._running_since is not None:self._elapsed=self.elapsed;self._running_since=None
            if state=='recording':self._running_since=self._clock()
        self.state=state
        if remaining is not None:self.remaining=remaining
        from .motion import reduced_motion
        motion=not reduced_motion()
        for border in self.borders:border.state=state;border.motion=motion;border.update()
        if state in ('selected','countdown','recording') and self.borders and motion:self.timer.start()
        else:self.timer.stop()
        self._caption(changed)

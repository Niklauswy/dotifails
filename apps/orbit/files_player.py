"""Compact, keyboard-accessible controls for the isolated embedded mpv player."""
from PySide6.QtCore import Qt, Signal, QSize, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QKeySequence, QShortcut, QIcon, QPixmap, QPainter
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QSlider, QLabel, QWidget
from file_viewer import VideoPlayer
from files_motion import SoftButton, reduced_motion
from files_visuals import STYLE, COLORS, TOKENS

_SYMBOLS = {
    'play': '<path d="m9 5 10 7-10 7z"/>',
    'pause': '<path d="M8 5v14M16 5v14"/>',
    'volume': '<path d="m11 4-6 5H2v6h3l6 5zM15 8a6 6 0 0 1 0 8M18 5a10 10 0 0 1 0 14"/>',
    'muted': '<path d="m11 4-6 5H2v6h3l6 5zM16 9l6 6M22 9l-6 6"/>',
    'fullscreen': '<path d="M8 3H3v5M16 3h5v5M21 16v5h-5M8 21H3v-5"/>',
    'restore': '<path d="M3 8h5V3M16 3v5h5M21 16h-5v5M8 21v-5H3"/>',
    'audio': '<path d="M9 18V5l11-2v12M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="15" rx="3" ry="2"/>',
}

def transport_icon(symbol, color=None, size=20):
    color = color or COLORS['text']
    data = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size*2}" height="{size*2}" '
            f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round">{_SYMBOLS[symbol]}</svg>')
    pixmap = QPixmap(); pixmap.loadFromData(data.encode(), 'SVG'); pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)

class TransportButton(SoftButton):
    """Native button with a short interruptible crossfade between transport states."""
    def __init__(self, symbol, label, parent=None, primary=False):
        super().__init__(parent)
        self.setFixedSize(38 if primary else 32, 38 if primary else 32)
        self.setIconSize(QSize(19,19)); self.setCursor(Qt.PointingHandCursor)
        self.setObjectName('mediaPlay' if primary else 'mediaControl')
        self._symbol=None; self._frame=QIcon(); self._old=QIcon(); self._next=QIcon()
        self._fade=QVariantAnimation(self); self._fade.setDuration(TOKENS['motion']['fast'])
        self._fade.setEasingCurve(QEasingCurve.OutCubic); self._fade.valueChanged.connect(self._blend)
        self.set_symbol(symbol,label)
    def set_symbol(self,symbol,label):
        self.setText(''); self.setToolTip(label); self.setAccessibleName(label)
        if symbol==self._symbol:
            self.setIcon(self._frame); return
        self._fade.stop(); self._old=self._frame; self._next=transport_icon(symbol); self._symbol=symbol
        if self._old.isNull() or reduced_motion() or not self.isVisible():
            self._frame=self._next; self.setIcon(self._frame)
        else:
            self._fade.setStartValue(0.0); self._fade.setEndValue(1.0); self._fade.start()
    def _blend(self,amount):
        pixmap=QPixmap(40,40); pixmap.fill(Qt.transparent); pixmap.setDevicePixelRatio(2)
        painter=QPainter(pixmap)
        for icon,opacity in ((self._old,1.0-amount),(self._next,amount)):
            painter.setOpacity(opacity); painter.drawPixmap(0,0,icon.pixmap(QSize(20,20),2.0))
        painter.end(); self._frame=QIcon(pixmap); self.setIcon(self._frame)

class InlinePlayer(VideoPlayer):
    fullscreenRequested=Signal(bool)
    def __init__(self,path,parent=None,audio=False):
        self.fullscreen=False; self.audio=audio
        super().__init__(path,parent)
        self.setObjectName('inlineMedia'); self.setMinimumWidth(0)
        self.setStyleSheet(STYLE+f'''
            QWidget#inlineMedia, QWidget#mediaAudio {{ background: transparent; border: none; }}
            QWidget#mediaControls {{ background: rgba(245,247,250,210); border: 1px solid rgba(255,255,255,190); border-radius: 12px; }}
            QPushButton#mediaPlay {{ background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 19px; padding: 0; }}
            QPushButton#mediaPlay:hover {{ background: {COLORS['hover']}; }}
            QPushButton#mediaPlay:pressed {{ background: {COLORS['pressed']}; }}
            QPushButton#mediaControl {{ border-radius: 8px; padding: 0; }}
            QPushButton#mediaControl:focus, QPushButton#mediaPlay:focus {{ border: 1px solid {COLORS['focus']}; }}
            QLabel#mediaTime {{ color: {COLORS['muted']}; font-size: 11px; }}
            QLabel#mediaStatus {{ color: {COLORS['muted']}; font-size: 11px; padding: 4px 2px; }}
            QSlider#mediaPosition, QSlider#mediaVolume {{ background: transparent; border: none; }}
            QSlider#mediaPosition::groove:horizontal, QSlider#mediaVolume::groove:horizontal {{ height: 3px; background: #cbd3dd; border-radius: 1px; }}
            QSlider#mediaPosition::handle:horizontal, QSlider#mediaVolume::handle:horizontal {{ width: 8px; background: {COLORS['paper']}; border: 2px solid {COLORS['accent']}; margin: -5px 0; border-radius: 6px; }}
        ''')
        self.surface.setMinimumHeight(100); self.surface.setVisible(not audio)
        self.surface.setProperty('orbitOriginalStyle',None); self.surface.setStyleSheet('background: #11161e;')
        layout=self.layout(); layout.setSpacing(8)
        original_controls=layout.takeAt(1).layout()
        for widget in (self.play_button,self.position,self.time_label,self.mute): original_controls.removeWidget(widget)
        self.play_button.hide(); self.mute.hide(); self.play_button.deleteLater(); self.mute.deleteLater(); original_controls.deleteLater()
        layout.removeWidget(self.status)
        self.play_button=TransportButton('play','Reproducir · Espacio',primary=True); self.play_button.clicked.connect(self.toggle)
        self.mute=TransportButton('volume','Silenciar'); self.mute.clicked.connect(lambda:self.send(['cycle','mute']))
        self.full_button=TransportButton('fullscreen','Pantalla completa · F'); self.full_button.setVisible(not audio)
        self.full_button.clicked.connect(lambda:self.set_fullscreen(not self.fullscreen))
        self.control_panel=QWidget(); self.control_panel.setObjectName('mediaControls')
        panel=QVBoxLayout(self.control_panel); panel.setContentsMargins(12,8,12,8); panel.setSpacing(2)
        self.position.setObjectName('mediaPosition'); self.position.setMinimumHeight(20)
        self.position.setAccessibleName('Posición de reproducción'); self.position.setToolTip('Arrastra para avanzar o retroceder')
        self.position.setTracking(False); self.position.setSingleStep(5); self.position.setPageStep(50)
        self.position.actionTriggered.connect(self._seek_keyboard)
        panel.addWidget(self.position)
        row=QHBoxLayout(); row.setContentsMargins(0,0,0,0); row.setSpacing(6)
        row.addWidget(self.play_button)
        self.time_label.setObjectName('mediaTime'); self.time_label.setWordWrap(False); self.time_label.setMinimumWidth(76); self.time_label.setAccessibleName('Tiempo de reproducción')
        row.addWidget(self.time_label); row.addStretch(1); row.addWidget(self.mute)
        self.volume=QSlider(Qt.Horizontal); self.volume.setObjectName('mediaVolume')
        self.volume.setRange(0,100); self.volume.setValue(65); self.volume.setFixedWidth(76)
        self.volume.setMinimumHeight(24); self.volume.setAccessibleName('Volumen'); self.volume.setToolTip('Volumen: 65 %')
        self.volume.valueChanged.connect(self._set_volume)
        row.addWidget(self.volume); row.addWidget(self.full_button); panel.addLayout(row)
        if audio:
            self.audio_art=QLabel(); self.audio_art.setObjectName('mediaAudio')
            self.audio_art.setPixmap(transport_icon('audio',COLORS['muted'],48).pixmap(48,48))
            self.audio_art.setAlignment(Qt.AlignCenter); self.audio_art.setMinimumHeight(110)
            layout.insertWidget(0,self.audio_art,1)
        layout.addWidget(self.control_panel)
        self.status.setObjectName('mediaStatus'); self.status.setWordWrap(True)
        self.status.setProperty('orbitOriginalStyle',None); self.status.setStyleSheet('')
        for widget in (self.time_label,self.position): widget.setProperty('orbitOriginalStyle',None); widget.setStyleSheet('')
        layout.addWidget(self.status)
        self.refresh_controls(); self.poll.timeout.connect(self.refresh_controls)
        for key,callback in [('Space',self.toggle),('F',self._toggle_fullscreen),('M',lambda:self.send(['cycle','mute']))]:
            shortcut=QShortcut(QKeySequence(key),self); shortcut.setContext(Qt.WidgetWithChildrenShortcut); shortcut.activated.connect(callback)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'volume'):self.volume.setVisible(self.width()>=360)
    def _toggle_fullscreen(self):
        if not self.audio:self.set_fullscreen(not self.fullscreen)
    def _set_volume(self,value):
        self.volume.setToolTip(f'Volumen: {value} %'); self.send(['set_property','volume',value])
    def _seek_keyboard(self,action):
        if not self.position.isSliderDown() and action!=QSlider.SliderNoAction:
            self.send(['seek',self.position.sliderPosition()/10,'absolute-percent+exact'])
    def refresh_controls(self):
        ready=bool(self.sock)
        for widget in (self.play_button,self.position,self.mute,self.volume):widget.setEnabled(ready)
        paused=self.props.get('pause',True)
        self.play_button.set_symbol('play' if paused else 'pause',('Reproducir' if paused else 'Pausar')+' · Espacio')
        self.mute.set_symbol('muted' if self.props.get('mute') else 'volume','Activar audio · M' if self.props.get('mute') else 'Silenciar · M')
        self.status.setVisible(not ready)
    def set_fullscreen(self,enabled):
        if enabled==self.fullscreen or self.audio:return
        self.fullscreen=enabled
        self.full_button.set_symbol('restore' if enabled else 'fullscreen','Salir de pantalla completa · Esc' if enabled else 'Pantalla completa · F')
        self.fullscreenRequested.emit(enabled)
    def player_finished(self,code,*args):
        super().player_finished(code,*args)
        if not self.stopped:
            self.poll.stop()
            if self.sock:self.sock.close();self.sock=None
            self.refresh_controls()
    def stop(self):
        self.set_fullscreen(False);super().stop()

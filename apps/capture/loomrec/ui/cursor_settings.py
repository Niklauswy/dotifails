"""Shared pre-record cursor intent and a synthetic, memory-only demonstration."""
import math
from PySide6.QtCore import QObject,Signal,QTimer,Qt,QPointF,QRectF,QSignalBlocker
from PySide6.QtGui import QPainter,QColor,QPen,QPolygonF
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout
from .components import CheckBox,ComboBox,Disclosure,label
from .motion import reduced_motion
from .tokens import color
from ..cursor import CURSOR_ARROW,CURSOR_FILL,CURSOR_OUTLINE,CURSOR_ACCENT,HALO_RADIUS,CLICK_DURATION,effect_settings

PRESETS=(('Sencillo','simple'),('Presentación','presentation'),('Estela','trail'))

class CursorOptions(QObject):
    changed=Signal()
    def __init__(self,owner,prefs,save):
        super().__init__(owner);self.owner=owner;self.save=save;self.visible=bool(prefs.get('cursor',True));self.live=bool(prefs.get('cursor_live',True))
        effects=prefs.get('cursor_effects',{})
        try:effect_settings(effects);self.effects=dict(effects)
        except (ValueError,TypeError):self.effects={}
        self.locked=False
    @property
    def preset(self):return self.effects.get('preset','simple')
    def set_locked(self,value):
        if self.locked!=value:self.locked=value;self.changed.emit()
    def update(self,*,visible=None,live=None,preset=None,**effects):
        if self.locked or self.owner.session or self.owner.capture_pending:
            self.changed.emit();return
        if visible is not None:self.visible=bool(visible)
        if live is not None:self.live=bool(live)
        if preset is not None:self.effects={} if preset=='simple' else {'preset':preset}
        if self.preset!='simple':self.effects.update(effects)
        self.save(cursor=self.visible,cursor_live=self.live,cursor_effects=dict(self.effects));self.changed.emit()
    def capture_values(self):return {'cursor':self.visible,'cursor_live':self.live,'cursor_effects':dict(self.effects)}
    def summary(self):
        if not self.visible:return self.tr('Cursor oculto en el video')
        return self.tr('Cursor: ')+dict((value,self.tr(title)) for title,value in PRESETS)[self.preset]

class CursorDemo(QWidget):
    def __init__(self,model,parent=None):
        super().__init__(parent);self.model=model;self.phase=0.;self.setFixedHeight(112)
        self.setAccessibleName(self.tr('Demostración local del cursor; no captura la pantalla'))
        self.timer=QTimer(self);self.timer.setInterval(40);self.timer.timeout.connect(self.tick);model.changed.connect(self.sync)
    def sync(self):
        animate=self.isVisible() and self.model.visible and not self.model.locked and not reduced_motion()
        if animate:self.timer.start()
        else:self.timer.stop()
        self.update()
    def tick(self):
        if reduced_motion():self.sync();return
        self.phase=(self.phase+.04)%4.;self.update()
    def showEvent(self,event):super().showEvent(event);self.sync()
    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen);p.setBrush(color('inset'));p.drawRoundedRect(QRectF(self.rect()),12,12)
        p.setBrush(color('track'));p.drawRoundedRect(QRectF(18,18,90,9),4,4);p.drawRoundedRect(QRectF(18,35,130,6),3,3)
        p.setPen(color('muted'));p.drawText(QRectF(18,80,self.width()-36,24),Qt.AlignLeft|Qt.AlignVCenter,self.tr('Demostración local') if self.model.visible else self.tr('El cursor no aparecerá en el video'))
        if not self.model.visible:return
        e=effect_settings(self.model.effects);enhanced=bool(e);t=self.phase
        size=e.get('size',32) if enhanced else 22;scale=size/32
        def point(q):return QPointF(self.width()*.56+math.sin(q*math.pi/2)*self.width()*.12,46+math.cos(q*math.pi/2)*12)
        def disc(center,radius,opacity):
            color=QColor(CURSOR_ACCENT);color.setAlpha(opacity);p.setPen(Qt.NoPen);p.setBrush(color);p.drawEllipse(center,radius,radius)
        center=point(t)
        if enhanced and e['trail']:
            for i in range(1,7):disc(point(t-e['trail_duration']*i/6),(7-i*.65)*scale,255-(140+i*16))
        if enhanced and e['halo']:disc(center,HALO_RADIUS*scale,35)
        if enhanced and e['clicks']:
            elapsed=t%1. if not reduced_motion() else CLICK_DURATION*.45
            if elapsed<CLICK_DURATION:
                progress=elapsed/CLICK_DURATION
                disc(point(t-elapsed),(12+20*progress)*scale,255-round(130+125*progress))
        p.translate(center);p.scale(scale,scale);p.setPen(QPen(QColor(CURSOR_OUTLINE),max(1/scale,1.3),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.setBrush(QColor(CURSOR_FILL))
        p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in CURSOR_ARROW]))

class CursorPanel(QWidget):
    def __init__(self,model,*,demo=False,compact=False,parent=None):
        super().__init__(parent);self.model=model;self.compact=compact;body=QVBoxLayout(self);body.setContentsMargins(0,0,0,0);body.setSpacing(12)
        self.visible=CheckBox(self.tr('Mostrar cursor en el video'));self.visible.setAccessibleName(self.visible.text());body.addWidget(self.visible)
        row=QHBoxLayout();row.addWidget(label(self.tr('Estilo')),1);self.preset=ComboBox()
        for name,key in PRESETS:self.preset.addItem(self.tr(name),key)
        self.preset.setAccessibleName(self.tr('Estilo del cursor'));row.addWidget(self.preset,2);body.addLayout(row)
        self.live=CheckBox(self.tr('Ver efectos mientras grabo'));self.live.setToolTip(self.tr('Los efectos visibles quedan fijados en la grabación.'));self.live.toggled.connect(lambda value:model.update(live=value));body.addWidget(self.live)
        self.description=label('','subtitle');self.description.setWordWrap(True);body.addWidget(self.description)
        self.custom=Disclosure(self.tr('Personalizar efectos'));form=QFormLayout(self.custom.body);form.setContentsMargins(0,6,0,0);form.setSpacing(10)
        self.size=ComboBox()
        for text,value in [('Pequeño',24),('Mediano',32),('Grande',48)]:self.size.addItem(self.tr(text),value)
        self.size.setAccessibleName(self.tr('Tamaño del cursor'));form.addRow(self.tr('Tamaño'),self.size)
        self.effects={}
        for key,title in [('halo','Halo alrededor del cursor'),('clicks','Indicador de clic'),('trail','Estela al mover')]:
            box=CheckBox(self.tr(title));box.toggled.connect(lambda value,k=key:model.update(**{k:value}));form.addRow(box);self.effects[key]=box
        body.addWidget(self.custom)
        self.demo=CursorDemo(model) if demo else None
        if self.demo:body.addWidget(self.demo)
        self.visible.toggled.connect(lambda value:model.update(visible=value));self.preset.currentIndexChanged.connect(lambda _:model.update(preset=self.preset.currentData()));self.size.currentIndexChanged.connect(lambda _:model.update(size=self.size.currentData()))
        model.changed.connect(self.sync);self.sync()
    def sync(self):
        m=self.model;widgets=[self.visible,self.live,self.preset,self.size,*self.effects.values()];blocks=[QSignalBlocker(w) for w in widgets]
        self.visible.setChecked(m.visible);self.visible.setEnabled(not m.locked)
        from ..portal import is_wayland
        native=is_wayland()
        self.live.setChecked(m.live);self.live.setVisible(m.preset!='simple');self.live.setEnabled(m.visible and not m.locked)
        self.preset.setCurrentIndex(self.preset.findData(m.preset));self.preset.setEnabled(m.visible and not m.locked)
        size=m.effects.get('size',32);index=self.size.findData(size)
        if index<0:self.size.addItem(str(size)+' px',size);index=self.size.count()-1
        self.size.setCurrentIndex(index)
        for key,box in self.effects.items():box.setChecked(m.effects.get(key,m.preset=='trail' if key=='trail' else True))
        self.custom.setVisible(not self.compact and m.preset!='simple');self.custom.setEnabled(m.visible and not m.locked)
        enabled=[self.tr(title) for key,title in [('halo','halo'),('clicks','clics'),('trail','estela')] if m.effects.get(key,m.preset=='trail' if key=='trail' else True)]
        text=self.tr('El puntero del sistema, sin efectos añadidos.') if m.preset=='simple' else self.tr('Puntero mejorado')+(' · '+' · '.join(enabled) if enabled else self.tr(', sin efectos adicionales.'))
        if m.preset!='simple':text+='\n'+(self.tr('Visibles al grabar; quedan incluidos en el video.') if m.live else self.tr('Los efectos se verán al reproducir o exportar.'))
        if native and m.preset!='simple':text=self.tr('Halo, clics y estela en monitor o región: incluidos en el vídeo al grabar o aplicados al exportar según la opción. No son una capa visible sobre el escritorio. Clics requieren autorización temporal por grabación; nunca se observa el teclado. El puntero nativo mantiene su tamaño y forma del compositor. Efectos de ventana independiente aún no disponibles.')
        if m.locked:text=self.tr('Se conserva durante esta grabación. Cambia el estilo antes de la siguiente.')
        elif not m.visible:text=self.tr('Cursor oculto. Tu estilo se conserva para cuando lo actives.')
        self.description.setText(text)

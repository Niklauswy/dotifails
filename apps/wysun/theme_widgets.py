"""Theme selector widgets. Previews paint with the tokens of the previewed
variant, so they are always faithful to what applying it will show."""
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,Signal
from PySide6.QtGui import QPainter,QPainterPath,QPen,QPixmap,QLinearGradient
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QSizePolicy
from ui_motion import MotionButton
import theme_core
from theme_tokens import color,font,tokens


def _wallpaper(home,values,cache={}):
    path=str(Path(home)/'.local/share/backgrounds'/values['wallpaper'])
    if path not in cache:cache[path]=QPixmap(path)
    return cache[path]


class StyleChoice(MotionButton):
    """Large card for one style; shows the variant currently chosen for it."""
    def __init__(self,style,home,parent=None):
        spec=theme_core.styles()[style];super().__init__(spec['name'],parent);self.style_key=style;self.home=home;self.variant=spec['default_variant']
        self.setCheckable(True);self.setMinimumSize(240,250);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.setAccessibleName('Estilo '+spec['name']);self.setAccessibleDescription(spec['description'])
    def set_variant(self,variant):self.variant=variant;self.update()
    def paintEvent(self,event):
        own=tokens();values=theme_core.resolve(self.style_key,self.variant)
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);rect=QRectF(1,1,self.width()-2,self.height()-2);radius=own['radius_l']-4
        active=self.isChecked() or self.hasFocus()
        p.setBrush(color('surface',values=values));p.setPen(QPen(color('focus' if self.hasFocus() else 'accent',values=own) if active else color('line_strong',values=own),2 if active else 1));p.drawRoundedRect(rect,radius,radius)
        image=QRectF(12,12,self.width()-24,128);clip=QPainterPath();clip.addRoundedRect(image,values['radius_m'],values['radius_m']);p.save();p.setClipPath(clip)
        pixmap=_wallpaper(self.home,values)
        if not pixmap.isNull():
            scaled=pixmap.scaled(int(image.width()),int(image.height()),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
            p.drawPixmap(int(image.center().x()-scaled.width()/2),int(image.center().y()-scaled.height()/2),scaled)
        # A miniature window in the style's own material, radius and accent.
        window=QRectF(image.x()+18,image.y()+22,image.width()*.56,image.height()-40);r=values['radius_m']
        gradient=QLinearGradient(window.topLeft(),window.bottomLeft())
        for stop,name in ((0,'material_top'),(.52,'material_mid'),(1,'material_bottom')):gradient.setColorAt(stop,color(name,240 if values['translucent'] else 255,values))
        p.setBrush(gradient);p.setPen(QPen(color('material_edge',values=values),1));p.drawRoundedRect(window,r,r)
        p.setPen(Qt.NoPen);p.setBrush(color('text',values=values));p.drawRoundedRect(QRectF(window.x()+12,window.y()+12,window.width()*.5,6),3,3)
        p.setBrush(color('muted',values=values));p.drawRoundedRect(QRectF(window.x()+12,window.y()+24,window.width()*.7,4),2,2)
        p.setBrush(color('accent',values=values));p.drawRoundedRect(QRectF(window.right()-58,window.bottom()-26,46,16),values['radius_s']*.8,values['radius_s']*.8)
        p.restore()
        p.setPen(color('text',values=values));p.setFont(font(15,600,values=values));p.drawText(QRectF(18,150,self.width()-60,26),Qt.AlignLeft|Qt.AlignVCenter,theme_core.styles()[self.style_key]['name'])
        p.setPen(color('muted',values=values));p.setFont(font(9.5,values=values));p.drawText(QRectF(18,178,self.width()-36,40),Qt.TextWordWrap,theme_core.styles()[self.style_key]['description'])
        x=18
        for variant in theme_core.styles()[self.style_key]['variants']:
            swatch=theme_core.resolve(self.style_key,variant);on=variant==self.variant
            p.setPen(QPen(color('accent' if on else 'line_strong',values=values),2 if on else 1));p.setBrush(color('canvas',values=swatch));p.drawEllipse(QRectF(x,self.height()-32,18,18))
            p.setPen(Qt.NoPen);p.setBrush(color('accent',values=swatch));p.drawPie(QRectF(x+2,self.height()-30,14,14),-90*16,180*16);x+=26
        if self.isChecked():
            p.setPen(QPen(color('accent',values=values),2,Qt.SolidLine,Qt.RoundCap));x=self.width()-31;y=self.height()-24;p.drawLine(x-7,y,x-2,y+5);p.drawLine(x-2,y+5,x+8,y-6)


class VariantChoice(MotionButton):
    """Chip with the variant's canvas/surface/accent; checkable."""
    def __init__(self,style,variant,parent=None):
        values=theme_core.resolve(style,variant);super().__init__(values['name'],parent);self.style_key=style;self.variant=variant
        self.setCheckable(True);self.setMinimumHeight(44);self.setMinimumWidth(132)
        self.setAccessibleName('Variante '+values['name']);self.setAccessibleDescription(values['description']);self.setToolTip(values['description'])
    def paintEvent(self,event):
        own=tokens();values=theme_core.resolve(self.style_key,self.variant)
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);rect=QRectF(1,1,self.width()-2,self.height()-2);r=own['radius_control']
        on=self.isChecked()
        p.setBrush(color('selection' if on else 'fill',values=own));p.setPen(QPen(color('focus',values=own) if self.hasFocus() else color('selection_line' if on else 'line',values=own),own['focus_width'] if self.hasFocus() else 1));p.drawRoundedRect(rect,r,r)
        for i,name in enumerate(('canvas','surface','accent')):
            p.setPen(QPen(color('line_strong',values=own),1));p.setBrush(color(name,values=values));p.drawEllipse(QRectF(12+i*13,self.height()/2-8,16,16))
        p.setPen(color('selection_text' if on else 'control_text',values=own));p.setFont(font(role='body',weight=600 if on else 400,values=own))
        p.drawText(QRectF(60,0,self.width()-68,self.height()),Qt.AlignVCenter|Qt.AlignLeft,self.text())


class ThemePicker(QWidget):
    """Style cards plus the variants of the selected style."""
    changed=Signal(str,str)
    def __init__(self,home,style,variant,parent=None):
        super().__init__(parent);self.home=home;self.style_key,self.variant=theme_core.normalize(style,variant);self.memory={self.style_key:self.variant}
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(16)
        row=QHBoxLayout();row.setSpacing(18);self.styles={}
        for key in theme_core.styles():
            card=StyleChoice(key,home);card.clicked.connect(lambda checked=False,k=key:self.choose_style(k));self.styles[key]=card;row.addWidget(card,1)
        layout.addLayout(row)
        self.variant_row=QHBoxLayout();self.variant_row.setSpacing(8);layout.addLayout(self.variant_row);self.variants={}
        self.refresh()
    def choose_style(self,style):
        self.memory[self.style_key]=self.variant;self.style_key=style
        self.variant=self.memory.get(style,theme_core.styles()[style]['default_variant']);self.refresh();self.changed.emit(self.style_key,self.variant)
    def choose_variant(self,variant):
        self.variant=variant;self.memory[self.style_key]=variant;self.refresh();self.changed.emit(self.style_key,self.variant)
    def set_selection(self,style,variant):
        self.style_key,self.variant=theme_core.normalize(style,variant);self.memory[self.style_key]=self.variant;self.refresh()
    def refresh(self):
        for key,card in self.styles.items():
            card.setChecked(key==self.style_key);card.set_variant(self.memory.get(key,theme_core.styles()[key]['default_variant']))
        if set(self.variants)!=set(theme_core.styles()[self.style_key]['variants']):
            while self.variant_row.count():
                item=self.variant_row.takeAt(0)
                if item.widget():item.widget().deleteLater()
            self.variants={}
            for variant in theme_core.styles()[self.style_key]['variants']:
                chip=VariantChoice(self.style_key,variant);chip.clicked.connect(lambda checked=False,v=variant:self.choose_variant(v));self.variants[variant]=chip;self.variant_row.addWidget(chip)
            self.variant_row.addStretch(1)
        for variant,chip in self.variants.items():chip.setChecked(variant==self.variant);chip.update()

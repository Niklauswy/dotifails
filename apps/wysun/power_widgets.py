# Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
# Fuente: 507d66285e9d9fde9330adc64159cfdebb28c19a; véase THIRD_PARTY.md.
# Los QML de origen no incluyen avisos de copyright adicionales por archivo.
"""Painted battery gauge and session controls with native keyboard semantics."""
from theme_tokens import color, font, tokens

from PySide6.QtCore import Qt, QRectF, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget
from ui_motion import MotionButton, reduced_motion
from utility_material import material_icon

def glyph(name, size, tone): return material_icon(name, size, tone).pixmap(size, size)


class BatteryGauge(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        values=tokens();self.setFixedSize(values['space_xl']*5,values['space_xl']*5)
        self._level=0.;self.tone='accent';self.known=False;self.charging=False
        self.animation=QPropertyAnimation(self,b'level',self);self.animation.setDuration(values['motion_enter']);self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.setAccessibleName('Nivel de batería')
    def _set_level(self,value):self._level=value;self.update()
    level=Property(float,lambda self:self._level,_set_level)
    def set_value(self,value,charging=False):
        self.known=value is not None;self.charging=charging
        self.tone='success' if charging else 'warning' if value is not None and value<=20 else 'accent'
        self.setAccessibleDescription(f'{value} por ciento' if value is not None else 'Sin dato')
        if self.animation.endValue()==float(value or 0):self.update();return
        self.animation.stop();self.animation.setDuration(0 if reduced_motion(self.window()) else tokens()['motion_enter'])
        self.animation.setStartValue(self._level);self.animation.setEndValue(float(value or 0));self.animation.start()
    def paintEvent(self,event):
        values=tokens();p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        edge=values['space_s']+1;ring=values['space_xs']+2;side=min(self.width(),self.height())
        r=QRectF(edge,edge,side-edge*2,side-edge*2)
        p.setPen(QPen(color('track'),ring,Qt.SolidLine,Qt.RoundCap));p.drawArc(r,90*16,-360*16)
        if self.known:
            p.setPen(QPen(color(self.tone),ring,Qt.SolidLine,Qt.RoundCap));p.drawArc(r,90*16,round(-self._level*3.6*16))
        inner=values['space_xl']-1;disk=QRectF(inner,inner,side-inner*2,side-inner*2)
        p.setPen(Qt.NoPen);p.setBrush(color('card'));p.drawEllipse(disk)
        icon=values['icon_size']+values['space_s']
        p.drawPixmap(round(side/2-icon/2),round(disk.center().y()-icon/2-values['space_xs']/2),glyph('power',icon,self.tone))
        p.setPen(color('muted'));p.setFont(font(role='caption'))
        p.drawText(QRectF(inner,disk.bottom()-values['space_l']-values['space_s'],side-inner*2,values['font_caption']+values['space_s']),Qt.AlignCenter,'CARGANDO' if self.charging else 'ENERGÍA')


class SessionAction(MotionButton):
    def __init__(self,title,hint,symbol,danger=False,compact=False):
        super().__init__(title);self.hint=hint;self.symbol=symbol;self.danger=danger;self.compact=compact
        values=tokens();self.setMinimumHeight(values['space_xl']*3+(values['space_xs'] if compact else values['space_l']))
        self.setMinimumWidth(values['space_xl']*5)
        self.setAccessibleName(title);self.setAccessibleDescription(hint);self.setToolTip(hint)
    def paintEvent(self,event):
        values=tokens();p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.width()/2,self.height()/2);p.scale(self._press,self._press);p.translate(-self.width()/2,-self.height()/2)
        r=QRectF(1,1,self.width()-2,self.height()-2)
        fill=color('danger_fill' if self.danger else 'card_strong')
        if fill.alpha()<255:fill.setAlpha(min(255,fill.alpha()+round(18*self._hover)))
        edge='danger' if self.danger and self.hasFocus() else 'focus' if self.hasFocus() else 'danger_line' if self.danger else 'line_strong'
        p.setPen(QPen(color(edge),1.5 if self.hasFocus() else 1));p.setBrush(fill);p.drawRoundedRect(r,values['radius_m'],values['radius_m'])
        if self._hover and fill.alpha()==255:p.setPen(Qt.NoPen);p.setBrush(color('tint',round(10*self._hover)));p.drawRoundedRect(r,values['radius_m'],values['radius_m'])
        ink='danger' if self.danger else 'text';left=values['space_l']+2
        if self.compact:
            left=values['space_l']-1;icon=values['icon_size']+1;p.drawPixmap(left,left,glyph(self.symbol,icon,ink))
            p.setPen(color(ink));p.setFont(font(role='body',weight=600));top=left+icon+values['space_xs']
            p.drawText(QRectF(left,top,self.width()-left*2,self.height()-top-values['space_s']),Qt.AlignLeft|Qt.AlignVCenter,self.text())
        else:
            icon=values['icon_size']+values['space_xs'];p.drawPixmap(left,left+1,glyph(self.symbol,icon,ink))
            p.setPen(color(ink));p.setFont(font(role='heading',weight=600));title=p.fontMetrics()
            p.setPen(color('glyph_muted'));p.setFont(font(role='small'));hint=p.fontMetrics()
            content=title.height()+values['space_xs']+hint.height();top=(self.height()-content)/2
            p.setPen(color(ink));p.setFont(font(role='heading',weight=600));p.drawText(QRectF(left+icon+values['space_m'],top,self.width()-(left+icon+values['space_m'])*2,title.height()),Qt.AlignLeft|Qt.AlignVCenter,self.text())
            p.setPen(color('glyph_muted'));p.setFont(font(role='small'));p.drawText(QRectF(left,top+title.height()+values['space_xs'],self.width()-left*2,hint.height()),Qt.AlignLeft|Qt.AlignVCenter,self.hint)

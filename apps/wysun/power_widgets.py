"""Painted battery gauge and session controls with native keyboard semantics."""
from theme_tokens import color

from PySide6.QtCore import Qt, QRectF, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget
from ui_motion import MotionButton, reduced_motion
from icons import glyph


class BatteryGauge(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedSize(116,116);self._level=0.;self.tone='accent';self.known=False;self.charging=False
        self.animation=QPropertyAnimation(self,b'level',self);self.animation.setDuration(500);self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.setAccessibleName('Nivel de batería')
    def _set_level(self,value):self._level=value;self.update()
    level=Property(float,lambda self:self._level,_set_level)
    def set_value(self,value,charging=False):
        self.known=value is not None;self.charging=charging
        self.tone='success' if charging else 'warning' if value is not None and value<=20 else 'accent'
        self.setAccessibleDescription(f'{value} por ciento' if value is not None else 'Sin dato')
        if self.animation.endValue()==float(value or 0):self.update();return
        self.animation.stop();self.animation.setDuration(0 if reduced_motion(self.window()) else 500)
        self.animation.setStartValue(self._level);self.animation.setEndValue(float(value or 0));self.animation.start()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);r=QRectF(9,9,98,98)
        p.setPen(QPen(color('track'),6,Qt.SolidLine,Qt.RoundCap));p.drawArc(r,90*16,-360*16)
        if self.known:
            p.setPen(QPen(color(self.tone),6,Qt.SolidLine,Qt.RoundCap));p.drawArc(r,90*16,round(-self._level*3.6*16))
        p.setPen(Qt.NoPen);p.setBrush(color('card'));p.drawEllipse(QRectF(23,23,70,70))
        p.drawPixmap(44,38,glyph('power',28,self.tone));p.setPen(color('muted'));p.setFont(QFont('Inter',8))
        p.drawText(QRectF(23,70,70,16),Qt.AlignCenter,'CARGANDO' if self.charging else 'ENERGÍA')


class SessionAction(MotionButton):
    def __init__(self,title,hint,symbol,danger=False,compact=False):
        super().__init__(title);self.hint=hint;self.symbol=symbol;self.danger=danger;self.compact=compact
        self.setMinimumHeight(88 if not compact else 76);self.setMinimumWidth(120)
        self.setAccessibleName(title);self.setAccessibleDescription(hint);self.setToolTip(hint)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.width()/2,self.height()/2);p.scale(self._press,self._press);p.translate(-self.width()/2,-self.height()/2)
        r=QRectF(1,1,self.width()-2,self.height()-2)
        fill=color('danger_fill' if self.danger else 'card_strong')
        if fill.alpha()<255:fill.setAlpha(min(255,fill.alpha()+round(18*self._hover)))
        edge='danger' if self.danger and self.hasFocus() else 'focus' if self.hasFocus() else 'danger_line' if self.danger else 'line_strong'
        p.setPen(QPen(color(edge),1.5 if self.hasFocus() else 1));p.setBrush(fill);p.drawRoundedRect(r,14,14)
        if self._hover and fill.alpha()==255:p.setPen(Qt.NoPen);p.setBrush(color('tint',round(10*self._hover)));p.drawRoundedRect(r,14,14)
        ink='danger' if self.danger else 'text'
        if self.compact:
            p.drawPixmap(15,15,glyph(self.symbol,19,ink));p.setPen(color(ink));p.setFont(QFont('Inter',10,QFont.DemiBold));p.drawText(15,57,self.text())
        else:
            p.drawPixmap(18,19,glyph(self.symbol,22,ink));p.setPen(color(ink));p.setFont(QFont('Inter',11,QFont.DemiBold));p.drawText(52,35,self.text())
            p.setPen(color('glyph_muted'));p.setFont(QFont('Inter',9));p.drawText(18,65,self.hint)

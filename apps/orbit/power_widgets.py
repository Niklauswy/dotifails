"""Painted battery gauge and session controls with native keyboard semantics."""
from theme_tokens import ThemeColor, apply_style

from PySide6.QtCore import Qt, QRectF, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget
from ui_motion import MotionButton, reduced_motion
from icons import glyph


class BatteryGauge(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFixedSize(116,116);self._level=0.;self.color=ThemeColor('#A8C5F7');self.known=False;self.charging=False
        self.animation=QPropertyAnimation(self,b'level',self);self.animation.setDuration(500);self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.setAccessibleName('Nivel de batería')
    def _set_level(self,value):self._level=value;self.update()
    level=Property(float,lambda self:self._level,_set_level)
    def set_value(self,value,charging=False):
        self.known=value is not None;self.charging=charging
        self.color=QColor('#9CE0C0' if charging else '#F0B196' if value is not None and value<=20 else '#A8C5F7')
        self.setAccessibleDescription(f'{value} por ciento' if value is not None else 'Sin dato')
        if self.animation.endValue()==float(value or 0):self.update();return
        self.animation.stop();self.animation.setDuration(0 if reduced_motion(self.window()) else 500)
        self.animation.setStartValue(self._level);self.animation.setEndValue(float(value or 0));self.animation.start()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);r=QRectF(9,9,98,98)
        p.setPen(QPen(ThemeColor('#2C3C54'),6,Qt.SolidLine,Qt.RoundCap));p.drawArc(r,90*16,-360*16)
        if self.known:
            p.setPen(QPen(self.color,6,Qt.SolidLine,Qt.RoundCap));p.drawArc(r,90*16,round(-self._level*3.6*16))
        p.setPen(Qt.NoPen);p.setBrush(ThemeColor(176,206,254,8));p.drawEllipse(QRectF(23,23,70,70))
        p.drawPixmap(44,38,glyph('power',28,self.color.name()));p.setPen(ThemeColor('#9CABC2'));p.setFont(QFont('Inter',8))
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
        fill=ThemeColor(86,37,55,95) if self.danger else ThemeColor(127,166,225,18);fill.setAlpha(fill.alpha()+round(18*self._hover))
        edge='#E4A0B1' if self.danger and self.hasFocus() else '#ACC8F5' if self.hasFocus() else '#624453' if self.danger else '#43516A'
        p.setPen(QPen(QColor(edge),1.5 if self.hasFocus() else 1));p.setBrush(fill);p.drawRoundedRect(r,14,14)
        ink='#F1B5C0' if self.danger else '#DDE9FE'
        if self.compact:
            p.drawPixmap(15,15,glyph(self.symbol,19,ink));p.setPen(QColor(ink));p.setFont(QFont('Inter',10,QFont.DemiBold));p.drawText(15,57,self.text())
        else:
            p.drawPixmap(18,19,glyph(self.symbol,22,ink));p.setPen(QColor(ink));p.setFont(QFont('Inter',11,QFont.DemiBold));p.drawText(52,35,self.text())
            p.setPen(ThemeColor('#A6B7D0'));p.setFont(QFont('Inter',9));p.drawText(18,65,self.hint)

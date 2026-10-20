"""One thin, pixel-aligned native outline icon family."""
from PySide6.QtCore import Qt,QPointF,QRectF
from PySide6.QtGui import QIcon,QPixmap,QPainter,QPen,QColor,QPainterPath

def _pixmap(name,color,size,stroke=1.6):
    pix=QPixmap(size*2,size*2);pix.fill(Qt.transparent);p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);p.scale(size/24*2,size/24*2)
    p.setPen(QPen(QColor(color),stroke,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.setBrush(Qt.NoBrush)
    def line(a,b,c,d):p.drawLine(QPointF(a,b),QPointF(c,d))
    if name in ('screen','window','library'):
        p.drawRoundedRect(QRectF(3,4,18,13),2,2)
        if name=='screen':line(12,17,12,21);line(8,21,16,21)
        elif name=='window':line(3,8,21,8)
        else:line(8,4,8,17);line(11,9,18,9);line(11,12,16,12)
    elif name=='region':
        for x,y,dx,dy in [(4,4,5,5),(20,4,-5,5),(4,20,5,-5),(20,20,-5,-5)]:line(x,y,x+dx,y);line(x,y,x,y+dy)
        p.setPen(QPen(QColor(color),1,Qt.DotLine));p.drawRect(QRectF(8,8,8,8))
    elif name=='mic':
        p.drawRoundedRect(QRectF(9,3,6,12),3,3);p.drawArc(QRectF(6,7,12,12),180*16,180*16);line(12,19,12,22);line(9,22,15,22)
    elif name=='sound':
        path=QPainterPath();path.moveTo(4,9);path.lineTo(8,9);path.lineTo(13,5);path.lineTo(13,19);path.lineTo(8,15);path.lineTo(4,15);path.closeSubpath();p.drawPath(path);p.drawArc(QRectF(11,6,10,12),-65*16,130*16)
    elif name=='fullscreen':
        for x,y,dx,dy in [(4,4,5,5),(20,4,-5,5),(4,20,5,-5),(20,20,-5,-5)]:line(x,y,x+dx,y);line(x,y,x,y+dy)
    elif name=='muted':
        line(4,9,8,9);line(8,9,12,5);line(12,5,12,19);line(12,19,8,15);line(8,15,4,15);line(4,15,4,9);line(17,9,22,15);line(22,9,17,15)
    elif name=='camera':
        p.drawRoundedRect(QRectF(3,6,12,12),2,2);line(15,10,21,7);line(21,7,21,17);line(21,17,15,14)
    elif name in ('record','play'):
        if name=='record':p.setBrush(QColor(color));p.setPen(Qt.NoPen);p.drawEllipse(QRectF(6,6,12,12))
        else:
            path=QPainterPath();path.moveTo(9,5);path.lineTo(19,12);path.lineTo(9,19);path.closeSubpath();p.drawPath(path)
    elif name=='pause':
        p.drawRoundedRect(QRectF(6,5,4,14),1,1);p.drawRoundedRect(QRectF(14,5,4,14),1,1)
    elif name=='stop':
        p.setBrush(QColor(color));p.setPen(Qt.NoPen);p.drawRoundedRect(QRectF(5,5,14,14),3,3)
    elif name=='close':line(6,6,18,18);line(18,6,6,18)
    elif name=='rewind':
        p.drawArc(QRectF(4,4,16,16),-40*16,285*16);line(3,3,3,9);line(3,9,9,9);line(12,8,12,13);line(12,13,15,15)
    elif name=='forward':
        p.drawArc(QRectF(4,4,16,16),-65*16,-285*16);line(21,3,21,9);line(21,9,15,9);line(12,8,12,13);line(12,13,9,15)
    elif name=='copy':
        p.drawRoundedRect(QRectF(8,8,12,12),2,2);line(4,16,4,6);p.drawArc(QRectF(4,4,4,4),90*16,90*16);line(6,4,16,4)
    elif name=='refresh':
        p.drawArc(QRectF(4,4,16,16),35*16,285*16);line(20,3,20,9);line(20,9,14,9)
    elif name=='eye':
        path=QPainterPath();path.moveTo(2,12);path.cubicTo(7,3,17,3,22,12);path.cubicTo(17,21,7,21,2,12);p.drawPath(path);p.drawEllipse(QRectF(9,9,6,6))
    elif name=='search':p.drawEllipse(QRectF(4,3,12,12));line(14,14,21,21)
    elif name=='folder':
        path=QPainterPath();path.moveTo(3,7);path.lineTo(3,4);path.lineTo(10,4);path.lineTo(12,7);path.lineTo(21,7);path.lineTo(21,19);path.lineTo(3,19);path.closeSubpath();p.drawPath(path)
    elif name=='settings':
        for y,x in [(6,8),(12,16),(18,10)]:
            line(3,y,x-2,y);line(x+2,y,21,y);p.drawEllipse(QRectF(x-2,y-2,4,4))
    elif name=='more':
        p.setBrush(QColor(color));p.setPen(Qt.NoPen)
        for x in (5,12,19):p.drawEllipse(QRectF(x-1,11,2,2))
    elif name=='plus':line(12,5,12,19);line(5,12,19,12)
    elif name=='back':line(19,12,5,12);line(5,12,11,6);line(5,12,11,18)
    elif name=='export':line(12,15,12,3);line(7,8,12,3);line(17,8,12,3);line(4,13,4,20);line(4,20,20,20);line(20,20,20,13)
    elif name in ('undo','redo'):
        if name=='redo':p.translate(24,0);p.scale(-1,1)
        line(4,5,4,11);line(4,11,10,11);p.drawArc(QRectF(4,7,16,13),0,160*16)
    elif name=='trash':line(5,6,19,6);line(9,3,15,3);p.drawRoundedRect(QRectF(7,6,10,15),2,2);line(10,10,10,17);line(14,10,14,17)
    elif name=='chevron':line(8,10,12,14);line(12,14,16,10)
    elif name=='check':line(5,12,10,17);line(10,17,20,6)
    elif name=='cut':p.drawEllipse(QRectF(3,3,6,6));p.drawEllipse(QRectF(3,15,6,6));line(8,8,20,20);line(8,16,20,4)
    else:p.drawRoundedRect(QRectF(5,5,14,14),3,3)
    p.end();pix.setDevicePixelRatio(2);return pix


def icon(name,color='#596A80',size=20):
    """One geometry in all states, optical weight retained at 1x and 2x."""
    result=QIcon()
    result.addPixmap(_pixmap(name,color,size),QIcon.Normal,QIcon.Off)
    result.addPixmap(_pixmap(name,'#A1ADBC',size),QIcon.Disabled,QIcon.Off)
    active='#FFFFFF' if color.upper()=='#FFFFFF' else '#2165D5'
    result.addPixmap(_pixmap(name,active,size,1.8),QIcon.Active,QIcon.Off)
    result.addPixmap(_pixmap(name,active,size,1.8),QIcon.Normal,QIcon.On)
    return result

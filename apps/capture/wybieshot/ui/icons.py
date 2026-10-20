"""Screenshot extensions to Recorder's single outline icon family."""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QPainterPath
from loomrec.ui.icons import icon as recorder_icon, remember
from loomrec.ui.tokens import tint


def icon(name, color='muted', size=20):
    if name not in ('select','text','arrow','rectangle','ellipse','pen','highlight','number','mask','blur','crop','copy','compare','compose','save'):
        return recorder_icon(name,color,size)
    result=QIcon()
    for mode,state,ink in ((QIcon.Normal,QIcon.Off,tint(color)),(QIcon.Disabled,QIcon.Off,tint('disabled')),(QIcon.Normal,QIcon.On,tint('accent'))):
        pix=QPixmap(size*2,size*2);pix.fill(Qt.transparent)
        p=QPainter(pix);p.setRenderHint(QPainter.Antialiasing);p.scale(size/12,size/12)
        p.setPen(QPen(QColor(ink),1.6,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.setBrush(Qt.NoBrush)
        def line(a,b,c,d):p.drawLine(QPointF(a,b),QPointF(c,d))
        if name=='select':
            path=QPainterPath();path.moveTo(5,3);path.lineTo(19,13);path.lineTo(12,14);path.lineTo(9,21);path.closeSubpath();p.drawPath(path)
        elif name=='text':line(4,5,20,5);line(12,5,12,21);line(8,21,16,21)
        elif name=='arrow':line(4,20,20,4);line(10,4,20,4);line(20,4,20,14)
        elif name=='rectangle':p.drawRoundedRect(QRectF(4,5,16,14),1,1)
        elif name=='ellipse':p.drawEllipse(QRectF(3,5,18,14))
        elif name=='pen':
            path=QPainterPath();path.moveTo(3,18);path.cubicTo(13,0,3,26,21,6);p.drawPath(path)
        elif name=='highlight':line(4,19,20,19);line(7,14,14,4);line(14,4,20,8);line(20,8,13,17);line(7,14,13,17)
        elif name=='number':
            p.drawEllipse(QRectF(3,3,18,18));line(10,9,12,7);line(12,7,12,17);line(9,17,15,17)
        elif name=='mask':p.fillRect(QRectF(4,6,16,12),QColor(ink))
        elif name=='blur':
            for x in (5,10,15):
                for y in (5,10,15):p.fillRect(QRectF(x,y,3,3),QColor(ink))
        elif name=='crop':line(7,3,7,17);line(7,17,21,17);line(3,7,17,7);line(17,7,17,21)
        elif name=='save':
            p.drawRoundedRect(QRectF(4,3,16,18),2,2);p.drawRect(QRectF(8,3,8,6));p.drawRect(QRectF(8,14,8,7))
        elif name=='copy':p.drawRoundedRect(QRectF(8,8,12,13),2,2);line(16,4,4,4);line(4,4,4,16)
        elif name=='compare':p.drawRoundedRect(QRectF(3,5,18,14),2,2);line(12,2,12,22);line(6,9,9,12);line(9,12,6,15);line(18,9,15,12);line(15,12,18,15)
        elif name=='compose':p.drawRoundedRect(QRectF(3,5,7,14),1,1);p.drawRoundedRect(QRectF(14,5,7,14),1,1)
        p.end();pix.setDevicePixelRatio(2);result.addPixmap(pix,mode,state)
    return remember(result, icon, (name, color, size))

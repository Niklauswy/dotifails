"""Immutable source pixels and undoable annotation state; render is deterministic."""
from dataclasses import replace
import math
from PySide6.QtCore import Qt, QPointF, QRectF, QSize
from PySide6.QtGui import QImage, QPainter, QPen, QColor, QFont, QPainterPath, QPolygonF
from .schema import Layer, Rect

MAX_PIXELS = 100_000_000

class Document:
    def __init__(self, image: QImage, title='Captura'):
        if image.isNull() or image.width()*image.height()>MAX_PIXELS:
            raise ValueError('Empty or oversized source image')
        self._original=image.convertToFormat(QImage.Format_ARGB32).copy()
        self._original.setDevicePixelRatio(1)
        self.title=str(title)
        self._layers=()
        self._crop=None
        self._undo=[]
        self._redo=[]
        self.session_id=None

    @property
    def original(self):return self._original.copy()
    @property
    def layers(self):return self._layers
    @property
    def crop(self):return self._crop
    @property
    def size(self):return self._original.size()
    @property
    def can_undo(self):return bool(self._undo)
    @property
    def can_redo(self):return bool(self._redo)

    def _change(self,layers,crop):
        self._undo.append((self._layers,self._crop))
        if len(self._undo)>200:self._undo.pop(0)
        self._redo.clear()
        self._layers,self._crop=tuple(layers),crop

    def add_layer(self,layer):
        if not isinstance(layer,Layer):raise ValueError('Expected Layer')
        if any(l.id==layer.id for l in self.layers):raise ValueError('Duplicate layer id')
        self._change((*self.layers,layer),self.crop)

    def replace_layer(self,id,layer):
        if not isinstance(layer,Layer):raise ValueError('Expected Layer')
        if not any(l.id==id for l in self.layers):raise KeyError(id)
        self._change(tuple(replace(layer,id=id) if l.id==id else l for l in self.layers),self.crop)

    def remove_layer(self,id):
        if not any(l.id==id for l in self.layers):raise KeyError(id)
        self._change(tuple(l for l in self.layers if l.id!=id),self.crop)

    def set_crop(self,crop):
        if crop is not None and not Rect(0,0,self.size.width(),self.size.height()).contains(crop):
            raise ValueError('Crop outside source')
        if crop!=self.crop:self._change(self.layers,crop)

    def undo(self):
        if not self._undo:return False
        self._redo.append((self.layers,self.crop));self._layers,self._crop=self._undo.pop();return True

    def redo(self):
        if not self._redo:return False
        self._undo.append((self.layers,self.crop));self._layers,self._crop=self._redo.pop();return True

    def render(self):
        image=self.original
        for layer in self.layers:
            points=[QPointF(*p) for p in layer.points]
            color=QColor(layer.color)
            rect=QRectF(points[0],points[-1]).normalized()
            if layer.tool=='blur':
                # Deliberately visual blur only: never represented as secure redaction.
                area=rect.toAlignedRect().intersected(image.rect())
                if area.isEmpty():continue
                patch=image.copy(area)
                patch=patch.scaled(max(1,area.width()//12),max(1,area.height()//12),Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
                patch=patch.scaled(area.size(),Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
                painter=QPainter(image);painter.drawImage(area.topLeft(),patch);painter.end();continue
            painter=QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing,layer.tool!='mask')
            painter.setPen(QPen(color,layer.width,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
            if layer.tool=='mask':
                # Opaque source replacement in the flattened export, without antialiased edges.
                painter.fillRect(rect.toAlignedRect(),color)
            elif layer.tool=='highlight':
                color.setAlpha(85);painter.fillRect(rect,color)
            elif layer.tool=='rectangle':painter.drawRect(rect)
            elif layer.tool=='ellipse':painter.drawEllipse(rect)
            elif layer.tool=='pen':
                path=QPainterPath(points[0])
                for point in points[1:]:path.lineTo(point)
                if len(points)==1:painter.drawPoint(points[0])
                else:painter.drawPath(path)
            elif layer.tool=='arrow':
                a,b=points[0],points[-1];painter.drawLine(a,b)
                angle=math.atan2(b.y()-a.y(),b.x()-a.x());length=max(10,layer.width*4)
                head=QPolygonF([b,QPointF(b.x()-length*math.cos(angle-.45),b.y()-length*math.sin(angle-.45)),QPointF(b.x()-length*math.cos(angle+.45),b.y()-length*math.sin(angle+.45))])
                painter.setBrush(color);painter.drawPolygon(head)
            elif layer.tool=='text':
                font=QFont();font.setPixelSize(layer.font_size);painter.setFont(font)
                # Anchor is top-left, multiline grows downward.
                metrics=painter.fontMetrics()
                for n,line in enumerate(layer.text.split('\n')):
                    painter.drawText(points[0]+QPointF(0,metrics.ascent()+n*metrics.height()),line)
            elif layer.tool=='number':
                radius=max(12,layer.font_size*.7);painter.setBrush(color);painter.drawEllipse(points[0],radius,radius)
                painter.setPen(Qt.white);font=QFont();font.setPixelSize(layer.font_size);font.setBold(True);painter.setFont(font)
                painter.drawText(QRectF(points[0].x()-radius,points[0].y()-radius,2*radius,2*radius),Qt.AlignCenter,str(layer.number))
            painter.end()
        if self.crop:image=image.copy(self.crop.x,self.crop.y,self.crop.width,self.crop.height)
        return image

    @staticmethod
    def compose(documents,axis='horizontal',gap=16):
        if not documents or axis not in ('horizontal','vertical') or not 0<=gap<=512:
            raise ValueError('Invalid composition')
        images=[doc.render() for doc in documents]
        horizontal=axis=='horizontal'
        width=sum(i.width() for i in images)+gap*(len(images)-1) if horizontal else max(i.width() for i in images)
        height=max(i.height() for i in images) if horizontal else sum(i.height() for i in images)+gap*(len(images)-1)
        if width*height>MAX_PIXELS:raise ValueError('Composition too large')
        output=QImage(width,height,QImage.Format_ARGB32);output.fill(QColor('#f3f6fb'))
        p=QPainter(output);offset=0
        for image in images:
            p.drawImage(offset if horizontal else 0,0 if horizontal else offset,image)
            offset+=(image.width() if horizontal else image.height())+gap
        p.end();return Document(output,'Composición')

    @staticmethod
    def compare(before,after,split=.5):
        if not 0<=split<=1:raise ValueError('Split outside 0..1')
        a,b=before.render(),after.render()
        if a.size()!=b.size():raise ValueError('Comparison requires equal image dimensions')
        output=a.copy();x=round(output.width()*split);p=QPainter(output)
        p.drawImage(QRectF(x,0,output.width()-x,output.height()),b,QRectF(x,0,b.width()-x,b.height()))
        p.end();return Document(output,'Antes y después')

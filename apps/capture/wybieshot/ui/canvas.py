"""Original-pixel annotation interactions with one history entry per gesture."""
from dataclasses import replace
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget
from wybieshot.schema import Layer, Rect
from loomrec.ui.tokens import color


class Canvas(QWidget):
    changed = Signal()
    selected = Signal(object)
    edit_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document=None; self.tool='select'; self.color='#2165d5'; self.stroke=3.; self.font_size=24  # theme-exception: default annotation ink saved in the user's document
        self.resizing=False; self.selected_id=None; self.points=[]; self.moving=None; self.start=None; self.preview=None
        self.setMinimumSize(240,180);self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('Lienzo. V seleccionar, A flecha, R rectángulo, E elipse, P lápiz, H resaltar, T texto, N paso, M máscara, B desenfoque, C recortar. Suprimir elimina; flechas mueven.')

    def set_document(self, document):
        self.document=document;self.selected_id=None;self.preview=None;self.update()

    def set_tool(self, tool):
        self.cancel_gesture();self.tool=tool
        if tool!='select':self.selected_id=None;self.selected.emit(None)
        self.setCursor(Qt.ArrowCursor if tool=='select' else Qt.CrossCursor)
        self.setFocus();self.update()

    def cancel_gesture(self):
        self.points=[];self.moving=None;self.resizing=False;self.start=None;self.preview=None;self.update()

    def image_rect(self):
        if not self.document:return QRectF()
        crop=self.document.crop
        w,h=(crop.width,crop.height) if crop else (self.document.size.width(),self.document.size.height())
        scale=min(max(1,self.width()-40)/w,max(1,self.height()-40)/h)
        return QRectF((self.width()-w*scale)/2,(self.height()-h*scale)/2,w*scale,h*scale)

    def to_image(self, pos):
        r=self.image_rect();crop=self.document.crop
        scale=r.width()/(crop.width if crop else self.document.size.width())
        x=(pos.x()-r.x())/scale+(crop.x if crop else 0)
        y=(pos.y()-r.y())/scale+(crop.y if crop else 0)
        return (max(0,min(self.document.size.width()-1,x)),max(0,min(self.document.size.height()-1,y)))

    def bounds(self, layer):
        xs,ys=zip(*layer.points)
        if layer.tool=='text':return QRectF(xs[0],ys[0],max(24,max(map(len,layer.text.split('\n')),default=0)*layer.font_size*.65),max(1,len(layer.text.split('\n')))*layer.font_size*1.3)
        if layer.tool=='number':
            radius=max(12,layer.font_size*.7);return QRectF(xs[0]-radius,ys[0]-radius,radius*2,radius*2)
        return QRectF(min(xs),min(ys),max(1,max(xs)-min(xs)),max(1,max(ys)-min(ys))).adjusted(-5,-5,5,5)

    def current_layer(self):
        return next((l for l in self.document.layers if l.id==self.selected_id),None) if self.document else None

    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),color('inset'))
        if not self.document:
            p.setPen(color('muted'));p.drawText(self.rect(),Qt.AlignCenter,'Captura una imagen para empezar');return
        doc=self.document
        if self.preview:
            from wybieshot.document import Document
            doc=Document(self.document.original)
            for layer in self.document.layers:doc.add_layer(self.preview if layer.id==self.preview.id else layer)
            if not any(l.id==self.preview.id for l in self.document.layers):doc.add_layer(self.preview)
            doc.set_crop(self.document.crop)
        r=self.image_rect();p.drawImage(r,doc.render())
        p.setPen(QPen(color('line'),1));p.setBrush(Qt.NoBrush);p.drawRect(r)
        if hasattr(self,'comparison_split'):
            x=r.x()+r.width()*self.comparison_split;p.setPen(QPen(color('accent'),2));p.drawLine(QPointF(x,r.top()),QPointF(x,r.bottom()))
        crop=self.document.crop;scale=r.width()/(crop.width if crop else self.document.size.width())
        p.save();p.setClipRect(r);p.translate(r.x(),r.y());p.scale(scale,scale);p.translate(-(crop.x if crop else 0),-(crop.y if crop else 0))
        layer=self.preview or self.current_layer()
        if layer:
            p.setPen(QPen(color('accent'),1/scale,Qt.DashLine));p.drawRect(self.bounds(layer))
            if layer.tool not in ('text','number','pen'):
                point=QPointF(*layer.points[-1]);p.setBrush(color('surface'));p.setPen(QPen(color('accent'),1/scale));p.drawRect(QRectF(point.x()-4/scale,point.y()-4/scale,8/scale,8/scale))
        if self.tool=='crop' and len(self.points)>1:
            p.setPen(QPen(color('accent'),2/scale));p.drawRect(QRectF(QPointF(*self.points[0]),QPointF(*self.points[-1])).normalized())
        p.restore();p.end()

    def mousePressEvent(self,event):
        if not self.document or event.button()!=Qt.LeftButton or not self.image_rect().contains(event.position()):return
        self.setFocus();point=self.to_image(event.position());self.start=point
        if self.tool=='select':
            current=self.current_layer()
            self.resizing=bool(current and current.tool not in ('text','number','pen') and (QPointF(*current.points[-1])-QPointF(*point)).manhattanLength()<15)
            layer=current if self.resizing else next((l for l in reversed(self.document.layers) if self.bounds(l).contains(QPointF(*point))),None)
            self.selected_id=layer.id if layer else None;self.moving=layer;self.selected.emit(layer)
        else:
            self.selected_id=None;self.points=[point]
        self.update()

    def mouseMoveEvent(self,event):
        if self.start is None:return
        point=self.to_image(event.position())
        if self.moving:
            dx,dy=point[0]-self.start[0],point[1]-self.start[1]
            self.preview=replace(self.moving,points=(*self.moving.points[:-1],point) if self.resizing else tuple((x+dx,y+dy) for x,y in self.moving.points))
        elif self.points:
            if self.tool=='pen':self.points.append(point)
            else:self.points=[self.points[0],point]
            if self.tool not in ('crop','text','number'):
                self.preview=Layer(self.tool,tuple(self.points),self.color,self.stroke,font_size=self.font_size)
        self.update()

    def mouseReleaseEvent(self,event):
        if self.start is None or event.button()!=Qt.LeftButton:return
        self.mouseMoveEvent(event)
        if self.moving and self.preview:
            if self.preview.points!=self.moving.points:self.document.replace_layer(self.moving.id,self.preview);self.changed.emit()
        elif self.tool=='crop' and len(self.points)>1:
            r=QRectF(QPointF(*self.points[0]),QPointF(*self.points[-1])).normalized().toAlignedRect()
            r=r.intersected(self.document.original.rect())
            if r.width()>1 and r.height()>1:self.document.set_crop(Rect(r.x(),r.y(),r.width(),r.height()));self.changed.emit()
        elif self.tool in ('text','number'):
            number=max((l.number for l in self.document.layers if l.tool=='number'),default=0)+1
            layer=Layer(self.tool,(self.start,),self.color,self.stroke,text='Texto' if self.tool=='text' else '',number=number,font_size=self.font_size)
            self.document.add_layer(layer);self.selected_id=layer.id;self.selected.emit(layer);self.changed.emit()
            if self.tool=='text':self.edit_requested.emit(layer)
        elif self.preview:
            layer=self.preview;self.document.add_layer(layer);self.selected_id=layer.id;self.selected.emit(layer);self.changed.emit()
        self.cancel_gesture()

    def mouseDoubleClickEvent(self,event):
        if self.current_layer():self.edit_requested.emit(self.current_layer())

    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape:self.cancel_gesture();self.selected_id=None;self.selected.emit(None);return
        if self.document and self.document.layers and event.key() in (Qt.Key_BracketRight,Qt.Key_BracketLeft):
            ids=[layer.id for layer in self.document.layers];current=ids.index(self.selected_id) if self.selected_id in ids else -1
            delta=-1 if event.key()==Qt.Key_BracketLeft else 1;self.selected_id=ids[(current+delta)%len(ids)];self.selected.emit(self.current_layer());self.update();return
        layer=self.current_layer()
        if layer and event.key() in (Qt.Key_Delete,Qt.Key_Backspace):
            self.document.remove_layer(layer.id);self.selected_id=None;self.selected.emit(None);self.changed.emit();self.update();return
        if layer and event.key() in (Qt.Key_Enter,Qt.Key_Return):self.edit_requested.emit(layer);return
        directions={Qt.Key_Left:(-1,0),Qt.Key_Right:(1,0),Qt.Key_Up:(0,-1),Qt.Key_Down:(0,1)}
        if layer and event.key() in directions:
            dx,dy=directions[event.key()];step=10 if event.modifiers()&Qt.ShiftModifier else 1
            self.document.replace_layer(layer.id,replace(layer,points=tuple((x+dx*step,y+dy*step) for x,y in layer.points)));self.changed.emit();self.update();return
        super().keyPressEvent(event)

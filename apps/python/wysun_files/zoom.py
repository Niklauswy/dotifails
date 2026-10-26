"""Cursor-anchored image zoom, trackpad pinch and drag panning."""
import math
from PySide6.QtCore import Qt,QPointF,QRectF,QEvent
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel

class ZoomCanvas(QLabel):
    def __init__(self,parent=None):
        super().__init__(parent);self.image=None;self.zoom=1.;self.offset=QPointF();self.drag=None
        self.setToolTip('Rueda o pellizco: zoom · Arrastrar: mover · Doble clic: ajustar')
        self.setFocusPolicy(Qt.StrongFocus);self.setAccessibleName('Vista previa con zoom')
        self.grabGesture(Qt.PinchGesture)
    def set_image(self,image):
        self.image=image;self.reset_zoom()
    def reset_zoom(self):
        self.zoom=1.;self.offset=QPointF();self.update()
    def clear(self):
        self.image=None;self.reset_zoom();super().clear()
    def zoom_at(self,factor,point):
        if self.image is None or self.image.isNull():return
        old=self.zoom;self.zoom=max(.25,min(12.,old*factor))
        center=QPointF(self.rect().center());self.offset=(point-center)-(point-center-self.offset)*(self.zoom/old)
        self.update()
    def wheelEvent(self,event):
        if self.image is None:return super().wheelEvent(event)
        delta=event.pixelDelta().y() or event.angleDelta().y()
        self.zoom_at(math.exp(max(-600,min(600,delta))*.0015),event.position());event.accept()
    def event(self,event):
        if event.type()==QEvent.NativeGesture and event.gestureType()==Qt.ZoomNativeGesture:
            self.zoom_at(1+event.value(),event.position());event.accept();return True
        if event.type()==QEvent.Gesture:
            pinch=event.gesture(Qt.PinchGesture)
            if pinch:
                self.zoom_at(pinch.scaleFactor()/max(.001,pinch.lastScaleFactor()),pinch.centerPoint());event.accept();return True
        return super().event(event)
    def mousePressEvent(self,event):
        if self.image is not None and event.button()==Qt.LeftButton:
            self.drag=event.position();self.setCursor(Qt.ClosedHandCursor);event.accept()
        else:super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.drag is not None:
            self.offset+=event.position()-self.drag;self.drag=event.position();self.update();event.accept()
        else:super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        self.drag=None;self.unsetCursor();super().mouseReleaseEvent(event)
    def mouseDoubleClickEvent(self,event):
        self.reset_zoom();event.accept()
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Plus,Qt.Key_Equal,Qt.Key_Minus):
            self.zoom_at(.8 if event.key()==Qt.Key_Minus else 1.25,QPointF(self.rect().center()));event.accept()
        elif event.key()==Qt.Key_0:self.reset_zoom();event.accept()
        else:super().keyPressEvent(event)
    def paintEvent(self,event):
        if self.image is None or self.image.isNull():return super().paintEvent(event)
        scale=min(self.width()/self.image.width(),self.height()/self.image.height())*self.zoom
        size=self.image.size()*scale;center=QPointF(self.rect().center())+self.offset
        rect=QRectF(center.x()-size.width()/2,center.y()-size.height()/2,size.width(),size.height())
        painter=QPainter(self);painter.setRenderHint(QPainter.SmoothPixmapTransform);painter.drawImage(rect,self.image)

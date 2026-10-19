"""Frozen-frame selection. Never captures a desktop or saves a frame itself."""
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class SelectionOverlay(QWidget):
    selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, image, geometry, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.image = image
        self.selection = QRect()
        self.anchor = None
        self.drag_origin = None
        self.initial_rect = QRect()
        self.setWindowTitle('Seleccionar región · Wysun Screenshot')
        self.setAccessibleName('Seleccionar región. Flechas para mover; Shift y flechas para ajustar; Enter para confirmar; Escape para cancelar.')
        self.setGeometry(geometry)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CrossCursor)

    def source_rect(self,rect):
        # Widget coordinates may be logical/scaled; originals always keep pixel resolution.
        sx=self.image.width()/max(1,self.width());sy=self.image.height()/max(1,self.height())
        left=round(rect.x()*sx);top=round(rect.y()*sy)
        right=round((rect.x()+rect.width())*sx);bottom=round((rect.y()+rect.height())*sy)
        return QRect(left,top,right-left,bottom-top).intersected(self.image.rect())

    def present(self):
        from loomrec.portal import is_wayland
        if is_wayland():
            from PySide6.QtWidgets import QApplication
            screen=QApplication.primaryScreen().availableGeometry()
            size=self.image.size();size.scale(screen.size(),Qt.KeepAspectRatio)
            self.resize(size);self.setWindowTitle('Recortar imagen autorizada · Wysun Screenshot')
        self.show(); self.raise_(); self.activateWindow(); self.setFocus()

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawImage(self.rect(), self.image)
        p.fillRect(self.rect(), QColor(12, 24, 40, 115))
        r = self.selection.normalized().intersected(self.rect())
        if not r.isEmpty():
            p.save(); p.setClipRect(r); p.drawImage(self.rect(), self.image); p.restore()
            p.setPen(QPen(QColor('#FFFFFF'), 1)); p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(r).adjusted(.5, .5, -.5, -.5))
            p.setPen(QPen(QColor('#2165D5'), 2))
            for point in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
                p.fillRect(QRect(point-QPoint(4,4), point+QPoint(4,4)), QColor('#FFFFFF'))
                p.drawRect(QRect(point-QPoint(4,4), point+QPoint(4,4)))
        hint = f'{r.width()} × {r.height()} · Enter capturar · Esc cancelar' if not r.isEmpty() else 'Arrastra para seleccionar · Enter inicia selección con teclado · Esc cancelar'
        width = min(self.width()-24, p.fontMetrics().horizontalAdvance(hint)+32)
        box = QRect(12, max(12, self.height()-54), width, 38)
        p.setPen(Qt.NoPen); p.setBrush(QColor('#FCFDFF')); p.drawRoundedRect(box, 19, 19)
        p.setPen(QColor('#1C2A3B')); p.drawText(box.adjusted(12,0,-12,0), Qt.AlignCenter, hint)
        p.end()

    def mousePressEvent(self, event):
        if event.button()!=Qt.LeftButton:return
        point=event.position().toPoint()
        r=self.selection.normalized()
        self.initial_rect=QRect(r)
        corners=((r.topLeft(),r.bottomRight()),(r.topRight(),r.bottomLeft()),(r.bottomLeft(),r.topRight()),(r.bottomRight(),r.topLeft()))
        corner=next((opposite for handle,opposite in corners if (point-handle).manhattanLength()<=16),None) if not r.isEmpty() else None
        if corner is not None:
            self.anchor=corner;self.drag_origin=None
        elif r.contains(point):
            self.drag_origin=point;self.anchor=None
        else:
            self.anchor=point;self.drag_origin=None;self.selection=QRect(point,point)
        self.update()

    def mouseMoveEvent(self, event):
        point=event.position().toPoint()
        point.setX(max(0,min(self.width()-1,point.x())))
        point.setY(max(0,min(self.height()-1,point.y())))
        if self.anchor is not None:self.selection=QRect(self.anchor,point).normalized()
        elif self.drag_origin is not None:
            r=self.initial_rect.translated(point-self.drag_origin)
            r.moveLeft(max(0,min(self.width()-r.width(),r.left())))
            r.moveTop(max(0,min(self.height()-r.height(),r.top())))
            self.selection=r
        self.update()

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton:
            self.mouseMoveEvent(event);self.anchor=None;self.drag_origin=None

    def keyPressEvent(self,event):
        key=event.key()
        if key==Qt.Key_Escape:self.hide();self.cancelled.emit();return
        if key in (Qt.Key_Return,Qt.Key_Enter):
            if self.selection.width()>1 and self.selection.height()>1:
                self.hide();self.selected.emit(self.source_rect(self.selection.normalized().intersected(self.rect())))
            else:
                self.selection=QRect(self.width()//4,self.height()//4,max(2,self.width()//2),max(2,self.height()//2));self.update()
            return
        directions={Qt.Key_Left:(-1,0),Qt.Key_Right:(1,0),Qt.Key_Up:(0,-1),Qt.Key_Down:(0,1)}
        if key in directions:
            if self.selection.isEmpty():self.selection=QRect(0,0,min(200,self.width()),min(150,self.height()))
            dx,dy=directions[key];step=10 if event.modifiers()&Qt.ControlModifier else 1
            r=QRect(self.selection)
            if event.modifiers()&Qt.ShiftModifier:
                r.setWidth(max(2,min(self.width()-r.x(),r.width()+dx*step)))
                r.setHeight(max(2,min(self.height()-r.y(),r.height()+dy*step)))
            else:
                r.moveLeft(max(0,min(self.width()-r.width(),r.x()+dx*step)))
                r.moveTop(max(0,min(self.height()-r.height(),r.y()+dy*step)))
            self.selection=r;self.update();return
        super().keyPressEvent(event)

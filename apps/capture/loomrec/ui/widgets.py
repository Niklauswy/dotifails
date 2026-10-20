from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QWidget
from .tokens import color


class RegionPicker(QWidget):
    selected = Signal(list)
    cancelled = Signal()
    def __init__(self, geometry):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                         Qt.X11BypassWindowManagerHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(self.tr('Seleccionar área · Wysun Recorder'))
        self.setGeometry(geometry)
        self.setCursor(Qt.CrossCursor)
        self.origin = None;self.selection=QRect();self.finished=False
        self.setMouseTracking(True)
    def showEvent(self,event):
        super().showEvent(event)
        self.raise_();self.activateWindow();self.grabMouse();self.grabKeyboard()
    def paintEvent(self,event):
        p = QPainter(self)
        # Clear previous paint so the moving selection remains transparent.
        p.setCompositionMode(QPainter.CompositionMode_Source);p.fillRect(self.rect(),Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        shade=QPainterPath();shade.addRect(self.rect())
        if not self.selection.isEmpty():shade.addRect(self.selection)
        p.fillPath(shade,QColor(0,0,0,100))  # theme-exception: velo sobre el contenido de la pantalla
        p.setPen(color('region_edge')); p.drawText(24,40,self.tr('Arrastra el área · Escape cancela'))
        if not self.selection.isEmpty():
            p.setPen(QPen(color('region'),2));p.drawRect(self.selection.adjusted(0,0,-1,-1))
            caption=f'{self.selection.width()//2*2} × {self.selection.height()//2*2}'
            x=max(0,min(self.selection.x(),self.width()-140));y=max(48,self.selection.y()-30)
            p.fillRect(x,y,140,26,color('hud'));p.setPen(color('on_hud'));p.drawText(QRect(x,y,140,26),Qt.AlignCenter,caption)
    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton:return
        self.origin = event.position().toPoint()
        self.selection=QRect();self.update()
    def drag_rect(self,point):
        # Pixel extents are exclusive at the release point, in either direction.
        left=min(self.origin.x(),point.x());top=min(self.origin.y(),point.y())
        return QRect(left,top,abs(point.x()-self.origin.x()),abs(point.y()-self.origin.y())).intersected(self.rect())
    def mouseMoveEvent(self,event):
        if self.origin is not None:self.selection=self.drag_rect(event.position().toPoint());self.update()
    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.LeftButton or self.origin is None:return
        rect = self.drag_rect(event.position().toPoint())
        if rect.width() >= 16 and rect.height() >= 16:
            result=[self.x()+rect.x(),self.y()+rect.y(),rect.width()//2*2,rect.height()//2*2]
            self.finished=True;self.close();self.selected.emit(result)
        else:self.close()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape:self.close()
    def closeEvent(self,event):
        self.releaseMouse();self.releaseKeyboard();super().closeEvent(event)
        if not self.finished:self.finished=True;self.cancelled.emit()


class Waveform(QWidget):
    seek = Signal(float)
    def __init__(self):
        super().__init__(); self.samples=[]; self.clips=[]; self.duration=0; self.position=0; self.zoom=1
        self.setMinimumHeight(74); self.setAccessibleName(self.tr('Forma de onda; pulsa para buscar'))
    def set_data(self,samples,duration):
        self.samples=samples; self.duration=duration; self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),color('well'))
        width=self.width();height=self.height();duration=self.duration or sum(self.clips)
        p.setPen(QPen(color('divider'),1));p.drawLine(0,25,width,25)
        if duration:
            step=max(.5,duration/max(1,width//90));count=int(duration/step)+1
            for tick in range(count+1):
                time=tick*step;x=int(time/duration*width);p.setPen(color('tick'));p.drawLine(x,20,x,25);p.setPen(color('muted'));p.drawText(x+5,16,f'{time:.1f}s')
            offset=0
            for i,length in enumerate(self.clips):
                x=int(offset/duration*width);end=int((offset+length)/duration*width);p.fillRect(x+1,30,max(1,end-x-2),22,color('selection' if i%2==0 else 'hover'));p.setPen(color('accent_ink'));p.drawText(x+8,46,self.tr('Clip ')+str(i+1));offset+=length
        n=len(self.samples);middle=height*.74
        if n:
            p.setPen(QPen(color('accent_muted'),1))
            for x in range(width):
                index=min(n-1,int(x/max(1,width)*n));h=self.samples[index]*max(5,height*.22);p.drawLine(x,int(middle-h),x,int(middle+h))
        else:
            p.setPen(color('muted'));p.drawText(12,int(middle+5),self.tr('Genera la vista previa para ver el audio.'))
        if duration:
            p.setPen(QPen(color('accent'),2));x=int(self.position/duration*width);p.drawLine(x,20,x,height)

    def mousePressEvent(self,event):
        duration=self.duration or sum(self.clips)
        if duration:self.seek.emit(max(0,min(duration,event.position().x()/self.width()*duration)))

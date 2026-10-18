"""Clipboard-specific surfaces, legible visual cards and restrained selection motion."""
import datetime,time
from PySide6.QtCore import Qt,QSize,QRectF,QVariantAnimation,QEasingCurve,Signal,QPropertyAnimation
from PySide6.QtGui import QColor,QPainter,QPen,QFont,QLinearGradient,QPixmap
from PySide6.QtWidgets import QListWidget,QStyledItemDelegate,QStyle,QWidget
from icons import icon
from files_motion import reduced_motion

COLORS={'base':'#171719','surface':'#1e1e21','raised':'#29292d','text':'#f0f2f6','muted':'#a5abb7','line':'#343943','accent':'#83afff'}
STYLE='''
QWidget { color:#f0f2f6; font-family:"Inter","Noto Sans"; font-size:13px; background:transparent; }
QWidget#clipSurface, QWidget#clipDetail { background:rgba(23,23,25,249); border:1px solid #38383c; border-radius:20px; }
QLabel { border:none; background:transparent; }
QLabel#clipLinkTitle { font-size:18px; font-weight:600; }
QLabel#clipDescription { color:#c3c5cb; font-size:12px; }
QLabel#clipTitle { font-size:15px; font-weight:600; }
QLabel#clipMuted, QLabel#clipStatus { color:#a5abb7; font-size:11px; }
QLineEdit { background:#22262e; border:1px solid #353b46; border-radius:10px; padding:9px 12px; color:#f0f2f6; selection-background-color:#34588b; }
QLineEdit#clipSearch { background:transparent; border:1px solid transparent; font-size:15px; padding:8px 4px; }
QLineEdit:focus, QLineEdit#clipSearch:focus { border-color:#83afff; }
QPushButton { border:1px solid #363c46; background:#242830; border-radius:9px; padding:7px 12px; color:#e7ebf1; }
QPushButton:hover { background:#303641; border-color:#566274; }
QPushButton:pressed { background:#3b4452; }
QPushButton:focus { border-color:#83afff; }
QPushButton:disabled { color:#686f7d; border-color:#2b3039; background:#1d2128; }
QPushButton#clipColorRow { background:transparent; border:1px solid transparent; padding:5px 10px; border-radius:7px; text-align:left; }
QPushButton#clipColorRow:hover { background:#252529; }
QPushButton#clipColorRow:focus { border-color:#83afff; background:#252529; }
QPushButton#clipCopy { padding:7px 12px; border-radius:17px; }
QPushButton#clipIcon { border-radius:16px; padding:0; }
QPushButton#clipChip { border-radius:15px; padding:5px 12px; background:#22262d; }
QPushButton#clipChip:checked { background:#e8edf5; color:#14161a; border-color:#e8edf5; }
QPushButton#clipPrimary { background:#86aff5; color:#101824; border-color:#86aff5; font-weight:600; }
QPushButton#clipPrimary:hover { background:#a4c3fa; }
QPushButton#clipPrimary:disabled { background:#2b3442; color:#909cac; border-color:#3b475a; }
QListWidget#clipCards { background:transparent; border:none; outline:none; padding:0; }
QListWidget#clipParts { background:#1b1e24; border:1px solid #343943; border-radius:10px; outline:none; }
QListWidget#clipParts::item { padding:9px 10px; border-bottom:1px solid #30353f; }
QListWidget#clipParts::item:selected { background:#2d3b51; }
QPlainTextEdit { background:#1c2027; border:1px solid #343943; border-radius:12px; padding:12px; color:#e5eaf1; selection-background-color:#34588b; }
QComboBox { background:#242830; border:1px solid #363c46; border-radius:9px; padding:6px 10px; min-height:18px; }
QComboBox QAbstractItemView { background:#242830; color:#f0f2f6; selection-background-color:#34588b; border:1px solid #495264; }
QMenu { background:#252527; border:1px solid #46464b; border-radius:12px; padding:6px; font-size:12px; }
QMenu::item { padding:8px 18px 8px 12px; border-radius:6px; }
QMenu::item:selected { background:#3a3a40; }
QMenu::item:disabled { color:#717b8b; }
QMenu::separator { height:1px; background:#414855; margin:5px 9px; }
QScrollArea { background:transparent; border:none; }
QScrollBar:vertical { background:transparent; width:8px; margin:2px; }
QScrollBar::handle:vertical { background:#515a69; min-height:28px; border-radius:3px; }
QScrollBar:horizontal { background:transparent; height:8px; margin:2px; }
QScrollBar::handle:horizontal { background:#515a69; min-width:28px; border-radius:3px; }
QScrollBar::add-line,QScrollBar::sub-line { width:0; height:0; }
QScrollBar::add-page,QScrollBar::sub-page { background:transparent; }
QSplitter::handle { background:transparent; height:10px; }
QToolTip { background:#282e38; color:#f0f2f6; border:1px solid #505b6c; padding:6px 9px; }
QDialog,QMessageBox,QInputDialog { background:#1b1e24; }
'''
KIND_LABEL={'text':'Texto','image':'Imagen','url':'Enlace','color':'Color','files':'Archivos','bundle':'Grupo'}
KIND_ICON={'text':'file-text','image':'image','url':'globe','color':'palette','files':'folder','bundle':'layers'}
def age(stamp):
    seconds=max(0,time.time()-stamp)
    if seconds<60:return 'Ahora'
    if seconds<3600:return f'{int(seconds//60)} min'
    if seconds<86400:return f'{int(seconds//3600)} h'
    return datetime.datetime.fromtimestamp(stamp).strftime('%d %b')

class ClipCards(QListWidget):
    favoriteRequested=Signal(int)
    previewRequested=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.setMouseTracking(True);self.hover_id=None;self.hover=0.;self.selection=1.
        self.selection_animation=QVariantAnimation(self);self.selection_animation.setDuration(150);self.selection_animation.setEasingCurve(QEasingCurve.OutCubic);self.selection_animation.valueChanged.connect(self._selection_frame);self.currentItemChanged.connect(self._selection_changed)
        self.scroll_animation=QPropertyAnimation(self.horizontalScrollBar(),b'value',self);self.scroll_animation.setEasingCurve(QEasingCurve.OutCubic);self.scroll_animation.setDuration(150)
        self.animation=QVariantAnimation(self);self.animation.setDuration(150);self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self._hover_frame)
    def _selection_frame(self,value):self.selection=float(value);self.viewport().update()
    def _selection_changed(self,*_):
        self.selection_animation.stop()
        if reduced_motion():self.selection=1.;self.viewport().update();return
        self.selection_animation.setStartValue(.25);self.selection_animation.setEndValue(1.);self.selection_animation.start()
    def wheelEvent(self,event):
        if self.isWrapping() or event.modifiers()!=Qt.NoModifier or not event.angleDelta().y():return super().wheelEvent(event)
        bar=self.horizontalScrollBar();target=max(bar.minimum(),min(bar.maximum(),(self.scroll_animation.endValue() if self.scroll_animation.state()==self.scroll_animation.State.Running else bar.value())-event.angleDelta().y()*2))
        self.scroll_animation.stop()
        if reduced_motion():bar.setValue(target)
        else:self.scroll_animation.setStartValue(bar.value());self.scroll_animation.setEndValue(target);self.scroll_animation.start()
        event.accept()
    def _hover_frame(self,value):self.hover=float(value);self.viewport().update()
    def mouseMoveEvent(self,event):
        item=self.itemAt(event.pos());ident=item.data(Qt.UserRole)['id'] if item else None
        if ident!=self.hover_id:
            self.hover_id=ident;self.animation.stop()
            if reduced_motion():self.hover=1.;self.viewport().update()
            else:self.animation.setStartValue(0.);self.animation.setEndValue(1.);self.animation.start()
        super().mouseMoveEvent(event)
    def leaveEvent(self,event):self.hover_id=None;self.viewport().update();super().leaveEvent(event)
    def mousePressEvent(self,event):
        item=self.itemAt(event.pos())
        if item and event.button()==Qt.LeftButton:
            rect=self.visualItemRect(item).adjusted(4,4,-4,-4)
            if QRectF(rect.right()-31,rect.top()+7,25,25).contains(event.position()):self.favoriteRequested.emit(item.data(Qt.UserRole)['id']);return
        super().mousePressEvent(event)

class ClipDelegate(QStyledItemDelegate):
    def __init__(self,window):super().__init__(window.cards);self.window=window
    def sizeHint(self,option,index):return QSize(194,155)
    def paint(self,painter,option,index):
        row=index.data(Qt.UserRole) or {};rect=QRectF(option.rect.adjusted(4,4,-4,-4));kind=row.get('kind','text')
        painter.save();painter.setRenderHint(QPainter.Antialiasing)
        selected=bool(option.state&QStyle.State_Selected);hover=row.get('id')==self.window.cards.hover_id
        if hover:rect.translate(0,-2*self.window.cards.hover)
        painter.setPen(Qt.NoPen);painter.setBrush(QColor('#303035' if hover else '#252528'));painter.drawRoundedRect(rect,13,13)
        path=__import__('PySide6.QtGui',fromlist=['QPainterPath']).QPainterPath();path.addRoundedRect(rect,13,13);painter.setClipPath(path)
        background=False
        if kind=='color':
            from data_v2 import color_value
            color=color_value(row.get('text',''))
            if color:painter.fillRect(rect,QColor(color));background=True
        elif kind in ('image','url'):
            pixmap=self.window.card_pixmap(row)
            if pixmap and not pixmap.isNull():
                scaled=pixmap.scaled(int(rect.width()),int(rect.height()),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation)
                painter.drawPixmap(int(rect.x()+(rect.width()-scaled.width())/2),int(rect.y()+(rect.height()-scaled.height())/2),scaled);background=True
        if background:
            gradient=QLinearGradient(rect.left(),rect.top()+rect.height()*.38,rect.left(),rect.bottom());gradient.setColorAt(0,QColor(0,0,0,0));gradient.setColorAt(1,QColor(0,0,0,205));painter.fillRect(rect,gradient)
        else:
            icon(KIND_ICON.get(kind,'file-text'),18,'#a8b5ca').paint(painter,int(rect.left()+12),int(rect.top()+12),18,18)
            painter.setPen(QColor('#b4bdcb'));painter.setFont(QFont('Inter',9));painter.drawText(QRectF(rect.left()+38,rect.top()+10,rect.width()-60,22),Qt.AlignLeft|Qt.AlignVCenter,KIND_LABEL.get(kind,'Clip'))
            if kind=='text':
                painter.setFont(QFont('Inter',10));painter.setPen(QColor('#e5eaf1'))
                painter.drawText(QRectF(rect.left()+12,rect.top()+40,rect.width()-24,62),Qt.TextWordWrap|Qt.AlignTop,row.get('text','')[:140])
            else:
                painter.setFont(QFont('Inter',11,QFont.DemiBold));painter.setPen(QColor('#e4eaf4'))
                painter.drawText(QRectF(rect.left()+12,rect.top()+43,rect.width()-24,45),Qt.TextWordWrap|Qt.AlignTop,row.get('title','')[:65])
        painter.setPen(QColor('#ffffff'));painter.setFont(QFont('Inter',9,QFont.DemiBold))
        if background:painter.drawText(int(rect.left()+12),int(rect.bottom()-30),painter.fontMetrics().elidedText(row.get('title',''),Qt.ElideRight,int(rect.width()-24)))
        painter.setFont(QFont('Inter',8));painter.setPen(QColor('#d1d8e2' if background else '#a5afbe'))
        source=row.get('source') or 'Local';caption=source+' · '+age(row.get('stamp',time.time()))
        painter.drawText(int(rect.left()+12),int(rect.bottom()-12),painter.fontMetrics().elidedText(caption,Qt.ElideRight,int(rect.width()-24)))
        if row.get('pinned') or hover or selected:
            for offset,symbol in [(31,'star')]:
                painter.save();painter.setOpacity(1. if row.get('pinned') or selected else self.window.cards.hover)
                circle=QRectF(rect.right()-offset,rect.top()+7,25,25);painter.setPen(Qt.NoPen);painter.setBrush(QColor(13,17,24,205));painter.drawEllipse(circle)
                icon(symbol,15,'#f7d68b' if symbol=='star' and row.get('pinned') else '#eef3fb').paint(painter,int(circle.x()+5),int(circle.y()+5),15,15);painter.restore()
        painter.setClipping(False);painter.setBrush(Qt.NoBrush)
        color=QColor(COLORS['accent'] if selected else '#505e73' if hover else '#343b47');color.setAlpha(int(160+95*self.window.cards.selection) if selected else int(110+120*self.window.cards.hover) if hover else 150)
        painter.setPen(QPen(color,2 if selected else 1));painter.drawRoundedRect(rect.adjusted(1,1,-1,-1),12,12)
        painter.restore()

class LinkHero(QWidget):
    """A single quiet cover image, rather than a nested browser or extra toolbar."""
    def __init__(self,parent=None):
        super().__init__(parent);self.pixmap=QPixmap();self.site='';self.loading=False;self.setMinimumHeight(90)
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Ignored)
    def set_content(self,data,site,loading=False):
        self.pixmap=QPixmap();self.pixmap.loadFromData(data);self.site=site;self.loading=loading;self.update()
    def paintEvent(self,event):
        from PySide6.QtGui import QPainterPath
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing);rect=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        path=QPainterPath();path.addRoundedRect(rect,12,12);painter.setClipPath(path);painter.fillRect(rect,QColor('#22252a'))
        if not self.pixmap.isNull():
            scaled=self.pixmap.scaled(self.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation)
            bounds=QRectF((self.width()-scaled.width())/2,(self.height()-scaled.height())/2,scaled.width(),scaled.height())
            painter.fillRect(rect,QColor('#171719'));path=QPainterPath();path.addRoundedRect(bounds,12,12);painter.setClipPath(path)
            painter.drawPixmap(int(bounds.x()),int(bounds.y()),scaled);rect=bounds
        else:
            icon('globe',28,'#82878f').paint(painter,self.width()//2-14,self.height()//2-30,28,28)
            painter.setPen(QColor('#a5abb7'));painter.setFont(QFont('Inter',10));painter.drawText(rect.adjusted(16,25,-16,0),Qt.AlignCenter,self.site)
        painter.setClipping(False);painter.setPen(QPen(QColor(255,255,255,22),1));painter.setBrush(Qt.NoBrush);painter.drawRoundedRect(rect,12,12)

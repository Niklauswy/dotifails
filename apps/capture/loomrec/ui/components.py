from PySide6.QtCore import Qt,QPointF,QSize,QVariantAnimation,QEasingCurve,QRectF
from PySide6.QtGui import QPainter,QColor,QPen,QFont,QFontMetrics
from PySide6.QtWidgets import (QPushButton,QFrame,QLabel,QVBoxLayout,QHBoxLayout,QGraphicsDropShadowEffect,QWidget,QCheckBox,QStyledItemDelegate,QStyle)
from .icons import icon
from .tokens import TOKENS
from .motion import reduced_motion

def label(text,role=None):
    widget=QLabel(text)
    if role:widget.setProperty('role',role)
    return widget

def surface(role='surface',shadow=False):
    widget=QFrame();widget.setProperty('role',role)
    if shadow:
        effect=QGraphicsDropShadowEffect(widget);effect.setBlurRadius(30);effect.setOffset(0,7);effect.setColor(QColor(35,63,100,24));widget.setGraphicsEffect(effect)
    return widget

def rule():return surface('rule')

class SoftButton(QPushButton):
    def __init__(self,text='',symbol=None,primary=False,quiet=False,parent=None):
        accessible_text=self.tr('Cerrar') if text=='×' else text.rstrip(' ⌄')
        if text=='×' and symbol is None:text='';symbol='close'
        super().__init__(text,parent);self._dropdown=False;self.setText(text);self.setProperty('primary',primary);self.setProperty('quiet',quiet)
        self.setCursor(Qt.PointingHandCursor);self.setMinimumHeight(36);self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(accessible_text);self.setToolTip(accessible_text)
        if symbol:self.setIcon(icon(symbol,'#FFFFFF' if primary else TOKENS['muted']));self.setIconSize(QSize(20,20))
        self._hover=0.;self.anim=QVariantAnimation(self);self.anim.setDuration(TOKENS['motion_ms']);self.anim.setEasingCurve(QEasingCurve.OutCubic);self.anim.valueChanged.connect(self._frame)
    def setText(self,text):
        dropdown=text.rstrip().endswith('⌄')
        self._dropdown=dropdown
        self.setProperty('dropdown',dropdown)
        super().setText(text.rstrip(' ⌄'))
    def sizeHint(self):
        size=super().sizeHint()
        if getattr(self,'_dropdown',False):size.setWidth(size.width()+12)
        return size
    def _frame(self,value):
        if reduced_motion():self.anim.stop();self._hover=0.
        else:self._hover=float(value)
        self.update()
    def enterEvent(self,event):
        if reduced_motion():self.anim.stop();self._hover=0.;self.update()
        else:self.anim.stop();self.anim.setStartValue(self._hover);self.anim.setEndValue(1.);self.anim.start()
        super().enterEvent(event)
    def leaveEvent(self,event):
        if reduced_motion():self.anim.stop();self._hover=0.;self.update()
        else:self.anim.stop();self.anim.setStartValue(self._hover);self.anim.setEndValue(0.);self.anim.start()
        super().leaveEvent(event)
    def paintEvent(self,event):
        super().paintEvent(event)
        if self._dropdown:
            painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor(TOKENS['muted'] if self.isEnabled() else TOKENS['disabled']),1.5,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
            x=self.width()-12;y=self.height()/2;painter.drawLine(QPointF(x-3,y-1.5),QPointF(x,y+1.5));painter.drawLine(QPointF(x,y+1.5),QPointF(x+3,y-1.5));painter.end()
        if self.property('sourceActive'):
            painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing);painter.setPen(QPen(QColor('#2165D5'),1.6,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
            x=self.width()-18;y=self.height()-12;painter.drawLine(QPointF(x-4,y),QPointF(x-1,y+3));painter.drawLine(QPointF(x-1,y+3),QPointF(x+4,y-3));painter.end()
        if self._hover and self.isEnabled():
            radius=min(self.property('hoverRadius') or (12 if self.property('primary') else 10),(self.width()-2)/2,(self.height()-2)/2)
            painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing);painter.setPen(Qt.NoPen);painter.setBrush(QColor(67,117,184,round(8*self._hover)));painter.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),radius,radius)

class Toggle(QCheckBox):
    def __init__(self,name):
        super().__init__();self.setAccessibleName(name);self.setToolTip(name);self.setFixedSize(42,26);self.setCursor(Qt.PointingHandCursor)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():p.setOpacity(.45)
        p.setPen(QPen(QColor('#2165D5' if self.isChecked() else '#C9D5E5'),1));p.setBrush(QColor('#2165D5' if self.isChecked() else '#DDE6F1'));p.drawRoundedRect(QRectF(1,3,40,20),10,10)
        p.setPen(Qt.NoPen);p.setBrush(Qt.white);p.drawEllipse(QRectF(23 if self.isChecked() else 5,7,12,12))
        if self.hasFocus():p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#164EAD'),2));p.drawRoundedRect(QRectF(0,1,41,24),11,11)
    def hitButton(self,pos):return self.rect().contains(pos)

class Disclosure(QWidget):
    def __init__(self,title):
        super().__init__();layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(10)
        self.trigger=SoftButton(title,'settings',quiet=True);self.trigger.setCheckable(True);layout.addWidget(self.trigger,0,Qt.AlignLeft)
        self.body=QWidget();self.body.setVisible(False);layout.addWidget(self.body);self.trigger.toggled.connect(self.body.setVisible)

class RecordingDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(450,102)
    def paint(self,painter,option,index):
        painter.save();painter.setRenderHint(QPainter.Antialiasing)
        rect=option.rect.adjusted(2,3,-2,-3);selected=bool(option.state&QStyle.State_Selected)
        painter.setPen(Qt.NoPen);painter.setBrush(QColor('#E3EDFD' if selected else '#FCFDFF'));painter.drawRoundedRect(QRectF(rect),12,12)
        thumb=QRectF(rect.left()+12,rect.top()+12,118,70);painter.setBrush(QColor('#E9F0F9'));painter.drawRoundedRect(thumb,8,8)
        image=index.data(Qt.DecorationRole)
        if image:image.paint(painter,thumb.toRect())
        else:icon('play','#7B96BB',28).paint(painter,thumb.adjusted(43,20,-43,-20).toRect())
        text=index.data(Qt.DisplayRole).split('\n');x=rect.left()+148;width=max(30,rect.width()-174)
        font=option.font;font.setWeight(QFont.DemiBold);painter.setFont(font);painter.setPen(QColor('#1C2A3B'));painter.drawText(x,rect.top()+35,QFontMetrics(font).elidedText(text[0],Qt.ElideRight,width))
        font.setWeight(QFont.Normal);font.setPixelSize(12);painter.setFont(font);painter.setPen(QColor('#596A80'));painter.drawText(x,rect.top()+61,QFontMetrics(font).elidedText(' · '.join(text[1:]),Qt.ElideRight,width))
        if option.state&QStyle.State_HasFocus:painter.setBrush(Qt.NoBrush);painter.setPen(QPen(QColor('#2165D5'),2));painter.drawRoundedRect(QRectF(rect),12,12)
        painter.restore()


from PySide6.QtWidgets import QComboBox,QStyleOptionButton
class ComboBox(QComboBox):
    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor('#596A80' if self.isEnabled() else '#9CAABD'),1.6,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        x=self.width()-18;y=self.height()/2;p.drawLine(int(x-4),int(y-2),int(x),int(y+2));p.drawLine(int(x),int(y+2),int(x+4),int(y-2))

class CheckBox(QCheckBox):
    def paintEvent(self,event):
        super().paintEvent(event)
        option=QStyleOptionButton();option.initFrom(self)
        rect=self.style().subElementRect(QStyle.SE_CheckBoxIndicator,option,self)
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        if self.isChecked():
            p.setPen(QPen(QColor('#FFFFFF' if self.isEnabled() else '#EDF2F8'),1.8,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
            p.drawLine(rect.left()+4,rect.center().y(),rect.left()+7,rect.bottom()-4);p.drawLine(rect.left()+7,rect.bottom()-4,rect.right()-3,rect.top()+4)
        if self.hasFocus():p.setPen(QPen(QColor('#164EAD'),1.5));p.setBrush(Qt.NoBrush);p.drawRoundedRect(QRectF(rect).adjusted(-2,-2,2,2),5,5)


def form_dialog(parent,title,description):
    from PySide6.QtWidgets import QDialog,QFormLayout,QScrollArea
    dialog=QDialog(parent);dialog.setWindowTitle(title);dialog.resize(560,650)
    layout=QVBoxLayout(dialog);layout.setContentsMargins(24,22,24,22);layout.setSpacing(12)
    layout.addWidget(label(title,'title'));hint=label(description,'subtitle');hint.setWordWrap(True);layout.addWidget(hint)
    scroll=QScrollArea();scroll.setWidgetResizable(True);layout.addWidget(scroll,1)
    content=QWidget();form=QFormLayout(content);form.setContentsMargins(0,8,8,4);form.setSpacing(12);form.setRowWrapPolicy(QFormLayout.WrapLongRows);scroll.setWidget(content)
    dialog.footer=QHBoxLayout();layout.addLayout(dialog.footer)
    from .materials import apply_material
    apply_material(dialog,kind='dialog',radius=18)
    return dialog,form


def paint_spin_chevrons(widget):
    p=QPainter(widget);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor('#596A80' if widget.isEnabled() else '#A3B1C3'),1.4,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
    x=widget.width()-12
    for y,direction in [(widget.height()*.3,-1),(widget.height()*.7,1)]:
        p.drawLine(int(x-3),int(y-direction*1.5),int(x),int(y+direction*1.5));p.drawLine(int(x),int(y+direction*1.5),int(x+3),int(y-direction*1.5))

from PySide6.QtWidgets import QSpinBox,QDoubleSpinBox
class SpinBox(QSpinBox):
    def paintEvent(self,event):super().paintEvent(event);paint_spin_chevrons(self)
class DoubleSpinBox(QDoubleSpinBox):
    def paintEvent(self,event):super().paintEvent(event);paint_spin_chevrons(self)


class ChoiceDelegate(QStyledItemDelegate):
    """Comfortable native device rows with one selected check and clear focus."""
    def __init__(self,source,symbol,parent=None):
        super().__init__(parent);self.source=source;self.symbol=symbol
    def sizeHint(self,option,index):return QSize(320,50)
    def paint(self,p,option,index):
        p.save();p.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(option.rect).adjusted(1,2,-1,-2)
        selected=index.row()==self.source.currentIndex();hover=bool(option.state&QStyle.State_MouseOver)
        p.setPen(Qt.NoPen);p.setBrush(QColor('#D9E8FA' if selected else '#E6EFF9' if hover else '#00FFFFFF'));p.drawRoundedRect(rect,12,12)
        color='#2C5B92' if selected else '#506780'
        icon(self.symbol if index.data(Qt.UserRole) is not None else 'close',color,22).paint(p,option.rect.left()+12,option.rect.top()+14,22,22)
        font=option.font;font.setPixelSize(14);font.setWeight(QFont.Medium if selected else QFont.Normal);p.setFont(font);p.setPen(QColor(color))
        text=QFontMetrics(font).elidedText(str(index.data() or ''),Qt.ElideRight,max(60,option.rect.width()-92))
        p.drawText(option.rect.adjusted(46,0,-38,0),Qt.AlignVCenter|Qt.AlignLeft,text)
        if selected:icon('check','#2165D5',20).paint(p,option.rect.right()-29,option.rect.top()+15,20,20)
        if option.state&QStyle.State_HasFocus:p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#2165D5'),1.5));p.drawRoundedRect(rect,12,12)
        p.restore()


class DeviceChoices(QWidget):
    def __init__(self,source,symbol='camera',parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QListView,QAbstractItemView
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.source=source;self.view=QListView();self.view.setModel(source.model())
        self.view.setItemDelegate(ChoiceDelegate(source,symbol,self.view));self.view.setMouseTracking(True)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection);self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel);self.view.setUniformItemSizes(True)
        self.view.setStyleSheet('QListView {background:transparent;border:0;outline:0;}');self.view.setAccessibleName(source.accessibleName() or self.tr('Dispositivo'))
        layout.addWidget(self.view)
        source.currentIndexChanged.connect(self.sync)
        self.view.clicked.connect(lambda index:source.setCurrentIndex(index.row()))
        self.view.activated.connect(lambda index:source.setCurrentIndex(index.row()))
        source.model().rowsInserted.connect(self.resize_rows);source.model().rowsRemoved.connect(self.resize_rows);source.model().modelReset.connect(self.resize_rows)
        self.sync(source.currentIndex());self.resize_rows()
    def resize_rows(self,*_):self.view.setFixedHeight(min(5,max(1,self.source.count()))*50+4)
    def sync(self,index):
        self.view.setCurrentIndex(self.source.model().index(index,0));self.view.viewport().update()


class WindowDelegate(QStyledItemDelegate):
    """Stable two-line window rows with elision and native selection/focus."""
    def sizeHint(self,option,index):return QSize(0,76)
    def paint(self,p,option,index):
        p.save();p.setRenderHint(QPainter.Antialiasing)
        r=option.rect.adjusted(2,2,-2,-2);selected=bool(option.state&QStyle.State_Selected)
        p.setPen(Qt.NoPen);p.setBrush(QColor('#DFEBFA' if selected else '#FCFDFF'));p.drawRoundedRect(QRectF(r),12,12)
        p.setBrush(QColor('#CBDFF6' if selected else '#EAF1F9'));p.drawRoundedRect(QRectF(r.left()+12,r.top()+16,40,40),10,10)
        icon('window','#476B97',24).paint(p,r.left()+20,r.top()+24,24,24)
        lines=str(index.data() or '').split('\n',1);font=option.font;font.setPixelSize(14);font.setWeight(QFont.Medium);p.setFont(font);p.setPen(QColor('#304D70'))
        width=max(1,r.width()-100);p.drawText(r.left()+66,r.top()+29,QFontMetrics(font).elidedText(lines[0],Qt.ElideRight,width))
        font.setPixelSize(12);font.setWeight(QFont.Normal);p.setFont(font);p.setPen(QColor('#64768D'));p.drawText(r.left()+66,r.top()+50,QFontMetrics(font).elidedText(lines[1] if len(lines)>1 else '',Qt.ElideRight,width))
        if selected:icon('check','#2165D5',20).paint(p,r.right()-28,r.top()+26,20,20)
        if option.state&QStyle.State_HasFocus:p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#4179C2'),1.5));p.drawRoundedRect(QRectF(r),12,12)
        p.restore()

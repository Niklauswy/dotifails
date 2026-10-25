"""Reader-specific Material 3 surfaces, shapes and controls, painted from the shared Wysun theme.

Colours, shape, type and motion are the desktop's tokens (wysun_core), so the reader follows its mode and
the wallpaper's colours live. It keeps one choice of its own, the sun/moon button, saved in pdf-reader.json;
until that is used the reader simply follows the desktop.
Drawing controls explicitly keeps native GTK/Qt platform palettes out of the UI.
"""
from PySide6.QtCore import Qt, QSize, QRectF, QEvent, QObject, Signal, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPainter, QPen, QPalette
from PySide6.QtWidgets import QWidget, QAbstractButton, QStyledItemDelegate, QStyle, QListWidget, QFrame
from music_material import load_fonts, symbol_family
from wysun_core import jsonio, paths, qt_theme, theme as core_theme

MODES = ('light', 'dark')
# The reader's roles, and the shared token each one is painted with.
ROLES = {'canvas': 'canvas', 'surface': 'surface', 'surface_low': 'well', 'surface_high': 'fill',
         'surface_bright': 'surface_raised', 'text': 'text', 'muted': 'muted', 'primary': 'accent',
         'on_primary': 'on_accent', 'primary_container': 'row_selected', 'on_primary_container': 'text',
         'outline': 'line', 'selection': 'selection', 'disabled': 'disabled'}
GLYPHS = {'notes': 0xe06f, 'palette': 0xe40a, 'back': 0xe5c4, 'forward': 0xe5c8, 'sidebar': 0xe9b4, 'list': 0xe8ef,
          'search': 0xe8b6, 'more': 0xe5d3, 'plus': 0xe145, 'documents': 0xe873, 'saved': 0xe161,
          'folder-open': 0xe2c8, 'trash': 0xe872, 'highlight': 0xe25f, 'underline': 0xe249, 'sun': 0xe518,
          'moon': 0xe51c, 'select': 0xe262, 'book': 0xe865, 'zoom': 0xe8ff, 'fit': 0xe5d0}


class Metrics:
    """Shape, spacing, type, icon and motion sizes are the shared theme's; only the layout sizes are the reader's."""
    LAYOUT = {'control': 44, 'rail': 80, 'sidebar': 244}
    # The reader's names for what the theme calls differently (Material shape scale, icon size, motion).
    ALIASES = {'radius_s': 'corner_m', 'radius_m': 'corner_l', 'radius_l': 'corner_xl', 'radius_xl': 'corner_xl',
               'icon': 'icon_size', 'motion_ms': 'motion_fast'}

    def __getitem__(self, name):
        if name in self.LAYOUT:
            return self.LAYOUT[name]
        values = qt_theme.tokens()
        if name == 'space_xxl':
            return values['space_l'] * 2
        return values[self.ALIASES.get(name, name)]


M = Metrics()


class ReaderTheme(QObject):
    changed = Signal()

    def __init__(self, parent=None, mode=None):
        super().__init__(parent)
        self.path = paths.config('wysun', 'pdf-reader.json')
        saved = jsonio.read_json(self.path, {})
        saved = saved.get('mode') if isinstance(saved, dict) else None
        # None follows the desktop's mode.
        self.override = mode if mode in MODES else saved if saved in MODES else None
        self._other = None
        load_fonts()
        qt_theme.on_theme_changed(self.desktop_changed)

    @property
    def mode(self):
        return self.override or qt_theme.tokens()['mode']

    def values(self):
        active = qt_theme.tokens()
        if self.override in (None, active['mode']):
            return active
        # The other mode has no wallpaper colours: its base palette.
        if self._other is None:
            self._other = core_theme.resolve(self.override)
        return self._other

    def desktop_changed(self):
        self._other = None
        self.changed.emit()

    def set_mode(self, mode, persist=False):
        self.override = 'light' if mode == 'light' else 'dark'
        self._other = None
        if persist:
            jsonio.atomic_write_json(self.path, {'mode': self.override})
        self.changed.emit()

    def color(self, role, alpha=None):
        return qt_theme.color(ROLES[role], alpha, self.values())

    def font(self, role='body', weight=400):
        return qt_theme.font(role=role, weight=weight, values=self.values())

    def palette(self):
        p = QPalette()
        for role, value in ((QPalette.Window, 'canvas'), (QPalette.Base, 'surface_low'),
                            (QPalette.Text, 'text'), (QPalette.WindowText, 'text'),
                            (QPalette.Button, 'surface'), (QPalette.ButtonText, 'text'),
                            (QPalette.Highlight, 'primary_container'),
                            (QPalette.HighlightedText, 'on_primary_container')):
            p.setColor(role, self.color(value))
        return p

    def icon(self, painter, name, rect, role='text', size=None):
        f = QFont(symbol_family()); f.setPixelSize(size or M['icon'])
        painter.setFont(f); painter.setPen(self.color(role))
        painter.drawText(rect, Qt.AlignCenter, chr(GLYPHS.get(name, GLYPHS['documents'])))

    def inputs(self):
        c = lambda role: self.color(role).name()
        family = qt_theme.family(self.values())
        return f'''
QDialog, QMessageBox {{background:{c('canvas')}; color:{c('text')};}}
QLabel {{color:{c('text')}; font-family:"{family}"; font-size:{M['font_body']}px;}}
QPushButton {{background:{c('primary_container')}; color:{c('on_primary_container')}; border:0; border-radius:{M['control']//2}px; min-height:{M['control']}px; padding:0 {M['space_xl']}px;}}
QPushButton:hover {{background:{c('selection')};}}
QPushButton:default {{background:{c('primary')}; color:{c('on_primary')};}}
QPushButton:disabled {{background:{c('surface_high')}; color:{c('disabled')};}}
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {{
 background:{c('surface_high')}; color:{c('text')}; border:0;
 border-radius:{M['radius_s']}px; padding:{M['space_m']}px;
 selection-background-color:{c('primary_container')}; selection-color:{c('on_primary_container')};
 font-family:"{family}"; font-size:{M['font_body']}px;
}}
QComboBox::drop-down {{border:0; width:{M['space_xl']}px;}}
QComboBox QAbstractItemView {{background:{c('surface_high')}; color:{c('text')}; selection-background-color:{c('primary_container')}; border:0;}}
QScrollArea {{border:0; background:transparent;}}
QScrollBar:vertical {{background:transparent; width:{M['space_s']}px; margin:0;}}
QScrollBar::handle:vertical {{background:{c('outline')}; border-radius:{M['space_xs']}px; min-height:{M['space_xxl']}px;}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{background:transparent;}}
QScrollBar:horizontal {{height:{M['space_s']}px; background:transparent;}}
QScrollBar::handle:horizontal {{background:{c('outline')}; border-radius:{M['space_xs']}px; min-width:{M['space_xxl']}px;}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{width:0;}}
QToolTip {{color:{c('text')}; background:{c('surface_high')}; border:0; padding:{M['space_s']}px;}}
'''


class Panel(QWidget):
    def __init__(self, theme, role='surface', radius='radius_l', parent=None):
        super().__init__(parent); self.theme = theme; self.role = role; self.radius = radius
        theme.changed.connect(self.update)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen); p.setBrush(self.theme.color(self.role))
        r = min(self.height()/2, M[self.radius]) if self.radius else 0
        p.drawRoundedRect(QRectF(self.rect()), r, r)


class Text(QWidget):
    def __init__(self, theme, text='', role='body', tone='text', weight=400):
        super().__init__(); self.theme=theme; self._text=text; self.role=role; self.tone=tone; self.weight=weight
        self.setMinimumWidth(0); self.setFixedHeight(M['font_'+role]+M['space_m'])
        theme.changed.connect(self.update)

    def text(self): return self._text

    def setText(self, text):
        self._text=str(text); self.setAccessibleName(self._text); self.setToolTip(self._text); self.update()

    def sizeHint(self): return QSize(160, self.height())

    def paintEvent(self, event):
        p=QPainter(self); p.setFont(self.theme.font(self.role,self.weight));p.setPen(self.theme.color(self.tone))
        p.drawText(self.rect(), Qt.AlignVCenter | Qt.AlignLeft,
                   p.fontMetrics().elidedText(self._text, Qt.ElideRight, self.width()))


class Action(QAbstractButton):
    """M3 full-rounded tonal/filled action with animated press shape and state layer."""
    def __init__(self, theme, text='', icon=None, callback=None, kind='text', size=None):
        super().__init__(); self.theme=theme; self.symbol=icon;self.kind=kind;self.progress=0.
        self.keyboard_focus=False
        self.setText(text); self.setAccessibleName(text or icon or 'Acción')
        self.setCursor(Qt.PointingHandCursor); self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_Hover);self.setFixedHeight(size or M['control'])
        if not text: self.setFixedWidth(self.height())
        self.animation=QVariantAnimation(self);self.animation.setDuration(M['motion_ms'])
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self.animate)
        self.pressed.connect(lambda:self.morph(1.));self.released.connect(lambda:self.morph(0.))
        if callback:self.clicked.connect(lambda _:callback())
        theme.changed.connect(self.update)

    def setToolTip(self, text):
        super().setToolTip(text)
        if not self.text():self.setAccessibleName(text.split(' · ')[0])

    def animate(self,value): self.progress=float(value);self.update()
    def morph(self,value):
        self.animation.stop();self.animation.setStartValue(self.progress);self.animation.setEndValue(value);self.animation.start()

    def sizeHint(self):
        if not self.text():return QSize(self.height(),self.height())
        from PySide6.QtGui import QFontMetrics
        return QSize(QFontMetrics(self.theme.font('body',500)).horizontalAdvance(self.text()) + M['space_xl']*2 + (M['icon']+M['space_s'] if self.symbol else 0), self.height())

    def event(self,event):
        if event.type() in (QEvent.Enter,QEvent.Leave,QEvent.HoverEnter,QEvent.HoverLeave):self.update()
        return super().event(event)

    def focusInEvent(self,event):
        self.keyboard_focus=event.reason() in (Qt.TabFocusReason,Qt.BacktabFocusReason,Qt.ShortcutFocusReason)
        super().focusInEvent(event);self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen)
        checked=self.isChecked();filled=self.kind=='filled';tonal=self.kind=='tonal' or checked
        fg='on_primary' if filled else 'on_primary_container' if tonal else 'text'
        bg='primary' if filled else 'primary_container' if tonal else None
        if not self.isEnabled(): fg='disabled';bg='surface_high' if filled else None
        r=self.height()/2-(self.height()/2-M['radius_s'])*self.progress
        if bg:p.setBrush(self.theme.color(bg));p.drawRoundedRect(QRectF(self.rect()),r,r)
        if self.isEnabled() and (self.underMouse() or self.isDown()):
            p.setBrush(self.theme.color(fg,24 if self.isDown() else 15));p.drawRoundedRect(QRectF(self.rect()),r,r)
        if self.keyboard_focus and self.hasFocus():
            p.setBrush(Qt.NoBrush);p.setPen(QPen(self.theme.color('primary'),2));p.drawRoundedRect(QRectF(self.rect()).adjusted(2,2,-2,-2),r,r)
        p.setFont(self.theme.font('body',500));fm=p.fontMetrics()
        text_width=fm.horizontalAdvance(self.text());icon_width=M['icon'] if self.symbol else 0
        total=text_width+icon_width+(M['space_s'] if self.symbol and self.text() else 0)
        x=(self.width()-total)/2
        if self.symbol:
            self.theme.icon(p,self.symbol,QRectF(x,0,icon_width,self.height()),fg)
            x+=icon_width+M['space_s']
        p.setFont(self.theme.font('body',500));p.setPen(self.theme.color(fg))
        p.drawText(QRectF(x,0,text_width,self.height()),Qt.AlignVCenter,self.text())


class RowDelegate(QStyledItemDelegate):
    def __init__(self,theme,parent=None):super().__init__(parent);self.theme=theme
    def sizeHint(self,option,index):return QSize(180,M['control']+M['space_m'])
    def paint(self,p,option,index):
        p.save();p.setRenderHint(QPainter.Antialiasing);r=QRectF(option.rect).adjusted(0,M['space_xs']/2,0,-M['space_xs']/2)
        selected=bool(option.state & QStyle.State_Selected)
        hover=bool(option.state & QStyle.State_MouseOver)
        if selected or hover:
            p.setPen(Qt.NoPen);p.setBrush(self.theme.color('primary_container' if selected else 'surface_high'))
            p.drawRoundedRect(r,M['radius_m'],M['radius_m'])
        text=str(index.data() or '')
        p.setFont(self.theme.font('body',500 if selected else 400))
        p.setPen(self.theme.color('on_primary_container' if selected else 'text'))
        text_rect=r.adjusted(M['space_l'],0,-M['space_l'],0)
        p.drawText(text_rect,Qt.AlignVCenter,p.fontMetrics().elidedText(text,Qt.ElideRight,int(text_rect.width())))
        p.restore()


def reader_list(theme):
    w=QListWidget();w.setFrameShape(QFrame.NoFrame);w.setMouseTracking(True)
    w.setItemDelegate(RowDelegate(theme,w));w.setSpacing(M['space_xs'])
    def refresh():
        w.setPalette(theme.palette());w.viewport().setPalette(theme.palette())
        w.setStyleSheet('QListWidget {background:transparent; border:0; outline:0;}'+theme.inputs())
        w.viewport().setAutoFillBackground(False);w.viewport().update()
    theme.changed.connect(refresh);refresh();return w


from collections import OrderedDict
from PySide6.QtCore import QAbstractListModel, QModelIndex
from PySide6.QtWidgets import QListView


class PageModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent);self.pages=0;self.images=OrderedDict()

    def reset(self, pages):
        self.beginResetModel();self.pages=pages;self.images.clear();self.endResetModel()

    def rowCount(self, parent=QModelIndex()):return 0 if parent.isValid() else self.pages

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():return None
        if role==Qt.DisplayRole:return str(index.row()+1)
        if role==Qt.UserRole:return self.images.get(index.row())
        if role==Qt.AccessibleTextRole:return f'Página {index.row()+1}'
        return None

    def put(self, page, image):
        self.images[page]=image;self.images.move_to_end(page)
        while len(self.images)>48:self.images.popitem(last=False)
        index=self.index(page,0);self.dataChanged.emit(index,index)


class ThumbnailDelegate(QStyledItemDelegate):
    def __init__(self,theme,parent=None):super().__init__(parent);self.theme=theme
    def sizeHint(self,option,index):return QSize(180, M['rail']*3)
    def paint(self,p,option,index):
        p.save();p.setRenderHint(QPainter.Antialiasing);p.setRenderHint(QPainter.SmoothPixmapTransform)
        r=QRectF(option.rect).adjusted(M['space_s'],M['space_xs'], -M['space_s'],-M['space_xs'])
        selected=bool(option.state & QStyle.State_Selected)
        p.setPen(Qt.NoPen);p.setBrush(self.theme.color('primary_container' if selected else 'surface'))
        p.drawRoundedRect(r,M['radius_m'],M['radius_m'])
        area=r.adjusted(M['space_l'],M['space_m'],-M['space_l'],-M['control'])
        image=index.data(Qt.UserRole)
        if image is not None and not image.isNull():
            scaled=image.size().scaled(int(area.width()),int(area.height()),Qt.KeepAspectRatio)
            rect=QRectF(area.center().x()-scaled.width()/2,area.center().y()-scaled.height()/2,scaled.width(),scaled.height())
            p.drawImage(rect,image)
        else:
            self.theme.icon(p,'documents',area,'muted',M['space_xxl'])
        p.setPen(self.theme.color('on_primary_container' if selected else 'muted'));p.setFont(self.theme.font('small',500))
        p.drawText(QRectF(r.x(),r.bottom()-M['control'],r.width(),M['control']),Qt.AlignCenter,index.data())
        p.restore()


def thumbnail_view(theme):
    view=QListView();view.setFrameShape(QFrame.NoFrame);view.setVerticalScrollMode(QListView.ScrollPerPixel)
    view.setUniformItemSizes(True);view.setItemDelegate(ThumbnailDelegate(theme,view))
    model=PageModel(view);view.setModel(model)
    def refresh():
        view.setPalette(theme.palette());view.viewport().setPalette(theme.palette())
        view.setStyleSheet('QListView {background:transparent; border:0; outline:0;}'+theme.inputs())
        view.viewport().setAutoFillBackground(False);view.viewport().update()
    theme.changed.connect(refresh);refresh()
    return view,model


class Emblem(QWidget):
    """A single expressive shape for the app identity, not every control."""
    def __init__(self,theme,size=None):
        super().__init__();self.theme=theme;self.setFixedSize(size or M['control']+M['space_m'],size or M['control']+M['space_m'])
        self.setAccessibleName('Wysun PDF');theme.changed.connect(self.update)

    def paintEvent(self,event):
        import math
        from PySide6.QtGui import QPainterPath
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);path=QPainterPath()
        for i in range(129):
            angle=i*math.tau/128;r=self.width()*.44*(1+.065*math.cos(8*angle))
            x=self.width()/2+math.cos(angle)*r;y=self.height()/2+math.sin(angle)*r
            if i==0:path.moveTo(x,y)
            else:path.lineTo(x,y)
        path.closeSubpath();p.setPen(Qt.NoPen);p.setBrush(self.theme.color('primary'));p.drawPath(path)
        self.theme.icon(p,'book',QRectF(self.rect()),'on_primary',round(self.width()*.44))


from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit


class NoteDialog(QDialog):
    def __init__(self,theme,parent=None,text='',title='Añadir una nota'):
        super().__init__(parent);self.setWindowTitle(title);self.setPalette(theme.palette());self.setStyleSheet(theme.inputs())
        self.setMinimumWidth(M['rail']*6)
        layout=QVBoxLayout(self);layout.setContentsMargins(M['space_xl'],M['space_xl'],M['space_xl'],M['space_xl']);layout.setSpacing(M['space_l'])
        layout.addWidget(Text(theme,title,'heading','text',500))
        layout.addWidget(Text(theme,'Una idea para volver a ella.','body','muted'))
        self.editor=QPlainTextEdit();self.editor.setPlainText(text);self.editor.setPlaceholderText('Escribe aquí…')
        self.editor.setMinimumHeight(M['rail']*2);layout.addWidget(self.editor)
        buttons=QHBoxLayout();buttons.addStretch()
        buttons.addWidget(Action(theme,'Cancelar',callback=self.reject,kind='tonal'))
        save=Action(theme,'Guardar nota',callback=self.accept,kind='filled');buttons.addWidget(save);layout.addLayout(buttons)
        self.editor.textChanged.connect(lambda:save.setEnabled(bool(self.editor.toPlainText().strip())))
        save.setEnabled(bool(text.strip()));self.editor.setFocus()

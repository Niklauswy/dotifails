"""Clipboard page inside the existing launcher; shared data/actions, native layout."""
import datetime,time
from collections import OrderedDict
from PySide6.QtCore import Qt,QTimer,QSize,QEvent
from PySide6.QtGui import QImage,QKeySequence,QShortcut
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QListWidget,
    QListView,QAbstractItemView,QComboBox,QStackedWidget,QPlainTextEdit,QScrollArea,QGraphicsOpacityEffect)
from PySide6.QtCore import QVariantAnimation,QEasingCurve
from clipboard_window import ClipboardWindow
from clipboard_data import ClipboardLibrary,unpack
from clipboard_controls import ColorValueRow
from clipboard_visuals import LinkHero,KIND_ICON,KIND_LABEL
from enhanced import ModernDelegate
from files_zoom import ZoomCanvas
from ui_motion import MotionButton
from theme_tokens import apply_style
from orbit import divider
from icons import icon

class LauncherClipboard(ClipboardWindow):
    """Reuse clipboard behavior while the launcher's chrome owns search and navigation."""
    def __init__(self,owner):
        QWidget.__init__(self,owner)
        self.owner=owner;self.store=owner.store;self.library=ClipboardLibrary(self.store);self.test=owner.test
        self.kind='';self.favorite=False;self.collection=None;self.grid=False;self.source_window='';self.rows=[]
        self._signature=None;self._picked=[];self.pixmaps=OrderedDict();self.detail_id=None;self._refreshing=False;self.ocr_mode=False;self.link_job=None;self._closing=False
        self.search=owner.search;self.status=owner.status;self.copy_button=owner.go;self.copy_options=owner.action_button;self.more=owner.action_button;self.add_collection=owner.filter_button
        self.sources=QComboBox(self);self.sources.addItem('Aplicaciones','');self.sources.hide();self.sources.currentIndexChanged.connect(lambda:self.refresh(True))
        self.collections=QComboBox(self);self.collections.hide();self.collections.currentIndexChanged.connect(self.choose_collection);self.chips={}
        self.pause=self.icon_button('pause','Pausar captura',self.toggle_capture);self.pause.hide()
        root=QHBoxLayout(self);root.setContentsMargins(8,0,8,0);root.setSpacing(0)
        left=QWidget();self.list_column=left;left.setMaximumWidth(325);column=QVBoxLayout(left);column.setContentsMargins(6,12,6,5);column.setSpacing(6)
        self.heading=self.label('Recientes','section');column.addWidget(self.heading)
        self.cards=QListWidget();self.cards.setViewMode(QListView.ListMode);self.cards.setItemDelegate(ModernDelegate(self.cards));self.cards.setSpacing(1);self.cards.setMouseTracking(True)
        self.cards.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.cards.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel);self.cards.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.cards.currentItemChanged.connect(lambda *_:self.update_detail());self.cards.itemSelectionChanged.connect(self.selection_changed);self.cards.itemDoubleClicked.connect(lambda *_:self.copy_selected(close=True))
        self.cards.setContextMenuPolicy(Qt.CustomContextMenu);self.cards.customContextMenuRequested.connect(self.context_menu);column.addWidget(self.cards,1)
        self.empty=self.label('Tu próxima copia aparecerá aquí.','muted');self.empty.setWordWrap(True);column.addWidget(self.empty)
        self.combine=self.button('Combinar selección',self.combine_selected);self.combine.setIcon(icon('layers',16));self.combine.hide();column.addWidget(self.combine)
        root.addWidget(left,1);line=divider();line.setFixedWidth(1);line.setMinimumHeight(0);line.setMaximumHeight(16777215);root.addWidget(line);self.separator=line
        self.detail=QWidget();self.detail.setMinimumWidth(420);details=QVBoxLayout(self.detail);details.setContentsMargins(23,18,18,16);details.setSpacing(9)
        tools=QHBoxLayout();self.detail_type=self.label('Vista previa','muted');tools.addWidget(self.detail_type,1)
        self.ocr_text=self.button('Texto',self.toggle_ocr_text);self.ocr_text.setIcon(icon('scan-text',16));tools.addWidget(self.ocr_text)
        self.open_link=self.icon_button('external-link','Abrir en el navegador · Ctrl+O',self.open_current);tools.addWidget(self.open_link);details.addLayout(tools)
        self.detail_title=self.label('','previewTitle');self.detail_title.setWordWrap(True);self.detail_title.setMaximumHeight(58);details.addWidget(self.detail_title)
        self.stack=QStackedWidget();self.stack.setMinimumHeight(90);details.addWidget(self.stack,1)
        self.text=QPlainTextEdit();self.text.setReadOnly(True);self.text.setAccessibleName('Contenido del clip');self.stack.addWidget(self.text)
        image_page=QWidget();images=QVBoxLayout(image_page);images.setContentsMargins(0,0,0,0);images.setSpacing(5)
        self.image=ZoomCanvas();self.image.setMinimumSize(0,60);images.addWidget(self.image,1)
        self.image_ocr=self.label('','muted');self.image_ocr.setWordWrap(True);images.addWidget(self.image_ocr);self.stack.addWidget(image_page)
        color_page=QWidget();color_layout=QVBoxLayout(color_page);color_layout.setContentsMargins(0,0,0,0);color_layout.setSpacing(4)
        self.swatch=QLabel();self.swatch.setMinimumHeight(45);self.swatch.setMaximumHeight(110);color_layout.addWidget(self.swatch,1)
        self.color_rows={};self.color_grid=QGridLayout();self.color_grid.setContentsMargins(0,0,0,0);self.color_grid.setSpacing(2)
        for number,name in enumerate(('HEX','RGB','HSL','CMYK'),1):
            row=ColorValueRow(name,number,lambda checked=False,n=name:self.copy_color(n));row.shortcut_prefix='Ctrl+Alt+';row.setMinimumHeight(26)
            apply_style(row,'QPushButton {background:transparent;border:1px solid transparent;padding:3px 7px;border-radius:7px;} QPushButton:hover {background:rgba(180,190,210,15);} QPushButton:focus {border-color:#91B5ED;}')
            self.color_rows[name]=row;self.color_grid.addWidget(row,number-1,0)
        color_layout.addLayout(self.color_grid);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(color_page);self.stack.addWidget(scroll)
        self.parts=QListWidget();self.parts.setDragDropMode(QAbstractItemView.InternalMove);self.parts.model().rowsMoved.connect(self.reorder_parts);self.stack.addWidget(self.parts)
        web=QWidget();web_layout=QVBoxLayout(web);web_layout.setContentsMargins(0,0,0,0);web_layout.setSpacing(7)
        self.link_hero=LinkHero();web_layout.addWidget(self.link_hero,1)
        self.link_title=self.label('','previewTitle');self.link_title.setWordWrap(True);self.link_title.setMaximumHeight(58);web_layout.addWidget(self.link_title)
        self.link_description=self.label('','muted');self.link_description.setWordWrap(True);self.link_description.setMaximumHeight(44);web_layout.addWidget(self.link_description)
        self.link_address=self.label('','muted');self.link_address.setWordWrap(True);self.link_address.setTextInteractionFlags(Qt.TextSelectableByMouse);web_layout.addWidget(self.link_address);self.stack.addWidget(web)
        self.metadata=self.label('','muted');self.metadata.setWordWrap(True);self.metadata.setTextInteractionFlags(Qt.TextSelectableByMouse);details.addWidget(self.metadata);root.addWidget(self.detail,1)
        self.detail_effect=QGraphicsOpacityEffect(self.stack);self.stack.setGraphicsEffect(self.detail_effect);self.detail_animation=QVariantAnimation(self);self.detail_animation.setDuration(150);self.detail_animation.setEasingCurve(QEasingCurve.OutCubic);self.detail_animation.valueChanged.connect(self.detail_effect.setOpacity)
        self.toast_timer=QTimer(self);self.toast_timer.setSingleShot(True);self.toast_timer.timeout.connect(self.reset_copy_button)
        self.link_timer=QTimer(self);self.link_timer.setSingleShot(True);self.link_timer.setInterval(180);self.link_timer.timeout.connect(self.request_link)
        self.layout_timer=QTimer(self);self.timer=QTimer(self);self.timer.setInterval(900);self.timer.timeout.connect(self.refresh)
        self.shortcuts=[]
        for key,fn in [('Ctrl+C',self.copy_unless_text_selection),('Ctrl+F',self.search.setFocus),('Ctrl+Shift+C',self.copy_menu),('Ctrl+I',self.toggle_ocr_text),('Ctrl+O',self.open_current),('Ctrl+G',self.combine_selected),('Delete',self.delete_selected),('F1',self.keyboard_menu),('Ctrl+Shift+F',self.filter_menu)]:
            shortcut=QShortcut(QKeySequence(key),self);shortcut.activated.connect(fn);self.shortcuts.append(shortcut)
        for number,name in enumerate(('HEX','RGB','HSL','CMYK'),1):
            shortcut=QShortcut(QKeySequence(f'Ctrl+Alt+{number}'),self);shortcut.activated.connect(lambda n=name:self.copy_color(n));self.shortcuts.append(shortcut)
        for delta,key in [(-1,'Alt+Up'),(1,'Alt+Down')]:
            shortcut=QShortcut(QKeySequence(key),self.parts);shortcut.setContext(Qt.WidgetShortcut);shortcut.activated.connect(lambda d=delta:self.move_part(d));self.shortcuts.append(shortcut)
        self.search.installEventFilter(self);self.cards.installEventFilter(self)
        self.refresh_collections()
    def showEvent(self,event):
        QWidget.showEvent(self,event);self.source_window=self.owner.source_window;self.timer.start();self.refresh(True)
    def hideEvent(self,event):
        self.timer.stop();self.link_timer.stop();self.toast_timer.stop();QWidget.hideEvent(self,event)
    def paintEvent(self,event):pass
    def adapt_color(self):self.metadata.show()
    def reset_copy_label(self):
        super().reset_copy_label();self.copy_options.setText('Acciones  Alt K');self.copy_button.setIcon(icon('copy',16))
    def copy_selected(self,close=False,paste=False,**kwargs):
        super().copy_selected(close=False,paste=False,**kwargs)
        if not self.selected_ids():return
        if close or paste:self.owner.hide()
        if paste and self.owner.source_window and not self.test:QTimer.singleShot(150,lambda:self.owner.paste_to(self.owner.source_window))
    def dismiss(self):self.owner.dismiss()
    def toggle_grid(self):pass
    def toggle_detail(self):
        visible=not self.detail.isVisible();self.detail.setVisible(visible);self.separator.setVisible(visible);self.list_column.setMaximumWidth(325 if visible else 16777215)
    def selection_changed(self):
        super().selection_changed();self.copy_options.setText('Acciones  Alt K')
    def refresh(self,force=False):
        if self.owner.mode!='clipboard':return
        before=self._signature;scroll=self.cards.verticalScrollBar().value();previous=self.current()
        super().refresh(force)
        self.owner.filter_button.setText(('Favoritos' if self.favorite else KIND_LABEL.get(self.kind,'Todos'))+'  ⌄')
        if not force and before==self._signature:return
        # The same row delegate used by home, snippets and the original launcher history.
        for index in range(self.cards.count()):
            item=self.cards.item(index);row=item.data(Qt.UserRole);meta=unpack(row.get('meta'))
            row['clip_kind']=row['kind'];row['icon']=KIND_ICON.get(row['kind'],'file-text')
            row['subtitle']=(row.get('source') or 'Local')+' · '+datetime.datetime.fromtimestamp(row['stamp']).strftime('%d %b, %H:%M')
            if row['kind']=='color':row['color_value']=row['text']
            if row['kind'] in ('image','url') and row.get('thumb'):
                from PySide6.QtGui import QPixmap
                row['thumbnail']=QPixmap.fromImage(QImage.fromData(row['thumb']))
            item.setData(Qt.UserRole,row)
        if previous and any(row['id']==previous['id'] for row in self.rows):self.cards.verticalScrollBar().setValue(scroll)
    def eventFilter(self,obj,event):
        if self.owner.mode!='clipboard':return False
        if event.type()==QEvent.KeyPress and obj==self.cards and event.key() in (Qt.Key_Left,Qt.Key_Right) and not event.modifiers():
            step=-1 if event.key()==Qt.Key_Left else 1;self.cards.setCurrentRow(max(0,min(self.cards.count()-1,self.cards.currentRow()+step)));return True
        return super().eventFilter(obj,event)
    def build_copy_menu(self):
        menu=super().build_copy_menu()
        for action in menu.actions():
            if action.data() in self.color_rows:action.setText(action.text().replace('\tAlt+','\tCtrl+Alt+'))
        return menu
    def keyboard_menu(self):
        from clipboard_controls import ActionMenu
        menu=ActionMenu(self);menu.command('search','Buscar',self.search.setFocus,'Ctrl+F');menu.command('copy','Copiar',self.copy_selected,'Ctrl+C');menu.command('chevron-down','Copiar como',self.copy_menu,'Ctrl+Shift+C');menu.command('scan-text','Imagen / texto reconocido',self.toggle_ocr_text,'Ctrl+I')
        menu.command('star','Favorito',lambda:self.toggle_favorite(),'Ctrl+P');menu.command('layers','Combinar selección',self.combine_selected,'Ctrl+G');self.show_menu(menu,self.owner.action_button,True)

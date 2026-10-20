"""Visual local clipboard library, backed by the resident capture controller."""
import datetime,json,os,subprocess,time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit
from PySide6.QtCore import Qt,QSize,QTimer,QUrl,QEvent,QVariantAnimation,QEasingCurve,QItemSelectionModel
from PySide6.QtGui import (QImage,QPixmap,QPainter,QPainterPath,QColor,QPen,QIcon,
    QKeySequence,QShortcut,QDesktopServices,QCursor)
from PySide6.QtWidgets import (QApplication,QWidget,QGridLayout,QVBoxLayout,QHBoxLayout,QLabel,
    QLineEdit,QComboBox,QScrollArea,QSplitter,QListWidget,QListWidgetItem,QListView,
    QAbstractItemView,QPlainTextEdit,QMenu,QInputDialog,QMessageBox,QStackedWidget,
    QGraphicsOpacityEffect,QSizePolicy)
from icons import icon
from ui_motion import WindowMotion,MotionButton,reveal_content
from files_motion import animate_popup,reduced_motion
from files_zoom import ZoomCanvas
from clipboard_data import ClipboardLibrary,unpack
from theme_tokens import apply_style,css
from clipboard_visuals import STYLE,KIND_LABEL,KIND_ICON,ClipCards,ClipDelegate,LinkHero
from link_preview import LinkPreviewJob
from data_v2 import color_formats
from clipboard_controls import ActionMenu,CopyButton,ColorValueRow

class ClipboardWindow(WindowMotion,QWidget):
    def __init__(self,owner,test=False):
        super().__init__();self.owner=owner;self.store=owner.store;self.library=ClipboardLibrary(self.store);self.test=test
        self.motion_from_top=True;self.motion_enter_ms=360;self.motion_exit_ms=220
        self.kind='';self.favorite=False;self.collection=None;self.grid=False;self.source_window=''
        self.rows=[];self._signature=None;self._picked=[];self.pixmaps=OrderedDict();self.detail_id=None;self._refreshing=False;self.ocr_mode=False;self.link_job=None;self._closing=False
        self.setWindowTitle('Wysun Clipboard');self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint);self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(680,520);self.resize(1080,860);apply_style(self,STYLE)
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);root.setSpacing(10)
        self.splitter=QSplitter(Qt.Vertical);self.splitter.setChildrenCollapsible(False);root.addWidget(self.splitter)
        surface=QWidget();surface.setObjectName('clipSurface');layout=QVBoxLayout(surface);layout.setContentsMargins(20,14,20,12);layout.setSpacing(10)
        top=QHBoxLayout();top.setSpacing(8)
        self.search=QLineEdit();self.search.setObjectName('clipSearch');self.search.setPlaceholderText('Buscar texto, imágenes o aplicación…');self.search.setClearButtonEnabled(True);self.search.setAccessibleName('Buscar en el historial y texto reconocido')
        self.search.addAction(icon('search',18,'muted'),QLineEdit.LeadingPosition);top.addWidget(self.search,1)
        self.sources=QComboBox();self.sources.setAccessibleName('Filtrar por aplicación');self.sources.setMaximumWidth(150);self.sources.addItem('Aplicaciones','');self.sources.currentIndexChanged.connect(lambda:self.refresh(True));self.sources.hide()
        self.pause=self.icon_button('pause','Pausar captura',self.toggle_capture);self.pause.hide()
        self.view=self.icon_button('layout-grid','Cambiar entre bandeja y cuadrícula',self.toggle_grid);top.addWidget(self.view)
        self.more=self.icon_button('ellipsis','Más opciones del historial',self.history_menu);top.addWidget(self.more)
        self.close_button=self.icon_button('x','Cerrar · Esc',self.dismiss);top.addWidget(self.close_button);layout.addLayout(top)
        filters=QHBoxLayout();filters.setSpacing(6)
        self.filters_scroll=QScrollArea();self.filters_scroll.setWidgetResizable(True);self.filters_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.filters_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.filters_scroll.setFixedHeight(37)
        filters_widget=QWidget();self.chips_layout=QHBoxLayout(filters_widget);self.chips_layout.setContentsMargins(0,0,0,0);self.chips_layout.setSpacing(6)
        self.chips={}
        for key,title in [('', 'Todo'),('image','Imágenes'),('url','Enlaces'),('favorite','Favoritos')]:
            chip=self.button(title,lambda checked=False,k=key:self.choose_type(k));chip.setObjectName('clipChip');chip.setFixedHeight(32);chip.setCheckable(True);chip.setChecked(key=='');self.chips[key]=chip;self.chips_layout.addWidget(chip)
        self.chips_layout.addStretch();self.filters_scroll.setWidget(filters_widget);filters.addWidget(self.filters_scroll,1)
        self.collections=QComboBox();self.collections.setAccessibleName('Colección');self.collections.setMaximumWidth(170);self.collections.currentIndexChanged.connect(self.choose_collection);self.collections.hide()
        self.add_collection=self.icon_button('sliders-horizontal','Filtrar por tipo, aplicación o colección',self.filter_menu);filters.addWidget(self.add_collection);layout.addLayout(filters)
        section=QHBoxLayout();self.heading=self.label('Recientes','clipMuted');self.heading.hide();section.addWidget(self.heading,1)
        self.combine=self.button('Combinar selección',self.combine_selected);self.combine.setIcon(icon('layers',16));self.combine.setObjectName('clipPrimary');self.combine.hide();section.addWidget(self.combine);layout.addLayout(section)
        self.cards=ClipCards();self.cards.setObjectName('clipCards');self.cards.setViewMode(QListView.IconMode);self.cards.setFlow(QListView.LeftToRight);self.cards.setWrapping(False);self.cards.setMovement(QListView.Static);self.cards.setResizeMode(QListView.Adjust);self.cards.setGridSize(QSize(198,160));self.cards.setSpacing(2);self.cards.setMinimumHeight(165)
        self.cards.setSelectionMode(QAbstractItemView.ExtendedSelection);self.cards.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel);self.cards.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.cards.setItemDelegate(ClipDelegate(self));self.cards.itemSelectionChanged.connect(self.selection_changed);self.cards.currentItemChanged.connect(lambda *_:self.update_detail());self.cards.itemDoubleClicked.connect(lambda *_:self.copy_selected(close=True))
        self.cards.favoriteRequested.connect(self.toggle_favorite);self.cards.previewRequested.connect(lambda:self.detail.show());self.cards.setContextMenuPolicy(Qt.CustomContextMenu);self.cards.customContextMenuRequested.connect(self.context_menu);layout.addWidget(self.cards,1)
        self.empty=self.label('Tu próxima copia aparecerá aquí.','clipMuted');self.empty.setAlignment(Qt.AlignCenter);self.empty.setMinimumHeight(70);layout.addWidget(self.empty)
        footer=QHBoxLayout();self.status=self.label('','clipStatus');footer.addWidget(self.status,1);footer.addWidget(self.label('↓ Explorar · Enter Copiar · F1 Atajos','clipMuted'));layout.addLayout(footer)
        self.splitter.addWidget(surface)
        self.detail=QWidget();self.detail.setObjectName('clipDetail');details=QVBoxLayout(self.detail);details.setContentsMargins(20,16,20,16);details.setSpacing(12)
        tools=QHBoxLayout();self.detail_type=self.label('Vista previa','clipMuted');tools.addWidget(self.detail_type,1)
        self.ocr_text=self.button('Texto',self.toggle_ocr_text);self.ocr_text.setIcon(icon('scan-text',16));self.ocr_text.setToolTip('Ver y copiar el texto reconocido');tools.addWidget(self.ocr_text)
        self.open_link=self.icon_button('external-link','Abrir en el navegador',self.open_current);tools.addWidget(self.open_link)
        self.copy_button=CopyButton(lambda:self.copy_selected());self.copy_button.menuRequested.connect(self.copy_menu);tools.addWidget(self.copy_button)
        self.copy_options=self.icon_button('ellipsis','Opciones del elemento',self.detail_menu);tools.addWidget(self.copy_options)
        details.addLayout(tools)
        self.detail_title=self.label('Selecciona un elemento','clipTitle');self.detail_title.setWordWrap(True);details.addWidget(self.detail_title)
        self.stack=QStackedWidget();self.stack.setMinimumHeight(100);details.addWidget(self.stack,1)
        self.text=QPlainTextEdit();self.text.setReadOnly(True);self.text.setAccessibleName('Contenido del clip');self.stack.addWidget(self.text)
        image_page=QWidget();images=QVBoxLayout(image_page);images.setContentsMargins(0,0,0,0);images.setSpacing(8)
        self.image=ZoomCanvas();self.image.setMinimumHeight(90);self.image.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Ignored);images.addWidget(self.image,1)
        self.image_ocr=self.label('','clipMuted');self.image_ocr.setWordWrap(True);self.image_ocr.setTextInteractionFlags(Qt.TextSelectableByMouse);images.addWidget(self.image_ocr);self.stack.addWidget(image_page)
        color_page=QWidget();color_layout=QVBoxLayout(color_page);color_layout.setContentsMargins(0,0,0,0)
        self.swatch=QLabel();self.swatch.setMinimumHeight(70);color_layout.addWidget(self.swatch,1)
        self.color_rows={};self.color_compact=None;self.color_grid=QGridLayout();self.color_grid.setContentsMargins(0,0,0,0);self.color_grid.setSpacing(4)
        for number,name in enumerate(('HEX','RGB','HSL','CMYK'),1):
            row=ColorValueRow(name,number,lambda checked=False,n=name:self.copy_color(n));self.color_rows[name]=row;self.color_grid.addWidget(row,number-1,0)
        color_layout.addLayout(self.color_grid);color_layout.setSpacing(5);color_scroll=QScrollArea();color_scroll.setWidgetResizable(True);color_scroll.setWidget(color_page);self.stack.addWidget(color_scroll)
        self.parts=QListWidget();self.parts.setObjectName('clipParts');self.parts.setDragDropMode(QAbstractItemView.InternalMove);self.parts.setAccessibleName('Elementos del grupo; arrastra para cambiar el orden');self.parts.model().rowsMoved.connect(self.reorder_parts);self.stack.addWidget(self.parts)
        link_page=QWidget();link_layout=QVBoxLayout(link_page);link_layout.setContentsMargins(0,0,0,0);link_layout.setSpacing(10)
        self.link_hero=LinkHero();link_layout.addWidget(self.link_hero,1)
        self.link_title=self.label('','clipLinkTitle');self.link_title.setWordWrap(True);link_layout.addWidget(self.link_title)
        self.link_description=self.label('','clipDescription');self.link_description.setWordWrap(True);self.link_description.setMaximumHeight(58);link_layout.addWidget(self.link_description)
        self.link_address=self.label('','clipMuted');self.link_address.setTextInteractionFlags(Qt.TextSelectableByMouse);self.link_address.setWordWrap(True);link_layout.addWidget(self.link_address);self.stack.addWidget(link_page)
        self.metadata=self.label('','clipMuted');self.metadata.setWordWrap(True);self.metadata.setTextInteractionFlags(Qt.TextSelectableByMouse);details.addWidget(self.metadata)
        self.splitter.addWidget(self.detail);self.splitter.setSizes([300,480]);self.detail.setMinimumHeight(190)
        self.detail_effect=QGraphicsOpacityEffect(self.stack);self.stack.setGraphicsEffect(self.detail_effect)
        self.detail_animation=QVariantAnimation(self);self.detail_animation.setDuration(150);self.detail_animation.setEasingCurve(QEasingCurve.OutCubic);self.detail_animation.valueChanged.connect(self.detail_effect.setOpacity)
        self.toast_timer=QTimer(self);self.toast_timer.setSingleShot(True);self.toast_timer.timeout.connect(self.reset_copy_button)
        self.debounce=QTimer(self);self.debounce.setSingleShot(True);self.debounce.setInterval(80);self.debounce.timeout.connect(lambda:self.refresh(True));self.search.textChanged.connect(lambda:self.debounce.start())
        self.link_timer=QTimer(self);self.link_timer.setSingleShot(True);self.link_timer.setInterval(180);self.link_timer.timeout.connect(self.request_link)
        self.layout_timer=QTimer(self);self.layout_timer.setSingleShot(True);self.layout_timer.timeout.connect(self.fit_panels)
        self.timer=QTimer(self);self.timer.setInterval(900);self.timer.timeout.connect(self.refresh)
        self.shortcuts=[]
        for key,callback in [('Escape',self.escape),('Ctrl+Return',lambda:self.copy_selected(close=True,paste=True)),('Ctrl+C',self.copy_unless_text_selection),('Ctrl+P',lambda:self.toggle_favorite()),('Ctrl+G',self.combine_selected),('Ctrl+F',self.search.setFocus),('Delete',self.delete_selected),('Ctrl+Shift+C',self.copy_menu),('Ctrl+I',self.toggle_ocr_text),('Ctrl+O',self.open_current),('Ctrl+Shift+F',self.filter_menu),('Ctrl+Shift+V',self.toggle_grid),('F1',self.keyboard_menu)]:
            shortcut=QShortcut(QKeySequence(key),self);shortcut.activated.connect(callback);self.shortcuts.append(shortcut)
        for number,key in enumerate(('', 'image','url','favorite'),1):
            shortcut=QShortcut(QKeySequence(f'Ctrl+{number}'),self);shortcut.activated.connect(lambda k=key:self.choose_type(k));self.shortcuts.append(shortcut)
        for number,name in enumerate(('HEX','RGB','HSL','CMYK'),1):
            shortcut=QShortcut(QKeySequence(f'Alt+{number}'),self);shortcut.activated.connect(lambda n=name:self.copy_color(n));self.shortcuts.append(shortcut)
        for delta,key in [(-1,'Alt+Up'),(1,'Alt+Down')]:
            shortcut=QShortcut(QKeySequence(key),self.parts);shortcut.setContext(Qt.WidgetShortcut);shortcut.activated.connect(lambda d=delta:self.move_part(d));self.shortcuts.append(shortcut)
        for widget in [self.search,self.cards,self.cards.viewport(),self.parts]:widget.installEventFilter(self)
        self.setTabOrder(self.search,self.cards);self.setTabOrder(self.cards,self.copy_button);self.setTabOrder(self.copy_button,self.copy_options)
        previous=self.copy_options
        for row in self.color_rows.values():self.setTabOrder(previous,row);previous=row
        self.search.installEventFilter(self);self.refresh_collections();self.refresh(True)
        if self.store.get('clipboard_grid')=='1':self.toggle_grid()
    def color_formats(self,text):
        result=color_formats(text)
        if result:
            color=QColor(result['HEX']);cyan,magenta,yellow,black,alpha=color.getCmykF()
            result['CMYK']=f'cmyk({round(cyan*100)}%, {round(magenta*100)}%, {round(yellow*100)}%, {round(black*100)}%)'
        return result
    def label(self,text='',name=''):
        label=QLabel(text);label.setTextFormat(Qt.PlainText);label.setObjectName(name);return label
    def button(self,title,callback):
        button=MotionButton(title);button.clicked.connect(callback);button.setCursor(Qt.PointingHandCursor);return button
    def icon_button(self,symbol,label,callback):
        button=self.button('',callback);button.setObjectName('clipIcon');button.setFixedSize(32,32);button.setIcon(icon(symbol,17,'glyph'));button.setIconSize(QSize(17,17));button.setToolTip(label);button.setAccessibleName(label);return button
    def present(self):
        if self.isVisible() and not getattr(self,'_motion_exiting',False):self.dismiss();return
        if not self.test:
            try:
                self.source_window=self.owner.source_window if self.owner.isVisible() else __import__('desktop_backend').previous_window()
            except (OSError,subprocess.SubprocessError):self.source_window=''
        self.owner.hide();self.refresh(True)
        screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen();area=screen.availableGeometry()
        self.resize(min(1080,area.width()-48),min(860,area.height()-64));self.move(area.center().x()-self.width()//2,area.top()+14)
        self.show();self.raise_();self.activateWindow();self.search.setFocus()
    def showEvent(self,event):
        super().showEvent(event);self.timer.start();self.layout_timer.start(0)
    def fit_panels(self):
        if self._closing:return
        if not self.grid:self.splitter.setSizes([self.splitter.widget(0).minimumSizeHint().height(),max(190,self.height()-self.splitter.widget(0).minimumSizeHint().height()-10)])
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'color_grid'):self.adapt_color()
    def adapt_color(self):
        compact=self.height()<700
        if compact!=self.color_compact:
            self.color_compact=compact
            while self.color_grid.count():self.color_grid.takeAt(0)
            for index,row in enumerate(self.color_rows.values()):
                row.setMinimumHeight(28 if compact else 32);self.color_grid.addWidget(row,index//2 if compact else index,index%2 if compact else 0)
            self.swatch.setMinimumHeight(32 if compact else 70)
        row=self.current();self.metadata.setVisible(not (compact and row and row['kind']=='color'))
    def hideEvent(self,event):self.timer.stop();self.link_timer.stop();self.layout_timer.stop();super().hideEvent(event)
    def closeEvent(self,event):event.ignore();self.dismiss()
    def paintEvent(self,event):pass
    def eventFilter(self,obj,event):
        if event.type()==QEvent.KeyPress:
            key=event.key();modifiers=event.modifiers()
            if obj==self.search and key==Qt.Key_Down and not modifiers:
                self.cards.setFocus()
                if self.cards.currentRow()<0 and self.cards.count():self.cards.setCurrentRow(0)
                self.cards.scrollToItem(self.cards.currentItem());return True
            if obj in (self.search,self.cards,self.cards.viewport()) and key in (Qt.Key_Return,Qt.Key_Enter) and not modifiers:
                self.copy_selected(close=True);return True
            if obj in (self.cards,self.cards.viewport()):
                if key==Qt.Key_Slash and not modifiers:self.search.setFocus();return True
                if key==Qt.Key_Space and not modifiers:self.toggle_detail();return True
                if key==Qt.Key_Menu or (key==Qt.Key_F10 and modifiers==Qt.ShiftModifier):
                    item=self.cards.currentItem();self.context_menu(self.cards.visualItemRect(item).center() if item else self.cards.rect().center());return True
        return super().eventFilter(obj,event)
    def escape(self):
        if self.search.text():self.search.clear()
        elif len(self._picked)>1:self.cards.clearSelection()
        else:self.dismiss()
    def choose_type(self,key):
        self.favorite=key=='favorite';self.kind='' if self.favorite else key
        for name,button in self.chips.items():button.setChecked(name==key)
        self.refresh(True);reveal_content(self.cards,150)
    def choose_collection(self,*_):
        self.collection=self.collections.currentData();self.refresh(True)
    def refresh_collections(self):
        self.collections.blockSignals(True);self.collections.clear();self.collections.addItem('Colecciones',None)
        for collection in self.library.collections():self.collections.addItem(f"{collection['name']}  {collection['count']}",collection['id'])
        index=self.collections.findData(self.collection);self.collections.setCurrentIndex(max(0,index));self.collections.blockSignals(False)
    def refresh(self,force=False):
        if self._refreshing:return
        self._refreshing=True
        try:
            all_rows=self.store.clips();sources=sorted({r.get('source') for r in all_rows if r.get('source')})
            if [self.sources.itemData(i) for i in range(1,self.sources.count())]!=sources:
                selected=self.sources.currentData();self.sources.blockSignals(True);self.sources.clear();self.sources.addItem('Aplicaciones','')
                for source in sources:self.sources.addItem(source,source)
                self.sources.setCurrentIndex(max(0,self.sources.findData(selected)));self.sources.blockSignals(False)
            rows=self.library.search(self.search.text(),self.kind,self.favorite,self.sources.currentData() or '',self.collection)
            signature=[(r['id'],r['stamp'],r['pinned'],r.get('ocr_done'),r.get('meta'),r.get('ocr')) for r in rows]
            if force or signature!=self._signature:
                self._signature=signature;self.refresh_collections();current=self.current();old=current['id'] if current else None;picked=set(self._picked)
                self.cards.blockSignals(True);self.cards.clear();self.rows=rows
                for row in rows:
                    item=QListWidgetItem();item.setData(Qt.UserRole,row);item.setText(row['title']);item.setToolTip(row['title']);self.cards.addItem(item)
                    if row['id'] in picked:item.setSelected(True)
                index=next((i for i,r in enumerate(rows) if r['id']==old),0)
                if rows:
                    self.cards.setCurrentRow(index,QItemSelectionModel.NoUpdate)
                    if not self.cards.selectedItems():self.cards.item(index).setSelected(True)
                self.cards.blockSignals(False);self.selection_changed();self.update_detail()
            self.empty.setVisible(not rows);self.cards.setVisible(bool(rows));self.empty.setText('No hay coincidencias. Prueba otro filtro o una palabra del texto de la imagen.' if self.search.text() or self.kind or self.collection else 'Tu próxima copia aparecerá aquí.')
            self.heading.setText('Favoritos' if self.favorite else KIND_LABEL.get(self.kind,'Recientes')+(' · '+self.collections.currentText() if self.collection else '')+(' · '+self.sources.currentText() if self.sources.currentData() else ''))
            self.status.setText(f'{len(rows)} elementos'+(' · Captura pausada' if self.owner.paused else ''))
            self.add_collection.setToolTip('Filtros activos' if self.kind or self.collection or self.sources.currentData() else 'Filtrar por tipo, aplicación o colección')
            self.add_collection.setIcon(icon('sliders-horizontal',17,'accent' if self.kind or self.collection or self.sources.currentData() else 'glyph'))
            self.pause.setIcon(icon('play' if self.owner.paused else 'pause',17));self.pause.setToolTip('Reanudar captura' if self.owner.paused else 'Pausar captura')
        finally:self._refreshing=False
    def current(self):
        item=self.cards.currentItem();return item.data(Qt.UserRole) if item else None
    def selected_ids(self):return list(self._picked)
    def selection_changed(self):
        selected=[item.data(Qt.UserRole)['id'] for item in self.cards.selectedItems()]
        self._picked=[ident for ident in self._picked if ident in selected]+[ident for ident in selected if ident not in self._picked]
        self.combine.setVisible(len(self._picked)>1);self.combine.setText(f'Combinar {len(self._picked)} elementos')
        self.copy_button.setEnabled(bool(self._picked));self.copy_options.setEnabled(bool(self._picked));self.update_detail()
    def card_pixmap(self,row):
        key=row['id']
        if key not in self.pixmaps:
            image=QImage.fromData((row.get('thumb') or b'') if row['kind']=='url' else self.store.blob(key) or row.get('thumb') or b'')
            if not image.isNull():self.pixmaps[key]=QPixmap.fromImage(image.scaled(400,300,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            else:return None
            while len(self.pixmaps)>48:self.pixmaps.popitem(last=False)
        self.pixmaps.move_to_end(key);return self.pixmaps[key]
    def update_detail(self):
        if not hasattr(self,'stack'):return
        row=self.current();previous=self.detail_id;self.detail_id=row['id'] if row else None
        if previous!=self.detail_id:
            self.detail_animation.stop()
            if reduced_motion():self.detail_effect.setOpacity(1.)
            else:self.detail_animation.setStartValue(.65);self.detail_animation.setEndValue(1.);self.detail_animation.start()
        changed=previous!=self.detail_id
        if changed:self.ocr_mode=False;self.toast_timer.stop()
        self.copy_button.setEnabled(bool(self._picked));self.copy_options.setEnabled(bool(self._picked))
        self.ocr_text.setVisible(bool(row and row['kind']=='image' and row.get('ocr') and len(self._picked)==1))
        self.open_link.setVisible(bool(row and row['kind']=='url'))
        self.detail_title.setVisible(bool(row and row['kind'] not in ('image','url','color')))
        self.reset_copy_label()
        if not row:
            self.detail_title.setText('Selecciona un elemento');self.detail_type.setText('Vista previa');self.stack.setCurrentIndex(0);self.text.clear();self.metadata.clear();return
        self.adapt_color()
        kind=row['kind'];meta=unpack(row.get('meta'));self.detail_type.setText(KIND_LABEL.get(kind,'Clip'));self.detail_title.setText(row['title'][:160])
        self.metadata.setText((row.get('source') or 'Origen local')+'  ·  '+datetime.datetime.fromtimestamp(row['stamp']).strftime('%d %b, %H:%M')+'  ·  '+(f"{row.get('bytes',0)/1024:.1f} KB" if kind=='image' else f"{len(row['text'])} caracteres" if kind in ('text','url') else f"{meta.get('count',len(meta.get('paths',[])))} elementos" if kind in ('bundle','files') else 'Formatos de color'))
        if kind=='image':
            if self.ocr_mode:
                self.stack.setCurrentIndex(0)
                if self.text.toPlainText()!=row.get('ocr',''):self.text.setPlainText(row.get('ocr',''))
            else:
                self.stack.setCurrentIndex(1)
                if changed or self.image.image.isNull():self.image.set_image(QImage.fromData(self.store.blob(row['id']) or b''))
            status=meta.get('ocr_status')
            if row.get('ocr'):message=f"Texto reconocido · {len(row['ocr']):,} caracteres"
            elif not row.get('ocr_done'):message='Reconociendo texto…'
            elif status=='no disponible':message=meta.get('ocr_error') or 'OCR no disponible · reintenta desde el menú'
            elif status=='protegido':message='Texto excluido por la protección de datos sensibles'
            else:message='No se detectó texto'
            self.image_ocr.setText(message)
        elif kind=='url':
            self.stack.setCurrentIndex(4);self.show_link(row)
            if not self.test:self.link_timer.start()
        elif kind=='color':
            self.stack.setCurrentIndex(2);formats=self.color_formats(row['text']);self.swatch.setStyleSheet('background:'+formats.get('HEX',css('inset'))[:7]+';border-radius:12px;');[button.set_value(formats.get(name,'')) for name,button in self.color_rows.items()]
        elif kind=='bundle':
            self.stack.setCurrentIndex(3);self.parts.blockSignals(True);self.parts.clear()
            for part in self.library.parts(row['id']):
                title=(unpack(part.get('meta')).get('title') or part['text'].split('\n')[0] or KIND_LABEL.get(part['kind'],'Clip'))[:130]
                item=QListWidgetItem(icon(KIND_ICON.get(part['kind'],'file-text')),title);item.setData(Qt.UserRole,part['position']);self.parts.addItem(item)
            self.parts.blockSignals(False)
        else:
            self.stack.setCurrentIndex(0)
            self.text.setPlainText('\n'.join(meta.get('paths',[])) if kind=='files' else row['text'])
    def toast(self,message):
        self.status.setText(message);self.copy_button.setText('Copiado');self.copy_button.setIcon(icon('check',16));self.toast_timer.start(1700)
    def reset_copy_button(self):self.reset_copy_label();self.copy_button.setIcon(icon('copy',16));self.refresh()
    def reset_copy_label(self):
        self.copy_button.setText('Copiar selección' if len(self._picked)>1 else 'Copiar texto' if self.ocr_mode else 'Copiar');self.ocr_text.setText('Imagen' if self.ocr_mode else 'Texto');self.ocr_text.setIcon(icon('image' if self.ocr_mode else 'scan-text',16))
    def copy_unless_text_selection(self):
        focus=QApplication.focusWidget()
        if isinstance(focus,QPlainTextEdit) and focus.textCursor().hasSelection():focus.copy()
        elif isinstance(focus,QLineEdit) and focus.hasSelectedText():focus.copy()
        else:self.copy_selected()
    def copy_selected(self,close=False,paste=False,plain=False,text=None,original=False):
        ids=self.selected_ids()
        if not ids:return
        try:mime=self.library.mime(ids,plain_only=plain)
        except ValueError as error:self.status.setText(str(error));return
        row=self.current()
        if text is None and not original and not plain and self.ocr_mode and row and row['kind']=='image' and len(ids)==1:text=row.get('ocr','')
        if text is not None:
            from PySide6.QtCore import QMimeData
            mime=QMimeData();mime.setText(text)
        self.owner.ignore_clip=True;QApplication.clipboard().setMimeData(mime);QTimer.singleShot(180,lambda:setattr(self.owner,'ignore_clip',False))
        self.toast('Copiado al portapapeles')
        if close or paste:self.hide()
        if paste and self.source_window and not self.test:QTimer.singleShot(150,lambda:self.owner.paste_to(self.source_window))
    def copy_color(self,name):
        row=self.current()
        if row and row['kind']=='color' and len(self.selected_ids())==1:
            value=self.color_formats(row['text']).get(name)
            if value:
                self.copy_selected(text=value)
                if getattr(self,'active_menu',None) and self.active_menu.isVisible():self.active_menu.close()
    def build_copy_menu(self):
        row=self.current();menu=ActionMenu(self)
        if not row:return menu
        if row['kind']=='color' and len(self.selected_ids())==1:
            symbols={'HEX':'code','RGB':'palette','HSL':'sliders-horizontal','CMYK':'layers'}
            for number,(name,value) in enumerate(self.color_formats(row['text']).items(),1):
                action=menu.command(symbols[name],name+'   '+value,lambda checked=False,v=value:self.copy_selected(text=v),f'Alt+{number}');action.setData(name)
        else:
            menu.command(KIND_ICON.get(row['kind'],'copy'),'Contenido original',lambda:self.copy_selected(original=True),'Ctrl+C')
            menu.command('file-text','Texto sin formato',lambda:self.copy_selected(plain=True))
            if row['kind']=='image' and row.get('ocr'):menu.command('scan-text','Texto reconocido',lambda:self.copy_selected(text=row['ocr']))
            if row['kind'] in ('text','url') and len(self.selected_ids())==1:
                transforms=menu.addMenu(icon('file-text',18),'Transformar texto');transforms.setIcon(icon('file-text',18))
                for title,transform in [('MAYÚSCULAS',str.upper),('minúsculas',str.lower),('Tipo título',str.title)]:transforms.addAction(icon('file-text',18),title,lambda checked=False,fn=transform:self.copy_selected(text=fn(row['text'])))
        menu.addSeparator();menu.command('clipboard','Pegar en la aplicación anterior',lambda:self.copy_selected(close=True,paste=True),'Ctrl+Enter');return menu
    def show_menu(self,menu,anchor,keyboard=False):
        animate_popup(menu);menu.popup(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        if keyboard:
            action=next((a for a in menu.actions() if a.isEnabled() and not a.isSeparator()),None)
            if action:menu.setActiveAction(action)
        self.active_menu=menu;menu.aboutToHide.connect(lambda m=menu:self.menu_closed(m))
    def menu_closed(self,menu):
        if getattr(self,'active_menu',None) is menu:self.active_menu=None
        menu.deleteLater()
    def copy_menu(self):
        if self.current():self.show_menu(self.build_copy_menu(),self.copy_button,True)
    def toggle_favorite(self,ident=None):
        row=self.current();ident=ident if isinstance(ident,int) and not isinstance(ident,bool) else row['id'] if row else None
        if ident is None:return
        if not self.library.row(ident):self.refresh(True);return
        if not self.store.pin(ident):self.status.setText('Ya tienes 50 favoritos. Quita uno para añadir otro.');return
        self.refresh(True)
    def toggle_capture(self):self.owner.toggle_capture();self.refresh(True)
    def create_collection(self):
        name,accepted=QInputDialog.getText(self,'Nueva colección','Nombre de la colección')
        if not accepted:return
        try:self.collection=self.library.create_collection(name)
        except ValueError as error:self.status.setText(str(error));return
        self.refresh_collections();self.refresh(True)
    def assign_menu(self):
        menu=ActionMenu(self)
        for collection in self.library.collections():menu.command('folder-open',collection['name'],lambda checked=False,c=collection['id']:self.assign_selected(c))
        if not self.library.collections():menu.addAction('No hay colecciones').setEnabled(False)
        if self.collection:menu.command('x','Quitar de esta colección',self.remove_from_collection)
        menu.addSeparator();menu.command('plus','Nueva colección…',self.create_collection);self.show_menu(menu,self.copy_options,True)
    def assign_selected(self,collection):self.library.assign(collection,self.selected_ids());self.refresh_collections();self.refresh(True)
    def remove_from_collection(self):self.library.remove_member(self.collection,self.selected_ids());self.refresh_collections();self.refresh(True)
    def combine_selected(self):
        try:ident=self.library.combine(self.selected_ids())
        except ValueError as error:self.status.setText(str(error));return
        self.search.clear();self.kind='';self.favorite=False;self.collection=None;self.sources.blockSignals(True);self.sources.setCurrentIndex(0);self.sources.blockSignals(False);self._picked=[ident];self.refresh_collections();self.choose_type('')
        for i in range(self.cards.count()):
            if self.cards.item(i).data(Qt.UserRole)['id']==ident:self.cards.setCurrentRow(i);break
    def reorder_parts(self,*_):
        if self._refreshing:return
        row=self.current()
        if not row or row['kind']!='bundle':return
        order=[self.parts.item(i).data(Qt.UserRole) for i in range(self.parts.count())]
        self.library.reorder(row['id'],order)
        for i in range(self.parts.count()):self.parts.item(i).setData(Qt.UserRole,i)
        self.status.setText('Orden del grupo guardado')
    def show_ocr_text(self):
        row=self.current()
        if row and row['kind']=='image' and row.get('ocr'):
            self.ocr_mode=True;self.text.setPlainText(row['ocr']);self.stack.setCurrentIndex(0);self.reset_copy_label();self.reveal_detail()
    def toggle_ocr_text(self):
        if self.ocr_mode:self.ocr_mode=False;self.update_detail();self.reveal_detail()
        else:self.show_ocr_text()
    def reveal_detail(self):
        self.detail_animation.stop()
        if reduced_motion():self.detail_effect.setOpacity(1.);return
        self.detail_animation.setStartValue(.55);self.detail_animation.setEndValue(1.);self.detail_animation.start()
    def retry_ocr(self):
        row=self.current()
        if not row or row['kind']!='image':return
        meta=unpack(row.get('meta'));meta['ocr_attempts']=0;meta['ocr_retry_after']=0
        import json
        self.store.db.execute('UPDATE clips SET ocr_done=0,meta=? WHERE id=?',(json.dumps(meta),row['id']));self.store.db.commit();self.owner.ocr_priority=row['id'];self.owner.next_ocr();self.refresh(True);self.status.setText('Reconociendo el texto de la imagen…')
    def toggle_grid(self):
        self.grid=not self.grid;self.store.set('clipboard_grid','1' if self.grid else '0');self.cards.setWrapping(self.grid);self.view.setIcon(icon('rows-3' if self.grid else 'layout-grid',17));self.splitter.setSizes([470,310] if self.grid else [300,480]);self.cards.doItemsLayout();reveal_content(self.cards,150)
    def context_menu(self,point):
        item=self.cards.itemAt(point)
        if item and not item.isSelected():self.cards.setCurrentItem(item)
        menu=self.build_detail_menu()
        if len(self._picked)>1:menu.command('layers','Combinar selección',self.combine_selected,'Ctrl+G')
        animate_popup(menu);menu.popup(self.cards.viewport().mapToGlobal(point));self.active_menu=menu;menu.aboutToHide.connect(lambda m=menu:self.menu_closed(m))
        if menu.actions():menu.setActiveAction(menu.actions()[0])
    def rename_group(self):
        row=self.current()
        if not row:return
        name,accepted=QInputDialog.getText(self,'Nombre del grupo','Nombre',text=row['title'])
        if accepted:
            try:self.library.rename(row['id'],name);self.refresh(True)
            except ValueError as error:self.status.setText(str(error))
    def open_current(self):
        row=self.current()
        if not row:return
        if row['kind']=='url' and urlsplit(row['text']).scheme in ('http','https'):QDesktopServices.openUrl(QUrl(row['text']))
        elif row['kind']=='files':
            paths=unpack(row['meta']).get('paths',[])
            if paths:QDesktopServices.openUrl(QUrl.fromLocalFile(paths[0]))
    def delete_selected(self):
        ids=self.selected_ids()
        if not ids:return
        if QMessageBox.question(self,'Eliminar del historial',f'¿Eliminar {len(ids)} elementos del historial? Los archivos originales se conservan.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        for ident in ids:self.store.delete_clip(ident);self.pixmaps.pop(ident,None)
        self.refresh_collections();self.refresh(True)
    def filter_menu(self):
        menu=ActionMenu(self)
        types=menu.addMenu(icon('layers',18),'Tipo de contenido')
        for key,title in [('', 'Todo'),('text','Texto'),('image','Imágenes'),('url','Enlaces'),('color','Colores'),('files','Archivos'),('bundle','Grupos')]:
            action=types.addAction(icon(KIND_ICON.get(key,'layers'),18),title,lambda checked=False,k=key:self.choose_type(k));action.setCheckable(True);action.setChecked(self.kind==key and not self.favorite)
        apps=menu.addMenu(icon('panels-top-left',18),'Aplicación')
        for i in range(self.sources.count()):
            action=apps.addAction(self.sources.itemText(i),lambda checked=False,n=i:self.sources.setCurrentIndex(n));action.setCheckable(True);action.setChecked(i==self.sources.currentIndex())
        collections=menu.addMenu(icon('folder-open',18),'Colección')
        for i in range(self.collections.count()):
            action=collections.addAction('Todas' if i==0 else self.collections.itemText(i),lambda checked=False,n=i:self.collections.setCurrentIndex(n));action.setCheckable(True);action.setChecked(i==self.collections.currentIndex())
        collections.addSeparator();collections.addAction(icon('plus',18),'Nueva colección…',self.create_collection)
        menu.addSeparator();menu.command('x','Quitar filtros',self.clear_filters);self.show_menu(menu,self.add_collection,True)
    def clear_filters(self):
        self.collection=None;self.sources.blockSignals(True);self.sources.setCurrentIndex(0);self.sources.blockSignals(False);self.choose_type('')
    def build_detail_menu(self):
        row=self.current();menu=ActionMenu(self)
        if not row:return menu
        menu.command('star','Quitar favorito' if row.get('pinned') else 'Guardar como favorito',lambda:self.toggle_favorite(),'Ctrl+P')
        if row['kind']=='image':menu.command('scan-text','Volver a reconocer texto',self.retry_ocr)
        if row['kind'] in ('url','files'):menu.command('external-link','Abrir',self.open_current,'Ctrl+O')
        if row['kind']=='url':menu.command('rotate-cw','Actualizar vista previa',self.retry_link)
        formats=self.build_copy_menu();formats.setParent(menu);formats.setTitle('Copiar como');formats.setIcon(icon('copy',18));menu.addMenu(formats)
        menu.command('folder-open','Añadir a colección…',self.assign_menu)
        if row['kind']=='bundle':menu.command('pencil','Renombrar grupo…',self.rename_group)
        menu.addSeparator();menu.command('trash','Eliminar…',self.delete_selected,'Supr');return menu
    def detail_menu(self):
        if self.current():self.show_menu(self.build_detail_menu(),self.copy_options,True)
    def toggle_detail(self):self.detail.setVisible(not self.detail.isVisible())
    def move_part(self,delta):
        index=self.parts.currentRow();target=index+delta
        if index<0 or target<0 or target>=self.parts.count():return
        item=self.parts.takeItem(index);self.parts.insertItem(target,item);self.parts.setCurrentRow(target);self.reorder_parts()
    def keyboard_menu(self):
        menu=ActionMenu(self);menu.section('Navegar')
        menu.command('search','Buscar',self.search.setFocus,'Ctrl+F / /')
        menu.command('arrow-right','Explorar clips',lambda:QTimer.singleShot(0,self.cards.setFocus),'↓ / ← →')
        menu.command('sliders-horizontal','Filtros',self.filter_menu,'Ctrl+Shift+F')
        menu.command('layout-grid','Bandeja o cuadrícula',self.toggle_grid,'Ctrl+Shift+V')
        menu.section('Copiar')
        menu.command('copy','Copiar selección',self.copy_selected,'Ctrl+C')
        menu.command('clipboard','Copiar y cerrar',lambda:self.copy_selected(close=True),'Enter')
        menu.command('chevron-down','Elegir formato',self.copy_menu,'Ctrl+Shift+C')
        if self.current() and self.current()['kind']=='color':
            for number,name in enumerate(('HEX','RGB','HSL','CMYK'),1):menu.command('palette',name,lambda checked=False,n=name:self.copy_color(n),f'Alt+{number}')
        menu.section('Organizar')
        menu.command('star','Favorito',lambda:self.toggle_favorite(),'Ctrl+P');menu.command('layers','Combinar selección',self.combine_selected,'Ctrl+G')
        self.show_menu(menu,self.more,True)
    def show_link(self,row):
        meta=unpack(row.get('meta')).get('link_preview',{});host=urlsplit(row['text']).hostname or row['text']
        status=meta.get('status');pending=status not in ('ready','unavailable')
        self.link_title.setText(meta.get('title') or host)
        description=meta.get('description') or ('Cargando vista previa…' if pending else 'Esta página no publica una vista previa. Puedes abrirla en el navegador.' if status=='unavailable' else '')
        self.link_description.setText(description);self.link_description.setVisible(bool(description))
        self.link_address.setText(row['text']);self.link_hero.set_content(row.get('thumb') or b'',meta.get('site') or host,pending);self.link_hero.setVisible(bool(row.get('thumb')) or pending)
    def request_link(self):
        if self._closing or self.link_job or not self.isVisible():return
        row=self.current()
        if not row or row['kind']!='url':return
        old=unpack(row.get('meta')).get('link_preview',{})
        if old and time.time()-old.get('stamp',0)<(604800 if old.get('status')=='ready' else 600):return
        job=LinkPreviewJob(row['id'],row['text']);self.link_job=job;job.ready.connect(self.link_ready);job.finished.connect(self.link_finished);job.start()
    def link_ready(self,ident,url,preview,image):
        row=self.library.row(ident)
        if not row or row['kind']!='url' or row['text']!=url:return
        meta=unpack(row.get('meta'));meta['link_preview']=preview
        if preview.get('title'):meta['title']=preview['title']
        self.store.db.execute('UPDATE clips SET meta=?,thumb=? WHERE id=?',(json.dumps(meta),image,ident));self.store.db.commit();self.pixmaps.pop(ident,None);self.refresh(True)
        if self.detail_id==ident:self.reveal_detail()
    def link_finished(self):
        job=self.link_job;self.link_job=None
        if job:job.deleteLater()
        if not self._closing and not self.test:self.link_timer.start()
    def retry_link(self):
        row=self.current()
        if not row or row['kind']!='url':return
        meta=unpack(row.get('meta'));meta.pop('link_preview',None)
        self.store.db.execute('UPDATE clips SET meta=? WHERE id=?',(json.dumps(meta),row['id']));self.store.db.commit();self.refresh(True)
        if not self.test:self.link_timer.start()
    def history_menu(self):
        menu=ActionMenu(self);menu.command('play' if self.owner.paused else 'pause','Reanudar captura' if self.owner.paused else 'Pausar captura',self.toggle_capture);menu.command('panels-top-left','Mostrar u ocultar detalle',self.toggle_detail,'Espacio')
        menu.command('keyboard','Atajos del teclado',self.keyboard_menu,'F1');menu.addSeparator();menu.command('folder-open','Eliminar colección actual…',self.delete_collection).setEnabled(bool(self.collection));menu.command('trash','Borrar historial…',self.clear_history);self.show_menu(menu,self.more,True)
    def delete_collection(self):
        if self.collection and QMessageBox.question(self,'Eliminar colección','¿Eliminar la colección? Sus clips permanecerán en el historial.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            self.library.delete_collection(self.collection);self.collection=None;self.refresh_collections();self.refresh(True)
    def clear_history(self):
        if QMessageBox.question(self,'Borrar historial','¿Eliminar todo el historial local, incluidos favoritos y grupos?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            self.store.clear_clips();self.pixmaps.clear();self.refresh_collections();self.refresh(True)
    def shutdown_jobs(self):
        self._closing=True;self.timer.stop();self.link_timer.stop();self.layout_timer.stop()
        if self.link_job:
            self.link_job.requestInterruption();self.link_job.wait()


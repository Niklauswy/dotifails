"""Órbita's complete desktop settings surface."""
import copy
import json
import os
import re
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QPointF,QSize,QThread,Signal,QTimer
from PySide6.QtGui import QColor,QPainter,QPen,QPixmap,QImageReader,QIcon,QFont,QKeySequence,QShortcut
from PySide6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QGridLayout,QLineEdit,QLabel,QListWidget,QListWidgetItem,QStackedWidget,QComboBox,QCheckBox,QSpinBox,QDoubleSpinBox,QPushButton,QScrollArea,QAbstractItemView,QTableWidget,QTableWidgetItem,QHeaderView,QFileDialog,QDialog,QDialogButtonBox,QMessageBox,QInputDialog,QPlainTextEdit,QFontComboBox)
from desktop_common import Surface,button,text_label,open_vim,launch
from settings_window import SettingsWindow as LegacySettingsWindow,ShortcutEditor
from settings_data import DesktopSettings,ShortcutFile,SCHEMA,canonical
from settings_shortcuts import expanded_rows,change_binding,application_shortcuts
from environment_settings import (ROOT,EnvironmentSettings,DisplayTrial,display_inventory,display_plan,BAR_MODULES,ROTATIONS,run)
from icons import icon

class Job(QThread):
    ready=Signal(object)
    progress=Signal(object)
    failed=Signal(str)
    def __init__(self,fn,parent,streaming=False):super().__init__(parent);self.fn=fn;self.streaming=streaming
    def run(self):
        try:self.ready.emit(self.fn(self.progress.emit) if self.streaming else self.fn())
        except Exception as exc:self.failed.emit(str(exc))

class DisplayCanvas(QWidget):
    selected=Signal(str)
    changed=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.setMinimumHeight(210);self.setMaximumHeight(250);self.plan=[];self.current='';self.rects={};self.drag=None
    def geometry_for(self,p):
        try:w,h=map(int,p['mode'].split('x'))
        except (ValueError,KeyError):w,h=1920,1080
        return (h,w) if p['rotation'] in ('left','right') else (w,h)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing);painter.setPen(Qt.NoPen);painter.setBrush(QColor('#191B24'));painter.drawRoundedRect(self.rect(),12,12)
        active=[p for p in self.plan if p['enabled']];self.rects={}
        if not active:painter.setPen(QColor('#979BAD'));painter.drawText(self.rect(),Qt.AlignCenter,'Detectando pantallas…');return
        minx=min(p['x'] for p in active);miny=min(p['y'] for p in active)
        maxx=max(p['x']+self.geometry_for(p)[0] for p in active);maxy=max(p['y']+self.geometry_for(p)[1] for p in active)
        self.scale=min((self.width()-60)/max(1,maxx-minx),(self.height()-54)/max(1,maxy-miny))
        ox=(self.width()-(maxx-minx)*self.scale)/2-minx*self.scale;oy=(self.height()-(maxy-miny)*self.scale)/2-miny*self.scale
        for n,p in enumerate(active):
            w,h=self.geometry_for(p);r=QRectF(ox+p['x']*self.scale,oy+p['y']*self.scale,w*self.scale,h*self.scale).adjusted(3,3,-3,-3);self.rects[p['name']]=r
            chosen=p['name']==self.current;painter.setPen(QPen(QColor('#B9AEDC' if chosen else '#52586C'),2 if chosen else 1));painter.setBrush(QColor('#363144' if chosen else '#242833'));painter.drawRoundedRect(r,8,8)
            painter.setPen(QColor('#E8EAF0'));painter.setFont(QFont('Inter',11,QFont.DemiBold));painter.drawText(r.adjusted(4,0,-4,-12),Qt.AlignCenter,f"{n+1}  {p['name']}");painter.setFont(QFont('Inter',9));painter.setPen(QColor('#A7ACBC'));painter.drawText(r.adjusted(2,30,-2,0),Qt.AlignCenter,'Principal' if p['primary'] else p['mode'])
    def mousePressEvent(self,e):
        if e.button()!=Qt.LeftButton:return
        for name,r in reversed(list(self.rects.items())):
            if r.contains(e.position()):
                self.current=name;self.selected.emit(name);p=next(p for p in self.plan if p['name']==name);self.drag=(e.position(),p['x'],p['y'],self.scale);self.update();break
    def mouseMoveEvent(self,e):
        if self.drag and e.buttons()&Qt.LeftButton:
            start,x,y,scale=self.drag;p=next(p for p in self.plan if p['name']==self.current);delta=e.position()-start;p['x']=round((x+delta.x()/scale)/16)*16;p['y']=round((y+delta.y()/scale)/16)*16;self.update()
    def mouseReleaseEvent(self,e):
        if self.drag:
            self.drag=None;active=[p for p in self.plan if p['enabled']];x=min(p['x'] for p in active);y=min(p['y'] for p in active)
            for p in active:p['x']-=min(0,x);p['y']-=min(0,y)
            self.changed.emit();self.update()

class SettingsHub(LegacySettingsWindow):
    def __init__(self,test=False,home=None):
        Surface.__init__(self,'Ajustes del escritorio','Tu espacio, conectado. Ventanas · pantallas · herramientas',1120,790)
        self.setMinimumSize(920,620);self.test=test;self.jobs=[];self.inventory=[];self.display_draft=[];self.trial=None;self.widgets={};self.rules=[];self.extra_shortcuts=[];self.extra_loaded=False;self.routes={};self.page_titles={};self.component_controls={}
        self.env=EnvironmentSettings(home);self.backend=DesktopSettings(home);self.shortcuts=ShortcutFile(Path(home)/'.config/sxhkd/sxhkdrc' if home else None);self.rules=copy.deepcopy(self.backend.saved.get('rules',[]))
        self.setStyleSheet(self.styleSheet()+'''QListWidget#navigation::item {padding:8px 10px;margin:1px 0;} QListWidget#navigation::item:selected {background:#343242;color:#ECE8F8;} QLabel#section-note {color:#999DAC;font-size:12px;} QTableWidget::item {padding:8px;}''')
        middle=QHBoxLayout();middle.setSpacing(24);sidebar=QVBoxLayout();sidebar.setSpacing(10);self.nav_search=QLineEdit();self.nav_search.setPlaceholderText('Buscar ajuste…');self.nav_search.setFixedWidth(190);sidebar.addWidget(self.nav_search);self.nav=QListWidget();self.nav.setObjectName('navigation');self.nav.setFixedWidth(190);self.nav.setIconSize(QSize(18,18));self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);sidebar.addWidget(self.nav,1);middle.addLayout(sidebar);self.pages=QStackedWidget();middle.addWidget(self.pages,1);self.outer.addLayout(middle,1)
        builders=[('home','Resumen','settings',self.build_home),('displays','Pantallas','monitor',self.build_displays),('workspaces','Escritorios','panels-top-left',self.build_workspaces),('wallpaper','Fondo de pantalla','image',self.build_wallpaper),('bar','Barra superior','sliders-horizontal',self.build_bar),('appearance','Ventanas','palette',lambda:self.build_config(False)),('behavior','Comportamiento','mouse-pointer-2',lambda:self.build_config(True)),('shortcuts','Todos los atajos','keyboard',self.build_shortcuts),('rules','Reglas de ventanas','panels-top-left',self.build_rules),('effects','Efectos y animaciones','sliders-horizontal',lambda:self.build_component('effects')),('terminal','Terminal','terminal',lambda:self.build_component('terminal')),('notifications','Notificaciones','bell',lambda:self.build_component('notifications')),('startup','Inicio y aplicaciones','circle-play',self.build_startup),('files','Archivos y copias','files',self.build_files)]
        for key,title,symbol,build in builders:
            self.routes[key]=self.pages.count();self.page_titles[key]=title;self.nav.addItem(QListWidgetItem(icon(symbol),title));build()
        footer=QHBoxLayout();self.status=text_label('Elige una sección para personalizar tu escritorio.','subtitle');footer.addWidget(self.status,1);footer.addWidget(button('Recargar',self.reload,symbol='refresh-cw'));self.apply_button=button('Aplicar cambios',self.apply,'primary',symbol='check');footer.addWidget(self.apply_button);self.outer.addLayout(footer)
        self.nav.currentRowChanged.connect(self.select_page);self.nav_search.textChanged.connect(self.filter_navigation);QShortcut(QKeySequence('Ctrl+F'),self).activated.connect(self.nav_search.setFocus);QShortcut(QKeySequence('Ctrl+Return'),self).activated.connect(self.apply)
        self.load_values();self.nav.setCurrentRow(0);self.start_job(lambda:display_inventory(self.env.runner),self.receive_displays)
        QTimer.singleShot(50,self,self.refresh_startup)

    def start_job(self,fn,callback,progress=None):
        job=Job(fn,self,progress is not None);self.jobs.append(job);job.ready.connect(callback);job.failed.connect(self.report_error);job.finished.connect(lambda j=job:self.finish_job(j))
        if progress:job.progress.connect(progress)
        job.start();return job
    def finish_job(self,job):
        if job in self.jobs:self.jobs.remove(job)
        job.deleteLater()
    def report_error(self,message):
        if hasattr(self,'status'):self.status.setText(message[:260]);self.status.setStyleSheet('color:#EDAAA7')
    def success(self,message):self.status.setStyleSheet('');self.status.setText(message);self.render_backups()
    def go(self,key):self.nav.setCurrentRow(self.routes[key])
    def section(self):return next((key for key,index in self.routes.items() if index==self.pages.currentIndex()),'home')
    def select_page(self,index):
        self.pages.setCurrentIndex(index);key=self.section();self.apply_button.setVisible(key in ('displays','wallpaper','bar','appearance','behavior','rules','effects','terminal','notifications'));self.apply_button.setText('Probar distribución' if key=='displays' else 'Aplicar cambios')
        if key=='shortcuts' and not self.extra_loaded:
            self.extra_loaded=True;self.start_job(lambda:application_shortcuts(home=self.env.home),self.receive_shortcuts)
        elif key=='workspaces':self.refresh_workspaces()
        elif key=='wallpaper' and not self.gallery.count():self.load_gallery()
    def filter_navigation(self,text):
        words={'displays':'monitor resolución frecuencia posición principal','bar':'polybar bandeja módulos transparencia','shortcuts':'sxhkd teclas grabar','effects':'picom sombra blur desenfoque velocidad','wallpaper':'wallpaper imagen fondo','appearance':'bspwm espacios bordes','terminal':'ghostty fuente colores','notifications':'dunst avisos'}
        for key,index in self.routes.items():self.nav.item(index).setHidden(text.casefold() not in (self.page_titles[key]+' '+words.get(key,'')).casefold())
    def page_heading(self,layout,title,note):layout.addWidget(text_label(title,'title'));layout.addWidget(text_label(note,'subtitle'))
    def scroll_form(self,layout):
        scroll=QScrollArea();scroll.setWidgetResizable(True);holder=QWidget();holder.setObjectName('page');form=QFormLayout(holder);form.setContentsMargins(0,8,12,8);form.setVerticalSpacing(12);scroll.setWidget(holder);layout.addWidget(scroll,1);return form

    def build_home(self):
        layout=self.page();self.page_heading(layout,'Todo tu escritorio, en un lugar','Configura cada parte del entorno con vistas previas, acciones directas y copias de seguridad.');grid=QGridLayout();grid.setSpacing(12)
        entries=[('displays','Pantallas y posición','Resolución, frecuencia, rotación y principal','monitor'),('wallpaper','Tu fondo de pantalla','Biblioteca de imágenes y fondos por monitor','image'),('shortcuts','Todos tus atajos','Buscar, grabar y editar combinaciones','keyboard'),('bar','La barra a tu medida','Pantallas, módulos, colores y transparencia','sliders-horizontal'),('effects','Movimiento y profundidad','Animaciones, sombras y desenfoque','sliders-horizontal'),('terminal','Tu terminal','Fuente, colores, márgenes y transparencia','terminal')]
        for i,(key,title,note,symbol) in enumerate(entries):
            b=button(title+'\n'+note,lambda k=key:self.go(k),symbol=symbol);b.setMinimumHeight(86);b.setStyleSheet('QPushButton {text-align:left;padding:16px;background:#242630;border:1px solid #363947;border-radius:10px;} QPushButton:hover {background:#2E3040;border-color:#6A6482;}');grid.addWidget(b,i//2,i%2)
        layout.addLayout(grid);layout.addWidget(text_label('También en Órbita','subtitle'));links=QHBoxLayout()
        for title,mode,symbol in [('Conexiones','network','wifi'),('Sonido','audio','volume-2'),('Sesión','power','power')]:links.addWidget(button(title,lambda m=mode:launch([str(self.env.home/'.local/bin/orbit'),m]),symbol=symbol))
        layout.addLayout(links);self.overview=text_label('BSPWM · sxhkd · Polybar · Picom · Ghostty · Dunst','subtitle');layout.addWidget(self.overview);layout.addStretch()

    def build_displays(self):
        layout=self.page();row=QHBoxLayout();row.addWidget(text_label('Ordena tus pantallas','title'),1);row.addWidget(button('Detectar',lambda:self.start_job(lambda:display_inventory(self.env.runner),self.receive_displays),symbol='refresh-cw'));layout.addLayout(row);layout.addWidget(text_label('Arrastra las pantallas o elige una posición exacta. Los cambios se prueban antes de guardarse.','subtitle'))
        self.canvas=DisplayCanvas();self.canvas.selected.connect(self.select_display);self.canvas.changed.connect(self.display_dragged);layout.addWidget(self.canvas)
        self.output_combo=QComboBox();self.output_combo.currentIndexChanged.connect(lambda:self.load_display_controls());layout.addWidget(self.output_combo)
        grid=QGridLayout();self.output_enabled=QCheckBox('Pantalla encendida');self.output_primary=QCheckBox('Principal');grid.addWidget(self.output_enabled,0,0);grid.addWidget(self.output_primary,0,1)
        self.output_mode=QComboBox();self.output_rate=QComboBox();self.output_rotation=QComboBox()
        for name,label in [('normal','Normal'),('left','90° izquierda'),('right','90° derecha'),('inverted','180°')]:self.output_rotation.addItem(label,name)
        self.output_x=QSpinBox();self.output_y=QSpinBox()
        for spin in (self.output_x,self.output_y):spin.setRange(0,16384);spin.setSuffix(' px')
        for i,(title,widget) in enumerate([('Resolución',self.output_mode),('Frecuencia',self.output_rate),('Rotación',self.output_rotation),('Posición X',self.output_x),('Posición Y',self.output_y)]):grid.addWidget(text_label(title,'subtitle'),1+(i//3)*2,i%3);grid.addWidget(widget,2+(i//3)*2,i%3)
        layout.addLayout(grid);position=QHBoxLayout();self.relative_to=QComboBox();position.addWidget(text_label('Respecto a','subtitle'));position.addWidget(self.relative_to,1)
        for label,direction in [('←','left'),('→','right'),('↑','above'),('↓','below'),('Duplicar','mirror')]:position.addWidget(button(label,lambda d=direction:self.place_display(d)))
        layout.addLayout(position);layout.addStretch();self.output_mode.currentIndexChanged.connect(self.change_resolution)
        for c in (self.output_rate,self.output_rotation):c.currentIndexChanged.connect(self.store_display_controls)
        for c in (self.output_x,self.output_y):c.valueChanged.connect(self.store_display_controls)
        self.output_enabled.toggled.connect(self.store_display_controls);self.output_primary.toggled.connect(self.store_display_controls)

    def receive_displays(self,outputs):
        self.inventory=outputs;self.display_draft=display_plan(outputs);self.canvas.plan=self.display_draft;self.output_combo.blockSignals(True);self.output_combo.clear()
        for p in self.display_draft:self.output_combo.addItem(p['name'],p['name'])
        self.output_combo.blockSignals(False);self.load_display_controls();self.refresh_bar_monitors();self.wallpaper_target.clear();self.wallpaper_target.addItem('Todas las pantallas','')
        for p in self.display_draft:self.wallpaper_target.addItem(p['name'],p['name'])
        self.overview.setText(f"{len(self.display_draft)} pantallas conectadas · {len(expanded_rows(self.shortcuts))} atajos globales · Preferencias locales")
    def select_display(self,name):self.output_combo.setCurrentIndex(self.output_combo.findData(name))
    def current_display(self):return next((p for p in self.display_draft if p['name']==self.output_combo.currentData()),None)
    def load_display_controls(self):
        p=self.current_display()
        if not p:return
        self.loading_display=True
        self.output_enabled.setChecked(p['enabled']);self.output_primary.setChecked(p['primary']);self.output_x.setValue(p['x']);self.output_y.setValue(p['y']);self.output_rotation.setCurrentIndex(self.output_rotation.findData(p['rotation']));self.output_mode.clear()
        original=next(o for o in self.inventory if o['name']==p['name'])
        for mode in original['modes']:self.output_mode.addItem(mode['name'],mode['name'])
        self.output_mode.setCurrentIndex(self.output_mode.findData(p['mode']));self.fill_rates(p['mode'],p['rate']);self.relative_to.clear()
        for other in self.display_draft:
            if other['name']!=p['name'] and other['enabled']:self.relative_to.addItem(other['name'],other['name'])
        self.canvas.current=p['name'];self.canvas.update();self.loading_display=False
    def fill_rates(self,mode,selected=''):
        self.output_rate.clear();p=self.current_display()
        if not p:return
        original=next(o for o in self.inventory if o['name']==p['name'])
        for m in original['modes']:
            if m['name']==mode:
                for rate in m['rates']:self.output_rate.addItem(rate+' Hz',rate)
        i=self.output_rate.findData(selected);self.output_rate.setCurrentIndex(max(0,i))
    def change_resolution(self):
        if getattr(self,'loading_display',False):return
        self.loading_display=True;self.fill_rates(self.output_mode.currentData());self.loading_display=False;self.store_display_controls()
    def store_display_controls(self,*_):
        if getattr(self,'loading_display',False):return
        p=self.current_display()
        if not p:return
        p.update(enabled=self.output_enabled.isChecked(),primary=self.output_primary.isChecked(),mode=self.output_mode.currentData(),rate=self.output_rate.currentData(),rotation=self.output_rotation.currentData(),x=self.output_x.value(),y=self.output_y.value())
        if p['primary']:
            for other in self.display_draft:
                if other is not p:other['primary']=False
        self.canvas.update()
    def display_dragged(self):self.load_display_controls();self.status.setText('Posición preparada. Pulsa Probar distribución para verla en tus pantallas.')
    def place_display(self,direction):
        p=self.current_display();other=next((p for p in self.display_draft if p['name']==self.relative_to.currentData()),None)
        if not p or not other:return
        w,h=self.canvas.geometry_for(p);ow,oh=self.canvas.geometry_for(other);p['x']=other['x'];p['y']=other['y']
        if direction=='right':p['x']+=ow
        elif direction=='left':p['x']-=w
        elif direction=='above':p['y']-=h
        elif direction=='below':p['y']+=oh
        active=[o for o in self.display_draft if o['enabled']];x=min(o['x'] for o in active);y=min(o['y'] for o in active)
        for o in active:o['x']-=min(0,x);o['y']-=min(0,y)
        self.display_dragged()
    def try_displays(self):
        try:self.trial=DisplayTrial(self.env,self.display_draft)
        except Exception as exc:self.report_error(str(exc));return
        QApplication.processEvents();self.present()
        dialog=QDialog(self);dialog.setWindowTitle('¿Conservar esta distribución?');dialog.resize(420,200);layout=QVBoxLayout(dialog);label=text_label('','title');layout.addWidget(label);layout.addWidget(text_label('Si no confirmas, volveremos a la distribución anterior.','subtitle'));row=QHBoxLayout();row.addWidget(button('Volver',dialog.reject));row.addWidget(button('Conservar',dialog.accept,'primary'));layout.addLayout(row);timer=QTimer(dialog);remaining=[15]
        def tick():
            label.setText(f'¿Se ve bien? · {remaining[0]} s');remaining[0]-=1
            if remaining[0]<0:dialog.reject()
        tick();timer.timeout.connect(tick);timer.start(1000)
        try:
            if dialog.exec()==QDialog.Accepted:self.trial.accept();self.success('Distribución confirmada y guardada para esta combinación de pantallas.');self.refresh_after_display()
            else:self.trial.reject();self.success('Se recuperó la distribución anterior.')
        except Exception as exc:self.report_error(str(exc))
        finally:
            if self.trial and not self.trial.done:self.trial.reject()
            self.trial=None;self.start_job(lambda:display_inventory(self.env.runner),self.receive_displays)
    def refresh_after_display(self):
        def work():
            if self.env.section('wallpaper').get('default'):
                from environment_settings import render_wallpaper
                render_wallpaper(self.env.wallpaper_values(),display_inventory(self.env.runner),self.env.home,self.env.runner)
            self.env.runner([str(ROOT/'desktop-bar')])
        self.start_job(work,lambda _:None)

    def build_wallpaper(self):
        layout=self.page();self.page_heading(layout,'Un fondo para cada pantalla','Elige una imagen de tu biblioteca o añade una carpeta. Los originales se conservan.');row=QHBoxLayout();self.wallpaper_target=QComboBox();self.wallpaper_target.addItem('Todas las pantallas','');self.wallpaper_mode=QComboBox()
        for label,value in [('Rellenar','fill'),('Ajustar','fit'),('Estirar','stretch'),('Centrar','center')]:self.wallpaper_mode.addItem(label,value)
        row.addWidget(self.wallpaper_target,1);row.addWidget(self.wallpaper_mode);row.addWidget(button('Elegir imagen',self.browse_wallpaper,symbol='image'));layout.addLayout(row);self.wallpaper_preview=QLabel('Selecciona una imagen');self.wallpaper_preview.setAlignment(Qt.AlignCenter);self.wallpaper_preview.setFixedHeight(185);self.wallpaper_preview.setStyleSheet('background:#191B24;border:1px solid #343845;border-radius:10px');layout.addWidget(self.wallpaper_preview);self.wallpaper_name=text_label('','subtitle');layout.addWidget(self.wallpaper_name)
        tools=QHBoxLayout();self.wallpaper_search=QLineEdit();self.wallpaper_search.setPlaceholderText('Buscar imagen…');self.wallpaper_search.textChanged.connect(self.filter_gallery);tools.addWidget(self.wallpaper_search,1);tools.addWidget(button('Añadir carpeta',self.add_wallpaper_folder,symbol='folder-open'));layout.addLayout(tools)
        self.gallery=QListWidget();self.gallery.setViewMode(QListWidget.IconMode);self.gallery.setResizeMode(QListWidget.Adjust);self.gallery.setMovement(QListWidget.Static);self.gallery.setIconSize(QSize(156,88));self.gallery.setGridSize(QSize(182,126));self.gallery.setWordWrap(False);self.gallery.itemClicked.connect(lambda item:self.select_wallpaper(item.data(Qt.UserRole)));layout.addWidget(self.gallery,1)
        self.gallery_info=text_label('','subtitle');layout.addWidget(self.gallery_info);self.gallery_generation=0
        self.wallpaper_values=self.env.wallpaper_values();self.wallpaper_selected=self.wallpaper_values.get('default','');self.wallpaper_mode.setCurrentIndex(max(0,self.wallpaper_mode.findData(self.wallpaper_values.get('mode','fill'))))
        self.wallpaper_target.currentIndexChanged.connect(self.wallpaper_target_changed)
        if self.wallpaper_selected:QTimer.singleShot(10,self,lambda:self.select_wallpaper(self.wallpaper_selected))
    def browse_wallpaper(self):
        path,_=QFileDialog.getOpenFileName(self,'Elegir fondo',str(self.env.home/'Pictures'),'Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)')
        if path:self.select_wallpaper(path)
    def wallpaper_target_changed(self):
        selected=self.wallpaper_values.get('monitors',{}).get(self.wallpaper_target.currentData(),{})
        path=selected.get('path') or self.wallpaper_values.get('default','')
        self.wallpaper_mode.setCurrentIndex(max(0,self.wallpaper_mode.findData(selected.get('mode') or self.wallpaper_values.get('mode','fill'))))
        if path:self.select_wallpaper(path)
    def add_wallpaper_folder(self):
        path=QFileDialog.getExistingDirectory(self,'Añadir carpeta',str(self.env.home/'Pictures'))
        if path:
            folders=self.wallpaper_values.setdefault('folders',[])
            if path not in folders:folders.append(path)
            try:self.env.save_section('wallpaper',copy.deepcopy(self.wallpaper_values))
            except Exception as exc:self.report_error(str(exc));return
            self.load_gallery()
    def load_gallery(self):
        self.gallery_generation+=1;generation=self.gallery_generation;self.gallery.clear();self.gallery_info.setText('Cargando biblioteca…')
        folders=[self.env.home/'.local/share/backgrounds',Path('/usr/share/backgrounds'),self.env.home/'Pictures/Wallpapers',self.env.home/'Pictures/wallpapers',self.env.home/'Wallpapers',*map(Path,self.wallpaper_values.get('folders',[]))]
        def collect(emit):
            count=0;batch=[];seen=set()
            for folder in folders:
                if not folder.is_dir():continue
                for directory,subdirs,files in os.walk(folder):
                    if len(Path(directory).relative_to(folder).parts)>=2:subdirs[:]=[]
                    if count>=400:break
                    for filename in files:
                        if generation!=self.gallery_generation:return count
                        path=Path(directory)/filename
                        if count>=400:break
                        if path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.bmp') or path in seen:continue
                        seen.add(path);reader=QImageReader(str(path));reader.setAutoTransform(True);reader.setScaledSize(reader.size().scaled(156,88,Qt.KeepAspectRatio));image=reader.read()
                        if not image.isNull():batch.append((str(path),image));count+=1
                        if len(batch)>=8:emit(batch);batch=[]
            if batch:emit(batch)
            return count
        def complete(count):
            if generation==self.gallery_generation:self.gallery_info.setText(f'{count} imágenes en tu biblioteca' if count else 'Añade una carpeta para encontrar más fondos.')
        self.start_job(collect,complete,lambda rows:self.receive_gallery(rows) if generation==self.gallery_generation else None)
    def receive_gallery(self,rows):
        for path,image in rows:
            item=QListWidgetItem(QIcon(QPixmap.fromImage(image)),Path(path).stem);item.setData(Qt.UserRole,path);item.setToolTip(path);self.gallery.addItem(item)
        self.gallery_info.setText(f'{self.gallery.count()} imágenes · cargando…')
        self.filter_gallery()
    def filter_gallery(self,*_):
        q=self.wallpaper_search.text().casefold()
        for i in range(self.gallery.count()):self.gallery.item(i).setHidden(q not in self.gallery.item(i).text().casefold())
    def select_wallpaper(self,path):
        reader=QImageReader(path);reader.setAutoTransform(True);reader.setScaledSize(reader.size().scaled(720,185,Qt.KeepAspectRatio));image=reader.read()
        if image.isNull():self.report_error('No se pudo leer esta imagen.');return
        self.wallpaper_selected=path;self.wallpaper_preview.setPixmap(QPixmap.fromImage(image));self.wallpaper_name.setText(Path(path).name+' · '+str(Path(path).parent))
    def apply_wallpaper(self):
        values=copy.deepcopy(self.wallpaper_values);target=self.wallpaper_target.currentData();mode=self.wallpaper_mode.currentData()
        if target:values.setdefault('monitors',{})[target]={'path':self.wallpaper_selected,'mode':mode}
        else:values.update(default=self.wallpaper_selected,mode=mode,monitors={})
        self.apply_button.setEnabled(False);job=self.start_job(lambda:self.env.apply_wallpaper(values),lambda _:(setattr(self,'wallpaper_values',values),self.success('Fondo aplicado y guardado.')));job.finished.connect(lambda:self.apply_button.setEnabled(True))

    def build_bar(self):
        layout=self.page();self.page_heading(layout,'Una barra que encaja contigo','Elige dónde aparece, ordena los módulos y ajusta el acabado.');form=self.scroll_form(layout)
        self.bar_screens=QWidget();self.bar_screens_layout=QHBoxLayout(self.bar_screens);self.bar_screens_layout.setContentsMargins(0,0,0,0);self.bar_checks={};form.addRow('Mostrar en',self.bar_screens)
        self.bar_tray=QComboBox();form.addRow('Bandeja de aplicaciones',self.bar_tray);self.bar_controls={}
        values=self.env.bar_values()
        for key,label,lo,hi,suffix in [('height','Altura',24,64,' px'),('offset','Separación superior',0,60,' px'),('radius','Esquinas',0,30,' px'),('opacity','Opacidad',10,100,' %')]:
            control=QSpinBox();control.setRange(lo,hi);control.setSuffix(suffix);control.setValue(values[key]);self.bar_controls[key]=control;form.addRow(label,control)
        for key,label in [('background','Fondo'),('foreground','Texto e iconos'),('accent','Acento')]:
            control=QLineEdit(values[key]);self.bar_controls[key]=control;row=QHBoxLayout();row.addWidget(control,1);row.addWidget(button('Elegir',lambda c=control:self.choose_color(c),symbol='palette'));form.addRow(label,row)
        module_holder=QWidget();grid=QGridLayout(module_holder);grid.setContentsMargins(0,0,0,0);self.bar_lists={}
        for column,(side,title) in enumerate([('left','Izquierda'),('center','Centro'),('right','Derecha')]):
            grid.addWidget(text_label(title,'subtitle'),0,column);listing=QListWidget();listing.setMinimumHeight(160);listing.setDragDropMode(QAbstractItemView.InternalMove);self.bar_lists[side]=listing;grid.addWidget(listing,1,column)
            for name in values[side]:self.add_bar_item(side,name)
            row=QHBoxLayout();row.addWidget(button('Añadir',lambda s=side:self.choose_bar_module(s),symbol='plus'));row.addWidget(button('Quitar',lambda s=side:self.remove_bar_module(s),symbol='x'));grid.addLayout(row,2,column)
        form.addRow('Módulos · arrastra para ordenar',module_holder)
        form.addRow(text_label('La bandeja se muestra en una sola pantalla. Puedes mantener la barra oculta en el portátil.','subtitle'))

    def add_bar_item(self,side,name):
        item=QListWidgetItem(BAR_MODULES.get(name,name));item.setData(Qt.UserRole,name);self.bar_lists[side].addItem(item)
    def choose_bar_module(self,side):
        existing=[self.bar_lists[side].item(i).data(Qt.UserRole) for i in range(self.bar_lists[side].count())];names=[name for name in BAR_MODULES if name not in existing and (side=='right' or name!='tray')]
        if not names:return
        label,ok=QInputDialog.getItem(self,'Añadir módulo','Módulo',[BAR_MODULES[n] for n in names],0,False)
        if ok:self.add_bar_item(side,names[[BAR_MODULES[n] for n in names].index(label)])
    def remove_bar_module(self,side):
        listing=self.bar_lists[side]
        if listing.currentRow()>=0:listing.takeItem(listing.currentRow())
    def refresh_bar_monitors(self):
        values=self.env.bar_values()
        while self.bar_screens_layout.count():
            item=self.bar_screens_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.bar_checks={};self.bar_tray.clear();self.bar_tray.addItem('Automática','')
        connected=[o for o in self.inventory if o['connected']]
        for output in connected:
            name=output['name'];control=QCheckBox(name);control.setChecked(values['monitors'].get(name,not(len(connected)>=3 and name.startswith('eDP'))));self.bar_checks[name]=control;self.bar_screens_layout.addWidget(control);self.bar_tray.addItem(name,name)
        self.bar_tray.setCurrentIndex(max(0,self.bar_tray.findData(values['tray_monitor'])))
    def bar_values_from_ui(self):
        values={key:c.value() if isinstance(c,QSpinBox) else c.text().strip() for key,c in self.bar_controls.items()}
        values.update({side:[listing.item(i).data(Qt.UserRole) for i in range(listing.count())] for side,listing in self.bar_lists.items()});values['monitors']={**self.env.section('bar').get('monitors',{}),**{name:c.isChecked() for name,c in self.bar_checks.items()}};values['tray_monitor']=self.bar_tray.currentData() or '';return values

    def build_workspaces(self):
        layout=self.page();self.page_heading(layout,'Tus escritorios y sus ventanas','Renombra, añade o mueve escritorios entre pantallas. Solo se pueden eliminar escritorios vacíos.');self.workspace_table=self.make_table(['Escritorio','Pantalla','Ventanas','Estado']);layout.addWidget(self.workspace_table,1);row=QHBoxLayout()
        for title,action,symbol in [('Añadir','add','plus'),('Renombrar','rename','pencil'),('Mover','move','monitor'),('Eliminar vacío','remove','trash')]:row.addWidget(button(title,lambda a=action:self.edit_workspace(a),symbol=symbol))
        row.addStretch();row.addWidget(button('Actualizar',self.refresh_workspaces,symbol='refresh-cw'));layout.addLayout(row)
    def refresh_workspaces(self):self.start_job(self.env.workspaces,self.receive_workspaces)
    def receive_workspaces(self,rows):
        self.workspace_rows=rows;self.workspace_table.setRowCount(0)
        for record in rows:self.add_table_row(self.workspace_table,[record['name'],record['monitor'],str(record['windows']),'Visible' if record['active'] else ''],record)
    def edit_workspace(self,action):
        current=self.table_selection(self.workspace_table)
        if action!='add' and not current:return
        value='';ident=current['id'] if current else ''
        if action=='add':
            monitors=list(dict.fromkeys(r['monitor'] for r in getattr(self,'workspace_rows',[])))
            if not monitors:self.report_error('No hay pantallas disponibles. Pulsa Actualizar.');return
            ident,ok=QInputDialog.getItem(self,'Añadir escritorio','Pantalla',monitors,0,False)
            if not ok:return
        if action in ('add','rename'):
            value,ok=QInputDialog.getText(self,'Nombre del escritorio','Nombre',text=current['name'] if current and action=='rename' else '')
            if not ok:return
        elif action=='move':
            monitors=[o['name'] for o in self.inventory if o['enabled'] and o['name']!=current['monitor']]
            if not monitors:self.report_error('Activa otra pantalla para mover este escritorio.');return
            value,ok=QInputDialog.getItem(self,'Mover escritorio','Pantalla de destino',monitors,0,False)
            if not ok:return
        elif QMessageBox.question(self,'Eliminar escritorio','¿Eliminar el escritorio vacío «'+current['name']+'»?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        self.start_job(lambda:self.env.workspace_action(action,ident,value),lambda _:(self.refresh_workspaces(),self.success('Escritorios actualizados y guardados.')))

    @staticmethod
    def make_table(titles):
        table=QTableWidget(0,len(titles));table.setHorizontalHeaderLabels(titles);table.verticalHeader().hide();table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setSelectionMode(QAbstractItemView.SingleSelection);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.setShowGrid(False);table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);table.setWordWrap(False);return table
    @staticmethod
    def add_table_row(table,values,data):
        row=table.rowCount();table.insertRow(row)
        for column,value in enumerate(values):
            item=QTableWidgetItem(str(value));item.setData(Qt.UserRole,data);item.setToolTip(str(value));table.setItem(row,column,item)
        table.setRowHeight(row,42)
    @staticmethod
    def table_selection(table):
        item=table.item(table.currentRow(),0)
        return item.data(Qt.UserRole) if item else None

    def build_shortcuts(self):
        layout=self.page();row=QHBoxLayout();row.addWidget(text_label('Todos tus atajos','title'),1);row.addWidget(button('Nuevo atajo global',lambda:self.edit_shortcut(),symbol='plus'));layout.addLayout(row);row=QHBoxLayout();self.shortcut_search=QLineEdit();self.shortcut_search.setPlaceholderText('Buscar teclas, acción o comando…');self.shortcut_scope=QComboBox();self.shortcut_scope.addItems(['Todos','Global','Conflictos','Terminal','Neovim','Órbita','Conexiones','Archivos','Ajustes']);row.addWidget(self.shortcut_search,1);row.addWidget(self.shortcut_scope);layout.addLayout(row);self.conflicts=text_label('','subtitle');layout.addWidget(self.conflicts)
        self.table=self.make_table(['Combinación','Acción','Dónde funciona']);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Interactive);self.table.setColumnWidth(0,220);self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents);self.table.cellDoubleClicked.connect(lambda *_:self.edit_selected());self.table.itemSelectionChanged.connect(self.shortcut_selected);layout.addWidget(self.table,1);self.shortcut_detail=text_label('Selecciona un atajo para ver su comando y su origen.','subtitle');self.shortcut_detail.setMinimumHeight(50);layout.addWidget(self.shortcut_detail);tools=QHBoxLayout();self.shortcut_edit=button('Editar / grabar',self.edit_selected,symbol='keyboard');self.shortcut_group=button('Editar grupo',self.edit_group,symbol='code');self.shortcut_delete=button('Eliminar',self.delete_shortcut,'danger',symbol='trash')
        for b in (self.shortcut_edit,self.shortcut_group,self.shortcut_delete):tools.addWidget(b)
        tools.addStretch();tools.addWidget(button('Abrir en Vim',self.open_shortcut_source,symbol='terminal'));layout.addLayout(tools);layout.addWidget(text_label('Globales: editables aquí. Los de aplicaciones respetan su contexto y se editan en su archivo; Neovim muestra los mapas cargados con descripción.','subtitle'));self.shortcut_search.textChanged.connect(self.render_shortcuts);self.shortcut_scope.currentIndexChanged.connect(self.render_shortcuts);self.render_shortcuts()
    def receive_shortcuts(self,rows):self.extra_shortcuts=rows;self.render_shortcuts()
    def render_shortcuts(self,*_):
        query=self.shortcut_search.text().casefold();scope=self.shortcut_scope.currentText();global_rows=expanded_rows(self.shortcuts);conflicts=self.shortcuts.conflicts();self.conflicts.setText(f'{len(global_rows)} globales · {len(self.extra_shortcuts)} de aplicaciones · '+(f'{len(conflicts)} combinaciones repetidas' if conflicts else 'Sin conflictos globales'));self.table.setRowCount(0)
        for record in global_rows+self.extra_shortcuts:
            duplicate=record.get('editable') and canonical(record['key']) in conflicts
            if scope=='Conflictos' and not duplicate:continue
            if scope not in ('Todos','Conflictos') and record['scope']!=scope:continue
            if query not in ' '.join(str(record.get(key,'')) for key in ('key','title','command','scope')).casefold():continue
            self.add_table_row(self.table,[record['key'],record['title'],record['scope']],record)
            if duplicate:
                item=self.table.item(self.table.rowCount()-1,0);item.setForeground(QColor('#E9BD93'));item.setToolTip('Combinación repetida. Edita una de las entradas o elimina la que no utilices.')
        if self.table.rowCount():self.table.selectRow(0)
        self.shortcut_selected()
    def selected_shortcut(self):return self.table_selection(self.table)
    def shortcut_selected(self):
        row=self.selected_shortcut();editable=bool(row and row.get('editable'));self.shortcut_edit.setEnabled(editable);self.shortcut_delete.setEnabled(editable);self.shortcut_group.setEnabled(editable)
        if row:self.shortcut_detail.setText((row.get('error') or row['command'])[:240]+'\n'+str(self.shortcuts.path if editable else row.get('path','')))
        else:self.shortcut_detail.setText('Selecciona un atajo para ver su comando y su origen.')
    def open_shortcut_source(self):
        row=self.selected_shortcut();open_vim(self.shortcuts.path if not row or row.get('editable') else row['path'])
    def edit_selected(self):
        row=self.selected_shortcut()
        if row and row.get('editable'):self.edit_shortcut(row)
        elif row:self.open_shortcut_source()
    def edit_group(self):
        row=self.selected_shortcut()
        if row and row.get('editable'):self.edit_shortcut(row,group=True)
    def edit_shortcut(self,row=None,group=False):
        if row and not group:
            model=self.shortcuts
            class Branch:
                rows=[row]
                def save(branch,key,command,index,title):return change_binding(model,row['source_index'],row['part'],key,command,title)
            dialog=ShortcutEditor(self,Branch(),0)
        else:dialog=ShortcutEditor(self,self.shortcuts,row['source_index'] if row else None)
        if dialog.exec()==QDialog.Accepted:self.render_shortcuts();self.success('Atajo guardado. sxhkd recargado y copia anterior conservada.')
    def delete_shortcut(self):
        row=self.selected_shortcut()
        if not row or not row.get('editable'):return
        if QMessageBox.question(self,'Eliminar atajo','¿Eliminar únicamente «'+row['key']+'»?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        try:change_binding(self.shortcuts,row['source_index'],row['part']);subprocess.run(['pkill','-USR1','-u',str(os.getuid()),'-x','sxhkd'],capture_output=True);self.render_shortcuts();self.success('Atajo eliminado; los demás se conservan.')
        except Exception as exc:self.report_error(str(exc))

    def build_component(self,kind):
        titles={'effects':('Efectos y animaciones','Ajusta el movimiento, las sombras y el cristal de Picom.'),'terminal':('Tu terminal, a tu medida','Fuente, colores y espacio de Ghostty. Los cambios se guardan en su configuración.'),'notifications':('Notificaciones','Ajusta la posición, el tamaño y el tiempo de los avisos de Dunst.')};layout=self.page();self.page_heading(layout,*titles[kind]);form=self.scroll_form(layout);values=self.env.component_values(kind);controls={};self.component_controls[kind]=controls
        schemas={
            'effects':[('duration','Duración de animaciones','int',50,600,120,' ms'),('corner-radius','Esquinas','int',0,30,12,' px'),('shadow','Sombras','bool',0,0,True,''),('shadow-radius','Tamaño de sombra','int',0,40,18,' px'),('shadow-opacity','Opacidad de sombra','float',0,1,.25,''),('blur-background','Desenfoque de fondo','bool',0,0,True,''),('blur-strength','Intensidad de desenfoque','int',1,8,3,''),('fading','Fundido al aparecer','bool',0,0,True,''),('vsync','Sincronización vertical','bool',0,0,True,'')],
            'terminal':[('font-family','Fuente','text',0,0,'FiraCode Nerd Font',''),('font-size','Tamaño','float',8,36,20,' pt'),('background-opacity','Opacidad del fondo','float',.1,1,.6,''),('window-padding-x','Margen horizontal','int',0,60,10,' px'),('window-padding-y','Margen vertical','int',0,60,10,' px'),('scrollback-limit','Memoria del historial','int',1000,1000000,10000,' bytes'),('background','Color de fondo','color',0,0,'#1a1b26',''),('foreground','Color del texto','color',0,0,'#c0caf5','')],
            'notifications':[('origin','Posición','position',0,0,'top-right',''),('font','Fuente y tamaño','text',0,0,'Inter 10',''),('transparency','Transparencia','int',0,60,5,' %'),('corner_radius','Esquinas','int',0,30,12,' px'),('notification_limit','Avisos simultáneos','int',1,12,4,''),('padding','Margen interior','int',4,40,18,' px'),('gap_size','Separación','int',0,30,10,' px'),('timeout','Duración normal','int',1,60,6,' s')]}
        if kind=='effects':
            match=re.search(r'duration\s*=\s*([\d.]+)',(self.env.home/'.config/bspwm/picom.conf').read_text())
            if match:values['duration']=round(float(match[1])*1000)
        for key,label,typ,lo,hi,default,suffix in schemas[kind]:
            value=values.get(key,default)
            if typ in ('int','float'):
                c=QSpinBox() if typ=='int' else QDoubleSpinBox();c.setRange(lo,hi);c.setSuffix(suffix)
                if typ=='float':c.setDecimals(2);c.setSingleStep(.05 if hi<=1 else .5)
                c.setValue(int(float(value)) if typ=='int' else float(value))
            elif typ=='bool':c=QCheckBox(label);c.setChecked(str(value).lower() in ('true','1'))
            elif typ=='position':
                c=QComboBox()
                for label2,position in [('Arriba · izquierda','top-left'),('Arriba · centro','top-center'),('Arriba · derecha','top-right'),('Abajo · izquierda','bottom-left'),('Abajo · centro','bottom-center'),('Abajo · derecha','bottom-right')]:c.addItem(label2,position)
                c.setCurrentIndex(max(0,c.findData(value)))
            else:c=QLineEdit(('#'+str(value).lstrip('#')) if typ=='color' else str(value))
            controls[key]=c
            if typ=='color':
                row=QHBoxLayout();row.addWidget(c,1);row.addWidget(button('Elegir',lambda control=c:self.choose_color(control),symbol='palette'));form.addRow(label,row)
            elif typ=='bool':form.addRow(c)
            else:form.addRow(label,c)
        if kind=='terminal':form.addRow(text_label('Se verá en las terminales nuevas. En una terminal abierta, recarga Ghostty con Ctrl + Shift + , . Neovim conserva su propio tema.','subtitle'))
        if kind=='notifications':form.addRow(button('Probar notificación',lambda:launch(['notify-send','Órbita · Notificaciones','Así se ven tus avisos actuales.']),symbol='bell'))
        if kind=='effects':form.addRow(text_label('Una duración de 100–140 ms mantiene el movimiento ágil. Las reglas especiales de ventanas se conservan.','subtitle'))
    def component_values_from_ui(self,kind):
        return {key:c.isChecked() if isinstance(c,QCheckBox) else c.currentData() if isinstance(c,QComboBox) else c.value() if isinstance(c,(QSpinBox,QDoubleSpinBox)) else c.text().strip() for key,c in self.component_controls[kind].items()}

    def build_startup(self):
        layout=self.page();self.page_heading(layout,'Aplicaciones al iniciar sesión','Activa las aplicaciones que quieres abrir al entrar. Los servicios base del escritorio se gestionan en bspwmrc.');self.startup_table=self.make_table(['Aplicación','Estado','Comando']);self.startup_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents);layout.addWidget(self.startup_table,1);row=QHBoxLayout()
        row.addWidget(button('Añadir aplicación',self.add_startup,symbol='plus'));row.addWidget(button('Activar / desactivar',self.toggle_startup,symbol='circle-play'));row.addWidget(button('Abrir en Vim',self.open_startup,symbol='terminal'));layout.addLayout(row)
        layout.addWidget(text_label('Servicios del escritorio','subtitle'));self.services_label=text_label('Consultando estado…','subtitle');layout.addWidget(self.services_label);tools=QHBoxLayout();tools.addWidget(button('Reiniciar barra',lambda:self.start_job(lambda:self.env.runner([str(ROOT/'desktop-bar')]),lambda _:self.success('Barra reiniciada.')),symbol='refresh-cw'));tools.addWidget(button('Editar inicio de BSPWM',lambda:open_vim(self.env.home/'.config/bspwm/bspwmrc'),symbol='file-code'));tools.addWidget(button('Actualizar',self.refresh_startup,symbol='refresh-cw'));layout.addLayout(tools)
    def refresh_startup(self):
        self.start_job(self.env.autostart_entries,self.receive_startup)
        def services():
            names=['bspwm','sxhkd','picom','polybar','dunst'];return '  ·  '.join(name+(' activo' if subprocess.run(['pgrep','-u',str(os.getuid()),'-x',name],capture_output=True).returncode==0 else ' detenido') for name in names)
        self.start_job(services,self.services_label.setText)
    def receive_startup(self,rows):
        self.startup_table.setRowCount(0)
        for row in rows:self.add_table_row(self.startup_table,[row['name'],'Activada' if row.get('managed') and row['enabled'] else 'Desactivada' if not row['enabled'] else 'Disponible',row['command']],row)
    def toggle_startup(self):
        row=self.table_selection(self.startup_table)
        if not row:return
        enabled=not(row.get('managed') and row['enabled']);self.start_job(lambda:self.env.set_autostart(row,enabled),lambda _:(self.refresh_startup(),self.success('Cambio guardado para el próximo inicio de sesión.')))
    def open_startup(self):
        row=self.table_selection(self.startup_table)
        if row:open_vim(row['path'])
    def add_startup(self):
        dialog=QDialog(self);dialog.setWindowTitle('Añadir aplicación al inicio');dialog.resize(550,245);layout=QVBoxLayout(dialog);form=QFormLayout();name=QLineEdit();command=QLineEdit();command.setPlaceholderText('Programa y argumentos, por ejemplo: nm-applet');form.addRow('Nombre',name);form.addRow('Comando',command);layout.addLayout(form);error=text_label('','subtitle');layout.addWidget(error);row=QHBoxLayout();row.addStretch();row.addWidget(button('Cancelar',dialog.reject))
        def save():
            try:self.env.add_autostart(name.text(),command.text());dialog.accept();self.refresh_startup();self.success('Aplicación añadida al próximo inicio.')
            except Exception as exc:error.setText(str(exc))
        row.addWidget(button('Añadir',save,'primary'));layout.addLayout(row);dialog.exec()

    def build_files(self):
        layout=self.page();self.page_heading(layout,'Archivos y copias de seguridad','Abre la configuración en Neovim. Antes de cada cambio conservamos la versión anterior.');grid=QGridLayout()
        files=[('BSPWM','bspwm/bspwmrc'),('Atajos · sxhkd','sxhkd/sxhkdrc'),('Picom','bspwm/picom.conf'),('Polybar','bspwm/polybar/config'),('Ghostty','ghostty/config'),('Notificaciones','bspwm/dunstrc'),('Neovim','nvim/lua/mappings.lua'),('Fuentes y temas GTK','xsettingsd/xsettingsd.conf'),('Preferencias del entorno','orbit/environment.json')]
        for i,(title,path) in enumerate(files):grid.addWidget(button(title,lambda p=path:open_vim(self.env.home/'.config'/p),symbol='file-code'),i//3,i%3)
        layout.addLayout(grid);layout.addWidget(text_label('Copias disponibles · selecciona para inspeccionar o restaurar','subtitle'));self.backups=QListWidget();layout.addWidget(self.backups,1);row=QHBoxLayout();row.addWidget(button('Ver en Vim',self.inspect_backup,symbol='terminal'));row.addWidget(button('Restaurar atajos / ventanas',self.restore_shortcuts,symbol='rotate-cw'));row.addWidget(button('Abrir carpeta',lambda:launch(['xdg-open',str(self.env.home/'.local/share/orbit/settings-backups')]),symbol='folder-open'));layout.addLayout(row);self.render_backups()
    def inspect_backup(self):
        item=self.backups.currentItem()
        if item:open_vim(item.data(Qt.UserRole))
    def render_backups(self):
        if not hasattr(self,'backups'):return
        self.backups.clear();root=self.env.home/'.local/share/orbit/settings-backups'
        for path in sorted(root.glob('*'),reverse=True)[:80]:
            if path.is_file():item=QListWidgetItem(path.name);item.setData(Qt.UserRole,str(path));self.backups.addItem(item)
    def reload(self):
        self.env.reload();self.backend.reload();self.shortcuts.reload();self.rules=copy.deepcopy(self.backend.saved.get('rules',[]));self.load_values();self.render_rules();self.render_shortcuts();self.render_backups();self.refresh_startup();self.start_job(lambda:display_inventory(self.env.runner),self.receive_displays)
        self.extra_loaded=False
        if self.section()=='shortcuts':self.extra_loaded=True;self.start_job(lambda:application_shortcuts(home=self.env.home),self.receive_shortcuts)
        values=self.env.bar_values()
        for key,c in self.bar_controls.items():c.setValue(values[key]) if isinstance(c,QSpinBox) else c.setText(values[key])
        for side,listing in self.bar_lists.items():
            listing.clear()
            for name in values[side]:self.add_bar_item(side,name)
        for kind,controls in self.component_controls.items():
            values=self.env.component_values(kind)
            if kind=='effects':
                match=re.search(r'duration\s*=\s*([\d.]+)',(self.env.home/'.config/bspwm/picom.conf').read_text())
                if match:values['duration']=round(float(match[1])*1000)
            for key,c in controls.items():
                if key not in values:continue
                value=values[key]
                if isinstance(c,QCheckBox):c.setChecked(str(value).lower()=='true')
                elif isinstance(c,QComboBox):c.setCurrentIndex(max(0,c.findData(value)))
                elif isinstance(c,QSpinBox):c.setValue(int(float(value)))
                elif isinstance(c,QDoubleSpinBox):c.setValue(float(value))
                else:c.setText('#'+str(value).lstrip('#') if key in ('background','foreground') else str(value))
        self.wallpaper_values=self.env.wallpaper_values();self.success('Configuración actual recargada.')
    def apply(self):
        key=self.section()
        if not self.apply_button.isEnabled():return
        if key=='displays':self.try_displays();return
        if key=='wallpaper':self.apply_wallpaper();return
        if key in ('appearance','behavior','rules'):values=self.values();rules=copy.deepcopy(self.rules);fn=lambda:self.backend.apply(values,rules);message='Ventanas y reglas actualizadas; se conservarán al iniciar sesión.'
        elif key=='bar':values=self.bar_values_from_ui();fn=lambda:self.env.apply_bar(values);message='Barra actualizada en las pantallas elegidas.'
        elif key in ('effects','terminal','notifications'):values=self.component_values_from_ui(key);fn=lambda:self.env.apply_component(key,values);message='Configuración guardada. Abre una terminal nueva o recarga Ghostty.' if key=='terminal' else 'Cambios aplicados.'
        else:return
        self.apply_button.setEnabled(False);self.status.setText('Aplicando…');job=self.start_job(fn,lambda _:self.success(message));job.finished.connect(lambda:self.apply_button.setEnabled(True))
    def closeEvent(self,event):
        for field in self.findChildren(QLineEdit):
            if hasattr(field,'cancel'):field.cancel()
        # The small settings process stays resident; worker threads can finish safely.
        self.hide();event.ignore()

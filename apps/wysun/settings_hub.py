"""Wysun's complete desktop settings surface.

Derivado de caelestia-dots/shell (GPL-3.0), modificado para Wysun.
Presentation translated from modules/nexus at commit
507d66285e9d9fde9330adc64159cfdebb28c19a. Upstream files have no individual
copyright headers; their GPL-3.0 notice is retained in LICENSES/GPL-3.0.txt.
See THIRD_PARTY.md for the exact adaptation map.
"""
from theme_tokens import apply_style, extend_style, color, tokens, font

import copy
import json
import theme_core
import os
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QPointF,QSize,QThread,Signal,QTimer,QFileSystemWatcher
from PySide6.QtGui import QColor,QPainter,QPen,QPixmap,QImageReader,QIcon,QFont,QKeySequence,QShortcut
from PySide6.QtWidgets import (QApplication,QWidget,QFrame,QVBoxLayout,QHBoxLayout,QFormLayout,QGridLayout,QLineEdit,QLabel,QListWidget,QListWidgetItem,QStackedWidget,QComboBox,QCheckBox,QSpinBox,QDoubleSpinBox,QPushButton,QScrollArea,QAbstractItemView,QTableWidget,QTableWidgetItem,QHeaderView,QFileDialog,QDialog,QDialogButtonBox,QMessageBox,QInputDialog,QPlainTextEdit,QFontComboBox)
from desktop_common import Surface,button,text_label,open_vim,launch
from settings_window import SettingsWindow as LegacySettingsWindow,ShortcutEditor
from settings_data import DesktopSettings,ShortcutFile,SCHEMA,canonical
from settings_shortcuts import expanded_rows,change_binding,application_shortcuts
from environment_settings import (EnvironmentSettings,DisplayTrial,display_inventory,display_plan,BAR_MODULES)
from icons import icon
from ui_motion import MotionButton as QPushButton

MATERIAL_VARIANTS=(('tonalspot','Tonal'),('vibrant','Vibrante'),('expressive','Expresiva'),('content','Contenido'),('fidelity','Fiel al fondo'),('neutral','Neutra'),('monochrome','Monocroma'),('rainbow','Arcoíris'),('fruitsalad','Macedonia'))

class Job(QThread):
    ready=Signal(object)
    progress=Signal(object)
    failed=Signal(str)
    def __init__(self,fn,parent,streaming=False):super().__init__(parent);self.fn=fn;self.streaming=streaming
    def run(self):
        try:self.ready.emit(self.fn(self.progress.emit) if self.streaming else self.fn())
        except Exception as exc:self.failed.emit(str(exc))

class DisplayCanvas(QWidget):
    """Monitors to scale. Dragging only reorders: on release the layout is
    normalized edge to edge, so monitors never overlap or float apart."""
    selected=Signal(str)
    changed=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.setMinimumHeight(240);self.setMaximumHeight(300);self.plan=[];self.current='';self.rects={};self.drag=None;self.setCursor(Qt.OpenHandCursor)
    def geometry_for(self,p):
        from display_layout import logical_size
        return logical_size(p)
    def paintEvent(self,event):
        from display_layout import order
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing);painter.setPen(Qt.NoPen);painter.setBrush(color('inset'));painter.drawRoundedRect(self.rect(),14,14)
        active=[p for p in self.plan if p['enabled']];self.rects={}
        if not active:painter.setPen(color('subtle'));painter.drawText(self.rect(),Qt.AlignCenter,'Detectando pantallas…');return
        if not self.drag:
            minx=min(p['x'] for p in active);miny=min(p['y'] for p in active)
            maxx=max(p['x']+self.geometry_for(p)[0] for p in active);maxy=max(p['y']+self.geometry_for(p)[1] for p in active)
            self.scale=min((self.width()-64)/max(1,maxx-minx),(self.height()-64)/max(1,maxy-miny))
            self.origin=((self.width()-(maxx-minx)*self.scale)/2-minx*self.scale,(self.height()-(maxy-miny)*self.scale)/2-miny*self.scale)
        ox,oy=self.origin;numbers={name:i+1 for i,name in enumerate(order(self.plan))}
        for p in sorted(active,key=lambda p:p['name']==self.current):
            w,h=self.geometry_for(p);r=QRectF(ox+p['x']*self.scale,oy+p['y']*self.scale,w*self.scale,h*self.scale).adjusted(3,3,-3,-3);self.rects[p['name']]=r
            chosen=p['name']==self.current
            painter.setPen(QPen(color('accent_alt' if chosen else 'line_strong'),2 if chosen else 1));painter.setBrush(color('chosen_fill' if chosen else 'surface_raised'));painter.drawRoundedRect(r,10,10)
            badge=QRectF(r.left()+10,r.top()+10,24,24);painter.setPen(Qt.NoPen);painter.setBrush(color('accent_alt' if chosen else 'track'));painter.drawEllipse(badge)
            painter.setPen(color('on_accent' if chosen else 'text'));painter.setFont(QFont('Inter',10,QFont.Bold));painter.drawText(badge,Qt.AlignCenter,str(numbers.get(p['name'],'')))
            painter.setPen(color('text'));painter.setFont(QFont('Inter',12,QFont.DemiBold));painter.drawText(r.adjusted(6,0,-6,-14),Qt.AlignCenter,p['name'])
            detail=p['mode'].replace('x','×')+(' · '+('%g' % float(p.get('scale',1)))+'×' if float(p.get('scale',1) or 1)!=1 else '')+(' · Principal' if p['primary'] else '')
            painter.setFont(QFont('Inter',9));painter.setPen(color('muted'));painter.drawText(r.adjusted(4,30,-4,0),Qt.AlignCenter,detail)
    def mousePressEvent(self,e):
        if e.button()!=Qt.LeftButton:return
        for name,r in sorted(self.rects.items(),key=lambda item:item[0]!=self.current):
            if r.contains(e.position()):
                self.current=name;self.selected.emit(name);p=next(p for p in self.plan if p['name']==name);self.drag=(e.position(),p['x'],p['y']);self.setCursor(Qt.ClosedHandCursor);self.update();break
    def mouseMoveEvent(self,e):
        if self.drag and e.buttons()&Qt.LeftButton:
            start,x,y=self.drag;p=next(p for p in self.plan if p['name']==self.current);delta=e.position()-start
            p['x']=round(x+delta.x()/self.scale);p['y']=round(y+delta.y()/self.scale);self.update()
    def mouseReleaseEvent(self,e):
        if self.drag:
            from display_layout import normalize
            self.drag=None;self.setCursor(Qt.OpenHandCursor)
            self.plan[:]=normalize(self.plan);self.changed.emit();self.update()

class SettingsHub(LegacySettingsWindow):
    def __init__(self,test=False,home=None):
        Surface.__init__(self,'Wysun Settings','',1120,740)
        self.setMinimumSize(920,620);self.test=test;self.jobs=[];self.inventory=[];self.display_draft=[];self.trial=None;self.widgets={};self.rules=[];self.extra_shortcuts=[];self.extra_loaded=False;self.routes={};self.page_titles={};self.component_controls={}
        self.env=EnvironmentSettings(home);self.backend=DesktopSettings(home);self.shortcuts=ShortcutFile(home);self.rules=copy.deepcopy(self.backend.saved.get('rules',[]))
        extend_style(self,'''QListWidget#navigation::item {padding:8px 10px;margin:1px 0;} QListWidget#navigation::item:selected {background:@nav_selected;color:@selection_text;} QLabel#section-note {color:@subtle;font-size:12px;} QTableWidget::item {padding:8px;}''')
        middle=QHBoxLayout();middle.setSpacing(int(tokens()['space_xl']));sidebar=QVBoxLayout();sidebar.setSpacing(int(tokens()['space_m']));self.nav_search=QLineEdit();self.nav_search.setPlaceholderText('Buscar ajuste…');self.nav_search.setFixedWidth(190);sidebar.addWidget(self.nav_search);self.nav=QListWidget();self.nav.setObjectName('navigation');self.nav.setFixedWidth(190);self.nav.setIconSize(QSize(18,18));self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);sidebar.addWidget(self.nav,1);middle.addLayout(sidebar);self.pages=QStackedWidget();middle.addWidget(self.pages,1);self.outer.addLayout(middle,1)
        builders=[('home','Resumen','settings',self.build_home),('displays','Pantallas','monitor',self.build_displays),('workspaces','Escritorios','panels-top-left',self.build_workspaces),('wallpaper','Fondo y estilo','palette',self.build_wallpaper),('shell','Paneles','panels-top-left',self.build_shell),('shortcuts','Atajos','keyboard',self.build_shortcuts),('rules','Reglas de ventanas','panels-top-left',self.build_rules),('effects','Efectos y animaciones','sliders-horizontal',lambda:self.build_component('effects')),('terminal','Terminal','terminal',lambda:self.build_component('terminal')),('startup','Inicio y aplicaciones','circle-play',self.build_startup),('files','Archivos y copias','files',self.build_files)]
        for key,title,symbol,build in builders:
            self.routes[key]=self.pages.count();self.page_titles[key]=title;self.nav.addItem(QListWidgetItem(icon(symbol),title));build()
        footer=QHBoxLayout();self.status=text_label('','subtitle');footer.addWidget(self.status,1);footer.addWidget(button('Recargar',self.reload,symbol='refresh-cw'));self.apply_button=button('Aplicar cambios',self.apply,'primary',symbol='check');footer.addWidget(self.apply_button);self.outer.addLayout(footer)
        self.nav.currentRowChanged.connect(self.select_page);self.nav_search.textChanged.connect(self.filter_navigation);QShortcut(QKeySequence('Ctrl+F'),self).activated.connect(self.nav_search.setFocus);QShortcut(QKeySequence('Ctrl+Return'),self).activated.connect(self.apply)
        self.load_values();self.nav.setCurrentRow(0);self.start_job(lambda:display_inventory(self.env.runner),self.receive_displays)
        self.preferences_backup=None;self.preferences_dirty=False;self.preferences_loading=False
        self.watch_preferences()
        QTimer.singleShot(50,self,self.refresh_startup)

    def start_job(self,fn,callback,progress=None):
        job=Job(fn,self,progress is not None);self.jobs.append(job);job.ready.connect(callback);job.failed.connect(self.report_error);job.finished.connect(lambda j=job:self.finish_job(j))
        if progress:job.progress.connect(progress)
        job.start();return job
    def finish_job(self,job):
        if job in self.jobs:self.jobs.remove(job)
        job.deleteLater()
    def report_error(self,message):
        if hasattr(self,'status'):self.status.setText(message[:260]);apply_style(self.status,'color:@danger')
    def success(self,message):apply_style(self.status,'');self.status.setText(message);self.render_backups()
    def go(self,key):self.nav.setCurrentRow(self.routes[key])
    def section(self):return next((key for key,index in self.routes.items() if index==self.pages.currentIndex()),'home')
    def select_page(self,index):
        self.pages.setCurrentIndex(index);
        from ui_motion import reveal_content
        reveal_content(self.pages.currentWidget())
        key=self.section();self.apply_button.setVisible(key in ('displays','wallpaper','shell','bar','appearance','behavior','rules','effects','terminal','notifications'));self.apply_button.setText('Probar distribución' if key=='displays' else 'Aplicar cambios');self.apply_button.setEnabled(not(key=='shell' and getattr(self,'shell_error','')))
        if key=='shortcuts' and not self.extra_loaded:
            self.extra_loaded=True;self.start_job(lambda:application_shortcuts(home=self.env.home),self.receive_shortcuts)
        elif key=='workspaces':self.refresh_workspaces()
        elif key=='wallpaper':self.refresh_theme_selection()
    def filter_navigation(self,text):
        words={'displays':'monitor resolución frecuencia posición principal','shortcuts':'hyprland teclas grabar','effects':'hyprland sombra blur desenfoque velocidad','wallpaper':'Material You dinámico claro oscuro tema Tokyo Severance Space Black Fluent colores imagen fondo', 'shell':'riel marco panel bandeja principal salidas bajo consumo','terminal':'ghostty fuente colores'}
        for key,index in self.routes.items():self.nav.item(index).setHidden(text.casefold() not in (self.page_titles[key]+' '+words.get(key,'')).casefold())
    def page_heading(self,layout,title,note=''):
        layout.addWidget(text_label(title,'title'))
        if note:
            label=text_label(note,'subtitle');label.setWordWrap(True);layout.addWidget(label)
    def scroll_form(self,layout):
        scroll=QScrollArea();scroll.setWidgetResizable(True);holder=QWidget();holder.setObjectName('page');form=QFormLayout(holder);form.setContentsMargins(0,8,12,8);form.setVerticalSpacing(12);scroll.setWidget(holder);layout.addWidget(scroll,1);return form

    def build_home(self):
        layout=self.page();self.page_heading(layout,'Resumen');grid=QGridLayout();grid.setSpacing(12)
        entries=[('wallpaper','Fondo y estilo','','palette'),('shell','Paneles','','panels-top-left'),('displays','Pantallas','','monitor'),('workspaces','Escritorios','','panels-top-left'),('shortcuts','Atajos','','keyboard'),('effects','Efectos y animaciones','','sliders-horizontal'),('terminal','Terminal','','terminal')]
        for i,(key,title,note,symbol) in enumerate(entries):
            b=button(title,lambda k=key:self.go(k),symbol=symbol);b.setMinimumHeight(72);apply_style(b,'QPushButton {text-align:left;padding:16px;background:@tile;border:@border solid @tile_line;border-radius:@radius_control;} QPushButton:hover {background:@tile_hover;border-color:@tile_hover_line;} QPushButton:focus {border:@focus_width solid @focus;}');grid.addWidget(b,i//2,i%2)
        layout.addLayout(grid);links=QHBoxLayout()
        for title,mode,symbol in [('Conexiones','network','wifi'),('Sonido','audio','volume-2'),('Sesión','power','power')]:links.addWidget(button(title,lambda m=mode:launch([str(self.env.home/'.local/bin/orbit'),m]),symbol=symbol))
        layout.addLayout(links);self.overview=text_label('','subtitle');self.overview.hide();layout.addStretch()

    def build_displays(self):
        layout=self.page();row=QHBoxLayout();row.addWidget(text_label('Pantallas','title'),1)
        row.addWidget(button('Descartar cambios',self.discard_displays,symbol='rotate-ccw'));row.addWidget(button('Detectar',lambda:self.start_job(lambda:display_inventory(self.env.runner),self.receive_displays),symbol='refresh-cw'));layout.addLayout(row)
        layout.addWidget(text_label('Arrastra una pantalla para cambiar su lugar. Siempre quedan pegadas, sin huecos ni solapes, y nada cambia hasta que pulses Probar distribución.','subtitle'))
        self.canvas=DisplayCanvas();self.canvas.selected.connect(self.select_display);self.canvas.changed.connect(self.display_dragged);layout.addWidget(self.canvas)
        arrange=QHBoxLayout();arrange.setSpacing(8)
        for label,direction,symbol in [('A la izquierda','left','arrow-left'),('A la derecha','right','arrow-right'),('Arriba','above','arrow-up'),('Abajo','below','arrow-down')]:
            arrange.addWidget(button(label,lambda d=direction:self.move_display(d),symbol=symbol))
        arrange.addStretch(1);self.display_order=text_label('','subtitle');self.display_order.setWordWrap(False);arrange.addWidget(self.display_order);layout.addLayout(arrange)
        card=QFrame();card.setObjectName('display-card');apply_style(card,'QFrame#display-card{background:@card;border:@border solid @tile_line;border-radius:@radius_m;}')
        grid=QGridLayout(card);grid.setContentsMargins(16,14,16,14);grid.setHorizontalSpacing(14);grid.setVerticalSpacing(6)
        self.output_combo=QComboBox();self.output_combo.currentIndexChanged.connect(lambda:self.load_display_controls())
        self.output_enabled=QCheckBox('Encendida');self.output_primary=QCheckBox('Principal (foco al iniciar)')
        grid.addWidget(text_label('Pantalla','subtitle'),0,0);grid.addWidget(self.output_combo,1,0);grid.addWidget(self.output_enabled,1,1);grid.addWidget(self.output_primary,1,2)
        self.output_mode=QComboBox();self.output_rate=QComboBox();self.output_scale=QComboBox();self.output_rotation=QComboBox()
        for name,label in [('normal','Normal'),('left','90° izquierda'),('right','90° derecha'),('inverted','180°')]:self.output_rotation.addItem(label,name)
        from display_layout import SCALES
        for value in SCALES:self.output_scale.addItem(('%g' % value)+'×',value)
        for i,(title,widget) in enumerate([('Resolución',self.output_mode),('Frecuencia',self.output_rate),('Escala',self.output_scale),('Rotación',self.output_rotation)]):
            grid.addWidget(text_label(title,'subtitle'),2,i);grid.addWidget(widget,3,i)
        layout.addWidget(card);layout.addStretch()
        self.output_mode.currentIndexChanged.connect(self.change_resolution)
        for c in (self.output_rate,self.output_rotation,self.output_scale):c.currentIndexChanged.connect(self.store_display_controls)
        self.output_enabled.toggled.connect(self.store_display_controls);self.output_primary.toggled.connect(self.store_display_controls)

    def receive_displays(self,outputs):
        from display_layout import normalize
        self.inventory=outputs;self.display_draft=normalize(display_plan(outputs));self.canvas.plan=self.display_draft;self.output_combo.blockSignals(True);self.output_combo.clear()
        for p in self.display_draft:self.output_combo.addItem(p['name'],p['name'])
        self.output_combo.blockSignals(False);self.load_display_controls();self.refresh_bar_monitors();self.refresh_shell_outputs();self.wallpaper_target.clear();self.wallpaper_target.addItem('Todas las pantallas','')
        for p in self.display_draft:self.wallpaper_target.addItem(p['name'],p['name'])
        self.overview.setText(f"{len(self.display_draft)} pantallas conectadas · {len(expanded_rows(self.shortcuts))} atajos globales · Preferencias locales")
        self.show_display_order()
    def discard_displays(self):
        self.status.setText('Cambios de pantallas descartados.');self.start_job(lambda:display_inventory(self.env.runner),self.receive_displays)
    def show_display_order(self):
        from display_layout import order
        if hasattr(self,'display_order'):self.display_order.setText('Orden: '+'  →  '.join(order(self.display_draft)))
    def select_display(self,name):self.output_combo.setCurrentIndex(self.output_combo.findData(name))
    def current_display(self):return next((p for p in self.display_draft if p['name']==self.output_combo.currentData()),None)
    def load_display_controls(self):
        p=self.current_display()
        if not p:return
        self.loading_display=True
        self.output_enabled.setChecked(p['enabled']);self.output_primary.setChecked(p['primary']);self.output_rotation.setCurrentIndex(self.output_rotation.findData(p['rotation']));self.output_mode.clear()
        scale=float(p.get('scale',1) or 1);index=self.output_scale.findData(scale)
        if index<0:self.output_scale.addItem(('%g' % scale)+'×',scale);index=self.output_scale.count()-1
        self.output_scale.setCurrentIndex(index)
        original=next(o for o in self.inventory if o['name']==p['name'])
        for mode in original['modes']:self.output_mode.addItem(mode['name'].replace('x','×'),mode['name'])
        self.output_mode.setCurrentIndex(self.output_mode.findData(p['mode']));self.fill_rates(p['mode'],p['rate'])
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
        if not self.output_enabled.isChecked() and not any(o['enabled'] for o in self.display_draft if o is not p):
            self.report_error('Deja al menos una pantalla encendida.');self.loading_display=True;self.output_enabled.setChecked(True);self.loading_display=False;return
        p.update(enabled=self.output_enabled.isChecked(),primary=self.output_primary.isChecked(),mode=self.output_mode.currentData(),rate=self.output_rate.currentData(),rotation=self.output_rotation.currentData(),scale=float(self.output_scale.currentData() or 1))
        if p['primary']:
            for other in self.display_draft:
                if other is not p:other['primary']=False
        # A new size or rotation changes the neighbours' positions too.
        from display_layout import normalize
        self.display_draft[:]=normalize(self.display_draft);self.canvas.update();self.show_display_order()
        self.status.setText('Cambio preparado. Pulsa Probar distribución para verlo en tus pantallas.')
    def display_dragged(self):self.load_display_controls();self.show_display_order();self.status.setText('Orden preparado. Pulsa Probar distribución para verlo en tus pantallas.')
    def move_display(self,direction):
        from display_layout import move
        p=self.current_display()
        if not p:return
        self.display_draft[:]=move(self.display_draft,p['name'],direction);self.display_dragged()
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
        self.start_job(work,lambda _:None)

    def build_wallpaper(self):
        import theme_core
        layout=self.page();self.page_heading(layout,'Fondo y estilo','Material You toma el acento de tu fondo. También puedes conservar uno de los cinco esquemas fijos.')
        form=self.scroll_form(layout)
        self.wallpaper_preview=QLabel();self.wallpaper_preview.setAlignment(Qt.AlignCenter)
        self.wallpaper_preview.setFixedHeight(int(tokens()['space_xl'])*6)
        apply_style(self.wallpaper_preview,'background:@surface_raised;border-radius:@radius_l;')
        form.addRow(self.wallpaper_preview)
        self.wallpaper_path=QLineEdit();self.wallpaper_path.setAccessibleName('Imagen de fondo')
        row=QHBoxLayout();row.addWidget(self.wallpaper_path,1);row.addWidget(button('Elegir imagen',self.choose_wallpaper,symbol='image'));form.addRow('Fondo global',row)
        self.colour_source=QComboBox();self.colour_source.addItem('Material You · desde el fondo','dynamic')
        for style,spec in theme_core.styles().items():
            for variant in spec['variants']:
                value=theme_core.resolve(style,variant)
                self.colour_source.addItem(spec['name']+' · '+value['name'],theme_core.key(style,variant))
        self.colour_source.setAccessibleName('Origen del esquema');form.addRow('Colores',self.colour_source)
        self.colour_mode=QComboBox();self.colour_mode.addItem('Oscuro','dark');self.colour_mode.addItem('Claro','light');form.addRow('Modo Material You',self.colour_mode)
        self.colour_variant=QComboBox();self.colour_variant.addItem('Automática · según el fondo','auto')
        for key,title in MATERIAL_VARIANTS:self.colour_variant.addItem(title,key)
        self.colour_variant.setAccessibleName('Variante Material You');form.addRow('Variante',self.colour_variant)
        self.colour_seed=QLineEdit();self.colour_seed.setPlaceholderText('#RRGGBB · vacío usa el fondo');self.colour_seed.setAccessibleName('Semilla de color');self.colour_seed.setMaxLength(7)
        seed_row=QHBoxLayout();seed_row.addWidget(self.colour_seed,1);seed_row.addWidget(button('Elegir',self.choose_seed,symbol='palette'));form.addRow('Semilla',seed_row)
        self.seed_note=text_label('Material You parte del fondo; una semilla manual lo sustituye sin cambiar el modo ni la variante.','subtitle');self.seed_note.setWordWrap(True);form.addRow(self.seed_note)
        self.theme_summary=text_label('','subtitle');self.theme_summary.setWordWrap(True);form.addRow(self.theme_summary)
        self.wallpaper_target=QComboBox();self.wallpaper_target.hide()
        self.load_colour_preferences()
        self.colour_source.currentIndexChanged.connect(self.colour_changed)
        self.colour_mode.currentIndexChanged.connect(self.preference_edited)
        self.colour_variant.currentIndexChanged.connect(self.preference_edited)
        self.colour_seed.textChanged.connect(self.preference_edited)
        self.wallpaper_path.textChanged.connect(self.preference_edited)

    def choose_seed(self):
        from PySide6.QtWidgets import QColorDialog
        chosen=QColorDialog.getColor(QColor(self.colour_seed.text().strip() or color('accent').name()),self,'Semilla de color')
        if chosen.isValid():self.colour_seed.setText(chosen.name())

    def choose_wallpaper(self):
        path,_=QFileDialog.getOpenFileName(self,'Elegir fondo',str(self.env.home),'Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)')
        if path:self.wallpaper_path.setText(path);self.update_wallpaper_preview()

    def update_wallpaper_preview(self):
        path=self.wallpaper_path.text().strip()
        pixmap=QPixmap(path) if path else QPixmap()
        self.wallpaper_preview.setPixmap(pixmap.scaledToHeight(self.wallpaper_preview.height(),Qt.SmoothTransformation))
        if pixmap.isNull():self.wallpaper_preview.setText('Selecciona una imagen para el fondo')

    def load_colour_preferences(self):
        self.colour_baseline=self.env.colour_values();self.theme_selected=tuple(self.colour_baseline['selection'])
        source='dynamic' if self.colour_baseline['dynamic'] else theme_core.key(*self.theme_selected)
        self.colour_source.setCurrentIndex(max(0,self.colour_source.findData(source)))
        self.colour_mode.setCurrentIndex(max(0,self.colour_mode.findData(self.colour_baseline['mode'])))
        self.colour_variant.setCurrentIndex(max(0,self.colour_variant.findData(self.colour_baseline['variant'])));self.colour_seed.setText(self.colour_baseline['seed'])
        self.set_dynamic_controls(source=='dynamic')
        self.wallpaper_values=self.env.wallpaper_values();self.wallpaper_path.setText(self.wallpaper_values.get('default',''))
        self.update_wallpaper_preview();self.refresh_theme_selection()

    def colour_changed(self,*_):
        selected=self.colour_source.currentData()
        self.set_dynamic_controls(selected=='dynamic')
        if selected!='dynamic':self.theme_selected=theme_core.parse(selected)
        self.preference_edited();self.refresh_theme_selection()

    def set_dynamic_controls(self,enabled):
        for control in (self.colour_mode,self.colour_variant,self.colour_seed):control.setEnabled(enabled)

    def refresh_theme_selection(self):
        if not hasattr(self,'colour_source'):return
        import theme_core
        current=theme_core.read_scheme(self.env.home)
        if current and current['name']=='dynamic':active='Material You'
        elif self.colour_baseline['dynamic']:active='Material You · elige un fondo para generar los colores; mientras tanto se usa '+self.theme_label(theme_core.read_file(self.env.home))
        else:active=self.theme_label(theme_core.read_file(self.env.home))
        self.theme_summary.setText('Activo · '+active)

    def theme_label(self,selection):
        import theme_core
        values=theme_core.resolve(*selection)
        return values['style_name']+' · '+values['name']

    def select_theme(self,key):
        import theme_core
        self.theme_selected=theme_core.parse(key) if isinstance(key,str) else theme_core.normalize(*key)
        self.colour_source.setCurrentIndex(self.colour_source.findData(theme_core.key(*self.theme_selected)))

    def apply_wallpaper(self):
        source=self.colour_source.currentData()
        values=dict(dynamic=source=='dynamic',selection=self.theme_selected if source=='dynamic' else source,mode=self.colour_mode.currentData(),variant=self.colour_variant.currentData(),seed=self.colour_seed.text().strip())
        path=self.wallpaper_path.text().strip()
        self.apply_button.setEnabled(False);self.status.setText('Aplicando fondo y colores…')
        def complete(result):
            self.preferences_backup=result['backup'];self.preferences_loading=True
            self.env.reload();self.load_colour_preferences();self.preferences_loading=False;self.preferences_dirty=False
            from theme_tokens import refresh_widgets
            refresh_widgets();self.success(result['message']+' · Puedes revertir este cambio.')
        job=self.start_job(lambda:self.env.apply_colour(values,path,self.colour_baseline),complete)
        job.finished.connect(lambda:self.apply_button.setEnabled(True))

    def build_shell(self):
        layout=self.page();self.page_heading(layout,'Paneles','El riel y el marco comparten las preferencias del escritorio. La bandeja tiene una sola salida propietaria.')
        form=self.scroll_form(layout)
        self.read_shell_state()
        self.shell_note=text_label('','subtitle');self.shell_note.setWordWrap(True);form.addRow(self.shell_note)
        self.rail_enabled=QCheckBox('Mostrar el riel izquierdo');self.frame_enabled=QCheckBox('Mostrar el marco del escritorio')
        self.low_power=QCheckBox('Bajo consumo');self.low_power.setToolTip('Permite al shell reducir trabajo visual; no cambia los servicios ni el perfil de energía del sistema.')
        for key,control in [('rail_enabled',self.rail_enabled),('frame_enabled',self.frame_enabled),('low_power',self.low_power)]:
            control.setChecked(self.shell_baseline[key]);form.addRow(control);control.toggled.connect(self.preference_edited)
        self.shell_screens=QWidget();self.shell_screen_layout=QVBoxLayout(self.shell_screens);self.shell_checks={};form.addRow('Salidas con paneles',self.shell_screens)
        self.shell_primary=QComboBox();self.shell_tray=QComboBox()
        for title,control in [('Salida principal',self.shell_primary),('Bandeja de aplicaciones',self.shell_tray)]:
            control.addItem('Automática','');form.addRow(title,control);control.currentIndexChanged.connect(self.preference_edited)
        self.shell_opacity=QSpinBox();self.shell_opacity.setRange(65,100);self.shell_opacity.setSuffix(' %')
        self.shell_motion=QCheckBox('Reducir movimiento')
        self.shell_opacity.setValue(self.appearance_baseline['opacity']);self.shell_motion.setChecked(self.appearance_baseline['reduced_motion'])
        form.addRow('Opacidad',self.shell_opacity);form.addRow(self.shell_motion)
        self.shell_opacity.valueChanged.connect(self.preference_edited);self.shell_motion.toggled.connect(self.preference_edited)
        form.addRow(button('Revertir último cambio de preferencias',self.undo_preferences,symbol='rotate-ccw'))
        self.panel_controls=[self.rail_enabled,self.frame_enabled,self.low_power,self.shell_primary,self.shell_tray,self.shell_opacity,self.shell_motion]
        self.show_shell_state()

    def read_shell_state(self):
        """Read shell.json and appearance.json; an unreadable file blocks only its own page."""
        from settings_data import SHELL_DEFAULTS
        self.shell_error=''
        try:self.shell_baseline=self.env.shell_values()
        except (OSError,ValueError) as error:
            self.shell_baseline=dict(SHELL_DEFAULTS);self.shell_error=str(error)
        try:self.appearance_baseline=self.env.appearance_values()
        except (OSError,ValueError) as error:
            self.appearance_baseline=dict(opacity=80,reduced_motion=False);self.shell_error=self.shell_error or str(error)

    def show_shell_state(self):
        blocked=bool(self.shell_error)
        self.shell_note.setVisible(blocked);self.shell_note.setText(self.shell_error+' Corrige o restaura el archivo y pulsa Recargar; no se modificó nada.' if blocked else '')
        for control in self.panel_controls+list(self.shell_checks.values()):control.setEnabled(not blocked)
        if self.section()=='shell':self.apply_button.setEnabled(not blocked)

    def apply_shell_preferences(self):
        if self.shell_error:self.report_error(self.shell_error);return
        values=dict(anchor='left',rail_enabled=self.rail_enabled.isChecked(),frame_enabled=self.frame_enabled.isChecked(),
                    low_power=self.low_power.isChecked(),monitors={name:c.isChecked() for name,c in self.shell_checks.items()},
                    primary_monitor=self.shell_primary.currentData() or '',tray_monitor=self.shell_tray.currentData() or '')
        appearance=dict(opacity=self.shell_opacity.value(),reduced_motion=self.shell_motion.isChecked())
        self.apply_button.setEnabled(False)
        def complete(backup):
            self.preferences_backup=backup;self.preferences_dirty=False;self.preferences_loading=True
            self.load_shell_preferences();self.preferences_loading=False;self.success('Paneles guardados. Puedes revertir este cambio.')
        job=self.start_job(lambda:self.env.apply_panels(values,appearance,self.shell_baseline,self.appearance_baseline),complete)
        job.finished.connect(lambda:self.apply_button.setEnabled(True))

    def refresh_shell_outputs(self):
        if not hasattr(self,'shell_checks'):return
        values=self.shell_baseline
        self.preferences_loading=True
        while self.shell_screen_layout.count():
            item=self.shell_screen_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.shell_checks={}
        names=list(dict.fromkeys([o['name'] for o in self.inventory]+list(values['monitors'])+[values['primary_monitor'],values['tray_monitor']]))
        for combo in (self.shell_primary,self.shell_tray):combo.clear();combo.addItem('Automática','')
        for name in filter(None,names):
            connected=any(o['name']==name for o in self.inventory)
            check=QCheckBox(name+('' if connected else ' · desconectada'));check.setChecked(values['monitors'].get(name,True));check.toggled.connect(self.preference_edited)
            self.shell_checks[name]=check;self.shell_screen_layout.addWidget(check)
            self.shell_primary.addItem(name,name);self.shell_tray.addItem(name,name)
        self.shell_primary.setCurrentIndex(max(0,self.shell_primary.findData(values['primary_monitor'])))
        self.shell_tray.setCurrentIndex(max(0,self.shell_tray.findData(values['tray_monitor'])))
        self.preferences_loading=False

    def preference_edited(self,*_):
        if not getattr(self,'preferences_loading',False):self.preferences_dirty=True

    def watch_preferences(self):
        self.preference_watcher=QFileSystemWatcher(self)
        self.preference_watcher.fileChanged.connect(self.preferences_changed)
        self.preference_watcher.directoryChanged.connect(self.preferences_changed)
        self.arm_preference_watcher()

    def arm_preference_watcher(self):
        import theme_core
        paths=[self.env.path,self.env.config/'orbit/shell.json',self.env.config/'orbit/appearance.json',theme_core.selection_path(self.env.home),theme_core.scheme_path(self.env.home)]
        watched=set(self.preference_watcher.files()+self.preference_watcher.directories())
        for path in paths:
            parent=path.parent
            while not parent.exists() and parent!=parent.parent:parent=parent.parent
            for item in (parent,path):
                if item.exists() and str(item) not in watched:self.preference_watcher.addPath(str(item));watched.add(str(item))

    def preferences_changed(self,*_):
        self.arm_preference_watcher()
        if getattr(self,'preference_refresh_pending',False):return
        self.preference_refresh_pending=True;QTimer.singleShot(80,self,self.sync_preferences)

    def sync_preferences(self):
        self.preference_refresh_pending=False
        if self.jobs:return
        if self.preferences_dirty:
            self.status.setText('Las preferencias cambiaron fuera de esta ventana. Tu borrador se conserva; pulsa Recargar para actualizarlo.')
            return
        try:
            self.preferences_loading=True;self.env.reload();self.load_colour_preferences();self.load_shell_preferences()
        except (OSError,ValueError) as error:self.report_error(str(error))
        finally:self.preferences_loading=False

    def load_shell_preferences(self):
        self.read_shell_state()
        for key,control in [('rail_enabled',self.rail_enabled),('frame_enabled',self.frame_enabled),('low_power',self.low_power)]:control.setChecked(self.shell_baseline[key])
        self.shell_opacity.setValue(self.appearance_baseline['opacity']);self.shell_motion.setChecked(self.appearance_baseline['reduced_motion'])
        self.refresh_shell_outputs();self.show_shell_state()

    def undo_preferences(self):
        if not self.preferences_backup:self.status.setText('No hay un cambio de esta ventana para revertir. Las copias anteriores siguen en Archivos y copias.');return
        try:
            self.env.undo_preferences(self.preferences_backup);self.preferences_backup=None;self.preferences_dirty=False
            self.sync_preferences();self.success('Preferencias anteriores restauradas.')
        except (OSError,ValueError,RuntimeError) as error:self.report_error(str(error))

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
        if not hasattr(self,'bar_screens_layout'):return
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
        layout=self.page();self.page_heading(layout,'Escritorios fijos por pantalla','Cada número del 1 al 0 pertenece a una pantalla concreta. Se aplican al guardar y se conservan al iniciar la sesión.');self.workspace_table=self.make_table(['Escritorio','Pantalla','Ventanas','Estado']);layout.addWidget(self.workspace_table,1);row=QHBoxLayout()
        for title,action,symbol in [('Asignar','add','plus'),('Mover','move','monitor'),('Quitar vacío','remove','trash'),('Restablecer','reset','refresh-cw')]:row.addWidget(button(title,lambda a=action:self.edit_workspace(a),symbol=symbol))
        row.addStretch();row.addWidget(button('Actualizar',self.refresh_workspaces,symbol='refresh-cw'));layout.addLayout(row)
        note=text_label('La barra muestra el 10 como 0 para que coincida con Super+0. Un número sin asignar se abre en la pantalla activa.','subtitle');note.setWordWrap(True);layout.addWidget(note)
    def refresh_workspaces(self):self.start_job(self.env.workspaces,self.receive_workspaces)
    def receive_workspaces(self,rows):
        self.workspace_rows=rows;self.workspace_table.setRowCount(0)
        for record in rows:
            status='Visible' if record['active'] else ''
            if record.get('fixed'):status=(status+' · Fijo').lstrip(' ·')
            self.add_table_row(self.workspace_table,[record.get('label',record['name']),record['monitor'],str(record['windows']),status],record)
    def workspace_saved(self,_):
        self.refresh_workspaces();self.success('Escritorios actualizados y guardados.')
    def edit_workspace(self,action):
        rows=list(getattr(self,'workspace_rows',[]));current=self.table_selection(self.workspace_table)
        monitors=[o['name'] for o in getattr(self,'inventory',[]) if o.get('enabled')]
        if action=='reset':
            if QMessageBox.question(self,'Restablecer escritorios','¿Volver a la distribución automática 1–5 / 6–9 / 0 para las pantallas conectadas?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
            self.start_job(self.env.reset_workspace_layout,self.workspace_saved);return
        if action!='add' and not current:return
        if not monitors:
            self.report_error('No hay pantallas activas. Abre Pantallas y pulsa Detectar.');return
        if action=='add':
            used={r.get('number') for r in rows if r.get('number')}
            free=[str(n) for n in range(1,11) if n not in used]
            if not free:
                self.report_error('Los 10 escritorios ya están asignados. Mueve o quita uno.');return
            number,ok=QInputDialog.getItem(self,'Asignar escritorio','Número',free,0,False)
            if not ok:return
            monitor,ok=QInputDialog.getItem(self,'Asignar escritorio','Pantalla',monitors,0,False)
            if not ok:return
            self.start_job(lambda:self.env.assign_workspace(int(number),monitor),self.workspace_saved);return
        number=current.get('number')
        if number is None:
            self.report_error('Ese escritorio no es numérico; no forma parte de la distribución fija.');return
        if action=='remove':
            if current['windows']:
                self.report_error('Solo se pueden quitar escritorios vacíos.');return
            if QMessageBox.question(self,'Quitar escritorio','¿Quitar el escritorio '+str(current.get('label',number))+' de la distribución fija?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
            self.start_job(lambda:self.env.unassign_workspace(number),self.workspace_saved);return
        options=[m for m in monitors if m!=current.get('assigned',current['monitor'])]
        if not options:
            self.report_error('Activa otra pantalla para mover este escritorio.');return
        monitor,ok=QInputDialog.getItem(self,'Mover escritorio','Pantalla de destino',options,0,False)
        if not ok:return
        self.start_job(lambda:self.env.assign_workspace(number,monitor),self.workspace_saved)

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
        layout=self.page();row=QHBoxLayout();row.addWidget(text_label('Todos tus atajos','title'),1);row.addWidget(button('Nuevo atajo global',lambda:self.edit_shortcut(),symbol='plus'));layout.addLayout(row);row=QHBoxLayout();self.shortcut_search=QLineEdit();self.shortcut_search.setPlaceholderText('Buscar teclas, acción o comando…');self.shortcut_scope=QComboBox();self.shortcut_scope.addItems(['Todos','Global','Conflictos','Terminal','Neovim','Wysun','Conexiones','Archivos','Ajustes']);row.addWidget(self.shortcut_search,1);row.addWidget(self.shortcut_scope);layout.addLayout(row);self.conflicts=text_label('','subtitle');layout.addWidget(self.conflicts)
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
                item=self.table.item(self.table.rowCount()-1,0);item.setForeground(color('warning'));item.setToolTip('Combinación repetida. Edita una de las entradas o elimina la que no utilices.')
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
        if dialog.exec()==QDialog.Accepted:self.render_shortcuts();self.success('Atajo guardado y copia anterior conservada.')
    def delete_shortcut(self):
        row=self.selected_shortcut()
        if not row or not row.get('editable'):return
        if QMessageBox.question(self,'Eliminar atajo','¿Eliminar únicamente «'+row['key']+'»?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        try:change_binding(self.shortcuts,row['source_index'],row['part']);__import__('settings_data').reload_shortcuts();self.render_shortcuts();self.success('Atajo eliminado; los demás se conservan.')
        except Exception as exc:self.report_error(str(exc))

    def build_component(self,kind):
        titles={'effects':('Efectos y animaciones','Ajusta el movimiento, las sombras y el cristal del compositor.'),'terminal':('Tu terminal, a tu medida','Fuente, colores y espacio de Ghostty. Los cambios se guardan en su configuración.'),'notifications':('Notificaciones','Ajusta la posición, el tamaño y el tiempo de los avisos de Dunst.')};layout=self.page();self.page_heading(layout,*titles[kind]);form=self.scroll_form(layout);controls={};self.component_controls[kind]=controls
        try:values=self.env.component_values(kind)
        except Exception as exc:
            form.addRow(QLabel('No se pudo leer el estado actual: '+str(exc)))
            return
        schemas={
            'effects':[('duration','Duración de animaciones','int',50,600,120,' ms'),('corner-radius','Esquinas','int',0,30,12,' px'),('shadow','Sombras','bool',0,0,True,''),('shadow-radius','Tamaño de sombra','int',0,40,18,' px'),('shadow-opacity','Opacidad de sombra','float',0,1,.25,''),('blur-background','Desenfoque de fondo','bool',0,0,True,''),('blur-strength','Intensidad de desenfoque','int',1,8,3,''),('fading','Fundido al aparecer','bool',0,0,True,''),('vsync','Sincronización vertical','bool',0,0,True,'')],
            'terminal':[('font-family','Fuente','text',0,0,'FiraCode Nerd Font',''),('font-size','Tamaño','float',8,36,20,' pt'),('background-opacity','Opacidad del fondo','float',.1,1,.6,''),('window-padding-x','Margen horizontal','int',0,60,10,' px'),('window-padding-y','Margen vertical','int',0,60,10,' px'),('scrollback-limit','Memoria del historial','int',1000,1000000,10000,' bytes'),('background','Color de fondo','color',0,0,'#1a1b26',''),('foreground','Color del texto','color',0,0,'#c0caf5','')],  # theme-exception: valores por defecto de la terminal del usuario
            'notifications':[('origin','Posición','position',0,0,'top-right',''),('font','Fuente y tamaño','text',0,0,'Inter 10',''),('transparency','Transparencia','int',0,60,5,' %'),('corner_radius','Esquinas','int',0,30,12,' px'),('notification_limit','Avisos simultáneos','int',1,12,4,''),('padding','Margen interior','int',4,40,18,' px'),('gap_size','Separación','int',0,30,10,' px'),('timeout','Duración normal','int',1,60,6,' s')]}
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
        if kind=='effects':
            controls['corner-radius'].setMaximum(20)
            controls['vsync'].setEnabled(False);controls['vsync'].setToolTip('Wayland sincroniza la presentación mediante el compositor.')
        if kind=='terminal':form.addRow(text_label('Se verá en las terminales nuevas. En una terminal abierta, recarga Ghostty con Ctrl + Shift + , . Neovim conserva su propio tema.','subtitle'))
        if kind=='notifications':form.addRow(button('Probar notificación',lambda:launch(['notify-send','Wysun · Notificaciones','Así se ven tus avisos actuales.']),symbol='bell'))
        if kind=='effects':form.addRow(text_label('Una duración de 100–140 ms mantiene el movimiento ágil. Las reglas especiales de ventanas se conservan.','subtitle'))
    def component_values_from_ui(self,kind):
        return {key:c.isChecked() if isinstance(c,QCheckBox) else c.currentData() if isinstance(c,QComboBox) else c.value() if isinstance(c,(QSpinBox,QDoubleSpinBox)) else c.text().strip() for key,c in self.component_controls[kind].items()}

    def build_startup(self):
        layout=self.page();self.page_heading(layout,'Aplicaciones al iniciar sesión','Activa las aplicaciones que quieres abrir al entrar. Los servicios base del escritorio se gestionan en la sesión Wysun.');self.startup_table=self.make_table(['Aplicación','Estado','Comando']);self.startup_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents);layout.addWidget(self.startup_table,1);row=QHBoxLayout()
        row.addWidget(button('Añadir aplicación',self.add_startup,symbol='plus'));row.addWidget(button('Activar / desactivar',self.toggle_startup,symbol='circle-play'));row.addWidget(button('Abrir en Vim',self.open_startup,symbol='terminal'));layout.addLayout(row)
        layout.addWidget(text_label('Servicios del escritorio','subtitle'));self.services_label=text_label('Consultando estado…','subtitle');layout.addWidget(self.services_label);tools=QHBoxLayout();tools.addWidget(button('Recargar shell',lambda:self.start_job(lambda:self.env.runner(['wysun','shell','reload-preferences']),lambda _:self.success('Shell recargado.')),symbol='refresh-cw'));tools.addWidget(button('Editar Hyprland',lambda:open_vim(self.env.home/'.config/wysun/hyprland.lua'),symbol='file-code'));tools.addWidget(button('Actualizar',self.refresh_startup,symbol='refresh-cw'));layout.addLayout(tools)
    def refresh_startup(self):
        self.start_job(self.env.autostart_entries,self.receive_startup)
        def services():
            names=['Hyprland','quickshell','dunst','pipewire','wireplumber'];return '  ·  '.join(name+(' activo' if subprocess.run(['pgrep','-u',str(os.getuid()),'-x',name],capture_output=True).returncode==0 else ' detenido') for name in names)
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
        files=[('Hyprland','wysun/hyprland.lua'),('Atajos Wysun','orbit/hypr-shortcuts.lua'),('Reglas Wysun','orbit/hypr-settings.lua'),('Efectos','orbit/hypr-effects.lua'),('Notificaciones','wysun/dunstrc'),('Ghostty','ghostty/config'),('Neovim','nvim/lua/mappings.lua'),('Preferencias del entorno','orbit/environment.json')]
        for i,(title,path) in enumerate(files):grid.addWidget(button(title,lambda p=path:open_vim(self.env.home/'.config'/p),symbol='file-code'),i//3,i%3)
        layout.addLayout(grid);layout.addWidget(text_label('Copias disponibles · selecciona para inspeccionar o restaurar','subtitle'));self.backups=QListWidget();layout.addWidget(self.backups,1);row=QHBoxLayout();row.addWidget(button('Ver en Vim',self.inspect_backup,symbol='terminal'));row.addWidget(button('Restaurar copia',self.restore_settings_backup,symbol='rotate-cw'));row.addWidget(button('Abrir carpeta',lambda:launch(['xdg-open',str(self.env.home/'.local/share/orbit/settings-backups')]),symbol='folder-open'));layout.addLayout(row);self.render_backups()
    def restore_settings_backup(self):
        item=self.backups.currentItem()
        if not item:return
        folder=Path(item.data(Qt.UserRole))
        if not (folder/'receipt.json').is_file():self.restore_shortcuts();return
        try:
            from settings_data import PreferenceBackup
            backup=PreferenceBackup.open(self.env.home,self.env.preference_paths(),folder)
            self.env.undo_preferences(backup);self.preferences_dirty=False;self.sync_preferences();self.success('Copia de preferencias restaurada.')
        except (OSError,ValueError,RuntimeError) as error:self.report_error(str(error))

    def inspect_backup(self):
        item=self.backups.currentItem()
        if item:
            path=Path(item.data(Qt.UserRole));open_vim(path/'receipt.json' if path.is_dir() else path)
    def render_backups(self):
        if not hasattr(self,'backups'):return
        self.backups.clear();root=self.env.home/'.local/share/orbit/settings-backups'
        for path in sorted(root.glob('*'),reverse=True)[:80]:
            if path.is_file() or (path/'receipt.json').is_file():
                item=QListWidgetItem(path.name);item.setData(Qt.UserRole,str(path));self.backups.addItem(item)
    def reload(self):
        self.env.reload();self.backend.reload();self.shortcuts.reload();self.rules=copy.deepcopy(self.backend.saved.get('rules',[]));self.load_values();self.render_rules();self.render_shortcuts();self.render_backups();self.refresh_startup();self.start_job(lambda:display_inventory(self.env.runner),self.receive_displays)
        self.extra_loaded=False
        if self.section()=='shortcuts':self.extra_loaded=True;self.start_job(lambda:application_shortcuts(home=self.env.home),self.receive_shortcuts)
        values=self.env.bar_values()
        for key,c in getattr(self,'bar_controls',{}).items():c.setValue(values[key]) if isinstance(c,QSpinBox) else c.setText(values[key])
        for side,listing in getattr(self,'bar_lists',{}).items():
            listing.clear()
            for name in values[side]:self.add_bar_item(side,name)
        for kind,controls in self.component_controls.items():
            values=self.env.component_values(kind)
            for key,c in controls.items():
                if key not in values:continue
                value=values[key]
                if isinstance(c,QCheckBox):c.setChecked(str(value).lower()=='true')
                elif isinstance(c,QComboBox):c.setCurrentIndex(max(0,c.findData(value)))
                elif isinstance(c,QSpinBox):c.setValue(int(float(value)))
                elif isinstance(c,QDoubleSpinBox):c.setValue(float(value))
                else:c.setText('#'+str(value).lstrip('#') if key in ('background','foreground') else str(value))
        self.preferences_loading=True;self.load_colour_preferences();self.load_shell_preferences();self.preferences_loading=False;self.preferences_dirty=False;self.success('Configuración actual recargada.')
    def apply(self):
        key=self.section()
        if not self.apply_button.isEnabled():return
        if key=='displays':self.try_displays();return
        if key=='wallpaper':self.apply_wallpaper();return
        if key=='shell':
            self.apply_shell_preferences();return
        if key in ('appearance','behavior','rules'):values=dict(self.backend.values) if key=='rules' else self.values();rules=copy.deepcopy(self.rules);fn=lambda:self.backend.apply(values,rules);message='Reglas actualizadas.'
        elif key=='bar':values=self.bar_values_from_ui();fn=lambda:self.env.apply_bar(values);message='Barra actualizada en las pantallas elegidas.'
        elif key in ('effects','terminal','notifications'):
            values=self.component_values_from_ui(key)
            def fn():
                self.env.apply_component(key,values)
            message='Configuración guardada. Abre una terminal nueva o recarga Ghostty.' if key=='terminal' else 'Cambios aplicados.'
        else:return
        self.apply_button.setEnabled(False);self.status.setText('Aplicando…');job=self.start_job(fn,lambda _:self.success(message));job.finished.connect(lambda:self.apply_button.setEnabled(True))
    def closeEvent(self,event):
        for field in self.findChildren(QLineEdit):
            if hasattr(field,'cancel'):field.cancel()
        # The small settings process stays resident; worker threads can finish safely.
        self.dismiss();event.ignore()

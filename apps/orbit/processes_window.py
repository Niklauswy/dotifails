"""Native process monitor with live metrics, process trees and contextual actions."""
import os
from collections import deque
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSize, QPointF, QItemSelectionModel, QEvent
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QShortcut, QKeySequence, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLineEdit, QComboBox, QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView,
    QSplitter, QTabWidget, QPlainTextEdit, QMessageBox, QScrollArea)
from desktop_common import Surface, button, text_label
from icons import icon
from process_data import Processes, STATES, matched


def size(value):
    if value is None:return '—'
    for unit in ('B','KiB','MiB','GiB','TiB'):
        if value<1024:return f'{value:.0f} {unit}' if unit=='B' else f'{value:.1f} {unit}'
        value/=1024
    return f'{value:.1f} PiB'

def duration(seconds):
    minutes,seconds=divmod(int(seconds),60);hours,minutes=divmod(minutes,60);days,hours=divmod(hours,24)
    return f'{days} d {hours} h' if days else (f'{hours} h {minutes} min' if hours else f'{minutes} min {seconds} s')

class Sparkline(QWidget):
    def __init__(self,color='#91B9FA',parent=None):
        super().__init__(parent);self.values=deque(maxlen=48);self.color=QColor(color);self.setMinimumHeight(20);self.setToolTip('Últimas 48 muestras · escala relativa al máximo observado')
    def add(self,value):
        if value is not None:self.values.append(value);self.update()
    def clear(self):self.values.clear();self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);w=self.width();h=self.height()-3
        p.setPen(QPen(QColor('#303541'),1));p.drawLine(0,h,w,h)
        if len(self.values)<2:return
        high=max(max(self.values)*1.15,1);path=QPainterPath()
        for i,v in enumerate(self.values):
            point=QPointF(i*w/(len(self.values)-1),h-v/high*(h-4))
            if i:path.lineTo(point)
            else:path.moveTo(point)
        fill=QPainterPath(path);fill.lineTo(w,h);fill.lineTo(0,h);fill.closeSubpath();c=QColor(self.color);c.setAlpha(22);p.fillPath(fill,c);p.setPen(QPen(self.color,1.8));p.drawPath(path)

class Metric(QWidget):
    def __init__(self,title,color):
        super().__init__();self.setObjectName('metric');self.setAttribute(Qt.WA_StyledBackground);self.setStyleSheet('QWidget#metric{background:rgba(255,255,255,5);border:1px solid #30343E;border-radius:10px;}');layout=QVBoxLayout(self);layout.setContentsMargins(14,10,14,8);layout.setSpacing(2)
        layout.addWidget(text_label(title,'subtitle'));self.value=text_label('—');self.value.setStyleSheet('font-size:23px;font-weight:600;');layout.addWidget(self.value)
        self.caption=text_label('Tomando la primera muestra…','subtitle');layout.addWidget(self.caption)
        self.chart=Sparkline(color);self.chart.setFixedHeight(28);layout.addWidget(self.chart)
    def update_value(self,text,caption,value):self.value.setText(text);self.caption.setText(caption);self.chart.add(value)

class ProcessScan(QThread):
    ready=Signal(object)
    failed=Signal(str)
    def __init__(self,model,selected=None,manual=False,parent=None):
        super().__init__(parent);self.model=model;self.selected=selected;self.manual=manual
    def run(self):
        try:
            rows=self.model.scan();details=None
            if self.selected:
                try:details=self.model.details(self.selected)
                except (OSError,RuntimeError,ValueError):pass
            self.ready.emit(dict(rows=rows,summary=self.model.summary,details=details,manual=self.manual))
        except (OSError,ValueError,IndexError) as e:self.failed.emit('No se pudo leer /proc: '+str(e))

class ProcessItem(QTreeWidgetItem):
    def __lt__(self,other):
        column=self.treeWidget().sortColumn();key=('name','pid','cpu','memory','read_rate','write_rate','user')[column]
        a=self.data(0,Qt.UserRole) or {};b=other.data(0,Qt.UserRole) or {}
        left=a.get(key);right=b.get(key)
        if key in ('name','user'):return str(left).casefold()<str(right).casefold()
        return (left if left is not None else -1)<(right if right is not None else -1)

class ProcessesWindow(Surface):
    def __init__(self,model=None):
        super().__init__('Procesos','ÓRBITA  /  Actividad del sistema',1140,760)
        self.setMinimumSize(900,600);self.model=model or Processes();self.rows=[];self.worker=None;self.detail=None;self.detail_key=None;self.items={};self.had_selection=False
        self.outer.setSpacing(14)
        self.setStyleSheet(self.styleSheet()+'''
            QWidget#metric {background:rgba(255,255,255,5);border:1px solid #30343E;border-radius:10px;}
            QTreeWidget {background:transparent;border:0;outline:0;alternate-background-color:rgba(255,255,255,3);}
            QTreeWidget::item {height:34px;border:0;padding:0 4px;}
            QTreeWidget::item:selected {background:#343C50;color:#F1F4FA;}
            QTreeWidget::item:hover {background:rgba(153,175,225,12);}
            QHeaderView::section {background:#1B1E26;padding:8px 4px;border:0;color:#959DAF;font-size:11px;}
            QSplitter::handle {background:#30343E;width:1px;}
            QTabWidget::pane {border:0;}
            QTabBar::tab {color:#959DAF;background:transparent;padding:10px 12px;border-bottom:2px solid transparent;}
            QTabBar::tab:selected {color:#DDE6FA;border-bottom:2px solid #A3B8E0;}
            QPlainTextEdit {background:#191C23;border:1px solid #30343E;font-family:monospace;font-size:11px;}
            QPushButton:disabled {color:#666D7D;background:rgba(255,255,255,3);border-color:#292D36;}
            QScrollBar:horizontal {height:7px;background:transparent;margin:0;}
            QScrollBar::handle:horizontal {background:#454B5C;border-radius:3px;min-width:30px;}
            QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {width:0;}
            QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal {background:transparent;}
        ''')
        metrics=QHBoxLayout();metrics.setSpacing(10);self.metrics=[]
        for name,color in [('CPU del equipo','#91B9FA'),('Memoria utilizada','#B7A6E8'),('Intercambio','#E3B978'),('Procesos','#88CBB3')]:
            metric=Metric(name,color);metrics.addWidget(metric,1);self.metrics.append(metric)
        self.outer.addLayout(metrics)
        filters=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Buscar nombre, PID o usuario…');self.search.setToolTip('También: pid:123 · ppid:123 · user:nombre');self.search.setClearButtonEnabled(True);filters.addWidget(self.search,1)
        self.owner=QComboBox();self.owner.addItems(['Mis procesos','Todos los usuarios']);filters.addWidget(self.owner)
        self.filter=QComboBox();self.filter.addItems(['Todos los estados','Ejecutando','Pausados','Consumo alto']);filters.addWidget(self.filter)
        self.view=QComboBox();self.view.addItems(['Lista','Árbol']);filters.addWidget(self.view)
        self.freeze=button('Congelar',self.toggle_freeze,symbol='circle-pause');self.freeze.setCheckable(True);self.freeze.setToolTip('Congelar solo la vista · Espacio cuando la tabla tiene el foco');filters.addWidget(self.freeze);self.outer.addLayout(filters)
        split=QSplitter();self.tree=QTreeWidget();self.list=self.tree
        self.tree.setStyleSheet('QTreeWidget{background:transparent;border:0;outline:0;alternate-background-color:rgba(255,255,255,3);} QTreeWidget::item{height:34px;padding:0 4px;border:0;} QTreeWidget::item:selected{background:#343C50;color:#F1F4FA;} QHeaderView::section{background:#1B1E26;color:#959DAF;border:0;padding:8px 4px;font-size:11px;}')
        self.tree.setColumnCount(7);self.tree.setHeaderLabels(['Proceso','PID','CPU %','Memoria','Lectura/s','Escritura/s','Usuario'])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection);self.tree.setUniformRowHeights(True);self.tree.setAlternatingRowColors(True);self.tree.setIconSize(QSize(18,18));self.tree.setRootIsDecorated(False);self.tree.setIndentation(15)
        self.tree.setSortingEnabled(True);self.tree.sortByColumn(2,Qt.DescendingOrder);self.tree.setColumnWidth(0,190)
        for column,width in [(1,86),(2,62),(3,80),(4,80),(5,80),(6,85)]:self.tree.setColumnWidth(column,width)
        self.tree.header().setStretchLastSection(True);self.tree.setContextMenuPolicy(Qt.CustomContextMenu);split.addWidget(self.tree)
        pane=QWidget();layout=QVBoxLayout(pane);layout.setContentsMargins(18,0,0,0);layout.setSpacing(9)
        head=QHBoxLayout();self.process_icon=text_label('');self.process_icon.setFixedSize(30,30);head.addWidget(self.process_icon);self.name=text_label('Selecciona un proceso');self.name.setStyleSheet('font-size:18px;font-weight:600;');head.addWidget(self.name,1);layout.addLayout(head)
        self.identity=text_label('Los detalles aparecerán aquí','subtitle');layout.addWidget(self.identity)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        self.tabs.setStyleSheet('QTabWidget::pane{border:0;background:transparent;} QTabBar::tab{color:#959DAF;background:transparent;padding:10px 8px;border-bottom:2px solid transparent;} QTabBar::tab:selected{color:#DDE6FA;border-bottom:2px solid #A3B8E0;}')
        overview=QWidget();overview_layout=QVBoxLayout(overview);overview_layout.setContentsMargins(0,8,0,0);overview_layout.setSpacing(6)
        self.usage=text_label('—');self.usage.setStyleSheet('font-size:15px;color:#BFD4FF;');overview_layout.addWidget(self.usage)
        self.cpu_chart=Sparkline();self.cpu_chart.setFixedHeight(28);overview_layout.addWidget(self.cpu_chart)
        self.ram=text_label('—','subtitle');overview_layout.addWidget(self.ram);self.ram_chart=Sparkline('#B7A6E8');self.ram_chart.setFixedHeight(22);overview_layout.addWidget(self.ram_chart)
        self.info=text_label('');self.info.setTextInteractionFlags(Qt.TextSelectableByMouse);overview_layout.addWidget(self.info);overview_layout.addStretch()
        self.command=QPlainTextEdit();self.command.setReadOnly(True);self.command.setPlaceholderText('Comando del proceso');self.command.setFixedHeight(65);overview_layout.addWidget(self.command)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(overview);overview.setAutoFillBackground(False);scroll.viewport().setAutoFillBackground(False);scroll.setStyleSheet('QScrollArea{background:transparent;border:0;}');self.tabs.addTab(scroll,'Resumen')
        self.files=QPlainTextEdit();self.files.setReadOnly(True);self.files.setPlaceholderText('Selecciona un proceso para ver sus descriptores.');self.tabs.addTab(self.files,'Archivos abiertos')
        self.paths=QPlainTextEdit();self.paths.setReadOnly(True);self.tabs.addTab(self.paths,'Rutas')
        self.reason=text_label('','subtitle');layout.addWidget(self.reason)
        actions=QHBoxLayout();self.pause_button=button('Pausar',lambda:self.act('pause'),symbol='circle-pause');self.normal=button('Terminar',lambda:self.act('terminate'),'danger', 'x');actions.addWidget(self.pause_button);actions.addWidget(self.normal);layout.addLayout(actions)
        self.more=button('Acciones  Alt K',self.actions,symbol='ellipsis');layout.addWidget(self.more)
        pane.setMinimumWidth(300);split.addWidget(pane);split.setSizes([745,330]);self.outer.addWidget(split,1)
        footer=QHBoxLayout();self.status=text_label('Leyendo procesos…','subtitle');footer.addWidget(self.status,1)
        self.interval=QComboBox();self.interval.addItems(['Cada 1 s','Cada 2 s','Cada 5 s']);self.interval.setCurrentIndex(1);footer.addWidget(self.interval);footer.addWidget(button('Actualizar  F5',lambda:self.scan(True),symbol='refresh-cw'));self.outer.addLayout(footer)
        self.timer=QTimer(self);self.timer.setInterval(2000);self.timer.timeout.connect(self.scan)
        for control in (self.owner,self.filter,self.view):control.currentIndexChanged.connect(self.render)
        self.search.textChanged.connect(self.render);self.search.installEventFilter(self);self.tree.itemSelectionChanged.connect(self.inspect);self.tree.customContextMenuRequested.connect(lambda _:self.actions());self.tree.itemDoubleClicked.connect(lambda *_:self.tabs.setCurrentIndex(0));self.interval.currentIndexChanged.connect(self.change_interval)
        for key,fn in [('Ctrl+F',self.search.setFocus),('F5',lambda:self.scan(True)),('Alt+K',self.actions)]:QShortcut(QKeySequence(key),self).activated.connect(fn)
        freeze_shortcut=QShortcut(QKeySequence('Space'),self.tree);freeze_shortcut.setContext(Qt.WidgetShortcut);freeze_shortcut.activated.connect(self.freeze.click)
        self.inspect()

    def eventFilter(self,obj,event):
        if obj is self.search and event.type()==QEvent.KeyPress and event.key()==Qt.Key_Down:
            if self.items:
                self.tree.setFocus()
                if not self.selected():
                    item=self.tree.topLevelItem(0);self.tree.setCurrentItem(item);item.setSelected(True)
            return True
        return super().eventFilter(obj,event)
    def current(self):
        item=self.tree.currentItem()
        return item.data(0,Qt.UserRole) if item and item.isSelected() else (self.selected()[0] if self.selected() else None)
    def selected(self):return [i.data(0,Qt.UserRole) for i in self.tree.selectedItems()]
    def change_interval(self):
        self.timer.setInterval((1000,2000,5000)[self.interval.currentIndex()])
    def toggle_freeze(self):
        self.freeze.setText('Reanudar vista' if self.freeze.isChecked() else 'Congelar')
        if self.freeze.isChecked():self.timer.stop();self.status.setText('Vista congelada · F5 toma una muestra')
        else:self.timer.start();self.scan()
    def scan(self,manual=False):
        if self.worker and self.worker.isRunning():return
        if self.worker:self.worker.deleteLater()
        self.worker=ProcessScan(self.model,self.current(),manual,self);self.worker.ready.connect(self.loaded);self.worker.failed.connect(self.status.setText);self.worker.start()
    def loaded(self,data):
        if not self.isVisible() or (self.freeze.isChecked() and not data['manual']):return
        self.rows=data['rows'];s=data['summary'];cpu=s.get('cpu')
        self.metrics[0].update_value(f'{cpu:.0f}%' if cpu is not None else '—','Capacidad total del equipo',cpu)
        self.metrics[1].update_value(size(s['memory']),f"de {size(s['total_memory'])} en total",s['memory'])
        self.metrics[2].update_value(size(s['swap']),f"de {size(s['total_swap'])}" if s['total_swap'] else 'Sin intercambio configurado',s['swap'])
        self.metrics[3].update_value(str(s['count']),f"{s['running']} ejecutándose",s['count'])
        self.render();row=self.current()
        if row:
            self.cpu_chart.add(row['cpu']);self.ram_chart.add(row['memory'])
            if data['details'] and data['details']['key']==(row['pid'],row['start']):self.show_details(data['details'])

    def render(self,*_):
        selected={(r['pid'],r['start']) for r in self.selected()};focused=self.current();expanded={key for key,item in self.items.items() if item.isExpanded()};scroll=self.tree.verticalScrollBar().value()
        self.tree.blockSignals(True);self.tree.setSortingEnabled(False);self.tree.clear();self.items={};by_pid={r['pid']:r for r in self.rows};visible=[]
        for r in self.rows:
            if self.owner.currentIndex()==0 and r['uid']!=os.getuid():continue
            f=self.filter.currentIndex()
            if (f==1 and r['state']!='R') or (f==2 and r['state'] not in ('T','t')) or (f==3 and r['cpu']<5 and r['memory']<250*1048576):continue
            if matched(r,self.search.text()):visible.append(r)
        included={r['pid']:r for r in visible};tree_mode=self.view.currentIndex()==1
        if tree_mode:
            for r in visible:
                parent=r['ppid'];visited={r['pid']}
                while parent in by_pid and parent not in visited:
                    visited.add(parent);included[parent]=by_pid[parent];parent=by_pid[parent]['ppid']
        for r in included.values():
            item=ProcessItem([r['name'],str(r['pid']),f"{r['cpu']:.1f}",size(r['memory']),size(r.get('read_rate')),size(r.get('write_rate')),r.get('user','')]);item.setData(0,Qt.UserRole,r)
            name=r['name'].casefold();symbol='code' if any(x in name for x in ('python','node','code','nvim')) else ('globe' if any(x in name for x in ('chrome','firefox','brave','edge')) else 'terminal')
            item.setIcon(0,icon(symbol));item.setToolTip(0,f"{r['name']} · {STATES.get(r['state'],r['state'])}")
            for col in (1,2,3,4,5):item.setTextAlignment(col,Qt.AlignRight|Qt.AlignVCenter)
            if r['state'] in ('T','t'):item.setForeground(0,QColor('#E3B978'))
            self.items[(r['pid'],r['start'])]=item
        for key,item in self.items.items():
            r=item.data(0,Qt.UserRole);parent=by_pid.get(r['ppid']);parent_item=self.items.get((parent['pid'],parent['start'])) if parent else None
            if tree_mode and parent_item is not None and parent_item is not item:parent_item.addChild(item)
            else:self.tree.addTopLevelItem(item)
        for key,item in self.items.items():
            item.setSelected(key in selected);item.setExpanded(key in expanded or bool(self.search.text()))
        if not included:
            empty=QTreeWidgetItem(['Sin procesos que coincidan']);empty.setFlags(Qt.NoItemFlags);self.tree.addTopLevelItem(empty);empty.setFirstColumnSpanned(True)
        self.tree.setRootIsDecorated(tree_mode);self.tree.setSortingEnabled(True)
        if focused:
            item=self.items.get((focused['pid'],focused['start']))
            if item:self.tree.setCurrentItem(item,0,QItemSelectionModel.NoUpdate)
        elif not self.had_selection and included:self.tree.setCurrentItem(self.tree.topLevelItem(0));self.tree.topLevelItem(0).setSelected(True)
        self.tree.verticalScrollBar().setValue(scroll);self.tree.blockSignals(False);self.inspect()
        self.status.setText(f"{len(visible)} resultados · {len(self.selected())} seleccionados · "+('Vista congelada' if self.freeze.isChecked() else 'CPU por núcleo; puede superar 100%'))

    def inspect(self):
        rows=self.selected();row=self.current();allowed=bool(rows) and all(self.model.action_reason(r) is None for r in rows)
        self.normal.setEnabled(allowed);self.pause_button.setEnabled(allowed);self.normal.setText('Terminar'+(f' ({len(rows)})' if len(rows)>1 else ''))
        paused=bool(rows) and all(r['state'] in ('T','t') for r in rows);self.pause_button.setText('Reanudar' if paused else 'Pausar')
        self.reason.setText(next((self.model.action_reason(r) for r in rows if self.model.action_reason(r)),''))
        if not row:
            self.detail=None;self.detail_key=None;self.name.setText('Selecciona un proceso');self.identity.setText('Selecciona varias filas con Ctrl o Shift');self.info.clear();self.command.clear();self.paths.clear();self.files.clear();self.usage.setText('—');self.ram.setText('—');self.cpu_chart.clear();self.ram_chart.clear();return
        self.had_selection=True;key=(row['pid'],row['start'])
        if self.detail_key!=key:
            self.detail_key=key;self.detail=None;self.cpu_chart.clear();self.ram_chart.clear();self.command.clear();self.paths.clear();self.files.clear()
            QTimer.singleShot(0,lambda:self.scan(True))
        self.name.setText(row['name']);self.process_icon.setPixmap(icon('cpu',26).pixmap(26,26));self.identity.setText(f"PID {row['pid']} · {row.get('user','')} · {STATES.get(row['state'],row['state'])}")
        self.usage.setText(f"{row['cpu']:.1f}% CPU");self.ram.setText(size(row['memory'])+' de memoria residente')
        self.info.setText(f"Activo desde hace {duration(row.get('age',0))}\nProceso padre    {row.get('ppid','—')}\nHilos    {row.get('threads','—')}\nPrioridad nice    {row.get('nice','—')}\nLectura    {size(row.get('read_rate'))}/s\nEscritura    {size(row.get('write_rate'))}/s")
    def show_details(self,detail):
        self.detail=detail;self.command.setPlainText(detail.get('command') or 'Comando no disponible')
        self.paths.setPlainText('EJECUTABLE\n'+(detail.get('exe') or 'No accesible')+'\n\nDIRECTORIO DE TRABAJO\n'+(detail.get('cwd') or 'No accesible'))
        count=detail.get('file_count');lines=[f'{fd:>3}   {target}' for fd,target in detail.get('files',[])]
        self.files.setPlainText(('Sin permiso para inspeccionar archivos' if count is None else f'{count} descriptores · se muestran hasta 60')+'\n\n'+'\n'.join(lines))

    def act(self,action):
        rows=[dict(r) for r in self.selected()]
        if not rows:return
        if action=='pause' and all(r['state'] in ('T','t') for r in rows):action='resume'
        if any(self.model.action_reason(r) for r in rows):return
        if action!='resume':
            verb={'terminate':'Terminar','kill':'Forzar el cierre de','pause':'Pausar'}[action]
            detail='\n'.join(f"{r['name']} · PID {r['pid']}" for r in rows[:5])
            message=f'{verb} {len(rows)} proceso(s)?\n\n{detail}'
            if len(rows)>5:message+=f'\nY {len(rows)-5} más'
            message+='\n\n'+('Las aplicaciones pueden perder cambios sin guardar.' if action!='pause' else 'Dejarán de responder hasta que los reanudes.')
            if QMessageBox.question(self,verb,message,QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        errors=[];done=0
        for row in rows:
            try:self.model.act(row,action);done+=1
            except (OSError,RuntimeError,ValueError) as e:errors.append(f"PID {row['pid']}: {e}")
        self.status.setText(f'{done} señales enviadas'+(f' · {len(errors)} no se aplicaron' if errors else ''))
        if errors:QMessageBox.information(self,'Resultado de la acción','\n'.join(errors[:8]))
        self.scan(True)
    def stop(self,force=False):self.act('kill' if force else 'terminate')
    def select_parent(self):
        row=self.current()
        if not row:return
        self.owner.setCurrentIndex(1);self.filter.setCurrentIndex(0);self.search.setText('pid:'+str(row['ppid']));self.tree.clearSelection()
        for item in self.items.values():
            if item.data(0,Qt.UserRole)['pid']==row['ppid']:self.tree.setCurrentItem(item);item.setSelected(True);break
    def actions(self):
        from enhanced import SearchMenu
        row=self.current();rows=self.selected();entries=[]
        if row:
            entries=[('Copiar PID','',lambda:QApplication.clipboard().setText(str(row['pid']))),('Ver proceso padre','',self.select_parent)]
            if self.detail:
                if self.detail.get('command'):entries.append(('Copiar comando','',lambda:QApplication.clipboard().setText(self.detail['command'])))
                if self.detail.get('cwd'):entries.append(('Abrir directorio de trabajo','',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(self.detail['cwd']))))
            if all(self.model.action_reason(r) is None for r in rows):entries.append(('Forzar cierre…','',lambda:self.act('kill')))
        entries.append(('Actualizar ahora','F5',lambda:self.scan(True)))
        self.popup=SearchMenu(self,entries);self.popup.present(self.more)
    def present(self):
        screen=QApplication.primaryScreen().availableGeometry();self.resize(min(self.width(),screen.width()-30),min(self.height(),screen.height()-60));super().present()
        if not self.freeze.isChecked():self.timer.start()
        self.scan(True)
    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)
    def closeEvent(self,event):
        self.timer.stop();event.accept()

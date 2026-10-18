"""Wysun's portal selector: local paths, explicit acceptance, no implicit uploads."""
import fnmatch
import os
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel, QModelIndex, QMimeDatabase
from PySide6.QtWidgets import (QWidget,QHBoxLayout,QVBoxLayout,QLabel,QComboBox,
    QLineEdit,QCheckBox,QMessageBox,QAbstractItemView)
from files_window import FilesWindow,button


def byte_path(value):
    return os.fsdecode(bytes(value).rstrip(b'\0')) if value else ''

def local_path(value):
    from PySide6.QtCore import QUrl
    url=QUrl(str(value))
    if url.scheme() and not url.isLocalFile():raise ValueError('Solo se admiten ubicaciones locales.')
    return Path(url.toLocalFile() if url.isLocalFile() else str(value)).expanduser().absolute()

class ChooserModel(QSortFilterProxyModel):
    """Keep folders navigable while intersecting filename and MIME filters."""
    def __init__(self,source,parent=None):
        super().__init__(parent);self.setSourceModel(source);self.query='';self.rules=[];self.directories=False
        self.setDynamicSortFilter(True);self.mime=QMimeDatabase()
    def filterAcceptsRow(self,row,parent):
        index=self.sourceModel().index(row,0,parent)
        if self.sourceModel().isDir(index):return True
        if self.directories:return False
        name=self.sourceModel().fileName(index)
        if self.query.casefold() not in name.casefold():return False
        if not self.rules:return True
        for kind,pattern in self.rules:
            if int(kind)==0 and fnmatch.fnmatchcase(name,str(pattern)):return True
            if int(kind)==1:
                mime=self.mime.mimeTypeForFile(self.sourceModel().filePath(index),QMimeDatabase.MatchExtension)
                if mime.name()==str(pattern) or mime.inherits(str(pattern)) or fnmatch.fnmatchcase(mime.name(),str(pattern)):return True
        return False
    def index(self,*args):
        if args and isinstance(args[0],str):return self.mapFromSource(self.sourceModel().index(*args))
        return super().index(*args)
    def setRootPath(self,path):return self.mapFromSource(self.sourceModel().setRootPath(path))
    def filePath(self,index):return self.sourceModel().filePath(self.mapToSource(index))
    def fileName(self,index):return self.sourceModel().fileName(self.mapToSource(index))
    def isDir(self,index):return self.sourceModel().isDir(self.mapToSource(index))
    def setNameFilters(self,values):self.query=values[0].strip('*') if values else '';self.invalidateFilter()
    def nameFilters(self):return ['*'+self.query+'*'] if self.query else []
    def setFilter(self,value):self.sourceModel().setFilter(value)
    @property
    def show_thumbnails(self):return self.sourceModel().show_thumbnails
    @show_thumbnails.setter
    def show_thumbnails(self,value):self.sourceModel().show_thumbnails=value

class FileChooser(FilesWindow):
    completed=Signal(int,object)
    def __init__(self,mode,title,options,parent_window=''):
        self.mode=mode;self.options=options;self.replied=False;self.result_uris=[]
        initial=byte_path(options.get('current_folder'))
        current=byte_path(options.get('current_file'))
        if current and Path(current).is_file():initial=str(Path(current).parent)
        if not initial or not Path(initial).is_dir():initial=str(Path.home())
        super().__init__([initial])
        self.setWindowFlag(Qt.Dialog,True)
        self.setWindowModality(Qt.WindowModal if options.get('modal',True) else Qt.NonModal)
        self.setWindowTitle((title or ('Guardar archivo' if mode=='save' else 'Seleccionar archivos'))+' · Wysun')
        self.directory=bool(options.get('directory')) or mode=='savefiles'
        self.multiple=bool(options.get('multiple')) and mode=='open'
        self.tabs.setTabsClosable(False);self.tabs.tabBar().hide();self.more_button.hide()
        self.open_button.setText('Seleccionar');self.open_button.clicked.disconnect();self.open_button.clicked.connect(self.accept_selection)
        # Selection dialogs never expose editing, terminal, or destructive shortcuts.
        for shortcut in self.shortcuts:shortcut.setEnabled(False)
        from PySide6.QtGui import QShortcut,QKeySequence
        for key,callback in [('Escape',self.close),('Ctrl+L',self.focus_path),('Alt+Up',self.up),('Alt+Left',lambda:self.current().go(-1)),('Ctrl+F',self.filter_edit.setFocus),('Ctrl+H',self.toggle_hidden),('Ctrl+A',lambda:self.current().view().selectAll())]:
            shortcut=QShortcut(QKeySequence(key),self);shortcut.activated.connect(callback);self.shortcuts.append(shortcut)
        tab=self.current();source=tab.model;self.proxy=ChooserModel(source,tab);self.proxy.directories=self.directory;tab.model=self.proxy
        for view in (tab.tree,tab.grid):
            view.setModel(self.proxy)
            view.setSelectionMode(QAbstractItemView.ExtendedSelection if self.multiple else QAbstractItemView.SingleSelection)
        tab.grid.setSelectionModel(tab.tree.selectionModel());tab.tree.selectionModel().selectionChanged.connect(lambda *_:tab.selected.emit())
        tab.navigate(initial,False)
        for view in (tab.tree,tab.grid):
            shortcut=QShortcut(QKeySequence('Return'),view);shortcut.setContext(Qt.WidgetWithChildrenShortcut);shortcut.activated.connect(self.open_selected);self.shortcuts.append(shortcut)
        footer=QWidget();layout=QVBoxLayout(footer);layout.setContentsMargins(16,8,16,12)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setStyleSheet('color:#aa293b;background:transparent;');layout.addWidget(self.error)
        row=QHBoxLayout();self.filename=QLineEdit();self.filename.setAccessibleName('Nombre del archivo')
        self.filename.setText(str(options.get('current_name') or (Path(current).name if current else '')))
        self.filename.returnPressed.connect(self.accept_selection)
        if mode=='save':row.addWidget(QLabel('Nombre'));row.addWidget(self.filename,1)
        else:self.filename.hide();row.addStretch()
        self.filters=list(options.get('filters',[]));self.filter_box=QComboBox();self.filter_box.setAccessibleName('Tipo de archivo')
        for name,rules in self.filters:self.filter_box.addItem(str(name))
        if self.filters:
            current_filter=options.get('current_filter')
            selected=next((i for i,f in enumerate(self.filters) if f==current_filter),0)
            self.filter_box.setCurrentIndex(selected);self.proxy.rules=list(self.filters[selected][1])
            self.filter_box.currentIndexChanged.connect(self.change_filter);row.addWidget(self.filter_box)
        else:self.filter_box.hide()
        layout.addLayout(row);self.choice_widgets=[]
        for ident,label,entries,selected in options.get('choices',[]):
            choice=QHBoxLayout();choice.addWidget(QLabel(str(label)))
            if entries:
                control=QComboBox()
                for value,text in entries:control.addItem(str(text),str(value))
                index=control.findData(str(selected));control.setCurrentIndex(max(0,index))
            else:control=QCheckBox();control.setChecked(str(selected)=='true')
            choice.addWidget(control);choice.addStretch();layout.addLayout(choice);self.choice_widgets.append((str(ident),control))
        actions=QHBoxLayout();actions.addStretch();actions.addWidget(button('Cancelar','back',self.close))
        self.accept_button=button(str(options.get('accept_label') or ('Guardar' if mode!='open' else 'Seleccionar')),'forward',self.accept_selection)
        self.accept_button.setObjectName('actionButton');actions.addWidget(self.accept_button);layout.addLayout(actions)
        self.centralWidget().layout().addWidget(footer)
        self.proxy.invalidateFilter();self.selection_changed()
        # Mark the selector as a dialog before creating its native window. BSPWM
        # floats dialogs; the transient parent and modal state belong to its caller.
        self.attach_requesting_window(parent_window)
        screen=self.screen().availableGeometry()
        self.resize(min(1040,int(screen.width()*.82)),min(720,int(screen.height()*.82)))

    def attach_requesting_window(self,parent_window):
        from PySide6.QtWidgets import QApplication
        if QApplication.platformName() not in ('xcb','x11'):return
        try:
            from Xlib import display,Xatom
            connection=display.Display();root=connection.screen().root
            wid=int(parent_window[4:],16) if parent_window.startswith('x11:') else 0
            if not wid:
                value=root.get_full_property(connection.intern_atom('_NET_ACTIVE_WINDOW'),Xatom.WINDOW)
                wid=int(value.value[0]) if value is not None and len(value.value) else 0
            if wid and wid!=int(self.winId()):
                from PySide6.QtGui import QWindow
                self.parent_handle=QWindow.fromWinId(wid)
                self.windowHandle().setTransientParent(self.parent_handle)
                native=connection.create_resource_object('window',int(self.winId()))
                native.set_wm_transient_for(connection.create_resource_object('window',wid))
                if self.options.get('modal',True):
                    native.change_property(connection.intern_atom('_NET_WM_STATE'),Xatom.ATOM,32,[connection.intern_atom('_NET_WM_STATE_MODAL')])
                connection.sync()
                parent=connection.create_resource_object('window',wid)
                geometry=parent.get_geometry();position=parent.translate_coords(root,0,0)
                self.requesting_geometry=(position.x,position.y,geometry.width,geometry.height)
            connection.close()
        except Exception:
            # Missing or stale foreign handles must not break file selection.
            self.parent_handle=None

    def showEvent(self,event):
        super().showEvent(event)
        geometry=getattr(self,'requesting_geometry',None)
        screen=self.screen().availableGeometry()
        if geometry:
            x,y,width,height=geometry;center_x=x+width//2;center_y=y+height//2
        else:center_x=screen.center().x();center_y=screen.center().y()
        self.move(max(screen.left(),min(screen.right()-self.width(),center_x-self.width()//2)),max(screen.top(),min(screen.bottom()-self.height(),center_y-self.height()//2)))

    def change_filter(self,index):
        self.proxy.rules=list(self.filters[index][1]);self.proxy.invalidateFilter()
    def context_menu(self,point):pass
    def more_menu(self):pass
    def properties(self):pass
    def open_path(self,path):
        if Path(path).is_dir():self.navigate(path)
        else:self.accept_selection([path])
    def open_selected(self):
        paths=self.current().selected_paths()
        if len(paths)==1 and Path(paths[0]).is_dir():self.navigate(paths[0])
        else:self.accept_selection()
    def accept_selection(self,paths=None):
        self.error.clear()
        if isinstance(paths,bool):paths=None
        paths=paths or self.current().selected_paths()
        folder=Path(self.current().path)
        if self.mode=='save':
            name=self.filename.text().strip()
            if not name or Path(name).name!=name or name in ('.','..'):
                self.error.setText('Escribe un nombre de archivo válido.');return
            targets=[folder/name]
            if targets[0].is_dir():self.error.setText('El nombre corresponde a una carpeta.');return
            if targets[0].exists() and QMessageBox.question(self,'Reemplazar archivo','El archivo ya existe. ¿Quieres reemplazarlo?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        elif self.mode=='savefiles':
            target=local_path(paths[0]) if paths and Path(paths[0]).is_dir() else folder
            targets=[]
            for raw in self.options.get('files',[]):
                name=Path(byte_path(raw)).name
                if not name or name in ('.','..'):self.error.setText('Nombre de archivo inválido.');return
                candidate=target/name;stem=candidate.stem;suffix=candidate.suffix;number=1
                while candidate.exists() or candidate in targets:
                    candidate=target/f'{stem} ({number}){suffix}';number+=1
                targets.append(candidate)
        else:
            if self.directory and not paths:paths=[str(folder)]
            if not paths:self.error.setText('Selecciona un archivo.');return
            targets=[local_path(path) for path in paths]
            if not self.multiple and len(targets)>1:self.error.setText('Selecciona un solo elemento.');return
            if any(not p.exists() or p.is_dir()!=self.directory or not os.access(p,os.R_OK) for p in targets):self.error.setText('La selección ya no está disponible o no es del tipo solicitado.');return
        if self.mode!='open' and not os.access(str(targets[0].parent) if targets else str(folder),os.W_OK):self.error.setText('No puedes guardar archivos en esta carpeta.');return
        self.result_uris=[p.as_uri() for p in targets];self.close()
    def closeEvent(self,event):
        super().closeEvent(event)
        if not event.isAccepted() or self.replied:return
        self.replied=True;result={}
        if self.result_uris:
            result['uris']=self.result_uris
            if self.filters:result['current_filter']=self.filters[self.filter_box.currentIndex()]
            result['choices']=[(ident,control.currentData() if isinstance(control,QComboBox) else ('true' if control.isChecked() else 'false')) for ident,control in self.choice_widgets]
        self.completed.emit(0 if self.result_uris else 1,result)

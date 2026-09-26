"""Focused menus, consistent icons and independent desktop utilities."""
import json
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,QSize
from PySide6.QtGui import QKeySequence,QShortcut,QDesktopServices,QIcon,QFont
from PySide6.QtWidgets import QMenu,QMessageBox,QFileIconProvider
from enhanced import OrbitV2,SearchMenu
from data_v2 import color_formats,template
from desktop_common import is_text_file,open_vim,edit_text,launch
from icons import icon

class OrbitV3(OrbitV2):
    def __init__(self,store=None,test=False):
        self.utilities={};super().__init__(store,test);self.setWindowTitle('Órbita');self.action_button.setText('Acciones  Alt K');self.back.setIcon(icon('search'));self.back.setToolTip('Inicio');self.private.setContextMenuPolicy(Qt.CustomContextMenu);self.private.customContextMenuRequested.connect(self.history_menu)
        QShortcut(QKeySequence('Alt+K'),self).activated.connect(self.actions);QShortcut(QKeySequence('Ctrl+E'),self).activated.connect(self.edit_in_vim)
        for b in self.tabs.values():b.setIconSize(QSize(16,16))
        self.emoji_tab.setIconSize(QSize(16,16));self.file_icons=QFileIconProvider()
        from files_controller import FilesController
        self.files_ui=FilesController(self);QShortcut(QKeySequence('Ctrl+Space'),self).activated.connect(self.files_ui.quicklook)
    def make_commands(self):
        rows=super().make_commands();rows=[r for r in rows if r.get('key')!='settings']
        for r in rows:
            if r.get('key')=='network':r.update(title='Centro de conexiones',subtitle='Wi-Fi, Bluetooth, VPN y SSH',tag='Super + N')
        rows.append(dict(kind='mode',mode='settings',title='Ajustes del escritorio',subtitle='Pantallas, fondos, barra, ventanas y todos tus atajos',icon='settings',key='settings',tag='Super + Alt + ,'))
        rows.append(dict(kind='command',title='Opciones del historial',subtitle='Pausar, limpiar y administrar el portapapeles',icon='clipboard',key='history-settings',cmd=[],tag='Ajustes'))
        rows=[r for r in rows if r.get('key') not in ('quicknote','color','processes')]
        for mode,title,subtitle,symbol in [('notes','Notas','Markdown, favoritos y edición en Vim','file-text'),('processes','Procesos','Consumo y aplicaciones en ejecución','activity'),('color','Color','Capturar, convertir y guardar colores','palette')]:
            rows.append(dict(kind='mode',mode=mode,title=title,subtitle=subtitle,icon=symbol,key=mode,tag='Herramienta'))
        return rows
    def show_utility(self,mode):
        self.hide()
        if mode=='settings' and not self.test:
            launch([str(Path(__file__).with_name('orbit-client')),'settings']);return
        if mode not in self.utilities:
            if mode=='settings':
                from settings_hub import SettingsHub
                window=SettingsHub(test=self.test)
            elif mode in ('notes','processes','color'):
                from utilities import NotesWindow,ProcessesWindow,ColorWindow
                window={'notes':NotesWindow,'processes':ProcessesWindow,'color':ColorWindow}[mode]()
            elif mode=='network':
                from connections_window import ConnectionsWindow
                window=ConnectionsWindow()
            else:
                from connections_window import PowerWindow
                window=PowerWindow(self)
            self.utilities[mode]=window
        self.utilities[mode].present()
        if mode=='network':self.utilities[mode].load()
    def show_mode(self,mode='home'):
        if mode in ('network','power','settings','notes','processes','color'):self.show_utility(mode);return
        super().show_mode(mode)
    def set_mode(self,mode):
        if getattr(self,'v2ready',False) and mode in ('network','power','settings','notes','processes','color'):self.show_utility(mode);return
        if getattr(self,'files_ui',None):self.files_ui.leave()
        super().set_mode(mode)
        if mode=='files' and getattr(self,'files_ui',None):self.files_ui.enter()
        if hasattr(self,'back'):self.back.setIcon(icon('search' if mode=='home' else 'back'))
    def activate(self,*args):
        r=self.current()
        if r and r.get('key')=='history-settings':self.history_menu();return
        if r and r['kind']=='file' and r.get('file_kind') not in ('image','video','audio') and is_text_file(r['path']):self.edit_in_vim();return
        super().activate(*args)
    def preview(self,*args):
        if getattr(self,'files_ui',None) and self.mode=='files':self.files_ui.preview();return
        super().preview(*args)
        if getattr(self,'files_ui',None):
            current=self.current();self.files_ui.preview_tools.setVisible(bool(current and current['kind']=='clip' and current.get('clip_kind')=='image'));self.files_ui.look.setText('Vista ampliada');self.files_ui.look.setEnabled(True)
        r=self.current()
        if r and r['kind']=='file' and is_text_file(r['path']):self.go.setText('Editar en Vim  ↵');self.body.setFont(QFont('DejaVu Sans Mono',10))
    def render(self):
        if getattr(self,'files_ui',None) and self.mode=='files':self.files_ui.render();return
        super().render()
        if getattr(self,'mode','')=='files':
            from PySide6.QtCore import QFileInfo
            for i in range(self.results.count()):
                item=self.results.item(i);r=item.data(Qt.UserRole)
                if r and r['kind']=='file':
                    provider=getattr(self,'file_icons',None)
                    if provider:r['thumbnail']=provider.icon(QFileInfo(r['path'])).pixmap(32,32);item.setData(Qt.UserRole,r)
            r=self.current()
            if r and is_text_file(r['path']):self.go.setText('Editar en Vim  ↵')
    def edit_in_vim(self):
        r=self.current()
        if not r:return
        try:
            if r['kind']=='file' and is_text_file(r['path']):open_vim(r['path'])
            elif r['kind']=='clip' and r['clip_kind']=='files':
                paths=json.loads(r.get('meta','{}')).get('paths',[])
                if not paths or not is_text_file(paths[0]):return
                open_vim(paths[0])
            elif r['kind']=='clip' and r['clip_kind']=='text':edit_text(r['text'])
            elif r['kind']=='snippet':edit_text(template(r['body'],self.clipboard.text()))
            else:return
            self.hide()
        except (OSError,RuntimeError) as e:QMessageBox.information(self,'Abrir en Vim',str(e))
    def menu(self,entries):
        self.popup=SearchMenu(self,entries);self.popup.present(self.action_button)
    def history_menu(self,*_):
        self.menu([('Reanudar historial' if self.paused else 'Pausar historial','',self.toggle_capture),('Eliminar varios elementos…','',self.delete_multiple),('Borrar historial completo…','',self.clear_history)])
    def index_ready(self,files):
        if getattr(self,'files_ui',None):self.files_ui.catalog_ready(files)
        super().index_ready(files)
    def start_preview(self,path):
        if self.mode=='files' and getattr(self,'files_ui',None):self.files_ui.start_preview(path)
        else:super().start_preview(path)
    def filter_menu(self):
        if self.mode=='files' and getattr(self,'files_ui',None):
            entries=[(c,'',lambda value=c:self.files_ui.choose_filter(value)) for c in ['Todos','Imágenes','Vídeos','Audio','Documentos','Código','Otros']];self.popup=SearchMenu(self,entries,'Filtrar archivos…');self.popup.present(self.filter_button)
        else:super().filter_menu()
    def actions(self):
        if self.mode=='files' and getattr(self,'files_ui',None) and self.current():self.menu(self.files_ui.actions());return
        if not getattr(self,'v2ready',False):return
        r=self.current();entries=[]
        if r:
            kind=r['kind'];copyable=kind in ('clip','snippet','calc','emoji')
            entries=[('Copiar','Enter',self.activate)] if copyable else [('Abrir','Enter',self.activate)]
            if copyable:entries.append(('Pegar','Ctrl + Enter',self.paste_selected))
            if kind=='clip':
                clip=r['clip_kind']
                if clip=='image':entries += [('Vista previa','Ctrl + Espacio',self.files_ui.quicklook),('Guardar imagen…','',lambda:self.save_image(r)),('Abrir con…','',lambda:self.open_with(r))]
                elif clip=='color':
                    formats=color_formats(r['text']);entries[0]=('Copiar HEX','Enter',lambda:self.copy(formats['HEX']))
                    entries += [('Copiar RGB','',lambda:self.copy(formats['RGB'])),('Copiar HSL','',lambda:self.copy(formats['HSL']))]
                elif clip=='url':entries.append(('Abrir enlace','',lambda:QDesktopServices.openUrl(QUrl(r['text']))))
                elif clip=='text':entries.append(('Editar una copia en Vim','Ctrl + E',self.edit_in_vim))
                elif clip=='files':
                    paths=json.loads(r.get('meta','{}')).get('paths',[])
                    if paths:
                        entries.append(('Abrir archivo','',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(paths[0]))))
                        if is_text_file(paths[0]):entries.append(('Editar en Vim','Ctrl + E',self.edit_in_vim))
                entries += [('Desfijar' if r.get('pinned') else 'Fijar','Ctrl + P',self.pin_current),('Eliminar','Ctrl + D',self.delete_current)]
            elif kind=='snippet':entries += [('Editar snippet','',lambda:self.edit_snippet(r)),('Editar una copia en Vim','Ctrl + E',self.edit_in_vim),('Eliminar snippet','Ctrl + D',self.delete_current)]
            elif kind=='emoji':entries.append(('Quitar de favoritos' if r.get('pinned') else 'Fijar en favoritos','Ctrl + P',self.pin_current))
            elif kind=='file':
                if is_text_file(r['path']):entries[0]=('Editar en Vim','Enter',self.edit_in_vim);entries.append(('Abrir con la aplicación predeterminada','',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(r['path']))))
                entries += [('Abrir carpeta','',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(r['path']).parent)))),('Copiar ruta','',lambda:self.copy(r['path']))]
        if self.mode=='home':entries += [('Actualizar aplicaciones','',self.refresh_sources),('Ajustes del escritorio','',lambda:self.show_utility('settings'))]
        if not entries:entries=[('Ajustes del escritorio','',lambda:self.show_utility('settings'))]
        self.menu(entries)

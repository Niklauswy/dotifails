"""File browser behavior shared by rows, previews and contextual actions."""
import datetime as dt,json,shutil,time
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QUrl,QMimeData,QThread,Signal,QPoint,QObject
from PySide6.QtGui import QImage,QPixmap,QDesktopServices,QFont
from PySide6.QtWidgets import QWidget,QHBoxLayout,QPushButton,QListWidgetItem,QFileDialog,QMessageBox
from file_media import (FileCache,FileOCRIndexer,FilePreviewJob,IMAGES,LABELS,file_kind,file_mime,fold,human_size,duration_label,read_image)
from desktop_common import button,is_text_file,launch
from icons import icon
from shiboken6 import isValid

class ThumbnailBatch(QThread):
    ready=Signal(object)
    def __init__(self,paths):super().__init__();self.paths=paths
    def run(self):
        rows=[]
        for path in self.paths:
            image,_=read_image(path,96)
            if not image.isNull():rows.append((path,image))
        self.ready.emit(rows)

class FilesController(QObject):
    def __init__(self,owner):
        super().__init__(owner)
        self.w=owner;self.cache=FileCache(owner.store.root);owner.destroyed.connect(self.cache.close);self.catalog=[];self.catalog_signature=None;self.filter='Todos';self.ocr_job=None;self.ocr_done=0;self.ocr_total=0;self.paused=owner.store.get('file_ocr_paused','0')=='1';self.thumb_job=None;self.thumbnails={};self.thumb_tried=set();self.viewers=[];self.loaded_path='';self.data={};self.ocr_started=False;self.ocr_rescan=False;self.loaded_stamp=None
        self.ocr_button=QPushButton('OCR local');self.ocr_button.setIcon(icon('scan-text',16));self.ocr_button.setToolTip('Pausar o reanudar el índice de texto de imágenes');self.ocr_button.clicked.connect(self.toggle_ocr);self.ocr_button.hide();owner.layout().itemAt(0).layout().insertWidget(3,self.ocr_button)
        self.preview_tools=QWidget();row=QHBoxLayout(self.preview_tools);row.setContentsMargins(0,0,0,0);row.setSpacing(4);self.look=button('Vista ampliada',self.quicklook,symbol='eye');row.addWidget(self.look);row.addWidget(button('Abrir con…',self.open_with,symbol='external-link'));row.addStretch();self.preview_tools.hide();owner.inspector.layout().insertWidget(owner.inspector.layout().count()-2,self.preview_tools)
        self.thumb_timer=QTimer(owner);self.thumb_timer.setSingleShot(True);self.thumb_timer.setInterval(100);self.thumb_timer.timeout.connect(self.load_thumbnails);owner.results.verticalScrollBar().valueChanged.connect(lambda *_:self.thumb_timer.start() if owner.mode=='files' else None)
    def catalog_ready(self,files):
        self.catalog=[(fold(name),path,fold(relative),file_kind(path)) for name,path,relative in files]
        downloads=str(Path.home()/'Downloads')+'/'
        self.catalog.sort(key=lambda r:(not r[1].startswith(downloads),len(r[1])))
        signature=(len(files),hash(tuple(path for _,path,_ in files)));changed=signature!=self.catalog_signature;self.catalog_signature=signature
        if changed and self.ocr_job and self.ocr_job.isRunning():self.ocr_rescan=True;self.ocr_job.requestInterruption()
        if self.ocr_started and not self.paused and not self.w.test:QTimer.singleShot(0,self.start_ocr)
    def enter(self):
        self.filter='Todos';self.w.filter_button.setText('Todos  ⌄');self.w.filter_button.show();self.ocr_button.show();self.w.search.setPlaceholderText('Buscar archivos, rutas o texto en imágenes…')
        if not self.catalog and self.w.files:self.catalog_ready(self.w.files)
        self.ocr_started=True
        if not self.w.test:QTimer.singleShot(300,self.start_ocr)
        self.render()
    def leave(self):self.ocr_button.hide();self.preview_tools.hide()
    def start_ocr(self):
        if self.paused or (self.ocr_job and self.ocr_job.isRunning()):return
        paths=[path for _,path,_,kind in self.catalog if kind=='image']
        if not paths:return
        self.ocr_rescan=False;self.ocr_job=FileOCRIndexer(paths,self.cache.root);self.ocr_job.finished.connect(self.ocr_finished);self.ocr_job.updated.connect(self.ocr_updated);self.ocr_job.progress.connect(self.ocr_progress);self.ocr_job.start()
        current=self.w.current()
        if current and current.get('kind')=='file' and current.get('file_kind')=='image':self.ocr_job.prioritize(current['path'])
    def ocr_finished(self):
        if self.ocr_rescan and not self.paused:QTimer.singleShot(0,self.start_ocr)
    def ocr_progress(self,done,total):
        self.ocr_done=done;self.ocr_total=total;self.ocr_button.setText('OCR pausado' if self.paused else f'OCR {done:,}/{total:,}' if done<total else 'OCR actualizado')
    def ocr_updated(self,path,done,total):
        self.ocr_progress(done,total)
        if self.w.mode=='files':
            current=self.w.current()
            if current and current.get('path')==path:self.update_metadata()
            if self.w.search.text().strip():self.render()
    def toggle_ocr(self):
        self.paused=not self.paused;self.w.store.set('file_ocr_paused','1' if self.paused else '0')
        if self.paused and self.ocr_job:self.ocr_job.requestInterruption()
        if not self.paused:
            if self.ocr_job and self.ocr_job.isRunning():self.ocr_job.finished.connect(self.resume_after_stop)
            else:self.start_ocr()
        self.ocr_progress(self.ocr_done,self.ocr_total)
    def resume_after_stop(self):
        if not self.paused:self.start_ocr()
    def choose_filter(self,value):self.filter=value;self.w.filter_button.setText(value+'  ⌄');self.render()
    def render(self):
        w=self.w;q=fold(w.search.text().strip());terms=q.split();ocr_matches=self.cache.search(q) if q else set();types={'Imágenes':'image','Vídeos':'video','Audio':'audio','Documentos':'document','Código':'code','Otros':'other'};matches=[];filter_kind=types.get(self.filter)
        selected=w.current();previous=selected.get('path') if selected else '';scroll=w.results.verticalScrollBar().value()
        for record in self.catalog:
            name,path,relative,kind=record
            if filter_kind and kind!=filter_kind:continue
            by_name=not terms or all(t in relative for t in terms)
            if terms and not by_name and path not in ocr_matches:continue
            matches.append((record,not by_name))
        if q:matches.sort(key=lambda r:(r[1],not r[0][0].startswith(q),len(r[0][1])))
        total=len(matches);rows=[];home=str(Path.home())
        # Build paths, icons and display strings only for the visible result limit.
        for (name,path,relative,kind),ocr_match in matches[:200]:
            p=Path(path);rows.append(dict(kind='file',file_kind=kind,title=p.name,subtitle=str(p.parent).replace(home,'~'),path=path,icon={'image':'image','video':'circle-play','audio':'volume-2','code':'file-code'}.get(kind,'file-text'),tag=LABELS[kind],ocr_match=ocr_match))
        w.results.blockSignals(True);w.results.clear()
        for row in rows:
            cached=self.cache.get(row['path']) if row['file_kind']=='image' else None
            if row['path'] in self.thumbnails:row['thumbnail']=self.thumbnails[row['path']]
            elif cached and cached.get('thumb'):
                pix=QPixmap.fromImage(QImage.fromData(cached['thumb']));self.thumbnails[row['path']]=pix;row['thumbnail']=pix
            if row['ocr_match']:row['subtitle']='Texto en imagen · '+row['subtitle']
            item=QListWidgetItem();item.setData(Qt.UserRole,row);item.setToolTip(row['path']);w.results.addItem(item)
            if row['path']==previous:w.results.setCurrentItem(item)
        if w.results.currentRow()<0:w.results.setCurrentRow(0)
        w.results.verticalScrollBar().setValue(scroll);w.results.blockSignals(False);w.heading.setText(self.filter if self.filter!='Todos' else 'ARCHIVOS Y CONTENIDO');w.results.setVisible(bool(rows));w.empty.setVisible(not rows);w.empty.setText('No hay resultados. El OCR se amplía mientras se indexan las imágenes.');w.status.setText(f'{total:,} resultados'+(' · mostrando 200' if total>200 else ''));self.preview();self.thumb_timer.start()
    def load_thumbnails(self):
        if self.w.mode!='files' or (self.thumb_job and self.thumb_job.isRunning()):return
        item=self.w.results.itemAt(QPoint(10,10));start=max(0,self.w.results.row(item)) if item else 0;paths=[]
        for i in range(start,min(start+9,self.w.results.count())):
            r=self.w.results.item(i).data(Qt.UserRole)
            if r.get('file_kind')=='image' and r['path'] not in self.thumbnails and r['path'] not in self.thumb_tried:paths.append(r['path']);self.thumb_tried.add(r['path'])
        if paths:self.thumb_job=ThumbnailBatch(paths);self.thumb_job.ready.connect(self.thumbnails_ready);self.thumb_job.start()
    def thumbnails_ready(self,rows):
        if not isValid(self.w) or not isValid(self.w.results):return
        for path,image in rows:self.thumbnails[path]=QPixmap.fromImage(image)
        if self.w.mode!='files':return
        for i in range(self.w.results.count()):
            item=self.w.results.item(i);row=item.data(Qt.UserRole)
            if row['path'] in self.thumbnails:row['thumbnail']=self.thumbnails[row['path']];item.setData(Qt.UserRole,row)
    def preview(self):
        w=self.w;r=w.current();self.preview_tools.setVisible(bool(r));w.calc_result.hide();w.preview_title.show()
        if not r or r.get('kind')!='file':self.preview_tools.hide();return
        path=r['path'];kind=r['file_kind'];w.go.setText('Editar en Vim  ↵' if kind=='code' or (kind=='document' and is_text_file(path)) else 'Abrir  ↵');self.look.setText('Reproducir / vista previa' if kind in ('video','audio') else 'Vista ampliada');self.look.setEnabled(kind!='other' or is_text_file(path))
        try:
            stat=Path(path).stat();stamp=(stat.st_mtime_ns,stat.st_size)
        except OSError:stamp=None
        if path==self.loaded_path and self.data and stamp==self.loaded_stamp:self.update_metadata();return
        self.loaded_stamp=stamp;self.loaded_path=path;self.data={};w.preview_path=path;w.picture.hide();w.body.show();w.body.setPlainText('Cargando vista previa…');w.preview_title.setText(r['title']);w.metadata.clear()
        if kind=='image' and self.ocr_job and not self.paused:self.ocr_job.prioritize(path)
        QTimer.singleShot(80,lambda p=path:self.start_preview(p))
    def start_preview(self,path):
        if not isValid(self.w) or not isValid(self.w.body):return
        w=self.w
        if w.mode!='files' or path!=w.preview_path or len(w.jobs)>=2 or any(j.path==path for j in w.jobs):return
        job=FilePreviewJob(path);w.jobs.append(job);job.ready.connect(self.ready);job.finished.connect(lambda j=job:w.finish_job(j) if isValid(w) and isValid(w.body) else j.deleteLater());job.start()
    def ready(self,path,data):
        if not isValid(self.w) or not isValid(self.w.body):return
        if path!=self.w.preview_path or self.w.mode!='files':return
        self.loaded_path=path;self.data=data;w=self.w;image=data.get('image');w.body.setPlainText(data.get('text',''));w.body.setFont(QFont('DejaVu Sans Mono' if data['kind'] in ('code','document') else 'Inter',10));w.body.show();w.picture.hide()
        if image is not None and not image.isNull():w.show_image(image);self.thumbnails[path]=QPixmap.fromImage(image.scaled(96,72,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        self.update_metadata()
    def update_metadata(self):
        w=self.w;r=w.current()
        if not r or r.get('kind')!='file':return
        meta=self.data.get('meta',{});rows=[('Tipo',LABELS[r['file_kind']]),('Tamaño',human_size(meta.get('size',0)))]
        if meta.get('width'):rows.append(('Dimensiones',f'{meta["width"]} × {meta["height"]}'))
        if meta.get('duration'):rows.append(('Duración',duration_label(meta['duration'])))
        if meta.get('codec_name'):rows.append(('Códec',meta['codec_name']))
        if meta.get('pages'):rows.append(('Páginas',meta['pages']))
        if meta.get('modified'):rows.append(('Modificado',dt.datetime.fromtimestamp(meta['modified']).strftime('%d/%m/%Y %H:%M')))
        if r['file_kind']=='image':
            cached=self.cache.get(r['path']);rows.append(('Búsqueda por texto','No aplica · imagen vectorial' if Path(r['path']).suffix.lower()=='.svg' else 'Disponible' if cached and cached['ocr'] else cached['status'] if cached else 'Pendiente de indexar'))
        w.metadata.setText(w.table(rows));w.metadata.setToolTip(r['path'])
    def path(self):
        r=self.w.current()
        if r and r['kind']=='file':return r['path']
        if r and r['kind']=='clip' and r['clip_kind']=='image':return str(self.w.image_path(r))
        return None
    def quicklook(self):
        path=self.path()
        if not path:return
        from file_viewer import FileViewer
        self.viewers=[v for v in self.viewers if v.isVisible() or (v.job and v.job.isRunning())];viewer=FileViewer(path,self.w);self.viewers.append(viewer);viewer.show()
    def open_with(self):
        path=self.path()
        if not path:return
        entries=[]
        try:
            import gi
            gi.require_version('Gio','2.0');from gi.repository import Gio
            content_type=Gio.content_type_guess(path,None)[0]
            for app in Gio.AppInfo.get_all_for_type(content_type):
                desktop=Gio.DesktopAppInfo.new(app.get_id()) if app.get_id() else None
                if desktop:entries.append((app.get_display_name(),'',lambda f=desktop.get_filename(),p=path:launch(['gio','launch',f,p])))
        except (ImportError,ValueError):pass
        if not entries:entries=[('Aplicación predeterminada','',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(path)))]
        from enhanced import SearchMenu
        self.w.popup=SearchMenu(self.w,entries,'Abrir con…');self.w.popup.present(self.w.action_button)
    def copy_file(self):
        path=self.path()
        if not path:return
        mime=QMimeData();url=QUrl.fromLocalFile(path);mime.setUrls([url]);mime.setData('x-special/gnome-copied-files',('copy\n'+url.toString()).encode());self.w.ignore_clip=True;self.w.clipboard.setMimeData(mime);QTimer.singleShot(150,lambda:setattr(self.w,'ignore_clip',False));self.w.hide()
    def copy_image(self):
        path=self.path()
        if not path:return
        image,_=read_image(path,100000)
        if image.isNull():QMessageBox.information(self.w,'Copiar imagen','No se pudo decodificar la imagen. Puedes copiar el archivo.');return
        self.w.copy(image=image)
    def save_copy(self):
        path=self.path()
        if not path:return
        source=Path(path);dest,_=QFileDialog.getSaveFileName(self.w,'Guardar una copia',str(source.with_name(source.stem+' - copia'+source.suffix)))
        if dest and Path(dest).absolute()!=source.absolute():
            try:shutil.copy2(source,dest)
            except OSError as e:QMessageBox.information(self.w,'Guardar copia',str(e))
    def actions(self):
        r=self.w.current();path=r['path'];kind=r['file_kind'];entries=[(LABELS[kind],'section',None)]
        if kind!='other' or is_text_file(path):entries.append(('Vista previa' if kind not in ('video','audio') else 'Previsualizar y reproducir','Ctrl + Espacio',self.quicklook))
        if kind=='image':entries.append(('Copiar imagen','',self.copy_image))
        if kind=='code' or (kind=='document' and is_text_file(path)):entries.append(('Editar en Vim','Enter',self.w.edit_in_vim))
        entries += [('Abrir con…','',self.open_with),('Archivo','section',None),('Copiar archivo','',self.copy_file),('Guardar una copia…','',self.save_copy),('Mostrar carpeta','',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))),('Copiar ruta','',lambda:self.w.copy(path))]
        return entries

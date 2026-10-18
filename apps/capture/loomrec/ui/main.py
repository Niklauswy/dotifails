"""Spanish-first native recorder, project editor and local library."""
from pathlib import Path
from datetime import datetime
import json
import os
import shutil
import sys
import uuid
import hashlib
import threading
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QProcess, QUrl, QRect
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut, QPixmap, QColor
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QGridLayout,
    QPushButton,QLabel,QComboBox,QSpinBox,QDoubleSpinBox,QCheckBox,QLineEdit,QListWidget,QListWidgetItem,
    QStackedWidget,QSplitter,QTabWidget,QFileDialog,QMessageBox,QInputDialog,QProgressBar,QSlider,
    QDialog,QDialogButtonBox,QScrollArea,QSystemTrayIcon,QMenu,QGroupBox,QSizePolicy)
from ..capture import CaptureConfig,CaptureSession,recover_project
from ..devices import discover,visible_window_rect
from ..render import RenderJob
from ..editing import Editor
from ..library import Library
from ..videolibrary import VideoLibrary,preferences,save_preferences
from ..integration import Concentration,theme_id,GlobalKeys,shortcut_settings
from .widgets import RegionPicker,Waveform
from .player import Player
from .meters import AudioMeter
from .components import ComboBox as QComboBox,CheckBox as QCheckBox,SpinBox as QSpinBox,DoubleSpinBox as QDoubleSpinBox


class Task(QThread):
    result=Signal(object); failed=Signal(str)
    def __init__(self,fn,parent=None): super().__init__(parent); self.fn=fn
    def run(self):
        try: self.result.emit(self.fn())
        except Exception as exc: self.failed.emit(str(exc))


def button(text,callback,layout):
    from .components import SoftButton
    b=SoftButton(text); b.clicked.connect(callback); layout.addWidget(b); return b


def number(low,high,value,decimals=2):
    w=QDoubleSpinBox(); w.setRange(low,high); w.setDecimals(decimals); w.setValue(value); return w


class Window(QMainWindow):
    def __init__(self,library=None,probe_devices=True):
        super().__init__(); self.library=library or VideoLibrary(); self.editor=None; self.session=None; self.media_path=None;self.metadata_cancel=threading.Event();self.active_metadata=0; self.scan_generation=0;self.library_entries=[];self.import_cancel=None;self._fullscreen=False
        self.finalization_path=None;self._finalization_state=None;self.job=None; self.preview_revision=-1; self.position=0; self.tasks=[]; self.discard=False; self.viewing=False
        self.analysis=None; self._job_cancel_pending=False; self.capture_pending=False; self.keys=None; self.concentration=Concentration(); self.countdown_timer=QTimer(self)
        self.countdown_timer.timeout.connect(self.countdown_tick)
        self.setWindowTitle(self.tr('Wysun Recorder · Grabador local')); self.resize(1180,790)
        self.stack=QStackedWidget()
        from .jobs import JobPanel
        central=QWidget();column=QVBoxLayout(central);column.setContentsMargins(0,0,0,0);column.setSpacing(0)
        self.job_panel=JobPanel(self.cancel_current_job);column.addWidget(self.job_panel);column.addWidget(self.stack,1);self.setCentralWidget(central)
        from .finalization import FinalizationPanel
        self.finalization_panel=FinalizationPanel(lambda:self.guard(self.cancel_finalization),lambda:self.guard(self.retry_finalization),self);column.insertWidget(1,self.finalization_panel)
        self.make_library(); self.make_setup(); self.make_editor(); self.make_tray()
        self.stack.currentChanged.connect(lambda _:self.selection_feedback())
        self.quick_mode=False;self.window_target=None
        from .quick import QuickBar
        self.quick=QuickBar(self)
        from .capture_feedback import Countdown,RecordingIndicator,load_countdown,save_countdown
        from .camera_preview import CameraPreview
        self.camera_preview=CameraPreview();self.camera_preview_layout.addWidget(self.camera_preview);self.camera_preview.hide()
        self.camera.currentIndexChanged.connect(self.camera_selected)
        self.countdown.setValue(load_countdown());self.countdown.valueChanged.connect(lambda value:self.guard(lambda:save_countdown(value)))
        self.countdown_overlay=Countdown(self.cancel_countdown);self.recording_indicator=RecordingIndicator()
        self._indicator_rect=None
        self.selection_timer=QTimer(self);self.selection_timer.setSingleShot(True);self.selection_timer.setInterval(0);self.selection_timer.timeout.connect(self.selection_feedback)
        for spin in self.rect:
            spin.valueChanged.connect(self.update_indicator_hint);spin.valueChanged.connect(lambda _:self.selection_timer.start())
        self.capture_modes.buttonToggled.connect(lambda *_:self.selection_timer.start())
        self.update_indicator_hint()
        QApplication.instance().screenRemoved.connect(lambda _:self.relayout_indicator())
        def watch_screen(screen):
            screen.geometryChanged.connect(lambda _:self.relayout_indicator());self.relayout_indicator()
        QApplication.instance().screenAdded.connect(watch_screen)
        for screen in QApplication.screens():screen.geometryChanged.connect(lambda _:self.relayout_indicator())
        self.timer=QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(300)
        self.shortcut('Ctrl+Z',self.undo); self.shortcut('Ctrl+Shift+Z',self.redo)
        self.shortcut('Ctrl+S',lambda:self.notice(self.tr('Los cambios ya se guardan automáticamente')))
        self.shortcut('Ctrl+Shift+R',self.pause_capture); self.shortcut('Ctrl+Shift+S',self.stop_capture)
        play_key=QShortcut(QKeySequence('Space'),self.player.parentWidget());play_key.setContext(Qt.WidgetWithChildrenShortcut);play_key.activated.connect(self.toggle_playback)
        for key,callback in [('M',self.player.toggle_mute),('F',self.toggle_fullscreen)]:
            shortcut=QShortcut(QKeySequence(key),self.player.parentWidget());shortcut.setContext(Qt.WidgetWithChildrenShortcut);shortcut.activated.connect(callback)
        self.shortcut('Escape',lambda:self.toggle_fullscreen() if self._fullscreen else None)
        for key,delta in [('Left',-5),('Right',5)]:
            shortcut=QShortcut(QKeySequence(key),self.player);shortcut.setContext(Qt.WidgetWithChildrenShortcut);shortcut.activated.connect(lambda d=delta:self.player.seek(max(0,min(self.player.duration,self.position+d))))
        self.player.setFocusPolicy(Qt.StrongFocus);self.player.surface.setFocusPolicy(Qt.StrongFocus)
        self.seek.setToolTip(self.tr('Arrastra para buscar. Con el video enfocado: ← / → saltan 5 segundos.'))
        prefs=preferences()
        from .cursor_settings import CursorOptions
        self.cursor_options=CursorOptions(self,prefs,lambda **values:self.guard(lambda:save_preferences(**values)))
        self.audio_selection_ids=dict(prefs.get('audio_sources',{}));self.audio_selection_names=dict(prefs.get('audio_source_names',{}));self._restoring_audio=False;self._devices_busy=False
        for kind,combo in [('mic',self.mic),('system',self.system)]:combo.currentIndexChanged.connect(lambda _,k=kind,c=combo:self.remember_audio(k,c))
        self.player.set_volume(prefs.get('playback_volume',80));self.player.set_speed(prefs.get('playback_speed',1.))
        self.player.muted=bool(prefs.get('playback_muted',False));self.player_state()
        self.speed.setCurrentIndex(max(0,self.speed.findData(self.player.speed)))
        self.playback_save=QTimer(self);self.playback_save.setSingleShot(True);self.playback_save.setInterval(500)
        self.playback_save.timeout.connect(lambda:self.guard(lambda:save_preferences(playback_volume=self.player.volume,playback_speed=self.player.speed,playback_muted=self.player.muted)))
        self.volume.valueChanged.connect(lambda _:self.playback_save.start());self.speed.currentIndexChanged.connect(lambda _:self.playback_save.start());self.mute_button.clicked.connect(lambda:self.playback_save.start())
        for key,combo in [('quality',self.quality),('fps',self.fps)]:
            index=combo.findData(prefs.get(key))
            if index>=0:combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(lambda _,k=key,c=combo:self.guard(lambda:save_preferences(**{k:c.currentData()})))
        self.quiet.setChecked(prefs.get('quiet',True));self.quiet.toggled.connect(lambda value:self.guard(lambda:save_preferences(quiet=value)))
        from .settings import build
        build(self)
        self.items.verticalScrollBar().valueChanged.connect(lambda _:self.load_visible_metadata())
        self.refresh_library()
        if probe_devices:
            try:self.concentration.recover()
            except Exception as exc:self.notice(self.tr('No se pudo restaurar concentración previa: ')+str(exc))
            self.refresh_devices()
        if os.environ.get('LOOMREC_START_RECORDING')=='1':self.stack.setCurrentWidget(self.setup_page)

    def update_indicator_hint(self,*_):
        from .capture_feedback import indicator_geometry
        _,badge=indicator_geometry([spin.value() for spin in self.rect],[screen.geometry().getRect() for screen in QApplication.screens()])
        self.indicator_hint.setText(self.tr('Borde y distintivo fuera del vídeo.') if badge else self.tr('Distintivo oculto: no hay espacio fuera del área grabada. En pantalla completa X11 no puede excluir un indicador; usa los atajos para pausar o terminar.'))

    def clear_idle_selection(self):
        if not hasattr(self,'recording_indicator') or self.session or self.capture_pending:return
        if hasattr(self,'selection_timer'):self.selection_timer.stop()
        if self.recording_indicator.state=='selected':self.recording_indicator.hide()
    def selection_feedback(self):
        if not hasattr(self,'recording_indicator') or self.session or self.capture_pending:return
        visible=self.quick.isVisible() or self.stack.currentWidget()==self.setup_page and self.isVisible()
        region=self.capture_modes.buttons()[1].isChecked() and self.window_target is None
        rect=[spin.value() for spin in self.rect]
        valid=rect[2]>=16 and rect[3]>=16 and QApplication.primaryScreen().virtualGeometry().contains(QRect(*rect))
        if not (visible and region and valid):
            self.clear_idle_selection();return
        self.recording_indicator.select(rect,[s.geometry().getRect() for s in QApplication.screens()])
    def relayout_indicator(self):
        if self.recording_indicator.rect is None:return
        if not self.session and not self.capture_pending:self.selection_feedback();return
        rect=self._indicator_rect if self.session else [spin.value() for spin in self.rect]
        if rect:self.recording_indicator.relayout(rect,[s.geometry().getRect() for s in QApplication.screens()])
    def camera_selected(self,*_):
        if not hasattr(self,'camera_preview'):return
        device=self.camera.currentData()
        self.camera_preview.setVisible(bool(device))
        if self.session or self.capture_pending:self.camera_preview.stop();return
        self.camera_preview.set_device(device)

    def showEvent(self,event):
        super().showEvent(event)
        if hasattr(self,'selection_timer'):self.selection_timer.start()
    def hideEvent(self,event):
        self.clear_idle_selection()
        if hasattr(self,'camera_preview'):self.camera_preview.stop()
        super().hideEvent(event)

    def stop_meters(self):
        self._meter_request=getattr(self,'_meter_request',0)+1
        self.mic_meter.stop();self.system_meter.stop()
    def ensure_keys(self):
        if not self.keys:
            settings=shortcut_settings()
            actions={'record':lambda:self.guard(self.begin_countdown),'status':self.capture_indicator,'pause':self.pause_capture,'stop':self.stop_capture,'cancel':self.cancel_capture,'rewind':self.rewind_capture}
            self.keys=GlobalKeys({settings[key]:callback for key,callback in actions.items()})
            self.shortcut_label.setText(self.tr('Grabar: ')+settings['record']+self.tr(' · Pausa: ')+settings['pause']+self.tr(' · Terminar: ')+settings['stop']+self.tr(' · Cancelar: ')+settings['cancel']+self.tr(' · Rebobinar: ')+settings['rewind']+self.tr(' · Estado: ')+settings['status'])

    def shortcut(self,key,fn):
        shortcut=QShortcut(QKeySequence(key),self); shortcut.activated.connect(fn)
    def notice(self,text): self.statusBar().showMessage(text,10000)
    def error(self,text):
        box=QMessageBox(QMessageBox.Warning,self.tr('No se pudo completar'),str(text),parent=self)
        accept=box.addButton(self.tr('Entendido'),QMessageBox.AcceptRole);accept.setIcon(QIcon());accept.setProperty('primary',True);box.exec()
    def guard(self,fn):
        try: return fn()
        except Exception as exc: self.error(str(exc))
    def task(self,fn,callback):
        t=Task(fn,self); self.tasks.append(t); t.result.connect(callback); t.failed.connect(self.error)
        t.finished.connect(lambda:self.tasks.remove(t)); t.start()

    def make_library(self):
        from .layouts import library
        library(self)

    def stop_metadata(self):
        self.scan_generation+=1;self.metadata_cancel.set()
    def refresh_library(self,*_):
        self.metadata_cancel.set();self.metadata_cancel=threading.Event()
        self.scan_generation+=1;generation=self.scan_generation
        query=self.search.text();trash=self.trash.isChecked()
        def ready(entries):
            if generation!=self.scan_generation:return
            self.library_entries=entries;self.populate_library(entries)
        if isinstance(self.library,VideoLibrary):
            self.path_label.setText(self.tr('Buscando videos…'))
            self.task(lambda:self.library.entries(query,trash),ready)
        else:ready(self.library.entries(query,trash))
    def populate_library(self,entries):
        self.items.clear()
        for entry in entries:
            date=datetime.fromtimestamp(entry.modified).strftime('%d %b %Y · %H:%M')
            duration=self.format_time(entry.duration) if entry.duration else self.tr('Video')
            text=f'{entry.title}\n{date} · {duration}'+(' · '+entry.collection if entry.collection else '')
            if entry.path.name=='project.json':
                from ..videolibrary import finalization_status
                state=finalization_status(entry.path).get('state','none')
                labels={'pending':'Preparando MP4…','running':'Preparando MP4…','ready':'MP4 guardado · editable','error':'MP4 pendiente · reintentar','cancelled':'MP4 pendiente · preparación cancelada'}
                if state in labels:text+=' · '+self.tr(labels[state])
            if entry.error:text+='\n'+self.tr('Requiere recuperación')
            item=QListWidgetItem(text);item.setData(Qt.UserRole,str(entry.path))
            thumb=entry.path.parent/'thumbnail.jpg' if entry.path.name=='project.json' else self.library.thumbnail_path(entry.path)
            if thumb.exists():item.setIcon(QIcon(str(thumb)))
            self.items.addItem(item)
        empty=not entries;self.library_empty.setVisible(empty);self.items.setVisible(not empty)
        self.path_label.setText(self.tr('Papelera · recuperable') if self.trash.isChecked() else self.tr('Videos locales')+f' · {len(entries)}')
        self.empty_title.setText(self.tr('No hay coincidencias') if self.search.text() else self.tr('La papelera está vacía') if self.trash.isChecked() else self.tr('Tus videos aparecerán aquí'))
        self.empty_description.setText(self.tr('Prueba otro título o colección.') if self.search.text() else self.tr('Los videos que elimines aparecerán aquí.') if self.trash.isChecked() else self.tr('Graba desde la barra rápida o guarda un video en tu carpeta Videos.'))
        if isinstance(self.library,VideoLibrary) and not self.trash.isChecked():self.enrich_library(entries[:12],self.scan_generation)
    def load_visible_metadata(self):
        if not isinstance(self.library,VideoLibrary) or self.trash.isChecked() or getattr(self,'metadata_running',False):return
        paths={self.items.item(i).data(Qt.UserRole) for i in range(self.items.count()) if self.items.visualItemRect(self.items.item(i)).intersects(self.items.viewport().rect())}
        self.enrich_library([e for e in self.library_entries if str(e.path) in paths],self.scan_generation)
    def enrich_library(self,entries,generation):
        if not entries or generation!=self.scan_generation or self.session or self.capture_pending or self.job or self.analysis or self.finalization_active():return
        entry,*rest=entries
        if entry.path.name=='project.json':self.enrich_library(rest,generation);return
        library=self.library;cancel=self.metadata_cancel;self.metadata_running=True;self.active_metadata+=1
        def work():
            try:library.enrich(entry,cancel);return library.thumbnail(entry.path,cancel)
            except Exception:return None
        def done(thumb):
            self.active_metadata-=1;self.metadata_running=bool(self.active_metadata)
            if generation!=self.scan_generation:return
            for i in range(self.items.count()):
                item=self.items.item(i)
                if item.data(Qt.UserRole)==str(entry.path):
                    if thumb and thumb.exists():item.setIcon(QIcon(str(thumb)))
                    text=item.text().split('\n');text[1]=datetime.fromtimestamp(entry.modified).strftime('%d %b %Y · %H:%M')+' · '+self.format_time(entry.duration);item.setText('\n'.join(text))
            self.enrich_library(rest,generation)
        self.task(work,done)
    @staticmethod
    def format_time(seconds):
        seconds=max(0,int(seconds));return f'{seconds//3600}:{seconds//60%60:02}:{seconds%60:02}' if seconds>=3600 else f'{seconds//60}:{seconds%60:02}'
    def show_settings(self):
        if self.session or self.capture_pending:return
        self.player.close_media();self.recording_indicator.hide();self.quick.hide_all();self.stack.setCurrentWidget(self.settings_page)
        from .activation import show_and_focus
        show_and_focus(self)
    def change_video_folder(self):
        if self.operation_busy():return
        path=QFileDialog.getExistingDirectory(self,self.tr('Carpeta de videos'),str(getattr(self.library,'videos',self.library.root)))
        if not path:return
        old=str(getattr(self.library,'videos',self.library.root));roots=preferences().get('previous_video_folders',[])
        save_preferences(videos_folder=path,previous_video_folders=list(dict.fromkeys([*roots,old])))
        self.library=VideoLibrary();self.folder_label.setText(path);self.refresh_library()
    def open_shortcuts(self):
        from ..schema import atomic_json
        path=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'loomrec/shortcuts.json'
        if not path.exists():atomic_json(path,shortcut_settings())
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    def open_media(self,path):
        if self.operation_busy():return
        self.media_path=Path(path);self.editor=None;self.preview_revision=-1;self.position=0
        self.set_viewing(True);self.title.setText(self.media_path.stem);self.stack.setCurrentWidget(self.editor_page)
        self.preview_label.setText(self.tr('Archivo original · la reproducción no modifica el video'))
        self.stop_metadata();selected=self.media_path
        def load():
            if selected!=self.media_path or self.stack.currentWidget()!=self.editor_page:return
            if self.active_metadata:QTimer.singleShot(100,load);return
            self.player.load(selected)
        load()
    def edit_selected(self):
        if self.trash.isChecked():return
        path=self.selected_path()
        if path.name=='project.json':self.guard(lambda:self.open_project(path,edit=True))
        else:self.open_media(path);self.enter_editor()
    def toggle_fullscreen(self):
        if self.stack.currentWidget()!=self.editor_page:return
        self._fullscreen=not self._fullscreen
        if self._fullscreen:
            self._was_maximized=self.isMaximized();self.showFullScreen();self.inspector.hide();self.editor_toolbar.hide();self.editor_timeline.hide();self.editor_status.hide()
        else:
            self.showMaximized() if self._was_maximized else self.showNormal();self.set_viewing(self.viewing)
    def player_state(self):
        from .icons import icon
        self.play_button.setIcon(icon('play' if self.player.paused else 'pause','#FFFFFF'))
        self.mute_button.setIcon(icon('muted' if self.player.muted else 'sound'))
        self.mute_button.setToolTip(self.tr('Activar sonido · M') if self.player.muted else self.tr('Silenciar · M'))
        self.volume.blockSignals(True);self.volume.setValue(self.player.volume);self.volume.blockSignals(False)
        self.position_changed(self.position)
    def selected_path(self):
        item=self.items.currentItem()
        if not item: raise ValueError(self.tr('Selecciona un video'))
        return Path(item.data(Qt.UserRole))
    def update_copy_path_action(self):
        items=self.items.selectedItems()
        enabled=len(items)==1 and not self.trash.isChecked() and Path(items[0].data(Qt.UserRole)).is_file()
        if enabled and Path(items[0].data(Qt.UserRole)).name=='project.json':
            from ..videolibrary import finalization_status
            enabled=finalization_status(items[0].data(Qt.UserRole)).get('state') not in ('pending','running')
        self.library_copy_path.setEnabled(enabled)
    def copy_video_path(self):
        if self.stack.currentWidget()!=self.library_page:return
        items=self.items.selectedItems()
        if len(items)!=1:self.notice(self.tr('Selecciona un video'));return
        if self.trash.isChecked():self.notice(self.tr('Restaura el video antes de copiar su ruta'));return
        from ..videolibrary import absolute_video_path
        try:
            selected=Path(items[0].data(Qt.UserRole));changed=False
            if selected.name=='project.json':
                from ..videolibrary import recording_video
                path,changed=recording_video(selected)
                if path is None:
                    self.notice(self.tr('MP4 aún no disponible. Usa Organizar → Preparar MP4.'));return
            else:path=absolute_video_path(selected)
        except (OSError,ValueError,RuntimeError) as exc:
            self.update_copy_path_action();self.notice(self.tr(str(exc)));return
        QApplication.clipboard().setText(str(path));self.notice(self.tr('Ruta copiada · el MP4 guardado no incluye los cambios de edición pendientes') if changed else self.tr('Ruta copiada'))

    def open_selected(self):
        if self.trash.isChecked(): self.notice(self.tr('Restaura el video antes de abrirlo')); return
        path=self.selected_path();self.guard(lambda:self.open_project(path) if path.name=='project.json' else self.open_media(path))
    def open_file(self):
        path,_=QFileDialog.getOpenFileName(self,self.tr('Abrir proyecto'),str(self.library.root),'Proyecto (project.json *.json)')
        if path: self.guard(lambda:self.open_project(path))
    def rename(self):
        def run():
            path=self.selected_path(); title,ok=QInputDialog.getText(self,self.tr('Renombrar'),self.tr('Título'))
            if ok: self.library.rename(path,title); self.refresh_library()
        self.guard(run)
    def organize(self):
        def run():
            path=self.selected_path(); title,ok=QInputDialog.getText(self,self.tr('Organizar'),self.tr('Colección (vacío para quitar)'))
            if ok: self.library.organize(path,title); self.refresh_library()
        self.guard(run)
    def reveal(self): self.guard(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.selected_path().parent))))
    def recover(self):
        def run():
            path=self.selected_path().parent
            self.task(lambda:recover_project(path),lambda _:self.refresh_library())
        self.guard(run)
    def trash_selected(self):
        def run():
            path=self.selected_path()
            if self.trash.isChecked(): self.library.restore(path)
            else: self.library.delete(path)
            self.refresh_library()
        self.guard(run)

    def make_setup(self):
        from .layouts import setup
        setup(self)

    def remember_audio(self,kind,combo):
        if self._restoring_audio:return
        self.audio_selection_ids[kind]=combo.currentData()
        if not combo.currentData(Qt.UserRole+1):self.audio_selection_names[kind]=combo.currentText()
        self.guard(lambda:save_preferences(audio_sources=self.audio_selection_ids,audio_source_names=self.audio_selection_names))
    def refresh_devices(self):
        if self._devices_busy:return
        self._devices_busy=True
        def work():
            try:return discover(),None
            except Exception as exc:return None,str(exc)
        def done(result):
            self._devices_busy=False;data,error=result
            if error:self.preflight.setText(self.tr('No se pudieron actualizar los dispositivos: ')+error)
            else:self.devices_ready(data)
        self.task(work,done)
    def devices_ready(self,data):
        monitor_name=self.monitor.currentText();self.monitor.blockSignals(True);self.monitor.clear()
        for monitor in data['monitors']:self.monitor.addItem(monitor['name'],monitor['rect'])
        index=self.monitor.findText(monitor_name);self.monitor.setCurrentIndex(max(0,index));self.monitor.blockSignals(False)
        if self.capture_modes.buttons()[0].isChecked():self.monitor_changed()
        self._restoring_audio=True
        try:
            for combo,kind in [(self.mic,'mic'),(self.system,'system')]:
                wanted=self.audio_selection_ids.get(kind,combo.currentData());combo.blockSignals(True)
                combo.clear();combo.addItem(self.tr('Desactivado'),None)
                for device in data['audio']:
                    if device['kind']==kind:combo.addItem(device['name'],device['id'])
                index=combo.findData(wanted)
                if wanted is not None and index<0:
                    name=self.audio_selection_names.get(kind,self.tr('Fuente guardada'))
                    combo.addItem(self.tr('No disponible · ')+name,wanted);index=combo.count()-1;combo.setItemData(index,True,Qt.UserRole+1)
                combo.setCurrentIndex(max(0,index));combo.blockSignals(False);combo.currentIndexChanged.emit(combo.currentIndex())
                combo.setToolTip(combo.currentText())
        finally:self._restoring_audio=False
        selected_camera=self.camera.currentData();self.camera.blockSignals(True);self.camera.clear();self.camera.addItem(self.tr('Desactivada'),None)
        for camera in data['cameras']:
            device=Path(camera).name
            try:name=(Path('/sys/class/video4linux')/device/'name').read_text().strip()
            except OSError:name=self.tr('Cámara')
            self.camera.addItem(f'{name} · {device}',camera)
        self.camera.setCurrentIndex(max(0,self.camera.findData(selected_camera)));self.camera.blockSignals(False);self.camera.currentIndexChanged.emit(self.camera.currentIndex())
        missing=any(combo.currentData(Qt.UserRole+1) for combo in (self.mic,self.system))
        self.preflight.setText(self.tr('Una fuente guardada no está disponible. Elige otra o desactívala.') if missing else self.tr('Fuentes restauradas. Puedes comprobar los niveles antes de grabar.'))
        try:self.ensure_keys()
        except (RuntimeError,ValueError,OSError) as exc:self.preflight.setText(str(exc))
    def start_meters(self):
        from ..devices import resolve_system_audio
        if any(combo.currentData(Qt.UserRole+1) for combo in (self.mic,self.system)):
            self.error(self.tr('La fuente guardada no está disponible. Elige otra o desactívala.'));return
        self.stop_meters();request=self._meter_request;selected=self.system.currentData();mic=self.mic.currentData()
        def work():
            try:return resolve_system_audio(selected),None
            except Exception as exc:return None,str(exc)
        def ready(result):
            if request!=self._meter_request or (mic,selected)!=(self.mic.currentData(),self.system.currentData()):return
            source,error=result
            if error:self.error(error);return
            if self.session or self.capture_pending:return
            self.mic_meter.start(self.mic.currentData(),self.mic_gain.value());self.system_meter.start(source,self.system_gain.value())
        self.task(work,ready)
    def monitor_changed(self,*_):
        self.window_target=None
        rect=self.monitor.currentData()
        if rect:
            if hasattr(self,'capture_modes'):self.capture_modes.buttons()[0].setChecked(True)
            for widget,value in zip(self.rect,rect): widget.setValue(value)
            QTimer.singleShot(0,self.selection_feedback)
    def pick_region(self):
        self.recording_indicator.hide();self.quick.hide_all();self.hide(); self.picker=RegionPicker(QApplication.primaryScreen().virtualGeometry())
        def selected(rect):
            self.window_target=None;self.capture_modes.buttons()[1].setChecked(True);self.region_selected(rect)
        self.picker.selected.connect(selected); self.picker.cancelled.connect(self.restore_capture_surface); self.picker.show()
    def region_selected(self,rect):
        for widget,value in zip(self.rect,rect): widget.setValue(value)
        self.restore_capture_surface()
    def restore_capture_surface(self):
        if self.quick_mode:self.quick.present()
        else:self.show()
        self.selection_feedback()
    def pick_window(self):
        self.capture_modes.buttons()[2].setChecked(True)
        from .quick import WindowChooser
        self.recording_indicator.hide();self.quick.hide_all()
        self.window_chooser=WindowChooser(self);self.window_chooser.finished.connect(lambda _:self.restore_capture_surface());self.window_chooser.open()

    def begin_countdown(self):
        if any(combo.currentData(Qt.UserRole+1) for combo in (self.mic,self.system)):raise ValueError(self.tr('Una fuente de audio guardada no está disponible. Selecciona otra o desactívala.'))
        self.stop_metadata()
        if self.session or self.job or self.analysis or self.capture_pending or self.import_cancel or self.finalization_active(): raise ValueError(self.tr('Termina la operación actual primero'))
        if not os.environ.get('DISPLAY'): raise ValueError(self.tr('Se necesita una sesión X11 con DISPLAY'))
        for executable in ('ffmpeg','ffprobe','mpv'):
            if not shutil.which(executable): raise ValueError(self.tr('Falta instalar: ')+executable)
        if self.window_target:
            rect=visible_window_rect(self.window_target)
            for widget,value in zip(self.rect,rect):widget.setValue(value)
        rect=[w.value() for w in self.rect]
        check=CaptureConfig(str(self.library.root),os.environ['DISPLAY'],rect,self.fps.currentData(),self.mic.currentData(),self.system.currentData(),self.camera.currentData(),quality=self.quality.currentData(),auto_finalize=True,output_dir=str(getattr(self.library,'videos',Path.home()/'Videos')),title=self.tr('Grabación ')+datetime.now().strftime('%d-%m-%Y %H-%M-%S'),mic_gain=self.mic_gain.value(),system_gain=self.system_gain.value(),**self.cursor_options.capture_values()); check.validate()
        if shutil.disk_usage(self.library.root).free<512*1024*1024: raise ValueError(self.tr('Libera al menos 512 MiB antes de grabar'))
        screen=QApplication.primaryScreen().virtualGeometry()
        if rect[0]<screen.x() or rect[1]<screen.y() or rect[0]+rect[2]>screen.right()+1 or rect[1]+rect[3]>screen.bottom()+1:
            raise ValueError(self.tr('El área debe estar dentro de la pantalla'))
        self.ensure_keys()
        self.capture_pending=True; self.cursor_options.set_locked(True); self.pending_config=check; self.remaining=self.countdown.value(); self.record.setEnabled(False); self.cancel_count.setEnabled(True)
        from .capture_feedback import indicator_geometry
        screens=[s.geometry().getRect() for s in QApplication.screens()]
        borders,badge=indicator_geometry(rect,screens)
        self.indicator_hint.setText(self.tr('Indicador fuera del vídeo.') if badge else self.tr('Sin espacio seguro para el distintivo: se oculta para no aparecer en el vídeo. Usa los atajos para pausar o terminar.'))
        self.camera_preview.stop()
        self.recording_indicator.present(rect,screens,state='countdown')
        self.countdown_timer.start(1000); self.countdown_tick()
    def countdown_tick(self):
        if self.remaining>0:
            self.preflight.setText(self.tr('Comienza en ')+str(self.remaining))
            self.quick.hide_all();self.hide();self.tray.hide()
            self.recording_indicator.update('countdown',remaining=self.remaining)
            self.countdown_overlay.present(self.remaining,self.pending_config.rect)
            self.remaining-=1;return
        self.countdown_timer.stop(); self.cancel_count.setEnabled(False)
        self.countdown_overlay.hide();self.stop_meters(); self.quick.hide_all(); self.hide(); self.tray.hide(); self.player.close_media()
        # Allow X11/compositor to remove setup and selector before starting capture.
        self.camera_preview.stop(lambda:QTimer.singleShot(500,lambda:self.guard(self.start_capture) if self.capture_pending else None))
    def cancel_countdown(self):
        self.capture_pending=False; self.cursor_options.set_locked(bool(self.session)); self.countdown_timer.stop(); self.record.setEnabled(True); self.cancel_count.setEnabled(False); self.preflight.setText(self.tr('Cuenta cancelada'));self.countdown_overlay.hide();self.restore_capture_surface();self.clear_idle_selection()
    def start_capture(self):
        if self.active_metadata:
            QTimer.singleShot(100,lambda:self.guard(self.start_capture) if self.capture_pending else None);return
        if self.window_target:
            try:
                rect=visible_window_rect(self.window_target)
                if rect!=self.pending_config.rect:raise ValueError(self.tr('La ventana cambió de posición o tamaño. Selecciónala de nuevo.'))
            except Exception:
                self.cancel_countdown();self.restore_capture_surface();raise
        self.capture_pending=False
        self.pending_config.project_dir=str(self.library.new_directory())
        self.session=CaptureSession(self.pending_config); self.discard=False;self._cursor_warning_seen=None
        self.show_paused=False
        self.capture_gains={'mic':self.mic_gain.value(),'system':self.system_gain.value()}
        try:
            if self.quiet.isChecked(): self.concentration.begin(self.pending_config.project_dir)
            self.session.start();self.concentration.watch()
            self._indicator_rect=list(self.pending_config.rect)
            self.recording_indicator.present(self._indicator_rect,[s.geometry().getRect() for s in QApplication.screens()],on_pause=self.pause_capture,on_stop=self.stop_capture)
        except Exception:
            self.session=None; self.recording_indicator.hide(); self.restore_concentration(); self.restore_capture_surface(); self.record.setEnabled(True); raise
        self.tray.setToolTip(self.tr('Wysun Recorder · grabando · menú para pausar o terminar'))
    def pause_capture(self):
        if self.session:
            state=self.session.status()['state']
            if state=='paused':
                self.hide_capture_controls(); self.show_paused=False
                QTimer.singleShot(500,lambda:self.session.resume() if self.session and self.session.status()['state']=='paused' else None)
            else: self.session.pause()
    def stop_capture(self):
        if self.session: self.session.stop()
    def cancel_capture(self):
        if self.capture_pending:self.cancel_countdown();self.tray.show();self.show()
        if self.session:
            self.discard=True; self.session.stop(discard=True)
    def rewind_capture(self):
        if self.session: self.session.rewind(10)
    def capture_indicator(self):
        if self.session:
            self.session.pause()
            self.show_paused=True

    def restore_concentration(self):
        try: self.concentration.restore()
        except Exception as exc: self.error(self.tr('No se pudo restaurar Dunst: ')+str(exc))

    def make_tray(self):
        icon=QPixmap(24,24); icon.fill(QColor('#ce594f'))
        self.tray=QSystemTrayIcon(QIcon(icon),self); self.tray.setToolTip('Wysun Recorder')
        menu=QMenu()
        menu.addAction(self.tr('Pausar / reanudar'),self.pause_capture)
        menu.addAction(self.tr('Detener y guardar MP4'),self.stop_capture)
        menu.addAction(self.tr('Cancelar a papelera'),self.cancel_capture)
        menu.addSeparator(); menu.addAction(self.tr('Abrir Wysun Recorder'),self.show_safe)
        self.tray.setContextMenu(menu); self.tray.show()
        self.tray.activated.connect(lambda reason:self.show_safe() if reason==QSystemTrayIcon.DoubleClick else None)
    def show_safe(self):
        if self.session:
            self.notice(self.tr('Detén o pausa desde la bandeja antes de abrir el editor')); return
        self.show(); self.raise_(); self.activateWindow()

    def make_editor(self):
        from .layouts import editor
        editor(self)

    def back_library(self):
        if self._fullscreen:self.toggle_fullscreen()
        self.player.close_media();self.recording_indicator.hide();self.refresh_library(); self.stack.setCurrentWidget(self.library_page)
    def open_project(self,path,*,edit=False):
        if self.operation_busy(): return
        path=Path(path)
        if (path.parent/'capture.json').exists():
            capture=CaptureSession.attach(path.parent)
            state=capture.status()['state']
            if state in ('starting','recording','paused','stopping'):
                if self.session is None:
                    self.session=capture;self.discard=False;self.capture_gains={}
                elif self.session.root.resolve()!=capture.root.resolve():
                    raise ValueError(self.tr('Termina la grabación actual antes de abrir otra captura activa.'))
                self.player.close_media();self.camera_preview.stop();self.quick_mode=False;self.quick.hide_all()
                self.stack.setCurrentWidget(self.setup_page);self.capture_presentation(state)
                self.preflight.setText(self.tr('Grabación en pausa. Reanuda o termina para ver el video.'))
                if state=='paused':
                    from .activation import show_and_focus
                    show_and_focus(self)
                else:
                    self.hide_capture_controls()
                    if state in ('starting','recording'):self.session.pause();self.show_paused=True
                try:self.ensure_keys()
                except (RuntimeError,ValueError,OSError) as exc:self.notice(str(exc))
                return
        if not edit and (path.parent/'capture.json').exists():
            from ..videolibrary import finalization_status,recording_video
            publication=finalization_status(path)
            if publication.get('state')!='none':
                self.finalization_path=path;self._finalization_state=None
                output,changed=recording_video(path)
                if output:
                    self._finalization_state='ready';self.open_media(output);self.finalization_panel.update_status(publication)
                    if changed:self.notice(self.tr('Mostrando el MP4 guardado. Los cambios de edición aún no están exportados.'))
                    return
                if publication.get('state') in ('pending','running','error','cancelled'):
                    self.stack.setCurrentWidget(self.library_page);self.poll_finalization();return
        if edit and self.finalization_path==path:self._finalization_state='ready'
        self.media_path=None;self.player.close_media(); self.editor=Editor(path); self.preview_revision=-1
        self.refresh_editor(); self.stack.setCurrentWidget(self.editor_page)
        self.set_viewing(not edit)
        from .activation import show_and_focus
        show_and_focus(self)
        if not edit:self.prepare_playback()

    def set_viewing(self,viewing):
        self.viewing=viewing
        for widget in [self.editor_toolbar,self.inspector,self.editor_timeline,self.editor_status,self.watch_video,*self.edit_actions]:widget.setVisible(not viewing)
        self.edit_video.setVisible(viewing)
        if not viewing:self.editor_split.setSizes([720,300])
        if self.editor:self.title.setText(self.editor.project.title+('' if viewing else ' · '+self.tr('Guardado')))

    def enter_editor(self):
        if self.operation_busy():return
        if self.media_path:
            if self.finalization_path:
                from ..videolibrary import recording_video
                output,_=recording_video(self.finalization_path)
                if output==self.media_path:self.open_project(self.finalization_path,edit=True);return
            import threading
            self.import_cancel=threading.Event();path=self.media_path;self.player.close_media()
            dialog=QProgressBar();dialog.setRange(0,0)
            self.import_dialog=QDialog(self);self.import_dialog.setWindowTitle(self.tr('Preparando edición'))
            layout=QVBoxLayout(self.import_dialog);layout.addWidget(QLabel(self.tr('Guardando una copia privada del original…')));layout.addWidget(dialog)
            cancel=QPushButton(self.tr('Cancelar'));cancel.clicked.connect(self.import_cancel.set);layout.addWidget(cancel);self.import_dialog.rejected.connect(self.import_cancel.set);self.import_dialog.show()
            def work():
                try:return self.library.create_edit(path,self.import_cancel),None
                except Exception as exc:return None,str(exc)
            def ready(result):
                self.import_dialog.close();self.import_cancel=None
                destination,error=result
                if error:self.notice(error)
                else:self.open_project(destination,edit=True)
            self.task(work,ready);return
        if self.editor:self.set_viewing(False)

    def show_playback(self):
        if not self.editor or self.operation_busy():return
        self.set_viewing(True);self.prepare_playback()

    def playback_path(self):
        # Key the rendered video by the complete saved edit, including audio/overlays.
        from ..render import PIPELINE_VERSION,render_profile_signature
        profile=json.dumps([PIPELINE_VERSION,render_profile_signature('preview')],sort_keys=True,default=str).encode()
        capture=self.editor.path.parent/'capture.json'
        capture_profile=capture.read_bytes() if capture.is_file() else b''
        key=hashlib.sha256(profile+b'\0'+capture_profile+b'\0'+self.editor.path.read_bytes()).hexdigest()
        return self.editor.path.parent/'.preview'/('playback-'+key+'.mp4')

    def prepare_playback(self):
        if not self.editor.project.clips:
            self.preview_label.setText(self.tr('Esta grabación no tiene clips para reproducir.'));return
        if self.preview_revision==self.editor.revision:return
        output=self.playback_path()
        if output.is_file():
            self.preview_revision=self.editor.revision
            self.preview_label.setText(self.tr('Video listo · pulsa reproducir'));self.player.load(output);return
        self.render(False)

    def toggle_playback(self):
        if self.stack.currentWidget()!=self.editor_page or (not self.editor and not self.media_path) or self.job or self.analysis:return
        if self.media_path:self.player.toggle();return
        if self.preview_revision!=self.editor.revision:
            self.guard(self.prepare_playback);return
        self.player.toggle()
    def playback_failed(self,message):
        self.preview_revision=-1;self.preview_label.setText(message);self.error(message)
    def refresh_editor(self):
        if not self.editor: return
        project=self.editor.project; selected=max(0,self.clips.currentRow())
        self.title.setText(project.title+' · '+self.tr('Guardado'))
        self.clips.clear()
        for i,c in enumerate(project.clips): self.clips.addItem(self.tr('Clip ')+f'{i+1:02} · {c.out_s-c.in_s:.2f} s')
        self.clips.setCurrentRow(min(selected,len(project.clips)-1))
        self.waveform.clips=[c.out_s-c.in_s for c in project.clips]
        self.seek.setRange(0,int(project.duration*1000)); self.audio_sources.clear()
        for source in project.sources:
            if source.kind in ('mic','system'): self.audio_sources.addItem(('Micrófono' if source.kind=='mic' else 'Sistema')+' · '+str(len([s for s in project.sources[:project.sources.index(source)] if s.kind==source.kind])+1),source.id)
        self.preview_label.setText(self.tr('Edición guardada · genera vista previa para actualizar reproducción'))
        self.preview_revision=-1; self.player.close_media();self.position_changed(0)
    def edit(self,fn):
        if self.operation_busy(): return
        if not self.editor: return
        fn(); self.refresh_editor()
    def undo(self): self.guard(lambda:self.edit(self.editor.undo) if self.editor and not self.viewing and self.stack.currentWidget()==self.editor_page else None)
    def redo(self): self.guard(lambda:self.edit(self.editor.redo) if self.editor and not self.viewing and self.stack.currentWidget()==self.editor_page else None)
    def clip_index(self):
        i=self.clips.currentRow()
        if i<0: raise ValueError(self.tr('Selecciona un clip'))
        return i
    def clip_selected(self,index):
        if self.editor and 0<=index<len(self.editor.project.clips):
            c=self.editor.project.clips[index]; self.trim_start.setValue(c.in_s); self.trim_end.setValue(c.out_s)
    def trim_clip(self): self.edit(lambda:self.editor.trim(self.clip_index(),self.trim_start.value(),self.trim_end.value()))
    def split_clip(self):
        i=self.clip_index(); c=self.editor.project.clips[i]
        start=sum(c.out_s-c.in_s for c in self.editor.project.clips[:i])
        self.edit(lambda:self.editor.split(i,c.in_s+self.position-start))
    def delete_clip(self): self.edit(lambda:self.editor.delete(self.clip_index()))
    def join_clip(self): self.edit(lambda:self.editor.join(self.clip_index()))
    def move_clip(self,direction): self.guard(lambda:self.edit(lambda:self.editor.move(self.clip_index(),self.clip_index()+direction)))
    def audio_selected(self,*_):
        if self.editor:
            source=next((s for s in self.editor.project.sources if s.id==self.audio_sources.currentData()),None)
            if source: self.gain.setValue(source.gain)
    def apply_gain(self):
        if self.audio_sources.currentData(): self.edit(lambda:self.editor.gain(self.audio_sources.currentData(),self.gain.value()))
    def position_changed(self,position):
        self.position=position;duration=self.player.duration or (self.editor.project.duration if self.editor else 0);self.clock.setText(self.format_time(position)+' / '+self.format_time(duration))
        if not self.seek.isSliderDown():self.seek.setValue(int(position*1000))
        self.waveform.position=position;self.waveform.update()
    def render(self,export):
        self.stop_metadata()
        if self.active_metadata:
            editor=self.editor
            QTimer.singleShot(100,lambda:self.guard(lambda:self.render(export)) if self.editor is editor else None);return
        if not self.editor or not self.editor.project.clips: raise ValueError(self.tr('El proyecto no tiene clips'))
        if self.operation_busy(): return
        self.player.close_media()
        if export:
            path,_=QFileDialog.getSaveFileName(self,self.tr('Exportar sin sobrescribir'),str(getattr(self.library,'videos',self.library.root)/(self.editor.project.title.replace('/','-')+'.mp4')),'MP4 (*.mp4)')
            if not path: return
            output=Path(path)
            if output.exists(): raise FileExistsError(self.tr('Elige un nombre nuevo: no se sobrescriben archivos'))
        else:
            cache=self.editor.path.parent/'.preview'; cache.mkdir(exist_ok=True)
            output=self.playback_path() if self.viewing else cache/(uuid.uuid4().hex+'.mp4')
        self.job_export=export; self.job_revision=self.editor.revision
        self.job=RenderJob(self.editor.path,output,preset=self.preset.currentData() if export else 'preview').start()
        self._job_cancel_pending=False;self.poll_job()
        self.progress.setValue(0); self.preview_label.setText(self.tr('Exportando · ')+self.preset.currentText() if export else self.tr('Preparando vista previa a resolución original…'))
    def capture_presentation(self,state):
        self.cursor_options.set_locked(bool(self.session or self.capture_pending or state in ('starting','recording','paused','stopping')))
        if getattr(self,'_capture_presentation_state',None)==state:return
        self._capture_presentation_state=state
        active=state in ('starting','recording','paused','stopping')
        self.setup_title.setText(self.tr('Grabación en pausa') if state=='paused' else self.tr('Grabación en curso') if active else self.tr('¿Qué quieres grabar?'))
        self.setup_subtitle.setText(self.tr('Reanuda la captura o termina para guardar el MP4.') if state=='paused' else self.tr('Tus fuentes se conservan mientras grabas.') if active else self.tr('Elige un área y las fuentes de audio.'))
        for widget in [self.monitor,*self.rect,self.mic,self.system,self.camera,*self.device_toggles,self.fps,self.quality,self.mic_gain,self.system_gain,self.countdown,self.quiet,self.setup_advanced.trigger,*self.capture_modes.buttons()]:widget.setEnabled(not active)
        self.stop_record.setVisible(active);self.cancel_count.setVisible(not active)
        self.pause_record.setVisible(state=='recording')
        self.record.setText(self.tr('Reanudar') if active else self.tr('Grabar'))
        from .icons import icon
        self.record.setIcon(icon('play' if active else 'record','#FFFFFF'))
        self.record.setEnabled(state=='paused' if active else not self.capture_pending)
        self.record.setAccessibleName(self.record.text());self.record.setToolTip(self.record.text())

    def poll(self):
        self.cursor_options.set_locked(bool(self.session or self.capture_pending))
        if self.keys: self.keys.poll()
        if self.session:
            status=self.session.status(); state=status['state'];self.capture_presentation(state)
            warning=status.get('cursor_warning')
            self.tray.setToolTip('Wysun Recorder · '+state+(' · '+warning if warning else ''));self.recording_indicator.update(state)
            if warning and warning!=getattr(self,'_cursor_warning_seen',None):
                self._cursor_warning_seen=warning;self.notice(warning);self.preflight.setText(warning)
            if state=='paused' and getattr(self,'show_paused',False):
                self.show_paused=False; self.preflight.setText(self.control_hint.text()); self.stack.setCurrentWidget(self.setup_page); self.show()
            if state in ('stopped','error','interrupted'):
                self.quick_mode=False;self.quick.hide_all();self.recording_indicator.hide()
                path=Path(status['project_path']); auto_finalize=bool(getattr(self.session.config,'auto_finalize',False)); self.session=None; self.restore_concentration(); self.record.setEnabled(True); self.tray.show()
                if self.discard and path.exists(): self.guard(lambda:self.library.delete(path)); self.refresh_library(); self.stack.setCurrentWidget(self.library_page)
                elif path.exists():
                    def open_final():
                        editor=Editor(path)
                        if not auto_finalize and editor.project.title==path.parent.name:
                            editor.apply(lambda p:setattr(p,'title',self.tr('Grabación ')+datetime.now().strftime('%d/%m/%Y %H:%M')))
                        if not auto_finalize and self.capture_gains:
                            editor.apply(lambda p:[setattr(s,'gain',self.capture_gains.get(s.kind,s.gain)) for s in p.sources])
                        if auto_finalize and state=='stopped':
                            self.finalization_path=path;self._finalization_state=None;self.stack.setCurrentWidget(self.library_page);self.refresh_library();self.poll_finalization()
                        else:self.open_project(path)
                    self.guard(open_final)
                self.show()
                if warning:self.notice(warning)
                if status.get('error'): self.error(status['error'])
        self.poll_job();self.poll_finalization()

    def set_job_controls(self,busy):
        for widget in [self.preview_button,self.export_button,self.preset,self.inspector,self.edit_video,self.watch_video,self.play_button,self.seek,*getattr(self,'edit_actions',[])]:widget.setEnabled(not busy)
        self.library_open.setEnabled(not busy and self.items.currentItem() is not None)
        self.library_more.setEnabled(not busy and self.items.currentItem() is not None)
        self.cancel_export.setEnabled(busy and not self._job_cancel_pending)

    def cancel_current_job(self):
        job=self.job or self.analysis
        if job and not self._job_cancel_pending:
            self._job_cancel_pending=True;job.cancel();self.poll_job()

    def finalization_active(self):
        if not self.finalization_path:return False
        from ..videolibrary import finalization_status
        return finalization_status(self.finalization_path).get('state') in ('pending','running')

    def prepare_selected_mp4(self):
        path=self.selected_path()
        if path.name!='project.json':self.notice(self.tr('Este video ya es un archivo listo para compartir.'));return
        if self.session or self.job or self.analysis or self.finalization_active():
            self.notice(self.tr('Termina la operación actual primero'));return
        self.finalization_path=path;self.guard(self.retry_finalization)

    def retry_finalization(self):
        if not self.finalization_path or self.session or self.job or self.analysis:return
        from ..finalize import retry
        self.stop_metadata();retry(self.finalization_path,output_dir=str(getattr(self.library,'videos',Path.home()/'Videos')))
        self._finalization_state=None;self.poll_finalization()

    def cancel_finalization(self):
        if self.finalization_path:
            from ..finalize import cancel
            cancel(self.finalization_path);self.finalization_panel.cancel.setEnabled(False)

    def poll_finalization(self):
        if not self.finalization_path:return
        from ..videolibrary import finalization_status,recording_video
        status=finalization_status(self.finalization_path);state=status.get('state','none')
        if state=='none':return
        self.finalization_panel.update_status(status);self.update_copy_path_action()
        if state==self._finalization_state:return
        self._finalization_state=state
        if state=='ready':
            output,changed=recording_video(self.finalization_path)
            if output and not changed:
                self.open_media(output);self.notice(self.tr('MP4 listo para enviar'))
            self.refresh_library()
        elif state in ('error','cancelled'):self.refresh_library()

    def operation_busy(self):
        if self.finalization_active():
            self.finalization_panel.show();self.notice(self.tr('El MP4 se está preparando. Puedes esperar o cancelar sin perder la grabación.'));return True
        if self.import_cancel:
            self.notice(self.tr('Espera o cancela la preparación de la edición.'));return True
        self.poll_job()
        if not (self.job or self.analysis):return False
        from .activation import show_and_focus
        show_and_focus(self);self.job_panel.show();self.job_panel.cancel.setFocus()
        self.notice(self.tr('La tarea actual está arriba. Puedes esperar o cancelarla.'))
        return True

    def poll_job(self):
        job=self.job or self.analysis
        if not job:return
        analysis=self.job is None
        kind=self.analysis_kind if analysis else ('export' if self.job_export else 'preview')
        status=job.poll();self.job_panel.update_job(kind,status,self._job_cancel_pending)
        self.progress.setValue(round(100*status.get('progress',0)))
        active=status['state'] not in ('done','error','cancelled');self.set_job_controls(active)
        if active:return
        self._job_cancel_pending=False
        if analysis:
            self.analysis=None
            if hasattr(self,'analysis_progress'):self.analysis_progress.close()
            if status['state']=='done':self.review_analysis(kind,status['result'])
            return
        self.job=None
        if status['state']=='done':
            if self.job_export and isinstance(self.library,VideoLibrary):self.library._write_metadata(Path(status['output']),edit_project=str(self.editor.path))
            if self.stack.currentWidget()==self.editor_page:
                self.preview_revision=self.job_revision;self.player.load(status['output'])
            self.preview_label.setText(self.tr('Exportación completada · MP4 guardado') if self.job_export else self.tr('Video listo · pulsa reproducir') if self.viewing else self.tr('Vista previa lista · edición aplicada'))
            self.wave_bytes.clear();self.wave_process.start('ffmpeg',['-v','error','-i',status['output'],'-vn','-ac','1','-ar','8000','-f','f32le','pipe:1'])
            self.thumbnail_source=status['output']
        elif status['state']=='error':self.preview_label.setText(self.tr('La tarea falló. Revisa el detalle mostrado arriba.'))
        else:self.preview_label.setText(self.tr('Tarea cancelada; proyecto conservado'))
    def wave_ready(self,*_):
        import array
        samples=array.array('f'); data=bytes(self.wave_bytes); samples.frombytes(data[:len(data)//4*4])
        self.waveform.set_data([min(1,max(abs(v) for v in samples[i:i+80])) for i in range(0,len(samples),80)],self.editor.project.duration if self.editor else 0)
        if hasattr(self,'thumbnail_source'):self.make_thumbnail(self.thumbnail_source)
    def make_thumbnail(self,path):
        if not self.editor: return
        self.thumbnail=QProcess(self); self.thumbnail.start('ffmpeg',['-v','error','-y','-i',str(path),'-frames:v','1','-vf','scale=288:-1',str(self.editor.path.parent/'thumbnail.jpg')])
    def annotation_dialog(self):
        if not self.editor: return
        from .components import form_dialog
        dialog,form=form_dialog(self,self.tr('Anotaciones y subtítulos'),self.tr('Define cuándo aparece cada elemento. Los cambios se guardan en el proyecto.'))
        kind=QComboBox()
        for label,key in [('Texto','text'),('Flecha →','arrow'),('Resaltado','highlight'),('Máscara','mask'),('Desenfoque','blur'),('Subtítulo','subtitle')]: kind.addItem(self.tr(label),key)
        form.addRow(self.tr('Tipo'),kind)
        start=number(0,self.editor.project.duration,self.position,3); end=number(0,self.editor.project.duration,min(self.position+2,self.editor.project.duration),3)
        form.addRow(self.tr('Inicio (s)'),start); form.addRow(self.tr('Fin (s)'),end)
        text=QLineEdit(); form.addRow(self.tr('Texto'),text)
        coords=[];coordinates=QGridLayout();coordinates.setSpacing(8)
        for index,(label,value) in enumerate([('X',.1),('Y',.1),('Ancho',.3),('Alto',.15)]):
            spin=number(0,1,value,3);coords.append(spin);coordinates.addWidget(QLabel(self.tr(label)),index//2,index%2*2);coordinates.addWidget(spin,index//2,index%2*2+1)
        form.addRow(self.tr('Posición y tamaño (0–1)'),coordinates)
        colors=QComboBox()
        for title,key in [('Amarillo','yellow'),('Blanco','white'),('Negro','black'),('Rojo','red'),('Verde','green'),('Azul','blue')]:colors.addItem(self.tr(title),key)
        form.addRow(self.tr('Color'),colors)
        existing=QListWidget();existing.setMinimumHeight(80);existing.setMaximumHeight(130)
        names={'text':self.tr('Texto'),'arrow':self.tr('Flecha'),'highlight':self.tr('Resaltado'),'mask':self.tr('Máscara'),'blur':self.tr('Desenfoque')}
        for a in self.editor.project.annotations:existing.addItem(f'{names[a.kind]} · {a.start:.2f}–{a.end:.2f} · {a.text}')
        for s in self.editor.project.subtitles: existing.addItem(f'SRT {s.start:.2f}–{s.end:.2f} {s.text}')
        form.addRow(self.tr('Existentes (selecciona para editar)'),existing)
        def choose(index):
            if index<0:return
            count=len(self.editor.project.annotations); item=(self.editor.project.annotations+self.editor.project.subtitles)[index]
            buttons.button(QDialogButtonBox.Save).setText(self.tr('Guardar cambios'))
            kind.setCurrentIndex(kind.findData(item.kind if index<count else 'subtitle'));start.setValue(item.start);end.setValue(item.end);text.setText(item.text)
            if index<count:
                for spin,value in zip(coords,item.rect):spin.setValue(value)
                colors.setCurrentIndex(colors.findData(item.color))
        existing.currentRowChanged.connect(choose)
        def remove():
            index=existing.currentRow()
            if index<0:return
            count=len(self.editor.project.annotations)
            self.guard(lambda:self.edit(lambda:self.editor.apply(lambda p:p.annotations.pop(index) if index<count else p.subtitles.pop(index-count))))
            dialog.accept()
        remove_button=QPushButton(self.tr('Eliminar seleccionada'));remove_button.setEnabled(False);existing.currentRowChanged.connect(lambda index:remove_button.setEnabled(index>=0));remove_button.clicked.connect(remove);form.addRow(remove_button)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText(self.tr('Añadir elemento'));buttons.button(QDialogButtonBox.Save).setProperty('primary',True);buttons.button(QDialogButtonBox.Cancel).setText(self.tr('Cancelar'));buttons.button(QDialogButtonBox.Save).setIcon(QIcon());buttons.button(QDialogButtonBox.Cancel).setIcon(QIcon());dialog.footer.addWidget(buttons);buttons.rejected.connect(dialog.reject)
        def save():
            def change():
                selected=existing.currentRow()
                if selected>=0:
                    from ..schema import Annotation,Subtitle
                    def replace_item(p):
                        count=len(p.annotations)
                        if selected<count:p.annotations.pop(selected)
                        else:p.subtitles.pop(selected-count)
                        if kind.currentData()=='subtitle':p.subtitles.append(Subtitle(start.value(),end.value(),text.text()))
                        else:p.annotations.append(Annotation(kind.currentData(),start.value(),end.value(),[s.value() for s in coords],text.text(),colors.currentData()))
                    self.editor.apply(replace_item);return
                if kind.currentData()=='subtitle': self.editor.subtitle(start.value(),end.value(),text.text())
                else: self.editor.add_annotation(kind.currentData(),start.value(),end.value(),[s.value() for s in coords],text.text(),colors.currentData())
            try: self.edit(change); dialog.accept()
            except Exception as exc:self.error(str(exc))
        buttons.accepted.connect(save); dialog.exec()
    def geometry_dialog(self):
        if not self.editor:return
        from .components import form_dialog
        dialog,form=form_dialog(self,self.tr('Encuadre y cámara'),self.tr('Ajusta el área visible y la posición de la cámara.'))
        crop=QCheckBox(self.tr('Recortar / ampliar imagen')); crop.setChecked(self.editor.project.crop is not None); form.addRow(crop)
        camera=QCheckBox(self.tr('Mostrar cámara')); camera.setChecked(self.editor.project.camera.enabled); form.addRow(camera)
        values=[]
        for prefix,rect in [('Recorte',self.editor.project.crop or [0,0,1,1]),('Cámara',self.editor.project.camera.rect)]:
            group=[]
            for label,value in zip(['X','Y','Ancho','Alto'],rect):
                spin=number(0,1,value,3); form.addRow(self.tr(prefix)+' '+label,spin); group.append(spin)
            values.append(group)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText(self.tr('Guardar cambios'));buttons.button(QDialogButtonBox.Save).setProperty('primary',True);buttons.button(QDialogButtonBox.Cancel).setText(self.tr('Cancelar'));buttons.button(QDialogButtonBox.Save).setIcon(QIcon());buttons.button(QDialogButtonBox.Cancel).setIcon(QIcon());dialog.footer.addWidget(buttons);buttons.rejected.connect(dialog.reject)
        def save():
            def update(p):
                p.crop=[s.value() for s in values[0]] if crop.isChecked() else None
                p.camera.enabled=camera.isChecked(); p.camera.rect=[s.value() for s in values[1]]
            try:self.edit(lambda:self.editor.apply(update)); dialog.accept()
            except Exception as exc:self.error(str(exc))
        buttons.accepted.connect(save); dialog.exec()
    def export_srt(self):
        if not self.editor:return
        path,_=QFileDialog.getSaveFileName(self,self.tr('Exportar subtítulos'),str(self.editor.path.parent/'subtitles.srt'),'SRT (*.srt)')
        if path:self.guard(lambda:self.editor.export_srt(path))
    def import_srt(self):
        if not self.editor:return
        path,_=QFileDialog.getOpenFileName(self,self.tr('Importar SRT'),'', 'SRT (*.srt)')
        if path:
            from ..analysis import import_srt
            self.guard(lambda:self.edit(lambda:self.editor.apply(lambda p:p.subtitles.extend(import_srt(path)))))
    def analysis_dialog(self):
        if not self.editor or self.operation_busy():return
        kind,ok=QInputDialog.getItem(self,self.tr('Análisis local'),self.tr('Revisar propuestas antes de aplicar'),[self.tr('Detectar silencios'),self.tr('Transcribir con whisper.cpp local')],0,False)
        if not ok:return
        from ..analysis import AnalysisJob
        key='silence' if kind==self.tr('Detectar silencios') else 'transcription'
        options={}
        if key=='transcription':
            executable,_=QFileDialog.getOpenFileName(self,self.tr('Selecciona whisper-cli instalado'))
            if not executable:return
            model,_=QFileDialog.getOpenFileName(self,self.tr('Selecciona modelo local; no se descargará nada'))
            if not model:return
            options={'executable':executable,'model_path':model}
        def start():
            self.player.close_media(); self.analysis_kind=key
            self.analysis=AnalysisJob(self.editor.path,kind=key,**options).start()
            self._job_cancel_pending=False;self.poll_job()
        self.guard(start)
    def review_analysis(self,kind,result):
        dialog=QDialog(self); dialog.setWindowTitle(self.tr('Revisar resultados')); layout=QVBoxLayout(dialog)
        layout.addWidget(QLabel(self.tr('Marca únicamente los intervalos que quieras eliminar. Los originales se conservan.')))
        items=QListWidget(); layout.addWidget(items)
        for entry in result:
            start=entry['start'] if isinstance(entry,dict) else entry.start
            end=entry['end'] if isinstance(entry,dict) else entry.end
            text='' if isinstance(entry,dict) else entry.text
            item=QListWidgetItem(f'{start:.2f}–{end:.2f} {text}'); item.setFlags(item.flags()|Qt.ItemIsUserCheckable); item.setCheckState(Qt.Unchecked); item.setData(Qt.UserRole,(start,end));items.addItem(item)
        def remove():
            selected=[items.item(i).data(Qt.UserRole) for i in range(items.count()) if items.item(i).checkState()==Qt.Checked]
            if selected:self.guard(lambda:self.edit(lambda:self.editor.remove_ranges(selected)))
            dialog.accept()
        button(self.tr('Eliminar intervalos marcados'),remove,layout)
        if kind=='transcription':
            def subtitles():
                self.guard(lambda:self.edit(lambda:self.editor.apply(lambda p:p.subtitles.extend(result))));dialog.accept()
            button(self.tr('Añadir transcripción como subtítulos'),subtitles,layout)
        button(self.tr('Cerrar sin cambios'),dialog.reject,layout); dialog.resize(650,450);dialog.exec()

    def hide_capture_controls(self):
        self.quick.hide_all();self.countdown_overlay.hide();self.camera_preview.stop();self.hide();self.tray.hide()
        for widget in QApplication.topLevelWidgets():
            if widget not in self.recording_indicator.windows:widget.hide()

    def activate_instance(self,action):
        if action=='hide_controls':
            if not self.session or self.session.status()['state']!='paused':return {'hidden':False}
            self.hide_capture_controls();return {'hidden':True}

        if action=='quick':
            if self.session or self.job or self.analysis or self.capture_pending or self.import_cancel or self.finalization_active():
                return {'pid':os.getpid(),'state':'busy','result':'quick_unavailable'}
            if QApplication.activeModalWidget():
                return {'pid':os.getpid(),'state':'busy','result':'modal_active'}
            self.quick.present()
            return {'pid':os.getpid(),'state':'idle','quick':True,'job':None}
        if action!='status':
            self.quick_mode=False;self.quick.hide_all();self.camera_preview_layout.addWidget(self.camera_preview)
        state=self.session.status()['state'] if self.session else 'idle'
        self.poll_job()
        if action!='status':
            if state in ('starting','recording','stopping'):
                return {'pid':os.getpid(),'state':state,'result':'capture_kept_hidden','project_path':str(self.session.root/'project.json')}
            modal=QApplication.activeModalWidget()
            if modal:
                from .activation import show_and_focus
                show_and_focus(modal)
            else:
                if action=='setup' and not (self.job or self.analysis):self.stack.setCurrentWidget(self.setup_page)
                from .activation import show_and_focus
                show_and_focus(self)
                if self.stack.currentWidget()==self.setup_page:self.camera_selected()
                if not self.keys:
                    try:self.ensure_keys();self.preflight.setText(self.tr('Listo para grabar'))
                    except Exception as exc:self.preflight.setText(str(exc))
        return {'pid':os.getpid(),'state':state,'window':int(self.winId()),
                'setup':self.stack.currentWidget()==self.setup_page,'keys_ready':self.keys is not None,
                'project_path':str(self.session.root/'project.json') if self.session else None,'controls_protocol':1,
                'job':(self.job or self.analysis).poll() if (self.job or self.analysis) else None}

    def closeEvent(self,event):
        self.stop_metadata()
        if self.session:
            response=QMessageBox.question(self,self.tr('Grabación activa'),self.tr('¿Ocultar Wysun Recorder y mantener la grabación? Puedes detenerla desde la bandeja.'),QMessageBox.Yes|QMessageBox.No)
            event.ignore()
            if response==QMessageBox.Yes:self.hide()
            return
        if self.import_cancel:self.import_cancel.set()
        if self.job or self.analysis or self.tasks:
            self.error(self.tr('Cancela la operación y espera a que termine antes de cerrar')); event.ignore(); return
        if self.camera_preview.is_running:
            event.ignore();self.camera_preview.stop(self.close);return
        self.capture_pending=False;self.countdown_timer.stop();self.countdown_overlay.hide();self.countdown_overlay.deleteLater();self.recording_indicator.hide()
        self.selection_timer.stop();self.quick.timer.stop();self.quick.hide_all();self.quick.deleteLater();self.stop_meters(); self.player.shutdown(); self.wave_process.kill(); self.wave_process.waitForFinished(1000)
        if hasattr(self,'thumbnail'):self.thumbnail.waitForFinished(1000)
        self.restore_concentration(); self.tray.hide();
        if self.keys:self.keys.close()
        event.accept(); QApplication.quit()


def apply_theme(app):
    from .tokens import apply_theme as apply
    apply(app)


def main():
    from .instance import Instance
    instance=Instance()
    quick=os.environ.get('LOOMREC_QUICK_RECORD')=='1'
    if not instance.claim():
        response=instance.request('quick' if quick else 'setup' if os.environ.get('LOOMREC_START_RECORDING')=='1' else 'focus')
        if quick:
            if response.get('state')!='busy':return 0
            response=instance.request('status')
            if response.get('state') not in ('starting','recording','paused','stopping'):return 0
            if response.get('state')!='paused':response['result']='capture_kept_hidden'
        from .activation import activate_response
        return activate_response(response,instance)
    try:
        app=QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName('Wysun Recorder'); app.setOrganizationName('Loom')
        apply_theme(app)
        app.setQuitOnLastWindowClosed(False)
        window=Window()
        from .activation import show_and_focus
        if quick:window.quick.present()
        else:show_and_focus(window)
        activation=QTimer(window);activation.timeout.connect(lambda:instance.poll(window.activate_instance));activation.start(50)
        return app.exec()
    finally:instance.close()

if __name__=='__main__': main()

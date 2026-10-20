"""Native page composition; behavior stays in Window's existing callbacks."""
from PySide6.QtCore import Qt,QSize
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QFormLayout,QLabel,QComboBox,QSpinBox,QDoubleSpinBox,QLineEdit,QListWidget,QCheckBox,QScrollArea,QMenu,QButtonGroup,QSizePolicy)
from .components import SoftButton,Toggle,Disclosure,RecordingDelegate,label,surface,rule,ComboBox,CheckBox,SpinBox,DoubleSpinBox
from .icons import icon
from .meters import AudioMeter


def action(text,callback,symbol=None,primary=False,quiet=False):
    b=SoftButton(text,symbol,primary,quiet);b.clicked.connect(callback);return b

def number(low,high,value,decimals=2):
    spin=DoubleSpinBox();spin.setRange(low,high);spin.setDecimals(decimals);spin.setValue(value);return spin

def header(w,title,subtitle=None):
    box=QWidget();layout=QHBoxLayout(box);layout.setContentsMargins(0,0,0,0)
    titles=QVBoxLayout();titles.setSpacing(5);titles.addWidget(label(title,'title'))
    if subtitle:titles.addWidget(label(subtitle,'subtitle'))
    layout.addLayout(titles,1);return box,layout

def library(w):
    page=QWidget();w.library_page=page;layout=QVBoxLayout(page);layout.setContentsMargins(28,26,28,20);layout.setSpacing(20)
    top,row=header(w,w.tr('Tu biblioteca'),w.tr('Tus videos y grabaciones, en un solo lugar.'));layout.addWidget(top)
    row.addWidget(action(w.tr('Nueva grabación'),lambda:w.activate_instance('quick'),'plus',True))
    tools=QHBoxLayout();tools.setSpacing(12);layout.addLayout(tools)
    w.search=QLineEdit();w.search.setPlaceholderText(w.tr('Buscar grabaciones o colecciones'));w.search.addAction(icon('search'),QLineEdit.LeadingPosition);w.search.textChanged.connect(w.refresh_library);tools.addWidget(w.search,1)
    w.trash=SoftButton(w.tr('Papelera'),'trash',quiet=True);w.trash.setCheckable(True);w.trash.toggled.connect(w.refresh_library);tools.addWidget(w.trash)
    tools.addWidget(action(w.tr('Ajustes'),w.show_settings,'settings',quiet=True))
    w.items=QListWidget();w.items.setItemDelegate(RecordingDelegate(w.items));w.items.setSpacing(6);w.items.setIconSize(QSize(144,81));w.items.itemDoubleClicked.connect(lambda _:w.open_selected());layout.addWidget(w.items,1)
    w.library_empty=surface(shadow=False);empty=QVBoxLayout(w.library_empty);empty.setAlignment(Qt.AlignCenter);empty.setSpacing(14)
    emblem=QLabel();emblem.setPixmap(icon('library','accent_muted',56).pixmap(56,56));emblem.setAlignment(Qt.AlignCenter);empty.addWidget(emblem)
    w.empty_title=label(w.tr('Tus videos aparecerán aquí'),'title');w.empty_title.setAlignment(Qt.AlignCenter);empty.addWidget(w.empty_title)
    w.empty_description=label(w.tr('Graba tu pantalla con tu cámara y tu voz.\nAl terminar tendrás un MP4 listo para enviar.'),'subtitle');w.empty_description.setAlignment(Qt.AlignCenter);empty.addWidget(w.empty_description)
    empty.addWidget(action(w.tr('Crear mi primera grabación'),lambda:w.activate_instance('quick'),'record',True),0,Qt.AlignCenter)
    layout.addWidget(w.library_empty,1)
    bottom=QHBoxLayout();layout.addLayout(bottom)
    w.path_label=label(w.tr('Biblioteca local'),'subtitle');w.path_label.setToolTip(str(w.library.root));bottom.addWidget(w.path_label);bottom.addStretch()
    w.library_copy_path=action(w.tr('Copiar ruta absoluta'),w.copy_video_path);w.library_copy_path.setToolTip(w.tr('Copiar la ruta del video seleccionado · Ctrl+C en la lista. El MP4 estará disponible al terminar su preparación.'));w.library_copy_path.setEnabled(False);bottom.addWidget(w.library_copy_path)
    from PySide6.QtGui import QShortcut,QKeySequence
    copy_key=QShortcut(QKeySequence('Ctrl+C'),w.items);copy_key.setContext(Qt.WidgetShortcut);copy_key.activated.connect(w.copy_video_path)
    w.items.itemSelectionChanged.connect(w.update_copy_path_action)
    w.library_open=action(w.tr('Ver video'),w.open_selected,'play',quiet=True);w.library_open.setEnabled(False);bottom.addWidget(w.library_open)
    more=SoftButton(w.tr('Organizar'),'more');menu=QMenu(more)
    for text,fn in [('Preparar MP4',lambda:w.guard(w.prepare_selected_mp4)),('Renombrar',w.rename),('Cambiar colección',w.organize),('Mostrar carpeta',w.reveal),('Recuperar captura',w.recover),('Mover a papelera / restaurar',w.trash_selected)]:menu.addAction(w.tr(text),fn)
    more.setMenu(menu);more.setEnabled(False);w.library_more=more;bottom.addWidget(more)
    w.items.itemSelectionChanged.connect(lambda:(w.library_open.setEnabled(w.items.currentItem() is not None and not (w.job or w.analysis)),w.library_more.setEnabled(w.items.currentItem() is not None and not (w.job or w.analysis))))
    w.stack.addWidget(page)


def setup(w):
    page=QWidget();w.setup_page=page;root=QVBoxLayout(page);root.setContentsMargins(24,18,24,18);root.setSpacing(16)
    nav=QHBoxLayout();nav.addWidget(action(w.tr('Biblioteca'),lambda:w.stack.setCurrentWidget(w.library_page),'back',quiet=True));nav.addStretch();nav.addWidget(label('Wysun Recorder','eyebrow'));root.addLayout(nav)
    scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QScrollArea.NoFrame);root.addWidget(scroll,1)
    host=QWidget();hl=QVBoxLayout(host);hl.setContentsMargins(12,10,12,20);hl.setAlignment(Qt.AlignTop|Qt.AlignHCenter);scroll.setWidget(host)
    panel=surface(shadow=True);panel.setMaximumWidth(740);panel.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred);hl.addWidget(panel)
    body=QVBoxLayout(panel);body.setContentsMargins(28,26,28,24);body.setSpacing(14)
    w.setup_title=label(w.tr('¿Qué quieres grabar?'),'title');w.setup_subtitle=label(w.tr('Elige un área y las fuentes de audio.'),'subtitle');body.addWidget(w.setup_title);body.addWidget(w.setup_subtitle)
    modes=QHBoxLayout();modes.setSpacing(6);body.addLayout(modes);w.capture_modes=QButtonGroup(w);w.capture_modes.setExclusive(True)
    for text,symbol,callback in [(w.tr('Pantalla'),'screen',lambda:w.monitor_changed()),(w.tr('Región'),'region',w.pick_region),(w.tr('Ventana'),'window',w.pick_window)]:
        b=action(text,callback,symbol);b.setCheckable(True);w.capture_modes.addButton(b);modes.addWidget(b,1)
    w.capture_modes.buttons()[0].setChecked(True)
    selection=surface('well');sl=QVBoxLayout(selection);sl.setContentsMargins(16,12,16,12);sl.setSpacing(8);body.addWidget(selection)
    sr=QHBoxLayout();sl.addLayout(sr);sr.addWidget(label(w.tr('ENCUADRE'),'eyebrow'));sr.addStretch();w.region_summary=label('1920 × 1080','section');sr.addWidget(w.region_summary)
    w.monitor=ComboBox();w.monitor.setMinimumWidth(100);w.monitor.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed);w.monitor.currentIndexChanged.connect(w.monitor_changed);sl.addWidget(w.monitor)
    hint=label(w.tr('Wayland: el portal autoriza pantalla o ventana. La región debe pertenecer al monitor autorizado.' if __import__('loomrec.portal',fromlist=['is_wayland']).is_wayland() else 'Se grabará lo que esté visible en esta área.'),'subtitle');hint.setWordWrap(True);hint.setToolTip(w.tr('La ventana es un recorte fijo de pantalla: cualquier ventana que la cubra también aparecerá.'));sl.addWidget(hint)
    body.addWidget(rule())
    devices=QVBoxLayout();devices.setSpacing(14);body.addLayout(devices)
    w.mic=ComboBox();w.system=ComboBox();w.camera=ComboBox();w.device_toggles=[]
    for title,symbol,combo in [(w.tr('Micrófono'),'mic',w.mic),(w.tr('Audio del equipo'),'sound',w.system),(w.tr('Cámara'),'camera',w.camera)]:
        combo.addItem(w.tr('Desactivado'),None);combo.setMinimumWidth(110);combo.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        row=QHBoxLayout();row.setSpacing(12);devices.addLayout(row)
        pict=QLabel();pict.setPixmap(icon(symbol).pixmap(20,20));row.addWidget(pict)
        name=label(title);name.setMinimumWidth(135);row.addWidget(name);row.addWidget(combo,1)
        toggle=Toggle(title);row.addWidget(toggle);w.device_toggles.append(toggle)
        def sync(index,c=combo,t=toggle):
            t.blockSignals(True);t.setChecked(index>0);t.blockSignals(False)
            if index>0:c.setProperty('lastDeviceIndex',index)
        def enable(on,c=combo,t=toggle):
            if on and c.count()>1:c.setCurrentIndex(min(c.count()-1,c.property('lastDeviceIndex') or 1))
            else:c.setCurrentIndex(0);t.setChecked(False)
        combo.currentIndexChanged.connect(sync);toggle.toggled.connect(enable)
    w.camera_preview_layout=QVBoxLayout();body.addLayout(w.camera_preview_layout)
    from .capture_feedback import control_hints
    w.control_hint=label(control_hints(),'subtitle');w.control_hint.setWordWrap(True);w.control_hint.hide()
    w.indicator_hint=label(w.tr('Borde y distintivo solo fuera del área grabada. En pantalla completa se ocultan si no hay otra pantalla disponible.'),'subtitle');w.indicator_hint.setWordWrap(True);body.addWidget(w.indicator_hint)
    advanced=Disclosure(w.tr('Ajustes de grabación'));body.addWidget(advanced);w.setup_advanced=advanced
    form=QFormLayout(advanced.body);form.setContentsMargins(0,4,0,0);form.setSpacing(12);form.setRowWrapPolicy(QFormLayout.WrapLongRows)
    coords=QGridLayout();coords.setSpacing(8);w.rect=[]
    for index,(title,value) in enumerate([('X',0),('Y',0),('Ancho',1920),('Alto',1080)]):
        spin=SpinBox();spin.setRange((-32768 if __import__('loomrec.portal',fromlist=['is_wayland']).is_wayland() else 0) if index<2 else 16,32768);spin.setValue(value);w.rect.append(spin);coords.addWidget(label(w.tr(title)),index//2,index%2*2);coords.addWidget(spin,index//2,index%2*2+1)
        spin.valueChanged.connect(lambda _:w.region_summary.setText(f'{w.rect[2].value()} × {w.rect[3].value()}' if len(w.rect)==4 else ''))
    form.addRow(w.tr('Área exacta'),coords)
    w.mic_gain=number(0,8,1);w.system_gain=number(0,8,1);form.addRow(w.tr('Ganancia del micrófono'),w.mic_gain);form.addRow(w.tr('Ganancia del equipo'),w.system_gain)
    w.mic_meter=AudioMeter();w.system_meter=AudioMeter();form.addRow(w.tr('Nivel micrófono'),w.mic_meter);form.addRow(w.tr('Nivel equipo'),w.system_meter)
    levels=QHBoxLayout();levels.addWidget(action(w.tr('Probar niveles'),w.start_meters,'sound'));levels.addWidget(action(w.tr('Detener prueba'),w.stop_meters,quiet=True));form.addRow(levels)
    w.fps=ComboBox()
    for fps in (15,24,30,60):w.fps.addItem(str(fps),fps)
    w.fps.setCurrentIndex(2);form.addRow(w.tr('Fotogramas por segundo'),w.fps)
    w.quality=ComboBox()
    for title,key in [('Ligera · menor tamaño','compact'),('Original · equilibrada','standard'),('Original · alta','high')]:w.quality.addItem(w.tr(title),key)
    w.quality.setToolTip(w.tr('Conserva la resolución del área elegida. La calidad cambia la compresión.'));w.quality.setCurrentIndex(1);form.addRow(w.tr('Calidad'),w.quality)
    w.countdown=SpinBox();w.countdown.setRange(0,30);w.countdown.setValue(3);form.addRow(w.tr('Cuenta atrás (s)'),w.countdown)
    w.shortcut_label=label(w.tr('Los atajos se activan al detectar los dispositivos.'),'subtitle');w.shortcut_label.setWordWrap(True);form.addRow(w.shortcut_label)
    form.addRow(action(w.tr('Actualizar dispositivos'),w.refresh_devices,'settings',quiet=True))
    w.quiet=CheckBox(w.tr('Pausar notificaciones mientras grabo'));w.quiet.setChecked(True);body.addWidget(w.quiet)
    body.addWidget(rule());footer=QHBoxLayout();footer.setSpacing(12);body.addLayout(footer)
    w.preflight=label(w.tr('Comprobando dispositivos…'),'subtitle');w.preflight.setWordWrap(True);footer.addWidget(w.preflight,1)
    w.cancel_count=action(w.tr('Cancelar'),w.cancel_countdown,quiet=True);w.cancel_count.setEnabled(False);footer.addWidget(w.cancel_count)
    w.pause_record=action(w.tr('Pausar'),w.pause_capture,quiet=True);w.pause_record.hide();footer.addWidget(w.pause_record)
    w.stop_record=action(w.tr('Terminar y ver video'),w.stop_capture,'check');w.stop_record.hide();footer.addWidget(w.stop_record)
    w.record=action(w.tr('Grabar'),lambda:w.pause_capture() if w.session else w.guard(w.begin_countdown),'record',True);w.record.setMinimumWidth(126);w.record.setMinimumHeight(42);footer.addWidget(w.record)
    w.stack.addWidget(page)


def editor(w):
    """Watch-only page: Wysun Recorder records and plays back; it never edits."""
    from PySide6.QtWidgets import QSlider
    from .player import Player
    from .seekbar import SeekBar
    page=QWidget();w.editor_page=page;outer=QVBoxLayout(page);outer.setContentsMargins(22,18,22,18);outer.setSpacing(14)
    w.viewer_header=QWidget();heading=QHBoxLayout(w.viewer_header);heading.setContentsMargins(0,0,0,0);heading.setSpacing(10);outer.addWidget(w.viewer_header)
    back=action('',w.back_library,'back',quiet=True);back.setAccessibleName(w.tr('Volver a biblioteca'));back.setToolTip(w.tr('Volver a biblioteca'));back.setFixedWidth(38);heading.addWidget(back)
    w.title=label('','section');w.title.setMinimumWidth(0);w.title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);heading.addWidget(w.title,1)
    w.copy_media=action(w.tr('Copiar ruta'),w.copy_media_path,'copy',quiet=True);w.copy_media.setToolTip(w.tr('Copiar la ruta absoluta del MP4'));heading.addWidget(w.copy_media)
    w.reveal_media=action(w.tr('Mostrar en carpeta'),w.reveal_media_path,'folder',quiet=True);heading.addWidget(w.reveal_media)
    stage=QWidget();stage.setObjectName('viewerStage');stage.setStyleSheet('#viewerStage{background:#0B0D12;border-radius:16px;}')  # theme-exception: escenario negro del reproductor
    video=QVBoxLayout(stage);video.setContentsMargins(0,0,0,0);video.setSpacing(0)
    w.player=Player();w.player.failed.connect(w.playback_failed);w.player.setMinimumSize(320,180);video.addWidget(w.player,1)
    outer.addWidget(stage,1)
    w.viewer_controls=surface(shadow=False);controls=QVBoxLayout(w.viewer_controls);controls.setContentsMargins(16,10,16,12);controls.setSpacing(6);outer.addWidget(w.viewer_controls)
    seekrow=QHBoxLayout();seekrow.setSpacing(12);controls.addLayout(seekrow)
    w.elapsed=label('0:00','subtitle');w.elapsed.setMinimumWidth(44);seekrow.addWidget(w.elapsed)
    w.seek=SeekBar();w.seek.seekRequested.connect(w.player.seek);seekrow.addWidget(w.seek,1)
    w.clock=label('0:00','subtitle');w.clock.setMinimumWidth(44);w.clock.setAlignment(Qt.AlignRight|Qt.AlignVCenter);seekrow.addWidget(w.clock)
    buttons=QHBoxLayout();buttons.setSpacing(8);controls.addLayout(buttons)
    play=action('',w.toggle_playback,'play',True);w.play_button=play;play.setFixedSize(46,40);play.setAccessibleName(w.tr('Reproducir o pausar'));play.setToolTip(w.tr('Reproducir / pausa · Espacio'));buttons.addWidget(play)
    for text,seconds,symbol in [(w.tr('Retroceder 5 s · ←'),-5,'rewind'),(w.tr('Avanzar 5 s · →'),5,'forward')]:
        b=action('',lambda checked=False,s=seconds:w.skip_playback(s),symbol,quiet=True);b.setFixedWidth(40);b.setToolTip(text);b.setAccessibleName(text);buttons.addWidget(b)
    w.mute_button=action('',w.player.toggle_mute,'sound',quiet=True);w.mute_button.setFixedWidth(40);w.mute_button.setToolTip(w.tr('Silenciar · M'));w.mute_button.setAccessibleName(w.tr('Silenciar'));buttons.addWidget(w.mute_button)
    w.volume=QSlider(Qt.Horizontal);w.volume.setRange(0,100);w.volume.setValue(80);w.volume.setFixedWidth(96);w.volume.setAccessibleName(w.tr('Volumen de reproducción'));w.volume.valueChanged.connect(w.player.set_volume);buttons.addWidget(w.volume)
    buttons.addStretch();w.preview_label=label('','subtitle');buttons.addWidget(w.preview_label);buttons.addStretch()
    w.speed=ComboBox();w.speed.setAccessibleName(w.tr('Velocidad de reproducción'));w.speed.setFixedWidth(84)
    for value in (.5,.75,1.,1.25,1.5,2.):w.speed.addItem(f'{value:g}×',value)
    w.speed.setCurrentIndex(2);w.speed.currentIndexChanged.connect(lambda _:w.player.set_speed(w.speed.currentData()));buttons.addWidget(w.speed)
    w.fullscreen_button=action('',w.toggle_fullscreen,'fullscreen',quiet=True);w.fullscreen_button.setFixedWidth(40);w.fullscreen_button.setAccessibleName(w.tr('Pantalla completa'));w.fullscreen_button.setToolTip(w.tr('Pantalla completa · F'));buttons.addWidget(w.fullscreen_button)
    w.player.positionChanged.connect(w.position_changed);w.player.durationChanged.connect(w.seek.set_duration);w.player.stateChanged.connect(w.player_state)
    w.stack.addWidget(page)

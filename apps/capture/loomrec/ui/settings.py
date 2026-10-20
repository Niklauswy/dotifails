"""Real preferences page and readable configured shortcut rows."""
import os,json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QScrollArea,QFileDialog
from .components import label,surface,SoftButton,ComboBox,CheckBox
from .tokens import apply_style
from .material import Navigation,Workspace,layout_tokens
from ..videolibrary import preferences,save_preferences
from ..schema import atomic_json
from ..integration import shortcut_settings

def key_rows(layout):
    names={'record':'Grabar','pause':'Pausar / reanudar','stop':'Terminar','cancel':'Cancelar grabación','rewind':'Rebobinar 10 s','status':'Mostrar controles'}
    for action,chord in shortcut_settings().items():
        row=QHBoxLayout();row.addWidget(label(names[action]),1)
        for key in chord.split('+'):
            cap=label(key.capitalize());apply_style(cap,'background:@hover;color:@ink;border:1px solid @line_strong;border-radius:6px;padding:5px 8px;');row.addWidget(cap)
        layout.addLayout(row)

def build(w):
    content=QWidget();outer=QVBoxLayout(content);layout_tokens(outer)
    navigation=Navigation('Wysun Recorder',[
        ('Biblioteca','library',w.back_library),
        ('Grabar','record',lambda:w.activate_instance('setup')),
        ('Ajustes','settings',lambda:None)],active=2)
    page=Workspace(navigation,content);w.settings_page=page
    outer.addWidget(label('Ajustes','title'));outer.addWidget(label('Tu espacio de trabajo y tus preferencias de grabación.','subtitle'))
    scroll=QScrollArea();scroll.setWidgetResizable(True);outer.addWidget(scroll,1);host=QWidget();body=QVBoxLayout(host);body.setContentsMargins(8,8,8,16);body.setSpacing(22);scroll.setWidget(host)
    from .cursor_settings import CursorPanel
    cursor=surface();cursor_layout=QVBoxLayout(cursor);cursor_layout.setContentsMargins(20,18,20,18);cursor_layout.setSpacing(12);cursor_layout.addWidget(label('Cursor','section'))
    w.cursor_panel=CursorPanel(w.cursor_options,demo=True);cursor_layout.addWidget(w.cursor_panel);body.addWidget(cursor)
    folder=surface();fl=QVBoxLayout(folder);fl.setContentsMargins(20,18,20,18);fl.addWidget(label('Videos y archivos','section'));w.folder_label=label(str(getattr(w.library,'videos',w.library.root)),'subtitle');w.folder_label.setWordWrap(True);fl.addWidget(w.folder_label)
    b=SoftButton('Cambiar carpeta…','folder');b.clicked.connect(w.change_video_folder);fl.addWidget(b,0,Qt.AlignLeft);hint=label('Los videos existentes se conservan en su ubicación. Las ediciones guardan una copia privada del original.','subtitle');hint.setWordWrap(True);fl.addWidget(hint);body.addWidget(folder)
    panel=surface();form=QFormLayout(panel);form.setContentsMargins(20,18,20,18);form.setSpacing(14);form.addRow(label('Grabación','section'))
    for title,source in [('Calidad',w.quality),('Fotogramas por segundo',w.fps)]:
        combo=ComboBox();combo.setModel(source.model());combo.setCurrentIndex(source.currentIndex());combo.currentIndexChanged.connect(source.setCurrentIndex);source.currentIndexChanged.connect(combo.setCurrentIndex);form.addRow(title,combo)
    from .components import SpinBox
    count=SpinBox();count.setRange(0,30);count.setValue(w.countdown.value());count.valueChanged.connect(w.countdown.setValue);w.countdown.valueChanged.connect(count.setValue);form.addRow('Cuenta atrás (s)',count)
    quiet=CheckBox('Pausar notificaciones durante la grabación');quiet.setChecked(w.quiet.isChecked());quiet.toggled.connect(w.quiet.setChecked);w.quiet.toggled.connect(quiet.setChecked);form.addRow(quiet)
    remember=CheckBox('Recordar el monitor del portal');remember.setToolTip('Evita el selector en las siguientes grabaciones de monitor o región de la misma pantalla. El portal pide el primer permiso una vez por pantalla.');remember.setChecked(bool(preferences().get('remember_source',True)));remember.toggled.connect(lambda value:w.guard(lambda:save_preferences(remember_source=value)));form.addRow(remember)
    def forget_source():
        from .. import consent
        consent.clear()
        w.notice('Se olvidó la fuente recordada. La próxima grabación de monitor volverá a pedir permiso.')
    forget=SoftButton('Olvidar fuente recordada','settings');forget.clicked.connect(forget_source);form.addRow(forget)
    source_hint=label('El portal pide permiso la primera vez. Después se reutiliza el monitor elegido hasta que lo olvides o desactives esta opción.','subtitle');source_hint.setWordWrap(True);form.addRow(source_hint)
    motion=CheckBox('Reducir animaciones');appearance=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'loomrec/appearance.json'
    try:values=json.loads(appearance.read_text())
    except (OSError,ValueError):values={}
    motion.setChecked(bool(values.get('reduced_motion')));motion.toggled.connect(lambda value:w.guard(lambda:atomic_json(appearance,{**values,'reduced_motion':value})));motion.toggled.connect(lambda _:w.cursor_panel.demo.sync());form.addRow(motion);body.addWidget(panel)
    keys=surface();kl=QVBoxLayout(keys);kl.setContentsMargins(20,18,20,18);kl.setSpacing(12);kl.addWidget(label('Atajos de teclado','section'));key_rows(kl)
    info=label('Barra rápida: Super + Shift + L. Los atajos de grabación se configuran en shortcuts.json; reinicia la aplicación para aplicar cambios.','subtitle');info.setWordWrap(True);kl.addWidget(info)
    edit=SoftButton('Abrir configuración de atajos','settings');edit.clicked.connect(w.open_shortcuts);kl.addWidget(edit,0,Qt.AlignLeft);body.addWidget(keys);body.addStretch();w.stack.addWidget(page)

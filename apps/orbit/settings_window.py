"""Órbita Ajustes: a native BSPWM and sxhkd editor."""
import ctypes, ctypes.util, json, subprocess
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QFont
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPlainTextEdit,QSpinBox,QDoubleSpinBox,QCheckBox,QComboBox,QStackedWidget,QListWidget,QTableWidget,QTableWidgetItem,QAbstractItemView,QHeaderView,QMessageBox,QDialogButtonBox,QColorDialog,QScrollArea)
from desktop_common import Surface,button,text_label,open_vim,launch
from settings_data import DesktopSettings,ShortcutFile,SCHEMA
from icons import icon

from shortcut_capture import KeyField

class ShortcutEditor(QDialog):
    def __init__(self,parent,model,index=None):
        super().__init__(parent);self.model=model;self.index=index;r=model.rows[index] if index is not None else {};self.setWindowTitle('Editar atajo' if r else 'Nuevo atajo');self.resize(640,330)
        layout=QVBoxLayout(self);layout.setSpacing(15);layout.addWidget(text_label(self.windowTitle(),'title'));form=QFormLayout();self.title=QLineEdit(r.get('title',''));self.key=KeyField(r.get('key',''));self.command=QPlainTextEdit(r.get('command',''));self.command.setFont(QFont('DejaVu Sans Mono',10));self.command.setMaximumHeight(85)
        keys=QHBoxLayout();keys.addWidget(self.key,1);self.record_button=button('Grabar',self.key.record,symbol='keyboard');keys.addWidget(self.record_button);self.key.recordingChanged.connect(lambda active:self.record_button.setText('Cancelar captura' if active else 'Grabar'));form.addRow('Nombre',self.title);form.addRow('Combinación',keys);form.addRow('Comando',self.command);layout.addLayout(form)
        self.error=text_label('Se conserva el resto del archivo. Las llaves permiten editar grupos de atajos.','subtitle');layout.addWidget(self.error);self.key.captureError.connect(self.error.setText);self.key.captured.connect(lambda key:self.error.setText('Combinación capturada: '+key))
        row=QHBoxLayout();row.addStretch();row.addWidget(button('Cancelar',self.reject));row.addWidget(button('Guardar atajo',self.save,'primary'));layout.addLayout(row)
    def save(self):
        try:
            self.model.save(self.key.text(),self.command.toPlainText(),self.index,self.title.text() or 'Atajo personalizado');subprocess.run(['pkill','-USR1','-u',str(__import__('os').getuid()),'-x','sxhkd'],capture_output=True);self.accept()
        except (ValueError,OSError,subprocess.SubprocessError) as e:self.error.setText(str(e));self.error.setStyleSheet('color:#EDAAA7')

class SettingsWindow(Surface):
    def __init__(self,test=False):
        super().__init__('Ajustes del escritorio','BSPWM · ventanas, comportamiento y atajos',960,670);self.test=test;self.backend=DesktopSettings();self.shortcuts=ShortcutFile();self.widgets={};self.rules=json.loads(json.dumps(self.backend.saved.get('rules',[])))
        middle=QHBoxLayout();middle.setSpacing(24);self.nav=QListWidget();self.nav.setFixedWidth(190);self.nav.setIconSize(QSize(18,18));self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.pages=QStackedWidget();middle.addWidget(self.nav);middle.addWidget(self.pages,1);self.outer.addLayout(middle,1)
        for title,symbol in [('Apariencia','palette'),('Comportamiento','mouse-pointer-2'),('Atajos','keyboard'),('Ventanas','panels-top-left'),('Archivos y copias','files')]:
            from PySide6.QtWidgets import QListWidgetItem
            self.nav.addItem(QListWidgetItem(icon(symbol),title))
        self.build_config(False);self.build_config(True);self.build_shortcuts();self.build_rules();self.build_files();self.nav.currentRowChanged.connect(self.pages.setCurrentIndex);self.nav.setCurrentRow(0)
        bottom=QHBoxLayout();self.status=text_label('Los cambios se aplican sin reiniciar la sesión.','subtitle');bottom.addWidget(self.status,1);bottom.addWidget(button('Recargar',self.reload,symbol='refresh-cw'));self.apply_button=button('Aplicar cambios',self.apply,'primary',symbol='check');bottom.addWidget(self.apply_button);self.outer.addLayout(bottom);self.nav.currentRowChanged.connect(lambda i:self.apply_button.setVisible(i in (0,1,3)));QShortcut(QKeySequence('Ctrl+Return'),self).activated.connect(self.apply)
        self.load_values()
    def page(self):
        w=QWidget();w.setObjectName('page');layout=QVBoxLayout(w);layout.setContentsMargins(0,0,0,0);layout.setSpacing(14);self.pages.addWidget(w);return layout
    def build_config(self,behavior):
        layout=self.page();layout.addWidget(text_label('Cómo se comportan tus ventanas' if behavior else 'Un espacio a tu medida','title'));layout.addWidget(text_label('Los ajustes se guardan para el próximo inicio.' if behavior else 'Ajusta los espacios, bordes y colores del escritorio.','subtitle'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);holder=QWidget();holder.setObjectName('page');holder.setStyleSheet('background:transparent;');form=QFormLayout(holder);form.setContentsMargins(0,8,12,8);form.setVerticalSpacing(11)
        for key,(title,kind,low,high) in SCHEMA.items():
            if (key not in list(SCHEMA)[:10])!=behavior:continue
            if kind=='int':control=QSpinBox();control.setRange(low,high);control.setSuffix(' px');control.setMaximumWidth(180)
            elif kind=='float':control=QDoubleSpinBox();control.setRange(low,high);control.setSingleStep(.05);control.setDecimals(2)
            elif kind=='bool':control=QCheckBox(title)
            elif kind=='enum':
                control=QComboBox();labels={'longest_side':'Lado más largo','alternate':'Alternar dirección','spiral':'Espiral','first_child':'Antes de la actual','second_child':'Después de la actual','mod4':'Super','mod1':'Alt','control':'Ctrl','shift':'Shift'}
                for value in low:control.addItem(labels.get(value,value),value)
            else:
                control=QLineEdit();control.setMaxLength(7);control.setMaximumWidth(145)
            self.widgets[key]=control
            if kind=='color':
                row=QHBoxLayout();row.addWidget(control);row.addWidget(button('Elegir',lambda c=control:self.choose_color(c),symbol='palette'));row.addStretch();form.addRow(title,row)
            elif kind=='bool':form.addRow(control)
            else:form.addRow(title,control)
        scroll.setWidget(holder);layout.addWidget(scroll,1)
    def choose_color(self,control):
        c=QColorDialog.getColor(QColor(control.text()),self,'Elegir color')
        if c.isValid():control.setText(c.name())
    def load_values(self):
        for key,c in self.widgets.items():
            value=self.backend.values.get(key,'');kind=SCHEMA[key][1]
            if kind in ('int','float'):
                try:c.setValue(int(value) if kind=='int' else float(value))
                except ValueError:pass
            elif kind=='bool':c.setChecked(value=='true')
            elif kind=='enum':c.setCurrentIndex(max(0,c.findData(value)))
            else:c.setText(value)
    def values(self):
        result={}
        for key,c in self.widgets.items():
            kind=SCHEMA[key][1];result[key]=str(c.value()) if kind in ('int','float') else ('true' if c.isChecked() else 'false') if kind=='bool' else c.currentData() if kind=='enum' else c.text()
        return result
    def build_shortcuts(self):
        layout=self.page();row=QHBoxLayout();row.addWidget(text_label('Tus atajos','title'),1);row.addWidget(button('Nuevo',lambda:self.edit_shortcut(),symbol='plus'));layout.addLayout(row);self.shortcut_search=QLineEdit();self.shortcut_search.setPlaceholderText('Buscar por combinación, nombre o comando…');self.shortcut_search.textChanged.connect(self.render_shortcuts);layout.addWidget(self.shortcut_search);self.conflicts=text_label('','subtitle');layout.addWidget(self.conflicts)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['Combinación','Acción','Estado']);self.table.verticalHeader().hide();self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.setShowGrid(False);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Interactive);self.table.setColumnWidth(0,225);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);self.table.setColumnWidth(2,85);self.table.cellDoubleClicked.connect(lambda row,col:self.edit_selected());layout.addWidget(self.table,1)
        tools=QHBoxLayout();tools.addWidget(button('Editar',self.edit_selected,symbol='pencil'));tools.addWidget(button('Eliminar',self.delete_shortcut,'danger',symbol='trash'));tools.addStretch();tools.addWidget(button('Abrir en Vim',lambda:open_vim(self.shortcuts.path),symbol='terminal'));layout.addLayout(tools);self.render_shortcuts()
    def render_shortcuts(self):
        q=self.shortcut_search.text().casefold();conflicts=self.shortcuts.conflicts();ids={i for group in conflicts.values() for i in group};self.conflicts.setText(f'{len(self.shortcuts.rows)} grupos · '+(f'{len(conflicts)} combinaciones repetidas: puedes corregirlas aquí.' if conflicts else 'Sin combinaciones repetidas.'));self.table.setRowCount(0)
        for i,r in enumerate(self.shortcuts.rows):
            if q not in (r['title']+' '+r['key']+' '+r['command']).casefold():continue
            row=self.table.rowCount();self.table.insertRow(row)
            for col,value in enumerate([r['key'],r['title'],'Repetido' if i in ids else '']):
                item=QTableWidgetItem(value);item.setData(Qt.UserRole,i);item.setToolTip(r['command']);self.table.setItem(row,col,item)
                if i in ids and col==2:item.setForeground(QColor('#E0AE82'))
            self.table.setRowHeight(row,40)
    def selected_shortcut(self):
        row=self.table.currentRow();return self.table.item(row,0).data(Qt.UserRole) if row>=0 else None
    def edit_selected(self):
        index=self.selected_shortcut()
        if index is not None:self.edit_shortcut(index)
    def edit_shortcut(self,index=None):
        dialog=ShortcutEditor(self,self.shortcuts,index)
        if dialog.exec()==QDialog.Accepted:self.render_shortcuts();self.status.setText('Atajo guardado y recargado. Copia anterior conservada.');self.render_backups()
    def delete_shortcut(self):
        index=self.selected_shortcut()
        if index is None:return
        if QMessageBox.question(self,'Eliminar atajo','¿Eliminar '+self.shortcuts.rows[index]['key']+'?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        try:
            self.shortcuts.delete(index);subprocess.run(['pkill','-USR1','-u',str(__import__('os').getuid()),'-x','sxhkd'],capture_output=True);self.render_shortcuts();self.render_backups()
        except (ValueError,OSError) as e:self.status.setText(str(e))
    def build_rules(self):
        layout=self.page();layout.addWidget(text_label('Reglas de ventanas','title'));layout.addWidget(text_label('Define cómo se abren las aplicaciones. Las reglas se aplican a las ventanas nuevas.','subtitle'));self.rule_list=QListWidget();layout.addWidget(self.rule_list,1);row=QHBoxLayout();row.addWidget(button('Añadir regla',self.add_rule,symbol='plus'));row.addWidget(button('Editar',self.edit_rule,symbol='pencil'));row.addWidget(button('Quitar seleccionada',self.remove_rule,symbol='trash'));row.addStretch();layout.addLayout(row);self.render_rules()
    def render_rules(self):
        self.rule_list.clear()
        for r in self.rules:self.rule_list.addItem(r['class']+'   ·   '+{'tiled':'Mosaico','floating':'Flotante','fullscreen':'Pantalla completa'}[r['state']]+('   ·   escritorio '+r['desktop'] if r.get('desktop') else ''))
    def edit_rule(self):
        i=self.rule_list.currentRow()
        if i>=0:self.add_rule(i)
    def add_rule(self,index=None):
        dialog=QDialog(self);dialog.setWindowTitle('Nueva regla');dialog.resize(440,290);layout=QVBoxLayout(dialog);form=QFormLayout();app=QLineEdit();app.setPlaceholderText('Por ejemplo: Code, Gimp, Ghostty');state=QComboBox()
        for name,value in [('Mosaico','tiled'),('Flotante','floating'),('Pantalla completa','fullscreen')]:state.addItem(name,value)
        desktop=QLineEdit();desktop.setPlaceholderText('Opcional · ^1, ^2…');center=QCheckBox('Centrar la ventana');border=QCheckBox('Mostrar borde');border.setChecked(True);form.addRow('Clase de aplicación',app);form.addRow('Estado',state);form.addRow('Escritorio',desktop);form.addRow(center);form.addRow(border);layout.addLayout(form);error=text_label('','subtitle');layout.addWidget(error);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('Añadir');buttons.button(QDialogButtonBox.Cancel).setText('Cancelar');layout.addWidget(buttons);buttons.rejected.connect(dialog.reject)
        if index is not None:
            old=self.rules[index];app.setText(old['class']);state.setCurrentIndex(state.findData(old['state']));desktop.setText(old.get('desktop',''));center.setChecked(old.get('center',False));border.setChecked(old.get('border',True));dialog.setWindowTitle('Editar regla')
        def save():
            rule={'class':app.text().strip(),'state':state.currentData(),'desktop':desktop.text().strip(),'center':center.isChecked(),'border':border.isChecked()}
            updated=self.rules.copy()
            if index is None:updated.append(rule)
            else:updated[index]=rule
            try:self.backend.validate({},updated)
            except ValueError as e:error.setText(str(e));return
            self.rules=updated;self.render_rules();dialog.accept()
        buttons.accepted.connect(save);dialog.exec()
    def remove_rule(self):
        i=self.rule_list.currentRow()
        if i>=0:self.rules.pop(i);self.render_rules()
    def build_files(self):
        layout=self.page();layout.addWidget(text_label('Tus archivos de configuración','title'));layout.addWidget(text_label('Edición directa en Vim. Cada cambio guardado desde Ajustes conserva una copia anterior.','subtitle'))
        for title,path in [('BSPWM · inicio y monitores','bspwm/bspwmrc'),('sxhkd · atajos','sxhkd/sxhkdrc'),('Picom · efectos','bspwm/picom.conf'),('Polybar · barra','bspwm/polybar/config')]:layout.addWidget(button(title,lambda p=path:open_vim(Path.home()/'.config'/p),symbol='file-code'))
        layout.addWidget(text_label('Copias de seguridad','subtitle'));self.backups=QListWidget();layout.addWidget(self.backups,1);layout.addWidget(button('Restaurar copia seleccionada',self.restore_shortcuts,symbol='rotate-cw'));self.render_backups()
    def render_backups(self):
        self.backups.clear();root=Path.home()/'.local/share/orbit/settings-backups'
        for path in sorted(root.glob('*'),reverse=True)[:40]:self.backups.addItem(path.name);self.backups.item(self.backups.count()-1).setData(Qt.UserRole,str(path))
    def restore_shortcuts(self):
        item=self.backups.currentItem()
        if not item or not item.text().endswith(('-sxhkdrc','-desktop.json')):self.status.setText('Selecciona una copia de atajos o de ajustes.');return
        if item.text().endswith('-desktop.json'):
            if QMessageBox.question(self,'Restaurar ajustes','¿Aplicar esta copia del escritorio?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
            try:
                data=json.loads(Path(item.data(Qt.UserRole)).read_text());self.backend.apply(data['values'],data['rules']);self.reload();self.status.setText('Ajustes restaurados.')
            except (ValueError,OSError,KeyError,subprocess.SubprocessError) as e:self.status.setText(str(e))
            return
        if QMessageBox.question(self,'Restaurar atajos','¿Restaurar esta copia? Se guardará la configuración actual.',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        from settings_data import backup_file,atomic_write
        try:
            backup_file(self.shortcuts.path);atomic_write(self.shortcuts.path,Path(item.data(Qt.UserRole)).read_text());self.shortcuts.reload();subprocess.run(['pkill','-USR1','-u',str(__import__('os').getuid()),'-x','sxhkd'],capture_output=True);self.render_shortcuts();self.render_backups();self.status.setText('Atajos restaurados y recargados.')
        except OSError as e:self.status.setText(str(e))
    def reload(self):
        self.backend.reload();self.shortcuts.reload();self.rules=json.loads(json.dumps(self.backend.saved.get('rules',[])));self.load_values();self.render_rules();self.render_shortcuts();self.render_backups();self.status.setText('Configuración actual recargada.')
    def apply(self):
        try:
            self.backend.apply(self.values(),self.rules);self.status.setText('Cambios aplicados y guardados para el próximo inicio.');self.render_backups()
        except (ValueError,OSError,subprocess.SubprocessError) as e:self.status.setText('No se aplicó el cambio: '+str(e)[:170])

"""Personal project workspace and bounded tooling jobs, using the shared CLI."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
from PySide6.QtCore import Qt, QProcess, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,
    QStackedWidget,QFileDialog,QLineEdit,QComboBox,QSpinBox,QCheckBox,QPlainTextEdit,
    QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox,QApplication)
from desktop_common import Surface, text_label, button, launch
from ui_motion import reveal_content

LIBRARY=Path(__file__).resolve().parent.parent/'tools'
if str(LIBRARY) not in sys.path:sys.path.insert(0,str(LIBRARY))
from orbit_tools.common import private_write, read_json, redact, ToolError
from orbit_tools.web import project, framework

HOME=Path.home()
STATE=Path(os.environ.get('XDG_CONFIG_HOME',str(HOME/'.config')))/'orbit/tools.json'
CLI=LIBRARY/'cli.py'


def load_projects(path=STATE):
    raw=read_json(path,{})
    if not isinstance(raw,dict):raise ToolError('La lista de proyectos no es válida.')
    values=raw.get('projects',[])
    if not isinstance(values,list) or any(not isinstance(p,str) for p in values):
        raise ToolError('La lista de proyectos no es válida.')
    return list(dict.fromkeys(values))


def cli_argv(group,*args):
    return [sys.executable,str(CLI),group,*map(str,args)]


class ToolsWindow(Surface):
    def __init__(self,test=False):
        super().__init__('Wysun Tools',width=1000,height=680)
        self.test=test;self.projects=[] if test else load_projects();self.jobs=[];self.sharing=None
        nav=QHBoxLayout();self.pages=QStackedWidget();self.tabs=[]
        for title in ('Proyectos','Diagnósticos','Archivos','Recordatorios'):
            b=button(title,lambda index=len(self.tabs):self.page(index));b.setCheckable(True);self.tabs.append(b);nav.addWidget(b)
        nav.addStretch();self.outer.addLayout(nav)
        self.make_projects();self.make_diagnostics();self.make_sharing();self.make_resets();self.outer.addWidget(self.pages,1)
        self.status=text_label('','subtitle');self.outer.addWidget(self.status)
        self.page(0);self.refresh_projects()

    def page(self,index):
        for i,b in enumerate(self.tabs):b.setChecked(i==index)
        self.pages.setCurrentIndex(index);reveal_content(self.pages.currentWidget())
        if index==3:self.refresh_resets()

    def panel(self):
        widget=QWidget();layout=QVBoxLayout(widget);layout.setContentsMargins(0,0,0,0);layout.setSpacing(14)
        self.pages.addWidget(widget);return layout

    def make_projects(self):
        page=self.panel();row=QHBoxLayout();row.addWidget(text_label('Tus proyectos','previewTitle'),1)
        row.addWidget(button('Añadir carpeta',self.choose_project,'primary','folder-open'));row.addWidget(button('Quitar de la lista',self.forget_project));page.addLayout(row)
        split=QHBoxLayout();self.project_list=QListWidget();self.project_list.setMinimumWidth(240);self.project_list.currentItemChanged.connect(self.select_project);split.addWidget(self.project_list,1)
        details=QVBoxLayout();self.project_title=text_label('Añade un proyecto','title');details.addWidget(self.project_title)
        self.project_info=text_label('','subtitle');details.addWidget(self.project_info)
        row=QHBoxLayout();self.folder_button=button('Carpeta',self.open_folder,symbol='folder-open');self.editor_button=button('Editor',self.open_editor,symbol='terminal');row.addWidget(self.folder_button);row.addWidget(self.editor_button);row.addStretch();details.addLayout(row)
        row=QHBoxLayout();self.task=QComboBox();self.task.setAccessibleName('Tarea del proyecto');row.addWidget(self.task,1)
        self.task_button=button('Ejecutar en terminal',self.run_task,'primary','terminal');row.addWidget(self.task_button);details.addLayout(row)
        row=QHBoxLayout();self.doctor_button=button('Revisar proyecto',lambda:self.project_check('doctor'));self.env_button=button('Revisar variables',lambda:self.project_check('env'));row.addWidget(self.doctor_button);row.addWidget(self.env_button);row.addStretch();details.addLayout(row)
        self.project_output=QPlainTextEdit();self.project_output.setReadOnly(True);self.project_output.setPlaceholderText('Selecciona un proyecto para ver sus tareas.');details.addWidget(self.project_output,1)
        split.addLayout(details,2);page.addLayout(split,1)
        row=QHBoxLayout();row.addWidget(button('VMs de Google Cloud',lambda:self.terminal('cloud'),symbol='terminal'));row.addStretch();page.addLayout(row)

    def refresh_projects(self):
        current=self.selected_project();self.project_list.clear()
        for name in self.projects:
            path=Path(name);item=QListWidgetItem(path.name+'\n'+str(path));item.setData(Qt.UserRole,str(path));item.setToolTip(str(path));self.project_list.addItem(item)
            if str(path)==current:self.project_list.setCurrentItem(item)
        if self.project_list.count() and not self.project_list.currentItem():self.project_list.setCurrentRow(0)
        self.select_project()

    def selected_project(self):
        item=self.project_list.currentItem();return item.data(Qt.UserRole) if item else None

    def save_projects(self):
        if not self.test:private_write(STATE,json.dumps({'projects':self.projects},ensure_ascii=False,indent=2)+'\n')

    def add_project(self,path):
        value=str(Path(path).expanduser().resolve())
        if not Path(value).is_dir():raise ToolError('La carpeta no existe.')
        if value not in self.projects:self.projects.append(value);self.save_projects();self.refresh_projects()

    def choose_project(self):
        path=QFileDialog.getExistingDirectory(self,'Añadir proyecto',str(HOME))
        if path:self.guard(lambda:self.add_project(path))

    def forget_project(self):
        value=self.selected_project()
        if value:self.projects.remove(value);self.save_projects();self.refresh_projects()

    def select_project(self,*_):
        value=self.selected_project();self.task.clear();self.task_button.setEnabled(False)
        for b in (self.folder_button,self.editor_button,self.doctor_button,self.env_button):b.setEnabled(bool(value))
        if not value:self.project_title.setText('Añade un proyecto');self.project_info.clear();return
        root=Path(value);self.project_title.setText(root.name);self.project_info.setText(str(root))
        try:
            _,package,manager,_=project(root);scripts=package.get('scripts',{})
            for name in ('dev','build','test','lint','typecheck'):
                if name in scripts:self.task.addItem(name)
            self.project_info.setText(f'{root}\n{framework(package)} · {manager}')
            self.task_button.setEnabled(self.task.count()>0)
            self.project_output.setPlainText('\n'.join(f'{name}  {redact(str(value))}' for name,value in scripts.items()))
        except ToolError:
            self.project_output.setPlainText('Carpeta disponible. No contiene un proyecto Node compatible.')

    def terminal(self,group,*args):
        if not self.test:launch([str(HOME/'.local/bin/desktop-terminal'),'-e',*cli_argv(group,*args)])
        self.status.setText('Abierto en terminal.' if not self.test else 'Terminal preparada.')

    def run_task(self):
        if self.selected_project() and self.task.currentText():self.terminal('dev',self.task.currentText(),'-C',self.selected_project())

    def open_folder(self):
        if self.selected_project() and not self.test:QDesktopServices.openUrl(QUrl.fromLocalFile(self.selected_project()))

    def open_editor(self):
        if self.selected_project() and not self.test:launch([str(HOME/'.local/bin/desktop-terminal'),'-e','nvim',self.selected_project()])

    def project_check(self,action):
        if self.selected_project():self.run_job(cli_argv('dev',action,'-C',self.selected_project(),'--json'),self.project_output)

    def make_diagnostics(self):
        page=self.panel();page.addWidget(text_label('Revisar un objetivo','previewTitle'))
        row=QHBoxLayout();self.audit_kind=QComboBox();self.audit_kind.addItems(['HTTP','TLS','Puertos TCP','Sistema local','Secretos del proyecto']);row.addWidget(self.audit_kind)
        self.target=QLineEdit();self.target.setPlaceholderText('URL, dominio o IP');self.target.setAccessibleName('Objetivo del diagnóstico');row.addWidget(self.target,1)
        self.audit_button=button('Revisar',self.audit,'primary');row.addWidget(self.audit_button);self.cancel_audit=button('Cancelar',self.cancel_jobs);self.cancel_audit.setEnabled(False);row.addWidget(self.cancel_audit);page.addLayout(row)
        self.audit_scope=text_label('','subtitle');page.addWidget(self.audit_scope)
        self.audit_output=QPlainTextEdit();self.audit_output.setReadOnly(True);self.audit_output.setPlaceholderText('Los resultados aparecerán aquí.');page.addWidget(self.audit_output,1)
        self.audit_kind.currentIndexChanged.connect(self.audit_hint);self.audit_hint()

    def audit_hint(self):
        index=self.audit_kind.currentIndex();self.target.setEnabled(index<3)
        self.target.setPlaceholderText(['https://tu-sitio.example','dominio o IP','IP de tu equipo o laboratorio','',''][index])
        self.audit_scope.setText(['Estado y cabeceras HTTP.','Certificado, protocolo y caducidad.','TCP: 22, 80, 443, 3000, 8000 y 8080. Solo equipos propios o autorizados.','Puertos locales y permisos de claves.','Archivos Git del proyecto seleccionado. No se muestran valores de secretos.'][index])

    def audit(self):
        index=self.audit_kind.currentIndex();value=self.target.text().strip()
        if index<3 and not value:self.status.setText('Introduce un objetivo.');self.target.setFocus();return
        args=[['http',value],['tls',value],['ports',value,'--ports','22,80,443,3000,8000,8080'],['host'],['project',self.selected_project() or '']][index]
        if index==4 and not self.selected_project():self.status.setText('Selecciona primero un proyecto.');return
        self.run_job(cli_argv('audit',*args,'--json'),self.audit_output)

    def make_sharing(self):
        page=self.panel();page.addWidget(text_label('Compartir una carpeta','previewTitle'))
        row=QHBoxLayout();self.share_path=QLineEdit();self.share_path.setPlaceholderText('Seleccionar carpeta');self.share_path.setAccessibleName('Carpeta compartida');row.addWidget(self.share_path,1);row.addWidget(button('Elegir',self.choose_share));page.addLayout(row)
        row=QHBoxLayout();self.share_port=QSpinBox();self.share_port.setRange(1024,65535);self.share_port.setValue(8000);self.share_port.setAccessibleName('Puerto del servidor');row.addWidget(text_label('Puerto'));row.addWidget(self.share_port)
        self.uploads=QCheckBox('Recibir archivos');row.addWidget(self.uploads);row.addStretch();page.addLayout(row)
        page.addWidget(text_label('Acceso local. Para compartir por LAN usa la terminal con código de acceso o HTTPS.','subtitle'))
        row=QHBoxLayout();self.share_button=button('Iniciar',self.toggle_share,'primary');row.addWidget(self.share_button);self.open_share_button=button('Abrir en navegador',self.open_share);self.open_share_button.setEnabled(False);row.addWidget(self.open_share_button);row.addStretch();page.addLayout(row)
        self.share_output=QPlainTextEdit();self.share_output.setReadOnly(True);self.share_output.setPlaceholderText('El servidor se detiene al cerrar este panel.');page.addWidget(self.share_output,1)
        row=QHBoxLayout();row.addWidget(button('Archivos recibidos',self.open_inbox,symbol='folder-open'));row.addWidget(button('Compartir por LAN en terminal',self.share_lan,symbol='terminal'));row.addStretch();page.addLayout(row)

    def choose_share(self):
        value=QFileDialog.getExistingDirectory(self,'Carpeta compartida',str(HOME))
        if value:self.share_path.setText(value)

    def share_args(self,lan=False):
        path=self.share_path.text().strip()
        if not path or not Path(path).is_dir():raise ToolError('Elige una carpeta existente.')
        args=['-C',str(Path(path).resolve()),'--port',str(self.share_port.value())]
        if self.uploads.isChecked():args+=['--uploads','--upload-dir',str(HOME/'.local/share/orbit/transfers/inbox')]
        if lan:args+=['--lan','--ask-code']
        return args

    def open_inbox(self):
        path=HOME/'.local/share/orbit/transfers/inbox'
        if not self.test:
            path.mkdir(parents=True,exist_ok=True,mode=0o700)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def share_lan(self):self.guard(lambda:self.terminal('share',*self.share_args(lan=True)))

    def toggle_share(self):
        if self.sharing and self.sharing.state()!=QProcess.NotRunning:self.stop_share();return
        self.guard(self.start_share)

    def start_share(self):
        args=self.share_args();self.share_output.clear();self.sharing=QProcess(self);job=self.sharing
        job.setProcessChannelMode(QProcess.MergedChannels)
        job.readyReadStandardOutput.connect(lambda:self.append_output(job,self.share_output))
        job.finished.connect(self.share_finished);job.errorOccurred.connect(lambda _:self.share_finished())
        job.started.connect(self.share_started);job.start(sys.executable,[str(CLI),'share',*args])
        self.share_button.setEnabled(False)

    def share_started(self):
        self.share_button.setEnabled(True);self.share_button.setText('Detener')
        self.share_path.setEnabled(False);self.share_port.setEnabled(False);self.uploads.setEnabled(False)
        self.open_share_button.setEnabled(False);self.status.setText('Iniciando servidor…')

    def stop_share(self):
        if self.sharing and self.sharing.state()!=QProcess.NotRunning:
            self.sharing.terminate();job=self.sharing;QTimer.singleShot(2000,lambda:job.kill() if job.state()!=QProcess.NotRunning else None)

    def share_finished(self,*_):
        self.share_button.setEnabled(True);self.share_button.setText('Iniciar');self.open_share_button.setEnabled(False)
        self.share_path.setEnabled(True);self.share_port.setEnabled(True);self.uploads.setEnabled(True)
        self.status.setText('Servidor detenido.')

    def open_share(self):
        if self.open_share_button.isEnabled() and not self.test:QDesktopServices.openUrl(QUrl(f'http://127.0.0.1:{self.share_port.value()}'))

    def make_resets(self):
        page=self.panel();row=QHBoxLayout();row.addWidget(text_label('Próximos resets','previewTitle'),1);row.addWidget(button('Actualizar',self.refresh_resets));row.addWidget(button('Editar en terminal',lambda:self.terminal('resets','edit')));page.addLayout(row)
        self.resets_table=QTableWidget(0,4);self.resets_table.setHorizontalHeaderLabels(['Cuenta','Servicio','Reset','Tiempo restante']);self.resets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.resets_table.setEditTriggers(QTableWidget.NoEditTriggers);self.resets_table.verticalHeader().hide();page.addWidget(self.resets_table,1)
        page.addWidget(text_label('Recordatorios guardados por ti.','subtitle'))

    def refresh_resets(self):
        if self.test:return
        self.run_job(cli_argv('resets','--json','list'),None,callback=self.show_resets)

    def show_resets(self,raw):
        try:values=json.loads(raw)
        except ValueError:self.status.setText('No se pudieron leer los recordatorios.');return
        rows=[(a,r) for a in values for r in a.get('resets',[])];self.resets_table.setRowCount(len(rows))
        for i,(account,reset) in enumerate(rows):
            seconds=reset.get('remaining_seconds',0);remaining='Pasado' if seconds<0 else f'{seconds//3600} h {(seconds%3600)//60} min'
            for col,value in enumerate((account['name'],account['service'],reset['label'],remaining)):self.resets_table.setItem(i,col,QTableWidgetItem(str(value)))
        self.status.setText('Sin recordatorios.' if not rows else '')

    def run_job(self,argv,output,callback=None):
        if self.jobs:self.status.setText('Hay una revisión en curso.');return
        job=QProcess(self);job.data=bytearray();self.jobs.append(job);self.audit_button.setEnabled(False);self.cancel_audit.setEnabled(True)
        self.status.setText('Revisando…')
        if output:output.clear()
        job.setProcessChannelMode(QProcess.MergedChannels)
        def collect():
            chunk=bytes(job.readAllStandardOutput());job.data.extend(chunk[:max(0,1024*1024-len(job.data))])
        job.readyReadStandardOutput.connect(collect)
        def finish(code=2,*_):
            if job not in self.jobs:return
            collect();raw=job.data.decode(errors='replace');self.jobs.remove(job)
            self.audit_button.setEnabled(True);self.cancel_audit.setEnabled(False)
            self.status.setText('Revisión completa.' if code==0 else 'Hay hallazgos.' if code==1 else 'No se pudo completar la revisión.')
            if callback and code==0:callback(raw)
            elif output:output.setPlainText(self.format_report(raw))
            job.deleteLater()
        job.finished.connect(finish);job.errorOccurred.connect(lambda _:finish());job.start(argv[0],argv[1:])

    def format_report(self,raw):
        try:report=json.loads(raw)
        except ValueError:return redact(raw.strip())
        if not isinstance(report,dict):return redact(raw.strip())
        labels={'pass':'Correcto','warn':'Revisar','fail':'Fallo','info':'Info'}
        lines=[f"{labels.get(c['status'],c['status'])} · {c['name']}"+(f"\n  {c['detail']}" if c.get('detail') else '') for c in report.get('checks',[])]
        if report.get('data'):lines+=['',json.dumps(report['data'],ensure_ascii=False,indent=2)]
        return redact('\n'.join(lines))

    def append_output(self,job,output):
        text=redact(bytes(job.readAllStandardOutput()).decode(errors='replace'))
        if job is self.sharing and 'Servidor:' in text:
            self.open_share_button.setEnabled(True);self.status.setText('Servidor local activo.')
        if output.document().blockCount()>1000:output.clear()
        output.appendPlainText(text.strip())

    def cancel_jobs(self):
        for job in self.jobs:
            job.terminate();timer=QTimer(job);timer.setSingleShot(True);timer.timeout.connect(lambda j=job:j.kill() if j.state()!=QProcess.NotRunning else None);timer.start(2000)

    def guard(self,fn):
        try:fn()
        except (ToolError,OSError) as error:self.status.setText(str(error))

    def closeEvent(self,event):
        self.stop_share();self.cancel_jobs();super().closeEvent(event)

    def shutdown_jobs(self):
        for job in [*self.jobs,*([self.sharing] if self.sharing else [])]:
            if job.state()!=QProcess.NotRunning:
                job.terminate()
                if not job.waitForFinished(1500):job.kill();job.waitForFinished(500)

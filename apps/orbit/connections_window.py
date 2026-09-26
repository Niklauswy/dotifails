"""Independent connection center: NetworkManager, BlueZ and SSH."""
import json,os,re,subprocess,time
from pathlib import Path
from PySide6.QtCore import Qt,QProcess,QProcessEnvironment,QTimer,QSize,QEvent,QDateTime,QLocale
from PySide6.QtWidgets import (QApplication,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QSpinBox,QListWidget,QListWidgetItem,QLabel,QMessageBox,QInputDialog,QWidget,QFrame,QScrollArea,QGridLayout,QCheckBox)
from desktop_common import Surface,button,text_label,launch,open_vim
from connections_data import ConnectionScan,SSHProfiles,ssh_args
from icons import icon,badge
from PySide6.QtGui import QKeySequence,QShortcut
from connection_details import DetailScan,identity

class ConnectionsWindow(Surface):
    def __init__(self):
        super().__init__('Conexiones','Redes, dispositivos y servidores · todo en un lugar',1040,650)
        self.mode='wifi';self.scan=None;self.rows=[];self.meta={};self.proc=None;self.prompting=False;self.output='';self.failed=False;self.scan_process=None;self.profile_store=SSHProfiles();self.page_state={};self.detail_cache={};self.detail_scan=None;self.detail_for='';self.refreshing=False
        self.tabs={};tabs=QHBoxLayout();tabs.setSpacing(5)
        for i,(key,title,symbol) in enumerate([('wifi','Wi-Fi y Ethernet','wifi'),('bluetooth','Bluetooth','bluetooth'),('vpn','VPN','vpn'),('ssh','SSH','ssh'),('saved','Guardadas','files')]):
            b=button(title,lambda k=key:self.select_mode(k),symbol=symbol);b.setCheckable(True);b.setToolTip(f'Alt + {i+1}');tabs.addWidget(b);self.tabs[key]=b
            QShortcut(QKeySequence(f'Alt+{i+1}'),self).activated.connect(lambda k=key:self.select_mode(k))
        tabs.addStretch();self.outer.addLayout(tabs)
        tools=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('Buscar red o dispositivo…');self.search.textChanged.connect(self.render);self.search.installEventFilter(self);tools.addWidget(self.search,1);self.toggle=button('Wi-Fi',self.toggle_radio,symbol='power');tools.addWidget(self.toggle);self.refresh=button('Actualizar',self.rescan,symbol='refresh-cw');tools.addWidget(self.refresh);self.outer.addLayout(tools)
        middle=QHBoxLayout();middle.setSpacing(22);left=QWidget();left.setFixedWidth(360);ll=QVBoxLayout(left);ll.setContentsMargins(0,0,0,0);ll.setSpacing(9);self.list_heading=text_label('Redes cercanas','subtitle');ll.addWidget(self.list_heading)
        from enhanced import ModernDelegate
        self.list=QListWidget();self.list.setItemDelegate(ModernDelegate());self.list.setStyleSheet('QListWidget {padding:0;}');self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.list.setSpacing(3);self.list.currentRowChanged.connect(self.selection_changed);self.list.itemActivated.connect(self.activate);ll.addWidget(self.list,1);self.empty=text_label('Consultando conexiones…','subtitle');self.empty.setAlignment(Qt.AlignCenter);ll.addWidget(self.empty,1)
        self.add=button('Red oculta…',self.add_item,symbol='plus');ll.addWidget(self.add);self.advanced=button('Administrar perfiles',self.advanced_settings,symbol='settings');ll.addWidget(self.advanced);middle.addWidget(left)
        line=QFrame();line.setFixedWidth(1);line.setStyleSheet('background:rgba(160,170,195,26);');middle.addWidget(line)
        self.inspector=QWidget();pr=QVBoxLayout(self.inspector);pr.setContentsMargins(0,0,0,0);pr.setSpacing(13);hero=QHBoxLayout();self.detail_icon=QLabel();self.detail_icon.setFixedSize(45,45);hero.addWidget(self.detail_icon);title_stack=QVBoxLayout();title_stack.setSpacing(4);self.detail_title=text_label('Selecciona una conexión','title');self.detail_title.setStyleSheet('font-size:19px; font-weight:600;');self.detail_title.setMaximumHeight(60);title_stack.addWidget(self.detail_title);self.detail_state=text_label('Sus detalles aparecerán aquí.','subtitle');title_stack.addWidget(self.detail_state);hero.addLayout(title_stack,1);pr.addLayout(hero)
        self.metrics=QHBoxLayout();self.metrics.setSpacing(10);pr.addLayout(self.metrics)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);container=QWidget();container.setObjectName('page');self.info_form=QFormLayout(container);self.info_form.setContentsMargins(0,2,6,3);self.info_form.setVerticalSpacing(12);self.info_form.setHorizontalSpacing(20);self.info_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow);scroll.setWidget(container);pr.addWidget(scroll,1)
        self.auto_connect=QCheckBox('Conectar automáticamente');self.auto_connect.clicked.connect(self.change_auto);pr.addWidget(self.auto_connect)
        self.primary=button('Conectar',self.activate,'primary');self.primary.setMinimumHeight(38);pr.addWidget(self.primary)
        self.action_grid=QGridLayout();self.action_grid.setSpacing(6);pr.addLayout(self.action_grid);middle.addWidget(self.inspector,1);self.outer.addLayout(middle,1)
        footer=QHBoxLayout();self.status=text_label('','subtitle');footer.addWidget(self.status,1);hint=text_label('↑↓ Selección · Alt 1–5 Secciones · Ctrl Tab Cambiar','subtitle');hint.setWordWrap(False);footer.addWidget(hint);self.outer.addLayout(footer)
        self.search.returnPressed.connect(self.activate);self.periodic=QTimer(self);self.periodic.setInterval(5000);self.periodic.timeout.connect(lambda:self.load() if self.isVisible() and not self.busy() else None);self.periodic.start()
        self.detail_timer=QTimer(self);self.detail_timer.setSingleShot(True);self.detail_timer.setInterval(100);self.detail_timer.timeout.connect(self.load_detail)
        for seq,fn in [('Ctrl+Tab',lambda:self.cycle_mode(1)),('Ctrl+Shift+Tab',lambda:self.cycle_mode(-1)),('Ctrl+L',self.search.setFocus),('Ctrl+R',self.rescan)]:QShortcut(QKeySequence(seq),self).activated.connect(fn)
        self.select_mode('wifi')
    def busy(self):return bool(self.proc and self.proc.state()!=QProcess.NotRunning)
    def cycle_mode(self,step):
        keys=list(self.tabs);self.select_mode(keys[(keys.index(self.mode)+step)%len(keys)])
    def eventFilter(self,obj,event):
        if obj==self.search and event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Down,Qt.Key_Up):
            self.list.setCurrentRow(max(0,min(self.list.count()-1,self.list.currentRow()+(1 if event.key()==Qt.Key_Down else -1))));return True
        return super().eventFilter(obj,event)
    def select_mode(self,mode):
        if self.rows:self.page_state[self.mode]=(self.search.text(),identity(self.current()) if self.current() else '',self.list.verticalScrollBar().value())
        self.mode=mode;self.rows=[];self.meta={};self.detail_for='';state=self.page_state.get(mode,('', '',0));self.search.blockSignals(True);self.search.setText(state[0]);self.search.blockSignals(False)
        self.search.setPlaceholderText({'wifi':'Buscar red o dispositivo…','bluetooth':'Buscar dispositivo…','vpn':'Buscar VPN guardada…','ssh':'Buscar servidor o alias…','saved':'Buscar conexión guardada…'}[mode]);self.toggle.setVisible(mode in ('wifi','bluetooth'));self.add.setVisible(mode in ('wifi','vpn','ssh'));self.add.setText({'wifi':'Conectar a red oculta…','vpn':'Añadir VPN…','ssh':'Nueva conexión SSH'}.get(mode,'Añadir'));self.advanced.setText('Editar configuración SSH' if mode=='ssh' else 'Administrar perfiles');self.advanced.setVisible(mode!='bluetooth');self.list_heading.setText({'wifi':'REDES Y DISPOSITIVOS','bluetooth':'TUS DISPOSITIVOS','vpn':'CONEXIONES PRIVADAS','ssh':'TUS SERVIDORES','saved':'PERFILES GUARDADOS'}[mode])
        for k,b in self.tabs.items():b.setChecked(k==mode)
        self.refresh.setText('Buscar dispositivos' if mode=='bluetooth' else 'Buscar redes' if mode=='wifi' else 'Actualizar')
        self.refreshing=True;self.render();self.load();self.search.setFocus()
    def load(self):
        if self.scan and self.scan.isRunning():return
        mode=self.mode;self.refreshing=True;self.scan=ConnectionScan(mode);self.scan.ready.connect(self.loaded);self.scan.finished.connect(lambda m=mode:QTimer.singleShot(0,self.load) if self.mode!=m else None);self.scan.start()
    def loaded(self,mode,rows,meta):
        if mode!=self.mode:return
        unchanged=rows==self.rows and meta==self.meta
        self.refreshing=False;self.rows=rows;self.meta=meta;self.toggle.setText(('Desactivar ' if meta.get('enabled') else 'Activar ')+('Bluetooth' if mode=='bluetooth' else 'Wi-Fi'));self.toggle.setEnabled(not self.busy() and (mode!='bluetooth' or meta.get('available',False)))
        if not unchanged or not rows:self.render()
        current=self.current()
        if current and current.get('uuid') and time.monotonic()-self.detail_cache.get(identity(current),{}).get('time',0)>15:self.detail_timer.start()
        if not self.busy():self.status.setText(meta.get('error') or f'{len(rows)} '+('dispositivos' if mode=='bluetooth' else 'conexiones'))
    def current(self):
        item=self.list.currentItem();return item.data(Qt.UserRole) if item else None
    def render(self):
        selected=self.current();state=self.page_state.get(self.mode,('', '',0));previous=identity(selected) if selected else state[1];scroll=self.list.verticalScrollBar().value() if selected else state[2];q=self.search.text().casefold();self.list.blockSignals(True);self.list.clear()
        for r in self.rows:
            if q not in (r['title']+' '+r.get('subtitle','')).casefold():continue
            item=QListWidgetItem();item.setData(Qt.UserRole,r);self.list.addItem(item)
            if identity(r)==previous:self.list.setCurrentItem(item)
        if self.list.currentRow()<0:self.list.setCurrentRow(0)
        self.list.verticalScrollBar().setValue(scroll);self.list.blockSignals(False);empty=self.list.count()==0;self.empty.setVisible(empty);self.list.setVisible(not empty)
        if self.meta.get('error'):message=self.meta['error']
        elif self.refreshing and not self.rows:message='Consultando…'
        elif q:message='No hay coincidencias.'
        elif self.mode=='bluetooth':message='No hay dispositivos cercanos.\nPulsa Buscar dispositivos para descubrirlos.' if self.meta.get('available') else 'Sin adaptador Bluetooth.'
        elif self.mode=='wifi':message='No hay redes disponibles.\nComprueba el Wi-Fi o pulsa Buscar redes.'
        else:message='No hay conexiones guardadas.\nPuedes añadir una abajo.'
        self.empty.setText(message);self.selection_changed()
    @staticmethod
    def clear_layout(layout):
        while layout.count():
            item=layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
    def selection_changed(self,*_):
        r=self.current();self.primary.setEnabled(bool(r) and not self.busy());self.auto_connect.hide();self.clear_layout(self.metrics);self.clear_layout(self.action_grid)
        while self.info_form.rowCount():self.info_form.removeRow(0)
        if not r:
            self.detail_icon.setPixmap(badge(self.mode,44));self.detail_title.setText('Selecciona una conexión');self.detail_state.setText('Detalles y controles sin abrir otro menú.');self.primary.hide();return
        self.primary.show();self.detail_icon.setPixmap(badge(r.get('icon',self.mode),44));self.detail_title.setText(r['title']);connected=r.get('connected');self.detail_state.setText('Conectado' if connected else 'Emparejado · disponible' if r.get('paired') else 'Conexión guardada' if r['kind'] in ('ssh','profile') else 'Disponible');self.detail_state.setStyleSheet('color:#8FCDA9;' if connected else 'color:#A8ADBD;')
        self.primary.setText('Abrir terminal SSH' if r['kind']=='ssh' else 'Desconectar' if connected else 'Emparejar dispositivo' if r['kind']=='bluetooth' and not r['paired'] else 'Conectar')
        info=[];metrics=[];actions=[];cached=self.detail_cache.get(identity(r),{}).get('data',{})
        if r['kind']=='wifi':
            metrics=[('SEÑAL',str(r.get('signal','—'))+'%'),('SEGURIDAD',r.get('security','—')),('BANDA','5 GHz' if r.get('frequency','').startswith('5') else '6 GHz' if r.get('frequency','').startswith('6') else '2.4 GHz' if r.get('frequency','').startswith('2') else '—')]
            info=(cached.get('info') or r.get('info',[]))+[('Interfaz',r.get('device','—')),('Canal',r.get('channel','—')),('Punto de acceso',r.get('bssid','—')),('Capacidad de la red',r.get('rate','—'))]
        elif r['kind'] in ('ethernet','network_device'):
            metrics=[('CONEXIÓN','Ethernet' if r['kind']=='ethernet' else 'Wi-Fi'),('ESTADO','Activa' if connected else 'Desconectada')];info=cached.get('info') or r.get('info',[]) or [('Interfaz',r.get('device','—'))]
        elif r['kind']=='bluetooth':
            metrics=[('BATERÍA',str(r['battery'])+'%' if r.get('battery') is not None else 'Sin dato'),('EMPAREJADO','Sí' if r.get('paired') else 'No'),('CONFIANZA','Sí' if r.get('trusted') else 'No')];info=[('Dirección',r['address']),('Tipo de dispositivo',{'audio-headset':'Auriculares','audio-headphones':'Auriculares','audio-card':'Dispositivo de audio','computer':'Ordenador','input-mouse':'Ratón','input-keyboard':'Teclado','phone':'Teléfono'}.get(r.get('device_type'),r.get('device_type','Dispositivo'))),('Adaptador',self.meta.get('adapter',r.get('adapter','Bluetooth')))];actions.append(('Dejar de confiar' if r['trusted'] else 'Confiar',lambda row=dict(r):self.command(['bluetoothctl','untrust' if row['trusted'] else 'trust',row['address']]),'shield-check',''))
            if r.get('paired'):actions.append(('Olvidar dispositivo',lambda row=dict(r):self.forget(row),'trash','danger'))
        elif r['kind']=='ssh':
            metrics=[('PUERTO',str(r.get('port',22))),('ORIGEN','OpenSSH' if r.get('imported') else 'Órbita')];info=[('Servidor',r['host']),('Usuario',r['user'] or 'Usuario de la sesión'),('Alias',r.get('alias') or r['name']),('Autenticación','Claves, agente o contraseña de OpenSSH')]
            actions.append(('Editar en Vim' if r.get('imported') else 'Editar conexión',lambda row=dict(r):open_vim(Path.home()/'.ssh/config') if row.get('imported') else self.ssh_editor(row),'pencil',''))
            if not r.get('imported'):actions.append(('Eliminar conexión',lambda row=dict(r):self.forget(row),'trash','danger'))
        elif r['kind']=='profile':
            metrics=[('TIPO','VPN' if r.get('icon')=='vpn' else 'Perfil de red'),('ESTADO','Activo' if connected else 'Guardado')];info=cached.get('info') or [('Perfil',r['title']),('Configuración','Consultando…')]
        if r.get('uuid'):
            self.auto_connect.blockSignals(True);self.auto_connect.setChecked(cached.get('auto',r.get('auto',False)));self.auto_connect.blockSignals(False);self.auto_connect.setVisible('auto' in cached or 'auto' in r)
            actions.append(('Configurar IP y DNS',lambda row=dict(r):launch(['nm-connection-editor','--edit',row['uuid']]),'settings',''))
            if r['kind']=='profile':actions.append(('Olvidar conexión',lambda row=dict(r):self.forget(row),'trash','danger'))
        actions.append(('Copiar datos',self.copy_details,'copy',''))
        for title,value in metrics:
            box=QWidget();box.setStyleSheet('background:rgba(160,175,215,9);border-radius:7px;');layout=QVBoxLayout(box);layout.setContentsMargins(11,9,11,9);layout.setSpacing(5);label=text_label(title,'subtitle');label.setStyleSheet('font-size:10px;color:#939AAC;background:transparent');layout.addWidget(label);value_label=text_label(value);value_label.setStyleSheet('font-size:14px;font-weight:600;background:transparent');layout.addWidget(value_label);self.metrics.addWidget(box,1)
        seen=set();self.visible_details=[]
        for key,value in info:
            if key in seen:continue
            seen.add(key);value=str(value or '—');name=text_label(key,'subtitle');name.setFixedWidth(148);content=text_label(value);content.setTextInteractionFlags(Qt.TextSelectableByMouse);self.info_form.addRow(name,content);self.visible_details.append((key,value))
        for i,(title,fn,symbol,name) in enumerate(actions):
            b=button(title,fn,name,symbol);b.setEnabled(not self.busy());self.action_grid.addWidget(b,i//2,i%2)
        key=identity(r)
        if r.get('uuid') and (key not in self.detail_cache or time.monotonic()-self.detail_cache[key]['time']>15):self.detail_timer.start()
    def load_detail(self):
        r=self.current()
        if not r or not r.get('uuid') or (self.detail_scan and self.detail_scan.isRunning()):return
        self.detail_scan=DetailScan(r);self.detail_for=identity(r);self.detail_scan.ready.connect(self.detail_ready);self.detail_scan.finished.connect(self.detail_finished);self.detail_scan.start()
    def detail_ready(self,key,data):
        unchanged=self.detail_cache.get(key,{}).get('data')==data
        self.detail_cache[key]={'time':time.monotonic(),'data':data}
        if not unchanged and self.current() and identity(self.current())==key:self.selection_changed()
    def detail_finished(self):
        if self.current() and identity(self.current())!=self.detail_for:self.detail_timer.start()
    def change_auto(self,checked):
        r=self.current()
        if r and r.get('uuid'):self.detail_cache.pop(identity(r),None);self.command(['nmcli','connection','modify','uuid',r['uuid'],'connection.autoconnect','yes' if checked else 'no'])
    def copy_details(self):
        r=self.current()
        if r:QApplication.clipboard().setText(r['title']+'\n'+'\n'.join(k+': '+v for k,v in self.visible_details));self.status.setText('Datos de la conexión copiados.')
    def activate(self,*_):
        r=self.current()
        if not r or self.busy():return
        kind=r['kind']
        if kind=='ssh':launch(ssh_args(r));self.hide();return
        if kind=='network_device':self.command(['nmcli','--ask','device','disconnect' if r.get('connected') else 'connect',r['device']]);return
        if kind=='wifi':args=['nmcli','--ask','--wait','30','device','disconnect',r['device']] if r['connected'] else ['nmcli','--ask','--wait','30','device','wifi','connect',r['ssid'],'ifname',r['device']]
        elif kind=='ethernet':args=['nmcli','--ask','device','disconnect' if r['connected'] else 'connect',r['device']]
        elif kind=='profile':args=['nmcli','--ask','--wait','30','connection','down' if r['connected'] else 'up','uuid',r['uuid']]
        else:args=['bluetoothctl','--agent','KeyboardDisplay','disconnect' if r['connected'] else 'connect' if r['paired'] else 'pair',r['address']]
        self.command(args)
    def command(self,args):
        if self.busy():return
        self.output='';self.failed=False;self.prompting=False;process=QProcess(self);self.proc=process;env=QProcessEnvironment.systemEnvironment();env.insert('LC_ALL','C');env.insert('TERM','dumb');process.setProcessEnvironment(env);process.setProcessChannelMode(QProcess.MergedChannels);process.readyReadStandardOutput.connect(self.read_output);process.finished.connect(self.finished);process.errorOccurred.connect(lambda error:self.finished(1) if error==QProcess.FailedToStart else None);process.start(args[0],args[1:]);self.status.setText('Aplicando cambio…');self.selection_changed();QTimer.singleShot(90000,lambda p=process:p.kill() if p.state()!=QProcess.NotRunning else None)
    def read_output(self):
        if not self.proc:return
        data=bytes(self.proc.readAllStandardOutput()).decode(errors='replace');data=re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',data);self.output=(self.output+data)[-3000:]
        if re.search(r'failed|not available|not ready|not found|error:',data,re.I):self.failed=True
        if self.prompting:return
        text=self.output
        if re.search(r'Confirm passkey|Authorize service|Accept pairing',text,re.I):
            self.prompting=True;match=re.search(r'passkey\s+(\d{6})',text,re.I);message='Confirma que este código aparece también en el dispositivo: '+match[1] if match else '¿Autorizar la conexión con el dispositivo seleccionado?';answer=QMessageBox.question(self,'Emparejar Bluetooth',message,QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel);self.proc.write(b'yes\n' if answer==QMessageBox.Yes else b'no\n');self.output='';self.prompting=False
        elif re.search(r'(password|passphrase|psk|Enter PIN code|Enter passkey).*[:?]',text,re.I):
            self.prompting=True;value,ok=QInputDialog.getText(self,'Credenciales de conexión','Contraseña o PIN solicitado por la conexión',QLineEdit.Password)
            if ok:self.proc.write((value+'\n').encode())
            else:self.proc.kill()
            value='';self.output='';self.prompting=False
        elif re.search(r'Passkey:\s*\d+',text):
            match=re.search(r'Passkey:\s*(\d+)',text);self.status.setText('Escribe '+match[1]+' en el dispositivo y pulsa Enter.')
    def finished(self,code,*_):
        self.status.setText('Cambio completado.' if code==0 and not self.failed else 'No se completó el cambio. Comprueba el dispositivo o las credenciales.');self.output='';self.selection_changed();QTimer.singleShot(800,self.load)
    def toggle_radio(self):
        target='off' if self.meta.get('enabled') else 'on'
        if target=='off' and QMessageBox.question(self,'Desactivar conexión','Se desconectarán los dispositivos de '+('Bluetooth' if self.mode=='bluetooth' else 'Wi-Fi')+'. ¿Continuar?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        self.command(['bluetoothctl','power',target] if self.mode=='bluetooth' else ['nmcli','radio','wifi',target])
    def rescan(self):
        if self.mode=='wifi':self.command(['nmcli','device','wifi','rescan'])
        elif self.mode=='bluetooth':
            if self.scan_process and self.scan_process.state()!=QProcess.NotRunning:return
            self.scan_process=QProcess(self);self.scan_process.setStandardOutputFile(os.devnull);self.scan_process.setStandardErrorFile(os.devnull);self.scan_process.finished.connect(lambda *_:self.load());self.scan_process.start('bluetoothctl',['--timeout','12','scan','on']);self.status.setText('Buscando dispositivos durante 12 segundos…');QTimer.singleShot(3000,self.load)
        else:self.load()
    def forget(self,r):
        if QMessageBox.question(self,'Olvidar conexión','¿Eliminar '+r['title']+' de las conexiones guardadas?',QMessageBox.Yes|QMessageBox.Cancel,QMessageBox.Cancel)!=QMessageBox.Yes:return
        if r['kind']=='ssh':self.profile_store.delete(r['profile_index']);self.load()
        else:self.command(['bluetoothctl','remove',r['address']] if r['kind']=='bluetooth' else ['nmcli','connection','delete','uuid',r['uuid']])
    def add_item(self):
        if self.mode=='ssh':self.ssh_editor();return
        if self.mode=='vpn':launch(['nm-connection-editor','--create','--type','vpn']);return
        ssid,ok=QInputDialog.getText(self,'Conectar a una red oculta','Nombre exacto de la red (SSID)')
        if ok and ssid.strip():self.command(['nmcli','--ask','--wait','30','device','wifi','connect',ssid.strip(),'hidden','yes'])
    def ssh_editor(self,r=None):
        row=r or {};dialog=QDialog(self);dialog.setWindowTitle('Editar SSH' if r else 'Nueva conexión SSH');dialog.resize(430,330);layout=QVBoxLayout(dialog);form=QFormLayout();fields={}
        for key,label in [('name','Nombre'),('host','Servidor'),('user','Usuario')]:c=QLineEdit(row.get(key,''));fields[key]=c;form.addRow(label,c)
        port=QSpinBox();port.setRange(1,65535);port.setValue(row.get('port',22));form.addRow('Puerto',port);layout.addLayout(form);error=text_label('Usa tus claves y configuración de OpenSSH.','subtitle');layout.addWidget(error);footer=QHBoxLayout();footer.addStretch();footer.addWidget(button('Cancelar',dialog.reject))
        def save():
            value={k:c.text().strip() for k,c in fields.items()};value['port']=port.value()
            try:self.profile_store.save(value,row.get('profile_index'));dialog.accept();self.load()
            except (ValueError,OSError) as e:error.setText(str(e))
        footer.addWidget(button('Guardar',save,'primary'));layout.addLayout(footer);dialog.exec()
    def advanced_settings(self):
        if self.mode=='ssh':open_vim(Path.home()/'.ssh/config')
        else:launch(['nm-connection-editor'])
    def closeEvent(self,event):
        # Keep any active credential operation alive, but never scan indefinitely.
        if self.scan_process and self.scan_process.state()!=QProcess.NotRunning:self.scan_process.terminate()
        self.hide();event.ignore()

class PowerWindow(Surface):
    def __init__(self,owner):
        super().__init__('Sesión','',460,370);self.owner=owner;self.action_buttons=[]
        self.setStyleSheet(self.styleSheet()+'''
            QPushButton[sessionAction="true"] { background:rgba(170,185,215,9); border:1px solid rgba(170,185,215,16); border-radius:9px; }
            QPushButton[sessionAction="true"]:hover { background:rgba(170,185,215,23); color:#F4F5F8; }
            QPushButton[sessionAction="true"]:focus { background:rgba(155,185,240,25); border-color:#829AC5; color:#EDF2FF; }
            QPushButton#danger { color:#ECA3AC; }
        ''')
        hero=QHBoxLayout();hero.setSpacing(18)
        self.clock_label=text_label('');self.clock_label.setStyleSheet('font-size:42px;font-weight:500;letter-spacing:-1px;color:#EEF2FA;');self.clock_label.setWordWrap(False)
        hero.addWidget(self.clock_label)
        self.date_label=text_label('');self.date_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter);self.date_label.setStyleSheet('color:#AEB7CA;font-size:13px;');hero.addWidget(self.date_label,1)
        self.outer.addLayout(hero)
        from system_panels import power_rows
        row=QHBoxLayout();row.setSpacing(10)
        for action in power_rows()[:2]:
            b=button(action['title'],lambda r=action:self.trigger(r),symbol=action['action']);b.setMinimumHeight(48);row.addWidget(b);self.action_buttons.append(b)
        self.outer.addLayout(row)
        for action in power_rows()[2:]:
            b=button(action['title'],lambda r=action:self.trigger(r),'danger' if action['action']=='shutdown' else '',symbol=action['action']);b.setStyleSheet('text-align:left; padding:7px 12px;');self.outer.addWidget(b);self.action_buttons.append(b)
        self.uptime_label=text_label('','subtitle');self.uptime_label.setAlignment(Qt.AlignCenter);self.outer.addWidget(self.uptime_label)
        self.outer.setSpacing(8)
        for b in self.action_buttons:
            b.setProperty('sessionAction',True);b.installEventFilter(self)
        self.clock_timer=QTimer(self);self.clock_timer.setInterval(1000);self.clock_timer.timeout.connect(self.update_clock)
    @staticmethod
    def uptime_text(seconds):
        minutes=max(0,int(seconds)//60);days,minutes=divmod(minutes,1440);hours,minutes=divmod(minutes,60)
        parts=[]
        if days:parts.append(f'{days} d')
        if hours:parts.append(f'{hours} h')
        if minutes or parts:parts.append(f'{minutes} min')
        return 'Encendido hace '+(' '.join(parts) if parts else 'menos de 1 min')
    def update_clock(self):
        now=QDateTime.currentDateTime();locale=QLocale('es_ES')
        self.clock_label.setText(now.toString('HH:mm'))
        self.date_label.setText(locale.toString(now,'dddd').capitalize()+'\n'+locale.toString(now,"d 'de' MMMM 'de' yyyy"))
        self.uptime_label.setText(self.uptime_text(time.clock_gettime(time.CLOCK_BOOTTIME)))
    def showEvent(self,event):
        self.update_clock();self.clock_timer.start();super().showEvent(event)
    def hideEvent(self,event):
        self.clock_timer.stop();super().hideEvent(event)
    def present(self):
        super().present();self.action_buttons[0].setFocus(Qt.OtherFocusReason)
    def eventFilter(self,obj,event):
        if obj in self.action_buttons and event.type()==QEvent.KeyPress:
            key=event.key()
            if key in (Qt.Key_Return,Qt.Key_Enter):
                if not event.isAutoRepeat() and obj.isEnabled():obj.click()
                return True
            if key in (Qt.Key_Left,Qt.Key_Up,Qt.Key_Right,Qt.Key_Down):
                step=-1 if key in (Qt.Key_Left,Qt.Key_Up) else 1
                self.action_buttons[(self.action_buttons.index(obj)+step)%len(self.action_buttons)].setFocus(Qt.OtherFocusReason)
                return True
        return super().eventFilter(obj,event)
    def trigger(self,row):
        if self.owner.power_action(row):self.hide()

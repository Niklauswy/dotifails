import glob, json, os, re, shlex
from pathlib import Path
from PySide6.QtCore import QThread,Signal
from system_panels import cmd,split_nm,NetworkScan
from desktop_common import terminal_args
from settings_data import atomic_write

def ssh_hosts(config=None):
    """Read names and display metadata only; never evaluate Match exec or commands."""
    config=Path(config or Path.home()/'.ssh/config');rows=[];seen=set();files=set()
    def read(path,depth=0):
        path=Path(path).expanduser()
        if depth>5 or str(path) in files or len(files)>64 or not path.is_file():return
        files.add(str(path));current=[]
        for line in path.read_text(errors='replace').splitlines():
            try:parts=shlex.split(line,comments=True)
            except ValueError:continue
            if not parts:continue
            key=parts[0].lower();values=parts[1:]
            if '=' in key:key,value=key.split('=',1);values=[value]+values
            if not values:continue
            if key=='include':
                for value in values:
                    pattern=Path(value).expanduser()
                    if not pattern.is_absolute():pattern=config.parent/pattern
                    for child in sorted(glob.glob(str(pattern))):read(child,depth+1)
            elif key=='host':
                current=[]
                for alias in values:
                    if re.search(r'[*!?]',alias) or alias in seen or alias.startswith('-'):continue
                    row={'name':alias,'host':alias,'alias':alias,'user':'','port':22,'imported':True};rows.append(row);current.append(row);seen.add(alias)
            elif key=='match':current=[]
            elif key in ('hostname','user','port'):
                for row in current:
                    if key=='hostname':row['host']=values[0]
                    elif key=='user':row['user']=values[0]
                    elif values[0].isdigit():row['port']=int(values[0])
    read(config);return rows

def validate_host(row):
    if not row.get('name','').strip():raise ValueError('Escribe un nombre para esta conexión.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:%-]{0,252}',row.get('host','')):raise ValueError('Escribe un host, IPv4 o IPv6 válido, sin espacios.')
    if row.get('user') and not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}',row['user']):raise ValueError('Usuario no válido.')
    if not 1<=int(row.get('port',22))<=65535:raise ValueError('El puerto debe estar entre 1 y 65535.')
    return row

def ssh_args(row):
    if row.get('imported'):
        alias=row['alias']
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.:%-]*',alias):raise ValueError('Alias SSH no válido.')
        command=['ssh','--',alias]
    else:
        validate_host(row);command=['ssh','-p',str(row.get('port',22))]
        if row.get('user'):command+=['-l',row['user']]
        command+=['--',row['host']]
    return terminal_args(command,'SSH · '+row['name'])

class SSHProfiles:
    def __init__(self,path=None):self.path=Path(path or Path.home()/'.config/orbit/ssh.json')
    def saved(self):
        try:return json.loads(self.path.read_text())
        except (OSError,ValueError):return []
    def all(self):return self.saved()+ssh_hosts()
    def save(self,row,index=None):
        validate_host(row);rows=self.saved()
        if index is None:rows.append(row)
        else:rows[index]=row
        atomic_write(self.path,json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    def delete(self,index):
        rows=self.saved();rows.pop(index);atomic_write(self.path,json.dumps(rows,ensure_ascii=False,indent=2)+'\n')

class ConnectionScan(QThread):
    ready=Signal(str,object,object)
    def __init__(self,mode):super().__init__();self.mode=mode
    def run(self):
        rows=[];meta={}
        try:
            if self.mode=='wifi':
                from connection_details import wifi_inventory
                rows,meta=wifi_inventory()
            elif self.mode in ('saved','vpn'):
                for line in cmd(['nmcli','-t','-f','NAME,UUID,TYPE,DEVICE,AUTOCONNECT','connection','show']).splitlines():
                    d=split_nm(line)
                    if len(d)<5 or d[2]=='loopback':continue
                    if self.mode=='vpn' and d[2] not in ('vpn','wireguard'):continue
                    rows.append(dict(kind='profile',title=d[0],subtitle=('VPN' if d[2] in ('vpn','wireguard') else 'Wi-Fi' if d[2]=='802-11-wireless' else 'Ethernet')+' · '+('Conectado' if d[3] else 'Guardado'),uuid=d[1],device=d[3],connected=bool(d[3]),auto=d[4]=='yes',icon='vpn' if self.mode=='vpn' else 'network'))
            elif self.mode=='bluetooth':
                import dbus
                bus=dbus.SystemBus(private=True)
                try:objects=dbus.Interface(bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager').GetManagedObjects(timeout=5)
                finally:bus.close()
                meta['available']=False;meta['enabled']=False
                for path,interfaces in objects.items():
                    if 'org.bluez.Adapter1' in interfaces:
                        a=interfaces['org.bluez.Adapter1'];meta.update(available=True,enabled=bool(a.get('Powered',False)),adapter=str(a.get('Alias','Bluetooth')))
                    if 'org.bluez.Device1' not in interfaces:continue
                    d=interfaces['org.bluez.Device1'];battery=interfaces.get('org.bluez.Battery1',{}).get('Percentage');connected=bool(d.get('Connected',False));paired=bool(d.get('Paired',False));state='Conectado' if connected else 'Emparejado' if paired else 'Disponible'
                    rows.append(dict(kind='bluetooth',title=str(d.get('Alias',d.get('Name',d['Address']))),subtitle=state+(f' · {battery}%' if battery is not None else ''),address=str(d['Address']),connected=connected,paired=paired,trusted=bool(d.get('Trusted',False)),icon='bluetooth',battery=int(battery) if battery is not None else None,device_type=str(d.get('Icon','Dispositivo')),adapter=str(d.get('Adapter','')).split('/')[-1]))
                rows.sort(key=lambda r:(not r['connected'],not r['paired'],r['title']))
            elif self.mode=='ssh':
                for i,r in enumerate(SSHProfiles().all()):rows.append(dict(r,kind='ssh',title=r['name'],subtitle=(r['user']+'@' if r['user'] else '')+r['host']+' · '+str(r['port'])+(' · ~/.ssh/config' if r.get('imported') else ''),profile_index=i,icon='ssh'))
        except Exception as e:meta['error']='No se pudo consultar '+self.mode+'. Revisa que el servicio esté activo.'
        self.ready.emit(self.mode,rows,meta)

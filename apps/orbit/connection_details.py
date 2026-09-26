"""Read-only connection inventory and structured details, never secrets."""
import os,re,subprocess
from PySide6.QtCore import QThread,Signal

def nm(args):
    try:
        return subprocess.check_output(['nmcli','--colors','no',*args],text=True,stderr=subprocess.DEVNULL,env=dict(os.environ,LC_ALL='C'),timeout=4).strip()
    except (OSError,subprocess.SubprocessError):return ''

def fields(line):
    values=[];value='';escaped=False
    for char in line:
        if escaped:value+=char;escaped=False
        elif char=='\\':escaped=True
        elif char==':':values.append(value);value=''
        else:value+=char
    values.append(value);return values

def device_inventory():
    raw=nm(['-t','-f','GENERAL.DEVICE,GENERAL.TYPE,GENERAL.STATE,GENERAL.CONNECTION,GENERAL.CON-UUID,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS','device','show'])
    devices={};current={}
    for line in raw.splitlines():
        parts=fields(line)
        if len(parts)<2:continue
        key=parts[0];value=':'.join(parts[1:])
        if key=='GENERAL.DEVICE':current={'device':value};devices[value]=current
        else:current.setdefault(key,[]).append(value)
    return devices

def device_info(data):
    get=lambda key:', '.join(data.get(key,[])) or '—'
    return [('Interfaz',data.get('device','—')),('Dirección IPv4',get('IP4.ADDRESS[1]')),('Puerta de enlace',get('IP4.GATEWAY')),('DNS',', '.join(v for k,values in data.items() if k.startswith('IP4.DNS') for v in values) or 'Automático')]

def wifi_inventory():
    devices=device_inventory();rows={};raw=nm(['-t','-f','IN-USE,SSID,BSSID,SIGNAL,SECURITY,DEVICE,FREQ,CHAN,RATE,MODE','device','wifi','list','--rescan','no'])
    for line in raw.splitlines():
        f=fields(line)
        if len(f)<10 or not f[1]:continue
        used,ssid,bssid,signal,security,device,freq,channel,rate,mode=f[:10];key=(ssid,device);connected=used.strip()=='*';old=rows.get(key)
        if old and (old['connected'] or (not connected and old['signal']>=int(signal or 0))):continue
        d=devices.get(device,{});uuid=(d.get('GENERAL.CON-UUID') or [''])[0] if connected else ''
        rows[key]=dict(kind='wifi',title=ssid,subtitle=('Conectada' if connected else security or 'Red abierta')+' · '+signal+'%',ssid=ssid,device=device,connected=connected,security=security or 'Abierta',icon='wifi',signal=int(signal or 0),bssid=bssid,frequency=freq,channel=channel,rate=rate,uuid=uuid,info=device_info(d) if connected else [],id='wifi:'+device+':'+ssid)
    result=list(rows.values())
    for name,d in devices.items():
        type=(d.get('GENERAL.TYPE') or [''])[0];connected=(d.get('GENERAL.STATE') or [''])[0].startswith('100')
        if type=='loopback' or type not in ('ethernet','wifi'):continue
        if type=='wifi':
            if any(r['device']==name and r['connected'] for r in result):continue
            if not connected:continue
        connection=(d.get('GENERAL.CONNECTION') or [name])[0]
        result.append(dict(kind='ethernet' if type=='ethernet' else 'network_device',title=connection if connected else name,subtitle=('Ethernet' if type=='ethernet' else 'Wi-Fi')+' · '+('Conectado' if connected else 'Sin conexión'),device=name,connected=connected,icon='cable' if type=='ethernet' else 'wifi',uuid=(d.get('GENERAL.CON-UUID') or [''])[0],info=device_info(d),id='device:'+name))
    result.sort(key=lambda r:(not r['connected'],-r.get('signal',0),r['title'].casefold()))
    return result,{'enabled':nm(['radio','wifi'])=='enabled'}

def identity(row):return row.get('id') or row.get('uuid') or row.get('address') or (('ssh:' if row.get('kind')=='ssh' else '')+row.get('title',''))

class DetailScan(QThread):
    ready=Signal(str,object)
    def __init__(self,row):super().__init__();self.row=dict(row)
    def run(self):
        row=self.row;info=[];extra={}
        if row.get('uuid'):
            keys=['connection.id','connection.type','connection.interface-name','connection.autoconnect','ipv4.method','ipv4.addresses','ipv4.gateway','ipv4.dns','ipv6.method']
            raw=nm(['-t','-f',','.join(keys),'connection','show','uuid',row['uuid']]);values={}
            for line in raw.splitlines():
                f=fields(line)
                if len(f)>1:values[f[0]]=':'.join(f[1:])
            extra['auto']=values.get('connection.autoconnect')=='yes'
            method={'auto':'Automático (DHCP)','manual':'Manual','disabled':'Desactivado','shared':'Compartido'}.get(values.get('ipv4.method'),values.get('ipv4.method','—'))
            info=[('Perfil',values.get('connection.id') or row['title']),('IPv4',method),('Dirección configurada',values.get('ipv4.addresses') or 'Asignada por la red'),('DNS del perfil',values.get('ipv4.dns') or 'Automático'),('IPv6',values.get('ipv6.method') or '—')]
        if row.get('device') and row.get('connected'):
            d=device_inventory().get(row['device'],{})
            if d:info=device_info(d)+info
        self.ready.emit(identity(row),dict(info=info,**extra))

import json,os,re,subprocess
from pathlib import Path
from PySide6.QtCore import QThread,Signal

def split_nm(line):return [x.replace(r'\:',':').replace(r'\\','\\') for x in re.split(r'(?<!\\):',line)]
def cmd(args):
 try:return subprocess.check_output(args,text=True,timeout=4,stderr=subprocess.DEVNULL).strip()
 except (OSError,subprocess.SubprocessError):return ''

class NetworkScan(QThread):
 done=Signal(object)
 def run(self):
  rows=[];enabled=cmd(['nmcli','radio','wifi'])=='enabled'
  rows.append(dict(kind='network_action',title='Desactivar Wi-Fi' if enabled else 'Activar Wi-Fi',subtitle='Radio inalámbrica',action=['nmcli','radio','wifi','off' if enabled else 'on'],icon='wifi'))
  devices=cmd(['nmcli','-t','-f','DEVICE,TYPE,STATE,CONNECTION','device','status'])
  for line in devices.splitlines():
   d=split_nm(line)
   if len(d)>=4 and d[2]=='connected':
    rows.append(dict(kind='network_device',title=d[3],subtitle=d[0]+' · '+d[1]+' · Conectado',device=d[0],icon='network',detail=cmd(['nmcli','-f','GENERAL.DEVICE,GENERAL.STATE,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS','device','show',d[0]])))
  for line in cmd(['nmcli','-t','-f','IN-USE,SSID,SIGNAL,SECURITY,DEVICE','device','wifi','list','--rescan','no']).splitlines():
   d=split_nm(line)
   if len(d)<5 or not d[1]:continue
   used,ssid,signal,security,device=d[:5]
   if any(r.get('ssid')==ssid for r in rows):continue
   rows.append(dict(kind='wifi',title=ssid,subtitle=f'{signal}% de señal · {security or "Abierta"}'+(' · Conectada' if used=='*' else ''),ssid=ssid,device=device,connected=used=='*',security=security,icon='wifi',detail=f'Red Wi-Fi\n\nSeñal: {signal}%\nSeguridad: {security or "Sin cifrado"}\nInterfaz: {device}\n\nEnter para conectar.'))
  for line in cmd(['nmcli','-t','-f','NAME,UUID,TYPE,DEVICE','connection','show']).splitlines():
   d=split_nm(line)
   if len(d)>=4 and d[2] in ('vpn','wireguard'):
    active=bool(d[3]);rows.append(dict(kind='network_action',title=d[0],subtitle='VPN · '+('Conectada' if active else 'Desconectada'),action=['nmcli','connection','down' if active else 'up','uuid',d[1]],icon='vpn'))
  rows.append(dict(kind='network_action',title='Volver a buscar redes',subtitle='Actualizar redes Wi-Fi cercanas',action=['nmcli','device','wifi','rescan'],icon='search'))
  self.done.emit(rows)

def power_rows():
 uptime=Path('/proc/uptime').read_text().split()[0];hours=int(float(uptime)//3600)
 rows=[('lock','Bloquear pantalla','Protege tu sesión sin cerrar aplicaciones'),('suspend','Suspender','Pausar el equipo y conservar la sesión'),('logout','Cerrar sesión','Cerrar BSPWM y volver al inicio de sesión'),('reboot','Reiniciar','Reiniciar el equipo'),('shutdown','Apagar','Apagar el equipo de forma segura')]
 return [dict(kind='power',action=k,title=t,subtitle=s,icon='lock' if k=='lock' else 'power',detail=f'{t}\n\n{s}.\n\nEquipo encendido: {hours} h\nSe pedirá confirmación antes de salir de la sesión.') for k,t,s in rows]

class StatusScan(QThread):
 done=Signal(object,object)
 def __init__(self,mode):super().__init__();self.mode=mode
 def run(self):
  rows=[];extra={}
  if self.mode=='system':
   mem={x.split(':')[0]:int(x.split()[1]) for x in Path('/proc/meminfo').read_text().splitlines()};total=mem['MemTotal']/1048576;used=(mem['MemTotal']-mem['MemAvailable'])/1048576;load=os.getloadavg();uptime=float(Path('/proc/uptime').read_text().split()[0]);disk=__import__('shutil').disk_usage(Path.home());battery='Sin batería'
   for p in Path('/sys/class/power_supply').glob('*'):
    if (p/'capacity').exists():battery=(p/'capacity').read_text().strip()+'% · '+(p/'status').read_text().strip();break
   for title,subtitle,detail,icon in [('Memoria',f'{used:.1f} / {total:.1f} GB',f'{100*used/total:.0f}% en uso\n\nDisponible: {total-used:.1f} GB','system'),('Procesador',f'Carga {load[0]:.2f}',f'Carga media\n1 min: {load[0]:.2f}\n5 min: {load[1]:.2f}\n15 min: {load[2]:.2f}\n\n{os.cpu_count()} procesadores lógicos','system'),('Almacenamiento',f'{disk.free/2**30:.1f} GB libres',f'Carpeta personal\n\nUsado: {disk.used/2**30:.1f} GB\nTotal: {disk.total/2**30:.1f} GB','file'),('Batería',battery,battery,'power'),('Tiempo encendido',f'{int(uptime//3600)} h {int(uptime%3600//60)} min','La sesión permanece activa.','clock')]:rows.append(dict(kind='info',title=title,subtitle=subtitle,detail=detail,icon=icon))
  elif self.mode=='audio':
   default=cmd(['pactl','get-default-sink']);volume=cmd(['pactl','get-sink-volume','@DEFAULT_SINK@']);m=re.search(r'(\d+)%',volume);extra['volume']=int(m[1]) if m else 0
   rows.append(dict(kind='status_action',title='Silenciar / activar sonido',subtitle=f'Volumen: {extra["volume"]}%',action=['pactl','set-sink-mute','@DEFAULT_SINK@','toggle'],icon='audio'))
   try:
    for sink in json.loads(cmd(['pactl','-f','json','list','sinks']) or '[]'):rows.append(dict(kind='status_action',title=sink.get('description',sink['name']),subtitle='Salida predeterminada' if sink['name']==default else 'Usar como salida predeterminada',detail='Esta selección define la salida para los nuevos flujos de audio.',action=['pactl','set-default-sink',sink['name']],icon='audio'))
   except (ValueError,KeyError):pass
  elif self.mode=='notifications':
   paused=cmd(['dunstctl','is-paused'])=='true';rows.append(dict(kind='status_action',title='Reanudar notificaciones' if paused else 'Modo concentración',subtitle='Desactivar pausa' if paused else 'Pausar avisos nuevos',action=['dunstctl','set-paused','toggle'],icon='notifications'))
   try:
    data=json.loads(cmd(['dunstctl','history']) or '{}').get('data',[[]])[0]
    for n in data:
     field=lambda k:n.get(k,{}).get('data','')
     rows.append(dict(kind='notification',title=str(field('summary')),subtitle=str(field('appname')),detail=re.sub('<[^>]+>','',str(field('body'))),nid=str(field('id')),action=['dunstctl','history-pop',str(field('id'))],icon='notifications'))
   except (ValueError,TypeError,KeyError,IndexError):pass
  self.done.emit(rows,extra)

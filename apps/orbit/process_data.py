"""Linux process snapshots and identity-checked actions; no commands or data are logged."""
import os
import pwd
import re
import shlex
import signal
import time
from pathlib import Path
from functools import lru_cache

STATES={'R':'Ejecutando','S':'En espera','D':'Espera de E/S','T':'Pausado','t':'Depuración','Z':'Zombi','I':'Inactivo','X':'Finalizado'}
SESSION_PROCESSES={'bspwm','sxhkd','Xorg','Xwayland','systemd','dbus-daemon','dbus-broker'}

@lru_cache(maxsize=256)
def username(uid):
    try:return pwd.getpwuid(uid).pw_name
    except KeyError:return str(uid)

def process_record(pid):
    root=Path('/proc')/str(int(pid));raw=(root/'stat').read_text();fields=raw.rsplit(') ',1)[1].split()
    return dict(pid=int(pid),name=raw.split('(',1)[1].rsplit(')',1)[0],uid=root.stat().st_uid,
        start=fields[19],ticks=int(fields[11])+int(fields[12]),memory=int(fields[21])*os.sysconf('SC_PAGE_SIZE'),
        state=fields[0],ppid=int(fields[1]),threads=int(fields[17]),nice=int(fields[16]))

def io_counters(pid):
    try:
        values=dict(line.split(':',1) for line in (Path('/proc')/str(pid)/'io').read_text().splitlines())
        return int(values['read_bytes']),int(values['write_bytes'])
    except (OSError,ValueError,KeyError):return None

def safe_command(args):
    """Redact credential arguments before placing a command in the UI or clipboard."""
    secret=re.compile(r'(?:password|passwd|token|secret|api[_-]?key|authorization|credential)',re.I)
    cleaned=[];hide_next=False
    for value in args:
        if hide_next:cleaned.append('••••');hide_next=False;continue
        if secret.search(value):
            if '=' in value:cleaned.append(value.split('=',1)[0]+'=••••')
            elif value.startswith('-'):cleaned.append(value);hide_next=True
            else:cleaned.append('••••')
        elif re.search(r'(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|eyJ\S+\.\S+\.)',value):cleaned.append('••••')
        else:cleaned.append(re.sub(r'(https?://)[^/@\s]+:[^/@\s]+@',r'\1••••@',value))
    return shlex.join(cleaned)

def matched(row,query):
    for term in query.casefold().split():
        if term.startswith('pid:'):ok=str(row['pid'])==term[4:]
        elif term.startswith('ppid:'):ok=str(row.get('ppid'))==term[5:]
        elif term.startswith('user:'):ok=term[5:] in row.get('user','').casefold()
        else:ok=term in f"{row['name']} {row['pid']} {row.get('user','')}".casefold()
        if not ok:return False
    return True

class Processes:
    def __init__(self):
        self.previous={};self.stamp=time.monotonic();self.last_cpu=None;self.summary={};self.protected={1,os.getpid()}
        pid=os.getpid()
        for _ in range(64):
            try:pid=process_record(pid)['ppid']
            except (OSError,ValueError,IndexError):break
            if pid<1 or pid in self.protected:break
            self.protected.add(pid)

    def scan(self):
        now=time.monotonic();elapsed=max(now-self.stamp,.01);rows=[];current={};ticks=os.sysconf('SC_CLK_TCK')
        uptime=float(Path('/proc/uptime').read_text().split()[0])
        for path in Path('/proc').iterdir():
            if not path.name.isdigit():continue
            try:
                row=process_record(path.name);key=(row['pid'],row['start']);io=io_counters(row['pid'])
                old=self.previous.get(key);row['cpu']=max(0,(row['ticks']-old[0])/ticks/elapsed*100) if old else 0
                row['read_rate']=max(0,(io[0]-old[1][0])/elapsed) if old and old[1] is not None and io is not None else None
                row['write_rate']=max(0,(io[1]-old[1][1])/elapsed) if old and old[1] is not None and io is not None else None
                row.update(user=username(row['uid']),age=max(0,uptime-int(row['start'])/ticks))
                row['actionable']=self.action_reason(row) is None
                current[key]=(row['ticks'],io);rows.append(row)
            except (OSError,ValueError,IndexError):continue
        self.previous=current;self.stamp=now;self.summary=self.system(rows);return rows

    def system(self,rows):
        values=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]));total=sum(values);idle=values[3]+values[4]
        cpu=None
        if self.last_cpu and total>self.last_cpu[0]:cpu=max(0,min(100,100*(1-(idle-self.last_cpu[1])/(total-self.last_cpu[0]))))
        self.last_cpu=(total,idle)
        mem={k:int(v.split()[0])*1024 for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
        total_mem=mem['MemTotal'];available=mem.get('MemAvailable',mem['MemFree'])
        return dict(cpu=cpu,memory=total_mem-available,total_memory=total_mem,swap=mem.get('SwapTotal',0)-mem.get('SwapFree',0),total_swap=mem.get('SwapTotal',0),count=len(rows),running=sum(r['state']=='R' for r in rows))

    def action_reason(self,row):
        if row['uid']!=os.getuid():return 'Pertenece a otro usuario'
        if row['pid'] in self.protected or row['name'] in SESSION_PROCESSES:return 'Proceso de la sesión protegido'
        if row['state'] in ('Z','X'):return 'El proceso ya finalizó'
        return None

    def checked(self,row):
        current=process_record(row['pid'])
        if current['start']!=row['start']:raise RuntimeError('El PID cambió de proceso. Actualiza la lista.')
        return current

    def details(self,row):
        self.checked(row);root=Path('/proc')/str(row['pid']);result={'key':(row['pid'],row['start'])}
        for name in ('exe','cwd'):
            try:result[name]=os.readlink(root/name)
            except OSError:result[name]=''
        try:result['command']=safe_command([a.decode(errors='replace') for a in (root/'cmdline').read_bytes().split(b'\0') if a])
        except OSError:result['command']=''
        result['files']=[];result['file_count']=None
        try:
            files=list((root/'fd').iterdir());result['file_count']=len(files)
            for file in sorted(files,key=lambda p:int(p.name))[:60]:
                try:result['files'].append((file.name,os.readlink(file)))
                except OSError:pass
        except OSError:pass
        self.checked(row);return result

    def act(self,row,action):
        signals={'terminate':signal.SIGTERM,'kill':signal.SIGKILL,'pause':signal.SIGSTOP,'resume':signal.SIGCONT}
        if action not in signals:raise ValueError('Acción no admitida')
        current=self.checked(row);reason=self.action_reason(current)
        if reason:raise PermissionError(reason)
        # The descriptor pins the identity even if a PID is reused before sending a signal.
        fd=os.pidfd_open(current['pid'])
        try:
            self.checked(row);signal.pidfd_send_signal(fd,signals[action])
        finally:os.close(fd)

    def terminate(self,row,force=False):self.act(row,'kill' if force else 'terminate')

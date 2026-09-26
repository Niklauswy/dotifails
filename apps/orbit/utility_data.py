"""Local storage and process operations; no shell interpolation or network access."""
import hashlib,json,os,signal,time,uuid
from pathlib import Path


def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    try:
        with temporary.open('x',encoding='utf8') as f:
            os.chmod(temporary,0o600);f.write(value);f.flush();os.fsync(f.fileno())
        temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)


def digest(text):return hashlib.sha256(text.encode()).hexdigest()


class Notes:
    def __init__(self,root=None):
        self.root=Path(root or Path.home()/'.local/share/orbit/notes');self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.trash=self.root/'.trash';self.trash.mkdir(exist_ok=True,mode=0o700)
    def path(self,key,trash=False):
        if len(key)!=32 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Nota inválida')
        return (self.trash if trash else self.root)/(key+'.md')
    def all(self,query='',trash=False):
        rows=[]
        for path in (self.trash if trash else self.root).glob('*.md'):
            try:
                body=path.read_text();title=next((s.strip('# ').strip() for s in body.splitlines() if s.strip()),'Sin título')
                if query.casefold() not in body.casefold():continue
                rows.append(dict(key=path.stem,title=title,body=body,stamp=path.stat().st_mtime,favorite=(self.root/(path.stem+'.star')).exists()))
            except (OSError,UnicodeError):continue
        return sorted(rows,key=lambda r:(not r['favorite'],-r['stamp']))
    def create(self,body='# Nueva nota\n\n'):
        key=uuid.uuid4().hex;atomic(self.path(key),body);return key
    def save(self,key,body,expected):
        path=self.path(key)
        if not path.exists() or digest(path.read_text())!=expected:raise RuntimeError('La nota cambió fuera de Órbita. Tu borrador se conserva; guarda una copia para continuar.')
        atomic(path,body);return digest(body)
    def toggle_favorite(self,key):
        p=self.path(key).with_suffix('.star')
        if p.exists():p.unlink()
        else:atomic(p,'')
    def move(self,key,restore=False):self.path(key,restore).replace(self.path(key,not restore))


class Colors:
    def __init__(self,path=None):self.path=Path(path or Path.home()/'.local/share/orbit/colors.json')
    def read(self):
        try:return json.loads(self.path.read_text())
        except (OSError,ValueError):return dict(recent=[],favorites=[])
    def save(self,color,favorite=False):
        data=self.read();key='favorites' if favorite else 'recent';rows=data.get(key,[])
        if favorite and color in rows:rows.remove(color)
        else:rows=[color]+[x for x in rows if x!=color]
        data[key]=rows[:64 if favorite else 24];atomic(self.path,json.dumps(data));return data


def process_record(pid):
    root=Path('/proc')/str(int(pid));raw=(root/'stat').read_text();fields=raw.rsplit(') ',1)[1].split()
    return dict(pid=int(pid),name=raw.split('(',1)[1].rsplit(')',1)[0],uid=root.stat().st_uid,
                start=fields[19],ticks=int(fields[11])+int(fields[12]),memory=int(fields[21])*os.sysconf('SC_PAGE_SIZE'),state=fields[0])


class Processes:
    def __init__(self):self.previous={};self.stamp=time.monotonic()
    def scan(self):
        now=time.monotonic();elapsed=max(now-self.stamp,.01);rows=[];current={};ticks=os.sysconf('SC_CLK_TCK')
        for path in Path('/proc').iterdir():
            if not path.name.isdigit():continue
            try:
                row=process_record(path.name);key=(row['pid'],row['start']);old=self.previous.get(key,row['ticks'])
                row['cpu']=max(0,(row['ticks']-old)/ticks/elapsed*100);current[key]=row['ticks'];rows.append(row)
            except (OSError,ValueError,IndexError):continue
        self.previous=current;self.stamp=now;return rows
    def terminate(self,row,force=False):
        current=process_record(row['pid'])
        if current['start']!=row['start']:raise RuntimeError('El proceso cambió; actualiza la lista.')
        if current['uid']!=os.getuid() or current['pid'] in (1,os.getpid()):raise PermissionError('Solo puedes detener tus propios procesos, salvo Órbita.')
        # pidfd closes the check/signal PID-reuse race on Linux 5.3+.
        fd=os.pidfd_open(current['pid'])
        try:
            if process_record(current['pid'])['start']!=row['start']:raise RuntimeError('El proceso cambió.')
            signal.pidfd_send_signal(fd,signal.SIGKILL if force else signal.SIGTERM)
        finally:os.close(fd)

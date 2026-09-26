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
    def import_legacy(self,path):
        """Import the previous local notebook once; never alter the original."""
        marker=self.root/'.legacy-imported'
        if marker.exists() or not path.is_file():return
        body=path.read_text()
        if body.strip():
            # Stable key makes retry after interruption safe without duplicates.
            key=hashlib.sha256(str(path).encode()).hexdigest()[:32]
            if not self.path(key).exists():atomic(self.path(key),body)
        atomic(marker,'Imported locally; original preserved.\n')
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


from process_data import Processes, process_record

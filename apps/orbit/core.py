"""Local data and search for Órbita. No network services or shell evaluation."""
from pathlib import Path
import ast, configparser, datetime as dt, hashlib, math, operator, os, re, sqlite3, time

HOME = Path.home()
STATE = HOME / '.local/share/orbit'
SKIP = {'node_modules', '.git', 'venv', '.venv', '__pycache__', 'target', 'dist', 'build', 'vendor', 'go', 'miniconda3', 'anaconda3', 'snap', 'Trash'}

def calculate(query):
    q = query.strip().lower().replace('×', '*').replace('÷', '/').replace('−', '-').replace('^', '**')
    q = re.sub(r'(?<=[\d)])\s*x\s*(?=[\d(])', '*', q)
    q = re.sub(r'(?<=\d),(?=\d)', '.', q)
    if not q or len(q) > 160:
        return None
    units = {'km': ('length', 1000), 'm': ('length', 1), 'cm': ('length', .01), 'mm': ('length', .001), 'mi': ('length', 1609.344), 'ft': ('length', .3048), 'in': ('length', .0254), 'kg': ('mass', 1000), 'g': ('mass', 1), 'lb': ('mass', 453.59237), 's': ('time', 1), 'min': ('time', 60), 'h': ('time', 3600), 'gb': ('data', 1e9), 'mb': ('data', 1e6), 'kb': ('data', 1000)}
    match = re.fullmatch(r'([-+]?\d+(?:\.\d+)?)\s*([a-z°]+)\s+(?:a|en|to)\s+([a-z°]+)', q)
    if match:
        n, a, b = match.groups(); n = float(n); a = a.replace('°', ''); b = b.replace('°', '')
        if a == 'c' and b == 'f': result = n * 9 / 5 + 32
        elif a == 'f' and b == 'c': result = (n - 32) * 5 / 9
        elif a in units and b in units and units[a][0] == units[b][0]: result = n * units[a][1] / units[b][1]
        else: return None
        return f'{result:.12g} {b}'
    q = re.sub(r'(\d+(?:\.\d+)?)\s*%\s*(?:de|of)\s*', r'(\1/100)*', q)
    q = re.sub(r'(\d+(?:\.\d+)?)%', r'(\1/100)', q)
    if not re.search(r'\d', q): return None
    try:
        tree = ast.parse(q, mode='eval')
        if len(list(ast.walk(tree))) > 50: return None
        def walk(n):
            if isinstance(n, ast.Constant) and type(n.value) in (int, float): value = float(n.value)
            elif isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)): value = walk(n.operand) * (-1 if isinstance(n.op, ast.USub) else 1)
            elif isinstance(n, ast.Name) and n.id in ('pi', 'e'): value = getattr(math, n.id)
            elif isinstance(n, ast.BinOp) and type(n.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow):
                a, b = walk(n.left), walk(n.right)
                if isinstance(n.op, ast.Pow) and (abs(b) > 1000 or abs(a) > 1e50): raise ValueError()
                value = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}[type(n.op)](a,b)
            else: raise ValueError()
            if isinstance(value, complex) or not math.isfinite(value) or abs(value) > 1e100: raise ValueError()
            return value
        return f'{walk(tree.body):.12g}'
    except (SyntaxError, ValueError, TypeError, OverflowError, ZeroDivisionError): return None

def sensitive(text, formats=()):
    if any('password' in x.lower() or 'keepass' in x.lower() or 'secret' in x.lower() for x in formats): return True
    return bool(re.search(r'(?i)(-----BEGIN .*PRIVATE KEY|(?:password|passwd|contrase[nñ]a|api[_-]?key|access[_-]?token|secret)\s*[=:]|\b(?:sk-[a-zA-Z0-9_-]{16,}|gh[pousr]_[a-zA-Z0-9]{16,}|AKIA[A-Z0-9]{16})\b|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)', text))

class Store:
    def __init__(self, root=STATE):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True, mode=0o700); self.root.chmod(0o700)
        self.db = sqlite3.connect(self.root / 'orbit.sqlite3'); os.chmod(self.root/'orbit.sqlite3',0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''PRAGMA secure_delete=ON;
        CREATE TABLE IF NOT EXISTS clips(id INTEGER PRIMARY KEY, digest TEXT UNIQUE, kind TEXT, text TEXT, blob BLOB, stamp REAL);
        CREATE TABLE IF NOT EXISTS snippets(id INTEGER PRIMARY KEY, title TEXT, shortcut TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS history(query TEXT PRIMARY KEY, result TEXT, stamp REAL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS usage(key TEXT PRIMARY KEY, count INTEGER);
        '''); self.prune()
    def prune(self):
        self.db.execute('DELETE FROM clips WHERE stamp < ?', (time.time()-7*86400,))
        self.db.execute('DELETE FROM clips WHERE id NOT IN (SELECT id FROM clips ORDER BY stamp DESC LIMIT 200)')
        while self.db.execute('SELECT coalesce(sum(length(blob)),0) FROM clips').fetchone()[0] > 64*1024*1024:
            self.db.execute('DELETE FROM clips WHERE id=(SELECT id FROM clips ORDER BY stamp LIMIT 1)')
        self.db.commit()
    def clip(self, kind, text='', blob=None):
        if sensitive(text) or len(text) > 65536 or (blob and len(blob)>4*1024*1024): return
        digest = hashlib.sha256((kind+text).encode()+(blob or b'')).hexdigest()
        self.db.execute('INSERT INTO clips(digest,kind,text,blob,stamp) VALUES(?,?,?,?,?) ON CONFLICT(digest) DO UPDATE SET stamp=excluded.stamp', (digest,kind,text,blob,time.time()));self.prune()
    def clips(self): return [dict(r) for r in self.db.execute('SELECT id,kind,text,stamp FROM clips ORDER BY stamp DESC')]
    def blob(self, ident):
        r=self.db.execute('SELECT blob FROM clips WHERE id=?',(ident,)).fetchone();return r[0] if r else None
    def delete_clip(self, ident): self.db.execute('DELETE FROM clips WHERE id=?',(ident,));self.db.commit()
    def clear_clips(self): self.db.execute('DELETE FROM clips');self.db.commit();self.db.execute('VACUUM')
    def snippets(self): return [dict(r) for r in self.db.execute('SELECT * FROM snippets ORDER BY title COLLATE NOCASE')]
    def save_snippet(self, title, shortcut, body, ident=None):
        if ident: self.db.execute('UPDATE snippets SET title=?,shortcut=?,body=? WHERE id=?',(title,shortcut,body,ident))
        else: self.db.execute('INSERT INTO snippets(title,shortcut,body) VALUES(?,?,?)',(title,shortcut,body))
        self.db.commit()
    def delete_snippet(self, ident): self.db.execute('DELETE FROM snippets WHERE id=?',(ident,));self.db.commit()
    def get(self,key,default=''):
        r=self.db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone();return r[0] if r else default
    def set(self,key,value): self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,str(value)));self.db.commit()
    def record_calc(self,q,r):
        self.db.execute('INSERT OR REPLACE INTO history VALUES(?,?,?)',(q,r,time.time()));self.db.execute('DELETE FROM history WHERE query NOT IN (SELECT query FROM history ORDER BY stamp DESC LIMIT 50)');self.db.commit()
    def calcs(self): return [dict(r) for r in self.db.execute('SELECT * FROM history ORDER BY stamp DESC')]
    def use(self,key): self.db.execute('INSERT INTO usage VALUES(?,1) ON CONFLICT(key) DO UPDATE SET count=count+1',(key,));self.db.commit()
    def usages(self): return dict(self.db.execute('SELECT * FROM usage'))

def expand_snippet(text):
    now=dt.datetime.now()
    for key,value in {'date':now.strftime('%Y-%m-%d'),'time':now.strftime('%H:%M'),'datetime':now.strftime('%Y-%m-%d %H:%M')}.items(): text=text.replace('{'+key+'}',value)
    return text

def applications():
    result=[];seen=set()
    roots=[HOME/'.local/share/applications']+[Path(x)/'applications' for x in os.environ.get('XDG_DATA_DIRS','/usr/local/share:/usr/share').split(':')]
    for root in roots:
        if not root.exists(): continue
        for path in root.rglob('*.desktop'):
            ident=str(path.relative_to(root)).replace('/','-')
            if ident in seen: continue
            seen.add(ident)
            try:
                parser=configparser.ConfigParser(interpolation=None,strict=False);parser.read(path,encoding='utf-8');d=parser['Desktop Entry']
                if d.get('Hidden','false')=='true' or d.get('NoDisplay','false')=='true' or d.get('Type')!='Application' or not d.get('Exec'): continue
                result.append({'title':d.get('Name[es]',d.get('Name',path.stem)), 'subtitle':d.get('GenericName[es]',d.get('Comment[es]',d.get('GenericName','Aplicación'))), 'icon':d.get('Icon','application-x-executable'), 'kind':'app','path':str(path),'tag':'Aplicación','key':ident})
            except (OSError,configparser.Error,KeyError): continue
    return result

def file_index(root=HOME):
    found=[]
    for base,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if not d.startswith('.') and d not in SKIP and not Path(base,d).is_symlink()]
        for name in files:
            if name.startswith('.') or name.endswith(('.pyc','.map','.lock')): continue
            p=Path(base,name)
            found.append((name.casefold(),str(p),str(p.relative_to(root)).casefold()))
            if len(found)>=100000:return found
    return found

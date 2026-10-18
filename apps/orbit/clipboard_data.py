"""Additive clipboard collections and self-contained multi-clip snapshots."""
import base64,html,json,time,unicodedata
from pathlib import Path
from PySide6.QtCore import QMimeData,QUrl
from PySide6.QtGui import QImage
from core import sensitive

def unpack(value):
    try:return json.loads(value or '{}')
    except (ValueError,TypeError):return {}

def folded(value):return ''.join(c for c in unicodedata.normalize('NFKD',str(value).casefold()) if not unicodedata.combining(c))

class ClipboardLibrary:
    def __init__(self,store):
        self.store=store;self.db=store.db
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS clip_collections(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS clip_members(collection_id INTEGER,clip_id INTEGER,PRIMARY KEY(collection_id,clip_id));
        CREATE TABLE IF NOT EXISTS clip_parts(group_id INTEGER,position INTEGER,kind TEXT,text TEXT,blob BLOB,meta TEXT,source TEXT,ocr TEXT,PRIMARY KEY(group_id,position));
        CREATE TRIGGER IF NOT EXISTS clip_library_cleanup AFTER DELETE ON clips BEGIN
            DELETE FROM clip_members WHERE clip_id=OLD.id;
            DELETE FROM clip_parts WHERE group_id=OLD.id;
        END;
        ''');self.db.commit()
    def row(self,ident):
        row=self.db.execute('SELECT * FROM clips WHERE id=?',(ident,)).fetchone()
        return dict(row) if row else None
    def collections(self):
        return [dict(r) for r in self.db.execute('SELECT c.id,c.name,count(m.clip_id) AS count FROM clip_collections c LEFT JOIN clip_members m ON c.id=m.collection_id GROUP BY c.id ORDER BY c.name COLLATE NOCASE')]
    def create_collection(self,name):
        name=name.strip()
        if not name or len(name)>60:raise ValueError('Usa un nombre de entre 1 y 60 caracteres.')
        self.db.execute('INSERT OR IGNORE INTO clip_collections(name) VALUES(?)',(name,));self.db.commit()
        return self.db.execute('SELECT id FROM clip_collections WHERE name=?',(name,)).fetchone()[0]
    def assign(self,collection,ids):
        if not self.db.execute('SELECT 1 FROM clip_collections WHERE id=?',(collection,)).fetchone():raise ValueError('La colección ya no existe.')
        with self.db:
            for ident in ids:
                if self.row(ident):self.db.execute('INSERT OR IGNORE INTO clip_members VALUES(?,?)',(collection,ident))
    def remove_member(self,collection,ids):
        with self.db:self.db.executemany('DELETE FROM clip_members WHERE collection_id=? AND clip_id=?',[(collection,i) for i in ids])
    def delete_collection(self,collection):
        with self.db:
            self.db.execute('DELETE FROM clip_members WHERE collection_id=?',(collection,));self.db.execute('DELETE FROM clip_collections WHERE id=?',(collection,))
    def parts(self,ident):return [dict(r) for r in self.db.execute('SELECT * FROM clip_parts WHERE group_id=? ORDER BY position',(ident,))]
    def snapshot(self,ids):
        result=[]
        for ident in dict.fromkeys(ids):
            row=self.row(ident)
            if not row:raise ValueError('Uno de los elementos ya no está disponible.')
            result+=self.parts(ident) if row['kind']=='bundle' else [row]
        if len(result)>20:raise ValueError('Combina hasta 20 elementos por clip.')
        if sum(len(r.get('blob') or b'')+len(r.get('text','').encode()) for r in result)>16*1024*1024:raise ValueError('El grupo supera los 16 MB.')
        return result
    def plain(self,parts):
        values=[]
        for row in parts:
            if row['kind']=='files':values.append('\n'.join(unpack(row.get('meta')).get('paths',[])))
            elif row['kind']=='image':values.append(row.get('ocr') or '[Imagen]')
            else:values.append(row.get('text',''))
        return '\n\n'.join(values)
    def combine(self,ids,title=''):
        parts=self.snapshot(ids)
        if len(parts)<2:raise ValueError('Selecciona al menos dos elementos.')
        plain=self.plain(parts)
        if sensitive(plain):raise ValueError('El grupo contiene contenido excluido del historial.')
        existing=self.db.execute('SELECT coalesce(sum(length(blob)),0) FROM clip_parts').fetchone()[0]
        if existing+sum(len(r.get('blob') or b'') for r in parts)>64*1024*1024:raise ValueError('Los grupos alcanzaron los 64 MB. Elimina un grupo para liberar espacio.')
        title=title.strip() or f'Clip combinado · {len(parts)} elementos'
        if len(title)>120:raise ValueError('El título es demasiado largo.')
        # Include a snapshot digest in metadata; header text remains searchable.
        import hashlib
        digest=hashlib.sha256(b''.join((str(p['kind'])+str(p.get('text',''))).encode()+(p.get('blob') or b'') for p in parts)).hexdigest()
        header=title+'\n'+plain[:60000]+'\n'+digest
        ident=self.store.clip('bundle',header,source='Wysun',meta={'title':title,'count':len(parts),'snapshot':digest})
        if not ident:raise ValueError('No se pudo guardar el grupo.')
        with self.db:
            self.db.execute('DELETE FROM clip_parts WHERE group_id=?',(ident,))
            self.db.executemany('INSERT INTO clip_parts VALUES(?,?,?,?,?,?,?,?)',[(ident,i,p['kind'],p.get('text',''),p.get('blob'),p.get('meta','{}'),p.get('source',''),p.get('ocr','')) for i,p in enumerate(parts)])
        return ident
    def reorder(self,ident,order):
        parts=self.parts(ident)
        if sorted(order)!=list(range(len(parts))):raise ValueError('Orden inválido.')
        with self.db:
            self.db.execute('DELETE FROM clip_parts WHERE group_id=?',(ident,))
            self.db.executemany('INSERT INTO clip_parts VALUES(?,?,?,?,?,?,?,?)',[(ident,i,parts[n]['kind'],parts[n]['text'],parts[n]['blob'],parts[n]['meta'],parts[n]['source'],parts[n]['ocr']) for i,n in enumerate(order)])
    def rename(self,ident,title):
        title=title.strip()
        if not title or len(title)>120:raise ValueError('Usa un título de entre 1 y 120 caracteres.')
        row=self.row(ident)
        if not row:return
        meta=unpack(row['meta']);meta['title']=title
        with self.db:self.db.execute('UPDATE clips SET meta=? WHERE id=?',(json.dumps(meta),ident))
    def search(self,query='',kind='',favorite=False,source='',collection=None):
        members={r[0] for r in self.db.execute('SELECT clip_id FROM clip_members WHERE collection_id=?',(collection,))} if collection else None
        words=folded(query).split();out=[]
        for row in self.store.clips():
            if kind and row['kind']!=kind or favorite and not row['pinned'] or source and row['source']!=source:continue
            if members is not None and row['id'] not in members:continue
            meta=unpack(row.get('meta'));haystack=folded(' '.join([row['text'],row.get('ocr',''),row.get('source',''),meta.get('title','')]))
            if not all(word in haystack for word in words):continue
            row['title']=meta.get('title') or (Path(meta['paths'][0]).name if row['kind']=='files' and meta.get('paths') else row['text'].split('\n')[0]) or 'Sin título'
            out.append(row)
        return out
    def mime(self,ids,plain_only=False):
        parts=self.snapshot(ids);mime=QMimeData();mime.setText(self.plain(parts))
        if plain_only:return mime
        if len(parts)==1 and parts[0]['kind']=='image':mime.setImageData(QImage.fromData(parts[0].get('blob') or b''))
        urls=[];fragments=[]
        for row in parts:
            if row['kind']=='image' and row.get('blob'):
                fragments.append('<p><img alt="Imagen" src="data:image/png;base64,'+base64.b64encode(row['blob']).decode()+'"></p>')
            elif row['kind']=='files':
                paths=unpack(row.get('meta')).get('paths',[])
                for path in paths:
                    uri=QUrl.fromLocalFile(path);urls.append(uri);fragments.append('<p><a href="'+html.escape(uri.toString(),quote=True)+'">'+html.escape(Path(path).name)+'</a></p>')
            elif row['kind']=='url':
                text=row.get('text','').strip()
                from urllib.parse import urlsplit
                if urlsplit(text).scheme not in ('https','http'):
                    fragments.append('<p>'+html.escape(text)+'</p>');continue
                fragments.append('<p><a href="'+html.escape(text,quote=True)+'">'+html.escape(text)+'</a></p>')
            else:fragments.append('<p style="white-space:pre-wrap">'+html.escape(row.get('text',''))+'</p>')
        if urls:
            mime.setUrls(urls);mime.setData('x-special/gnome-copied-files',('copy\n'+'\n'.join(u.toString() for u in urls)).encode())
        mime.setHtml('<html><body>'+''.join(fragments)+'</body></html>')
        mime.setData('application/x-orbit-clip-group',json.dumps({'version':1,'count':len(parts),'kinds':[p['kind'] for p in parts]}).encode())
        return mime

import colorsys,datetime as dt,hashlib,json,re,time
from core import Store,sensitive

def color_value(text):
 s=text.strip()
 if re.fullmatch(r'#?[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?',s):return '#'+s.lstrip('#').upper()
 if re.fullmatch(r'#[0-9a-fA-F]{3}',s):return '#'+''.join(x*2 for x in s[1:]).upper()
 m=re.fullmatch(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)',s,re.I)
 if m:
  values=list(map(int,m.groups()[:3]))
  if max(values)>255:return None
  alpha=float(m[4]) if m[4] else 1
  if not 0<=alpha<=1:return None
  return '#'+''.join(f'{x:02X}' for x in values)+(f'{round(alpha*255):02X}' if alpha!=1 else '')
 m=re.fullmatch(r'hsl\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*\)',s,re.I)
 if m:
  h,s,l=map(float,m.groups())
  if s<=100 and l<=100:return '#'+''.join(f'{round(x*255):02X}' for x in colorsys.hls_to_rgb(h%360/360,l/100,s/100))
 return None

def color_formats(text):
 c=color_value(text)
 if not c:return {}
 r,g,b=[int(c[i:i+2],16) for i in (1,3,5)];h,l,s=colorsys.rgb_to_hls(r/255,g/255,b/255)
 return {'HEX':c,'RGB':f'rgb({r}, {g}, {b})','HSL':f'hsl({round(h*360)}, {round(s*100)}%, {round(l*100)}%)'}

def template(text,clipboard=''):
 now=dt.datetime.now()
 text=re.sub(r'\{date([+-]\d+)\}',lambda m:(now+dt.timedelta(days=int(m[1]))).strftime('%Y-%m-%d'),text)
 for k,v in {'date':now.strftime('%Y-%m-%d'),'time':now.strftime('%H:%M'),'datetime':now.strftime('%Y-%m-%d %H:%M'),'week':now.strftime('%V'),'clipboard':clipboard}.items():text=text.replace('{'+k+'}',v)
 return text

class StoreV2(Store):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  for table,columns in {'clips':{'source':"TEXT DEFAULT ''",'meta':"TEXT DEFAULT '{}'",'ocr':"TEXT DEFAULT ''",'ocr_done':'INTEGER DEFAULT 0','pinned':'INTEGER DEFAULT 0','thumb':'BLOB'},'snippets':{'icon':"TEXT DEFAULT 'snippet'",'html':"TEXT DEFAULT ''",'created':'REAL DEFAULT 0','modified':'REAL DEFAULT 0','uses':'INTEGER DEFAULT 0','lastused':'REAL DEFAULT 0'}}.items():
   existing={x[1] for x in self.db.execute(f'PRAGMA table_info({table})')}
   for name,decl in columns.items():
    if name not in existing:self.db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {decl}')
  for r in self.db.execute("SELECT id,text FROM clips WHERE kind='text'").fetchall():
   if color_value(r['text']):self.db.execute("UPDATE clips SET kind='color' WHERE id=?",(r['id'],))
  self.db.commit()
 def prune(self):
  if 'pinned' not in {x[1] for x in self.db.execute('PRAGMA table_info(clips)')}:return super().prune()
  self.db.execute('DELETE FROM clips WHERE pinned=0 AND stamp < ?',(time.time()-7*86400,))
  self.db.execute('DELETE FROM clips WHERE pinned=0 AND id NOT IN (SELECT id FROM clips WHERE pinned=0 ORDER BY stamp DESC LIMIT 200)')
  while self.db.execute('SELECT coalesce(sum(length(blob)),0) FROM clips').fetchone()[0]>64*1024*1024:
   row=self.db.execute('SELECT id FROM clips WHERE pinned=0 ORDER BY stamp LIMIT 1').fetchone()
   if not row:break
   self.db.execute('DELETE FROM clips WHERE id=?',(row[0],))
  self.db.commit()
 def clip(self,kind,text='',blob=None,source='',meta=None,thumb=None):
  if sensitive(text) or len(text)>65536 or (blob and len(blob)>4*1024*1024):return None
  if kind=='text' and color_value(text):kind='color'
  digest=hashlib.sha256((kind+text).encode()+(blob or b'')).hexdigest()
  self.db.execute('''INSERT INTO clips(digest,kind,text,blob,stamp,source,meta,thumb) VALUES(?,?,?,?,?,?,?,?)
   ON CONFLICT(digest) DO UPDATE SET stamp=excluded.stamp,source=CASE WHEN excluded.source!='' THEN excluded.source ELSE source END''',(digest,kind,text,blob,time.time(),source,json.dumps(meta or {}),thumb));self.prune()
  row=self.db.execute('SELECT id FROM clips WHERE digest=?',(digest,)).fetchone();return row[0] if row else None
 def clips(self):return [dict(r) for r in self.db.execute('SELECT id,kind,text,stamp,source,meta,ocr,ocr_done,pinned,thumb,length(blob) AS bytes FROM clips ORDER BY pinned DESC,stamp DESC')]
 def pin(self,ident):
  if self.db.execute('SELECT count(*) FROM clips WHERE pinned=1').fetchone()[0]>=50 and not self.db.execute('SELECT pinned FROM clips WHERE id=?',(ident,)).fetchone()[0]:return False
  self.db.execute('UPDATE clips SET pinned=1-pinned WHERE id=?',(ident,));self.db.commit();return True
 def save_media(self,ident,ocr,meta,thumb):
  if sensitive(ocr):ocr=''
  self.db.execute('UPDATE clips SET ocr=?,ocr_done=1,meta=?,thumb=? WHERE id=?',(ocr,json.dumps(meta),thumb,ident));self.db.commit()
 def rich_snippet(self,title,shortcut,body,html,icon,ident=None):
  now=time.time()
  if ident:self.db.execute('UPDATE snippets SET title=?,shortcut=?,body=?,html=?,icon=?,modified=? WHERE id=?',(title,shortcut,body,html,icon,now,ident))
  else:self.db.execute('INSERT INTO snippets(title,shortcut,body,html,icon,created,modified) VALUES(?,?,?,?,?,?,?)',(title,shortcut,body,html,icon,now,now))
  self.db.commit()
 def used_snippet(self,ident):self.db.execute('UPDATE snippets SET uses=uses+1,lastused=? WHERE id=?',(time.time(),ident));self.db.commit()

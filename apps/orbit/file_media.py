"""Typed file previews and a private, incremental image OCR index."""
import datetime as dt,json,mimetypes,os,queue,sqlite3,subprocess,time,unicodedata
from pathlib import Path
from PySide6.QtCore import Qt,QThread,Signal
from PySide6.QtGui import QImage,QImageReader
from core import sensitive,HOME
from media import png_bytes

IMAGES={'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff','.gif','.svg','.avif','.heic'}
VIDEOS={'.mp4','.mkv','.mov','.webm','.avi','.m4v','.mpeg','.mpg','.mts','.m2ts'}
AUDIO={'.mp3','.m4a','.wav','.flac','.ogg','.opus','.aac'}
CODE={'.py','.js','.jsx','.ts','.tsx','.css','.scss','.html','.json','.yaml','.yml','.toml','.xml','.sh','.bash','.zsh','.fish','.rs','.go','.c','.h','.cpp','.hpp','.java','.sql','.conf','.ini','.lua','.nix','.r','.ipynb'}
DOCS={'.txt','.md','.rst','.csv','.log','.tex','.pdf','.doc','.docx','.odt','.rtf','.xls','.xlsx','.ppt','.pptx'}
LABELS={'image':'Imagen','video':'Vídeo','audio':'Audio','document':'Documento','code':'Código','other':'Archivo'}

def fold(text):return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))
def file_kind(path):
    ext=Path(path).suffix.lower()
    return 'image' if ext in IMAGES else 'video' if ext in VIDEOS else 'audio' if ext in AUDIO else 'code' if ext in CODE else 'document' if ext in DOCS else 'other'
def file_mime(path):return mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
def human_size(size):
    for unit in ('B','KB','MB','GB','TB'):
        if size<1024:return f'{size:.0f} {unit}' if unit=='B' else f'{size:.1f} {unit}'
        size/=1024
def duration_label(seconds):
    n=max(0,int(seconds or 0));return f'{n//3600}:{n%3600//60:02d}:{n%60:02d}' if n>=3600 else f'{n//60}:{n%60:02d}'

def read_image(path,edge=1600):
    reader=QImageReader(str(path));reader.setAutoTransform(True);size=reader.size()
    if size.width()<=0 or size.height()<=0 or size.width()*size.height()>80_000_000:return QImage(),{}
    meta={'width':size.width(),'height':size.height()}
    if max(size.width(),size.height())>edge:reader.setScaledSize(size.scaled(edge,edge,Qt.KeepAspectRatio))
    image=reader.read()
    return image,meta

def probe_media(path):
    try:
        result=subprocess.run(['ffprobe','-v','error','-protocol_whitelist','file,pipe,crypto','-show_entries','format=duration,format_name:stream=codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels','-of','json',str(path)],capture_output=True,timeout=5)
        data=json.loads(result.stdout or '{}');meta={'duration':float(data.get('format',{}).get('duration',0))}
        for stream in data.get('streams',[]):
            if stream.get('codec_type')=='video':meta.update({k:stream[k] for k in ('width','height','codec_name','avg_frame_rate') if k in stream})
            elif stream.get('codec_type')=='audio':meta['audio_codec']=stream.get('codec_name','');meta['channels']=stream.get('channels',0)
        return meta
    except (OSError,ValueError,subprocess.SubprocessError):return {}

def preview_file(path,page=1):
    p=Path(path);data={'kind':file_kind(p),'path':str(p),'meta':{},'text':''}
    try:
        st=p.stat();data['meta']={'size':st.st_size,'modified':st.st_mtime,'mime':file_mime(p)};kind=data['kind']
        if kind=='image':data['image'],meta=read_image(p);data['meta'].update(meta)
        elif kind in ('video','audio'):
            data['meta'].update(probe_media(p))
            if kind=='video':
                result=subprocess.run(['ffmpeg','-v','error','-protocol_whitelist','file,pipe,crypto','-ss',str(min(1,data['meta'].get('duration',0)/3)),'-i',str(p),'-frames:v','1','-vf','scale=800:-2','-threads','1','-f','image2pipe','-vcodec','png','-'],capture_output=True,timeout=6)
                if result.returncode==0:data['image']=QImage.fromData(result.stdout)
        elif p.suffix.lower()=='.pdf':
            result=subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-singlefile','-scale-to','1200','-png',str(p)],capture_output=True,timeout=8)
            if result.returncode==0:data['image']=QImage.fromData(result.stdout)
            result=subprocess.run(['pdfinfo',str(p)],capture_output=True,text=True,env=dict(os.environ,LC_ALL='C'),timeout=3)
            import re
            found=re.search(r'^Pages:\s*(\d+)',result.stdout,re.M)
            if found:data['meta']['pages']=int(found[1])
        elif st.st_size<8*1024*1024:
            with p.open('rb') as f:raw=f.read(50000)
            if b'\0' not in raw:data['text']=raw.decode('utf8',errors='replace')
        if not data.get('image') and not data['text']:data['text']='Abre el archivo con su aplicación para ver el contenido completo.'
    except (OSError,subprocess.SubprocessError):data['error']='No se pudo leer el archivo.'
    return data

class FilePreviewJob(QThread):
    ready=Signal(str,object)
    def __init__(self,path,page=1):super().__init__();self.path=path;self.page=page
    def run(self):self.ready.emit(self.path,preview_file(self.path,self.page))

class FileCache:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700);self.path=self.root/'file-media.sqlite3'
        self.db=sqlite3.connect(self.path,timeout=4);self.path.chmod(0o600);self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('''CREATE TABLE IF NOT EXISTS media(path TEXT PRIMARY KEY,mtime INTEGER,size INTEGER,meta TEXT,ocr TEXT,search TEXT,thumb BLOB,status TEXT)''');self.db.commit()
    def get(self,path,validate=True):
        row=self.db.execute('SELECT * FROM media WHERE path=?',(str(path),)).fetchone()
        if not row:return None
        if validate:
            try:
                st=Path(path).stat()
                if st.st_mtime_ns!=row['mtime'] or st.st_size!=row['size']:return None
            except OSError:return None
        return dict(row)
    def put(self,path,stat,meta,text,thumb,status):
        text='' if sensitive(text) else text
        self.db.execute('INSERT OR REPLACE INTO media VALUES(?,?,?,?,?,?,?,?)',(str(path),stat.st_mtime_ns,stat.st_size,json.dumps(meta),text,fold(str(path)+' '+text),thumb,status));self.db.commit()
    def search(self,query):
        terms=fold(query).split()
        if not terms:return set()
        sql='SELECT path FROM media WHERE '+' AND '.join("search LIKE ? ESCAPE '\\'" for _ in terms)
        values=['%'+t.replace('\\','\\\\').replace('%',r'\%').replace('_',r'\_')+'%' for t in terms]
        return {r[0] for r in self.db.execute(sql,values).fetchall() if self.get(r[0])}
    def close(self,*_):
        if self.db is not None:self.db.close();self.db=None

def index_image(path,cache):
    try:
        p=Path(path);st=p.stat()
        if cache.get(path):return False
        if st.st_size>32*1024*1024:cache.put(path,st,{},'',b'','omitida: tamaño');return True
        image,meta=read_image(p,2400);text='';status='listo';thumb=b''
        if image.isNull():status='formato no compatible'
        else:
            thumb=png_bytes(image.scaled(96,72,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            if image.width()<160 or image.height()<60 or p.suffix.lower()=='.svg':status='sin texto: imagen pequeña o vectorial'
            else:
                binary='tesseract';env=dict(os.environ,OMP_THREAD_LIMIT='1')
                try:
                    result=subprocess.run(['nice','-n','15',str(binary),'stdin','stdout','-l','spa+eng','--psm','11'],input=png_bytes(image),capture_output=True,env=env,timeout=18)
                    if result.returncode==0:text=result.stdout.decode(errors='replace').strip()[:30000]
                    else:status='OCR no disponible'
                except (OSError,subprocess.SubprocessError):status='OCR no disponible'
        # Never attach a result to a file replaced while it was being recognized.
        after=p.stat()
        if after.st_mtime_ns!=st.st_mtime_ns or after.st_size!=st.st_size:return False
        cache.put(path,st,meta,text,thumb,status);return True
    except OSError:return False

class FileOCRIndexer(QThread):
    updated=Signal(str,int,int)
    progress=Signal(int,int)
    def __init__(self,paths,root):super().__init__();self.paths=[p for p in paths if Path(p).suffix.lower()!='.svg'];self.root=root;self.priority=queue.Queue()
    def prioritize(self,path):
        if Path(path).suffix.lower()!='.svg':self.priority.put(path)
    def run(self):
        cache=FileCache(self.root)
        try:
            valid=[]
            for path in self.paths:
                if self.isInterruptionRequested():return
                try:valid.append((Path(path).stat().st_mtime_ns,path))
                except OSError:pass
            valid.sort(reverse=True);pending=[p for _,p in valid if not cache.get(p)];done=len(valid)-len(pending);total=len(valid);self.progress.emit(done,total);completed=set()
            while pending or not self.priority.empty():
                if self.isInterruptionRequested():break
                try:path=self.priority.get_nowait()
                except queue.Empty:path=pending.pop(0)
                if path in completed and cache.get(path):continue
                changed=index_image(path,cache);completed.add(path)
                if changed:done+=1;self.updated.emit(path,min(done,total),total)
                for _ in range(4):
                    if self.isInterruptionRequested():break
                    self.msleep(100)
        finally:cache.close()

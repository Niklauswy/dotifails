"""Background OCR and bounded, direct-origin favicon requests."""
from pathlib import Path
import hashlib,ipaddress,json,os,socket,subprocess,urllib.request,urllib.parse
from PySide6.QtCore import QThread,Signal,QBuffer,QByteArray,QIODevice,Qt
from PySide6.QtGui import QImage,QImageReader
from core import HOME,STATE,sensitive

def png_bytes(image):
 data=QByteArray();buf=QBuffer(data);buf.open(QIODevice.WriteOnly);image.save(buf,'PNG');return bytes(data)

class OCRJob(QThread):
 done=Signal(int,str,object,bytes)
 def __init__(self,ident,blob):super().__init__();self.ident=ident;self.blob=blob
 def run(self):
  img=QImage.fromData(self.blob);meta={};text='';thumb=b''
  if not img.isNull():
   meta={'width':img.width(),'height':img.height(),'bytes':len(self.blob)};thumb=png_bytes(img.scaled(80,80,Qt.KeepAspectRatio,Qt.SmoothTransformation))
   binary='tesseract';env=dict(os.environ,OMP_THREAD_LIMIT='1')
   image=img.scaled(2400,2400,Qt.KeepAspectRatio,Qt.SmoothTransformation) if max(img.width(),img.height())>2400 else img
   try:
    r=subprocess.run([str(binary),'stdin','stdout','-l','spa+eng','--psm','11'],input=png_bytes(image),capture_output=True,env=env,timeout=18)
    if r.returncode==0:text=r.stdout.decode('utf-8',errors='replace').strip()[:30000]
    meta['ocr_status']='listo' if r.returncode==0 else 'no disponible'
   except (OSError,subprocess.SubprocessError):meta['ocr_status']='no disponible'
  self.done.emit(self.ident,'' if sensitive(text) else text,meta,thumb)

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

class FaviconJob(QThread):
 done=Signal(str,str)
 def __init__(self,url,root=STATE):super().__init__();self.url=url;self.root=Path(root)
 def run(self):
  host=urllib.parse.urlsplit(self.url).hostname or '';path=self.root/'favicons'/(hashlib.sha256(host.encode()).hexdigest()+'.png')
  if path.exists():self.done.emit(host,str(path));return
  try:
   parsed=urllib.parse.urlsplit(self.url)
   if parsed.scheme!='https' or parsed.username or parsed.port not in (None,443) or '.' not in host:return
   addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
   if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):return
   request=urllib.request.Request('https://'+host+'/favicon.ico',headers={'User-Agent':'Orbit/2','Accept':'image/*'})
   with urllib.request.build_opener(NoRedirect).open(request,timeout=3) as response:
    data=response.read(512*1024+1)
   if len(data)>512*1024:return
   # Bound dimensions before decoding untrusted image data.
   arr=QByteArray(data);buffer=QBuffer(arr);buffer.open(QIODevice.ReadOnly);reader=QImageReader(buffer)
   size=reader.size()
   if size.width()<=0 or size.width()*size.height()>4_000_000:return
   reader.setScaledSize(size.scaled(64,64,Qt.KeepAspectRatio));img=reader.read()
   if img.isNull():return
   path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);img.save(str(path),'PNG');self.done.emit(host,str(path))
  except (OSError,ValueError):return

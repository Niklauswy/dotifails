"""Bounded web metadata previews. No scripts, cookies, or third-party preview API."""
import http.client,ipaddress,re,socket,ssl,time
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin
from PySide6.QtCore import QThread,Signal,Qt,QByteArray,QBuffer,QIODevice
from PySide6.QtGui import QImageReader
from media import png_bytes

class PageMetadata(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.values={};self.title='';self.in_title=False
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='title':self.in_title=True
        if tag=='meta':
            key=(values.get('property') or values.get('name') or '').lower();value=values.get('content') or ''
            if key in ('og:title','twitter:title','description','og:description','twitter:description','og:image','og:image:url','twitter:image','og:site_name') and key not in self.values:self.values[key]=value
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
    def handle_data(self,data):
        if self.in_title and len(self.title)<1000:self.title+=data
    def metadata(self,url):
        def first(*keys):return re.sub(r'\s+',' ',next((self.values[k] for k in keys if self.values.get(k)),'' )).strip()
        image=first('og:image','og:image:url','twitter:image')
        return {'title':(first('og:title','twitter:title') or re.sub(r'\s+',' ',self.title).strip() or urlsplit(url).hostname or url)[:240],
                'description':first('og:description','description','twitter:description')[:600],
                'site':(first('og:site_name') or urlsplit(url).hostname or '')[:120],
                'image_url':urljoin(url,image) if image else ''}

def fetch_public(url,limit,accept):
    """Validate every redirect and pin connections to the validated public address."""
    for _ in range(4):
        parsed=urlsplit(url);host=parsed.hostname
        if parsed.scheme not in ('http','https') or not host or parsed.username or parsed.password:raise ValueError('URL no compatible')
        port=parsed.port or (443 if parsed.scheme=='https' else 80)
        addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Dirección privada')
        connection=http.client.HTTPConnection(host,port,timeout=3)
        sock=socket.create_connection(addresses[0][4][:2],timeout=3)
        try:
            if parsed.scheme=='https':sock=ssl.create_default_context().wrap_socket(sock,server_hostname=host)
            connection.sock=sock
            path=parsed.path or '/'
            if parsed.query:path+='?'+parsed.query
            connection.request('GET',path,headers={'Host':parsed.netloc,'User-Agent':'Mozilla/5.0 (compatible; Orbit/3; LinkPreview)','Accept':accept,'Accept-Encoding':'identity'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:raise ValueError('Redirección sin destino')
                url=urljoin(url,location);continue
            if response.status!=200:raise ValueError('Página no disponible')
            length=response.getheader('Content-Length')
            if length and int(length)>limit:raise ValueError('Contenido demasiado grande')
            data=response.read(limit+1)
            if len(data)>limit:raise ValueError('Contenido demasiado grande')
            return url,data,response.getheader('Content-Type','')
        finally:connection.close();sock.close()
    raise ValueError('Demasiadas redirecciones')

def preview(url,interrupted=lambda:False,fetch=fetch_public):
    meta={'status':'unavailable','stamp':time.time(),'site':urlsplit(url).hostname or ''};image=b''
    try:
        final,data,content_type=fetch(url,768*1024,'text/html,application/xhtml+xml')
        if 'html' not in content_type.lower():return meta,image
        match=re.search(r'charset=["\s]*([\w-]+)',content_type,re.I)
        encoding=match[1] if match else 'utf-8'
        try:source=data.decode(encoding,errors='replace')
        except LookupError:source=data.decode('utf-8',errors='replace')
        parser=PageMetadata();parser.feed(source);meta.update(parser.metadata(final),status='ready')
        image_url=meta.pop('image_url','')
        if image_url and not interrupted():
            try:
                _,data,kind=fetch(image_url,3*1024*1024,'image/*')
                if not kind.lower().startswith('image/'):return meta,image
                buffer=QBuffer();buffer.setData(QByteArray(data));buffer.open(QIODevice.ReadOnly);reader=QImageReader(buffer);size=reader.size()
                if size.width()<=0 or size.height()<=0 or size.width()*size.height()>24_000_000:return meta,image
                reader.setScaledSize(size.scaled(1200,720,Qt.KeepAspectRatio));result=reader.read()
                if not result.isNull():image=png_bytes(result)
                if len(image)>768*1024:image=png_bytes(result.scaled(720,420,Qt.KeepAspectRatio,Qt.SmoothTransformation))
                if len(image)>768*1024:image=b''
            except (OSError,ValueError,http.client.HTTPException):pass
    except (OSError,ValueError,http.client.HTTPException):pass
    return meta,image

class LinkPreviewJob(QThread):
    ready=Signal(int,str,object,bytes)
    def __init__(self,ident,url):super().__init__();self.ident=ident;self.url=url
    def run(self):
        meta,image=preview(self.url,self.isInterruptionRequested)
        if not self.isInterruptionRequested():self.ready.emit(self.ident,self.url,meta,image)

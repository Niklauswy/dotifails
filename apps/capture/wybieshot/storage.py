"""Private local sessions and atomic, no-overwrite flattened bitmap exports."""
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
import uuid
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication
from .document import Document, MAX_PIXELS
from .schema import Layer, Rect


def image_bytes(image,format='PNG'):
    buffer=QBuffer();buffer.open(QIODevice.WriteOnly)
    if not image.save(buffer,format):raise OSError('Image encoder failed')
    return bytes(buffer.data())


def atomic_write(path,data,overwrite=True):
    path=Path(path)
    if path.is_symlink():raise ValueError('Refusing symlink destination')
    fd,name=tempfile.mkstemp(prefix='.wybie-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        if overwrite:os.replace(name,path)
        else:os.link(name,path)  # Atomic exclusive publication even across processes.
    finally:
        if os.path.exists(name):os.unlink(name)


def private_dir(path):
    path=Path(path)
    # Do not follow links in any portion of private session roots.
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Refusing symlinked private directory')
    path.mkdir(mode=0o700,parents=True,exist_ok=True)
    if not path.is_dir():raise ValueError('Expected private directory')
    os.chmod(path,0o700)
    return path

class Storage:
    def __init__(self,root=None):
        base=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
        self.root=private_dir(Path(root) if root else base/'wybie-screenshot')
        self.sessions=private_dir(self.root/'sessions')
        self.default_output=Path.home()/'Pictures/Wybie'
        self._settings={'format':'PNG','delay':0,'include_cursor':False,'reduced_motion':False}
        prefs=self.root/'preferences.json'
        if prefs.is_symlink():raise ValueError('Symlinked preferences')
        if prefs.exists():
            data=json.loads(prefs.read_text());self.default_output=Path(data['output']).expanduser().absolute()
            settings=data.get('settings',{})
            self._validate_settings(settings);self._settings.update(settings)

    def set_output(self,path):
        path=Path(path).expanduser().absolute()
        if path.exists() and not path.is_dir():raise ValueError('Output must be a directory')
        atomic_write(self.root/'preferences.json',json.dumps({'output':str(path),'settings':self.settings}).encode())
        self.default_output=path

    @property
    def settings(self):return dict(self._settings)

    @staticmethod
    def _validate_settings(changes):
        allowed={'format','delay','include_cursor','reduced_motion'}
        if not isinstance(changes,dict) or changes.keys()-allowed:raise ValueError('Unknown screenshot setting')
        if 'format' in changes and changes['format'] not in ('PNG','JPEG'):raise ValueError('Invalid format')
        if 'delay' in changes and (type(changes['delay']) is not int or not 0<=changes['delay']<=60):raise ValueError('Invalid countdown')
        for key in ('include_cursor','reduced_motion'):
            if key in changes and type(changes[key]) is not bool:raise ValueError('Expected boolean setting')

    def update_settings(self,**changes):
        self._validate_settings(changes)
        settings={**self.settings,**changes}
        atomic_write(self.root/'preferences.json',json.dumps({'output':str(self.default_output),'settings':settings}).encode())
        self._settings=settings

    def _session(self,id):
        if not isinstance(id,str) or not re.fullmatch('[a-f0-9]{32}',id):raise ValueError('Invalid session ID')
        path=self.sessions/id
        if path.is_symlink():raise ValueError('Symlinked session')
        return path

    def save(self,doc):
        id=doc.session_id or uuid.uuid4().hex
        path=private_dir(self._session(id));source=path/'original.png'
        if not source.exists():atomic_write(source,image_bytes(doc.original),overwrite=False)
        elif source.is_symlink():raise ValueError('Symlinked source')
        metadata={'version':1,'id':id,'title':doc.title,'updated':time.time(),
                  'width':doc.size.width(),'height':doc.size.height(),
                  'layers':[asdict(l) for l in doc.layers], 'crop':asdict(doc.crop) if doc.crop else None}
        atomic_write(path/'document.json',json.dumps(metadata,ensure_ascii=False,allow_nan=False).encode())
        doc.session_id=id;return id

    def load(self,id):
        path=self._session(id);meta=path/'document.json';source=path/'original.png'
        if meta.is_symlink() or source.is_symlink():raise ValueError('Symlinked session content')
        if meta.stat().st_size>32_000_000:raise ValueError('Oversized document')
        data=json.loads(meta.read_text())
        if data.get('version')!=1 or data.get('id')!=id:raise ValueError('Unsupported or invalid document')
        width,height=data['width'],data['height']
        if type(width) is not int or type(height) is not int or width<=0 or height<=0 or width*height>MAX_PIXELS:
            raise ValueError('Invalid source dimensions')
        from PySide6.QtGui import QImageReader
        reader=QImageReader(str(source))
        if reader.size().width()!=width or reader.size().height()!=height:raise ValueError('Source dimensions changed')
        image=reader.read();doc=Document(image,data['title'])
        if len(data['layers'])>10000:raise ValueError('Too many layers')
        for item in data['layers']:doc.add_layer(Layer(**item))
        if data['crop']:doc.set_crop(Rect(**data['crop']))
        doc._undo.clear();doc._redo.clear();doc.session_id=id;return doc

    def list_sessions(self):
        result=[]
        for path in self.sessions.iterdir():
            try:
                meta=self._session(path.name)/'document.json'
                if meta.is_symlink() or meta.stat().st_size>32_000_000:continue
                data=json.loads(meta.read_text())
                if data.get('version')!=1 or data.get('id')!=path.name:continue
                if not isinstance(data.get('title'),str):continue
                if not isinstance(data.get('updated'),(int,float)) or not math.isfinite(data['updated']):continue
                if any(type(data.get(k)) is not int or data[k]<=0 for k in ('width','height')):continue
                if data['width']*data['height']>MAX_PIXELS:continue
                result.append({k:data[k] for k in ('id','title','updated','width','height')})
            except (OSError,ValueError,KeyError,TypeError):continue
        return sorted(result,key=lambda item:item['updated'],reverse=True)

    def export(self,doc,path):
        path=Path(path).expanduser().absolute()
        extension=path.suffix.lower()
        if extension not in ('.png','.jpg','.jpeg'):raise ValueError('Choose PNG or JPEG')
        path.parent.mkdir(parents=True,exist_ok=True)
        image=doc.render()
        if extension!='.png':
            # Explicit white background for transparent imported images.
            from PySide6.QtGui import QPainter
            flattened=QImage(image.size(),QImage.Format_RGB32);flattened.fill(QColor('white'))
            p=QPainter(flattened);p.drawImage(0,0,image);p.end();image=flattened
        atomic_write(path,image_bytes(image,'PNG' if extension=='.png' else 'JPEG'),overwrite=False)
        return path

    def copy(self,doc):
        app=QApplication.instance()
        if app is None:raise RuntimeError('Clipboard requires a running QApplication')
        app.clipboard().setImage(doc.render())

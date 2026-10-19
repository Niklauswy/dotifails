"""Bounded rich MIME snapshots; no opaque application/private formats are stored."""
import base64
import json
from PySide6.QtCore import QMimeData,QUrl
from PySide6.QtGui import QImage
from core import sensitive

TYPES=('text/uri-list','image/png','text/plain;charset=utf-8','text/plain','text/html',
       'x-special/gnome-copied-files','application/x-kde-cutselection')
LIMIT=4*1024*1024


def from_packet(packet):
    offers=packet.get('formats') or {packet['mime']:packet['data']}
    if sensitive('',offers):raise ValueError('Sensitive clipboard offer')
    mime=QMimeData();total=0
    for name,encoded in offers.items():
        if name not in TYPES:continue
        data=base64.b64decode(encoded,validate=True);total+=len(data)
        if total>LIMIT:raise ValueError('Clipboard offer too large')
        if name!='image/png' and sensitive(data.decode('utf8',errors='replace')):raise ValueError('Sensitive clipboard content')
        mime.setData(name,data)
        if name=='image/png':
            image=QImage.fromData(data,'PNG')
            if image.isNull() or image.width()*image.height()>25_000_000:raise ValueError('Clipboard image too large')
            mime.setImageData(image)
        elif name.startswith('text/plain'):mime.setText(data.decode('utf8'))
        elif name=='text/uri-list':mime.setUrls([QUrl(s) for s in data.decode('utf8').splitlines() if s and not s.startswith('#')])
    return mime


def encode(mime):
    formats={};size=0
    for name in TYPES:
        if name=='image/png' or not mime.hasFormat(name):continue
        data=bytes(mime.data(name));size+=len(data)
        if size>2*1024*1024:raise ValueError('Rich clipboard too large')
        if sensitive(data.decode('utf8',errors='replace')):raise ValueError('Sensitive clipboard content')
        formats[name]=base64.b64encode(data).decode()
    return json.dumps({'version':1,'formats':formats},ensure_ascii=False).encode()


def restore(blob):
    data=json.loads(blob)
    if data.get('version')!=1:raise ValueError('Unknown clipboard MIME format')
    mime=from_packet(data)
    # A history item is a copy; never replay a stale destructive cut operation.
    if mime.hasUrls():
        mime.setData('x-special/gnome-copied-files',('copy\n'+'\n'.join(u.toString() for u in mime.urls())).encode())
        mime.setData('application/x-kde-cutselection',b'0')
    return mime

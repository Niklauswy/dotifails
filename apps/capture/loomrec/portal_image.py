"""One real frame from a consent-scoped monitor/window PipeWire stream."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
from .wayland_capture import PipeWireCapture


def desktop_image():
    """Screenshot portal captures the virtual desktop (XDPH uses whole grim).

    Screenshot has no cursor-mode option; this path is used only without cursor.
    The portal owns the returned file; read it now without removing its storage.
    """
    from .portal import Portal
    from PySide6.QtGui import QImageReader
    portal=Portal()
    try:
        path=portal.screenshot(interactive=False);reader=QImageReader(str(path));size=reader.size()
        if not size.isValid() or size.width()*size.height()>100_000_000:raise ValueError('El portal devolvió una imagen inválida o demasiado grande')
        image=reader.read()
        if image.isNull():raise RuntimeError('No se pudo leer la imagen del portal: '+reader.errorString())
        image.setDevicePixelRatio(1);return image
    finally:portal.close()


def read_frame(capture,on_wait=None):
    """One bounded, cancellable authorized frame; caller owns session teardown."""
    from PySide6.QtGui import QImage
    import os,selectors,time
    with tempfile.TemporaryFile() as log:
        fd,w,h=capture.begin(log,even=False)
        if w*h>100_000_000:raise ValueError('La imagen supera 100 megapíxeles')
        remaining=w*h*4;chunks=[];deadline=time.monotonic()+10
        with selectors.DefaultSelector() as selector:
            selector.register(fd,selectors.EVENT_READ)
            while remaining:
                if on_wait:on_wait()
                capture.check()
                timeout=deadline-time.monotonic()
                if timeout<=0:raise TimeoutError('El portal no entregó una imagen completa')
                if not selector.select(min(.25,timeout)):continue
                block=os.read(fd,min(remaining,1024*1024))
                if not block:raise RuntimeError('La fuente se cerró antes del primer fotograma')
                chunks.append(block);remaining-=len(block)
        image=QImage(b''.join(chunks),w,h,w*4,QImage.Format_ARGB32).copy();image.setDevicePixelRatio(1)
        return image


def capture_frame(source='monitor',cursor=False,*,progress=None,on_wait=None):
    if source=='desktop' and not cursor:return desktop_image()
    if source=='desktop':
        from .desktop_capture import desktop_cursor_image
        return desktop_cursor_image(progress,on_wait)
    config=SimpleNamespace(rect=[0,0,1920,1080],fps=15,source_type=source,cursor=cursor)
    capture=PipeWireCapture(config)
    try:
        return read_frame(capture,on_wait)
    finally:capture.close()


def compose_frames(frames):
    """Compose authorized monitors in logical space at the highest source scale.

    No simultaneous-frame promise: static screenshots are acquired sequentially.
    Missing topology metadata is an error, never an invented monitor placement.
    """
    from PySide6.QtGui import QImage,QPainter
    from PySide6.QtCore import QRectF
    if len(frames)==1:return frames[0][0]
    for image,meta in frames:
        if not meta.get('position') or not meta.get('size') or min(meta['size'])<=0:raise ValueError('El portal no describe la topología para combinar monitores')
    scale=max(max(image.width()/meta['size'][0],image.height()/meta['size'][1]) for image,meta in frames)
    left=min(meta['position'][0] for _,meta in frames);top=min(meta['position'][1] for _,meta in frames)
    right=max(meta['position'][0]+meta['size'][0] for _,meta in frames);bottom=max(meta['position'][1]+meta['size'][1] for _,meta in frames)
    width=round((right-left)*scale);height=round((bottom-top)*scale)
    if not 0<width*height<=100_000_000:raise ValueError('La imagen combinada es demasiado grande')
    image=QImage(width,height,QImage.Format_ARGB32);image.fill(0)
    painter=QPainter(image)
    try:
        for frame,meta in frames:
            x,y=meta['position'];w,h=meta['size']
            painter.drawImage(QRectF((x-left)*scale,(y-top)*scale,w*scale,h*scale),frame)
    finally:painter.end()
    return image

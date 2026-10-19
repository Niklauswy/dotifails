"""Wayland portal pixels and X11 visible pixels, with explicit coordinate spaces.

Wayland desktop uses Screenshot (no cursor control); monitor/window use genuine
ScreenCast/PipeWire. Native selection coordinates belong to the authorized image.
X11 uses physical root coordinates and visible window crops, including occlusion.
"""
from dataclasses import dataclass
import ctypes
import ctypes.util
import os
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from .schema import Rect, CaptureRequest

@dataclass(frozen=True)
class FrozenDesktop:
    image: QImage
    geometry: Rect
    monitors: tuple[Rect,...]
    cursor_image: QImage | None = None
    cursor_embedded: bool = False

@dataclass(frozen=True)
class CaptureResult:
    image: QImage
    geometry: Rect
    mode: str
    warning: str = ''

class CaptureEngine:
    def _screens(self):
        if QGuiApplication.platformName()!='xcb':raise RuntimeError('Capture currently requires a real X11/xcb desktop')
        screens=QGuiApplication.screens()
        if not screens:raise RuntimeError('No display available')
        if any(abs(s.devicePixelRatio()-1)>0.001 for s in screens):
            raise RuntimeError('Physical pixel capture requires display scaling 1×; mixed/high DPI is not yet supported')
        return screens

    def _geometry(self):
        screens=self._screens();rect=screens[0].geometry()
        for s in screens[1:]:rect=rect.united(s.geometry())
        return Rect(rect.x(),rect.y(),rect.width(),rect.height())

    def _grab(self,region):
        screens=self._screens();bounds=self._geometry()
        if not bounds.contains(region):raise ValueError('Capture outside desktop')
        # Root coordinates are relative to the primary root on X11 (not screen-local).
        pixmap=screens[0].grabWindow(0,region.x,region.y,region.width,region.height)
        image=pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        image.setDevicePixelRatio(1)
        if image.isNull() or image.width()!=region.width or image.height()!=region.height:
            raise RuntimeError('Desktop returned an incomplete capture')
        return image

    def freeze(self,include_cursor=False):
        from loomrec.portal import is_wayland
        if is_wayland():
            from loomrec.portal_image import capture_frame
            image=capture_frame('monitor',include_cursor)
            bounds=Rect(0,0,image.width(),image.height())
            return FrozenDesktop(image,bounds,(bounds,),image if include_cursor else None,include_cursor)
        bounds=self._geometry()
        monitors=tuple(Rect(s.geometry().x(),s.geometry().y(),s.geometry().width(),s.geometry().height()) for s in self._screens())
        image=self._grab(bounds)
        cursor_image=image.copy()
        try:self._cursor(cursor_image,bounds)
        except (OSError,RuntimeError):cursor_image=None
        return FrozenDesktop(image,bounds,monitors,cursor_image)

    def windows(self):
        try:
            from Xlib import display, X
        except ImportError as exc:raise RuntimeError('Window selection requires optional python-xlib') from exc
        connection=display.Display()
        try:
            root=connection.screen().root
            atom=connection.intern_atom('_NET_CLIENT_LIST_STACKING')
            prop=root.get_full_property(atom,X.AnyPropertyType)
            ids=list(prop.value) if prop else []
            result=[]
            for id in reversed(ids):
                try:
                    window=connection.create_resource_object('window',int(id))
                    if window.get_attributes().map_state!=X.IsViewable:continue
                    geom=window.get_geometry();point=root.translate_coords(window,0,0)
                    title=window.get_full_property(connection.intern_atom('_NET_WM_NAME'),X.AnyPropertyType)
                    name=title.value.decode('utf8',errors='replace') if title else window.get_wm_name() or 'Ventana'
                    bounds=Rect(point.x,point.y,geom.width,geom.height)
                    # Include only wholly visible root rectangles, no hidden areas invented.
                    if self._geometry().contains(bounds):result.append({'id':int(id),'title':name,'geometry':bounds})
                except Exception:continue
            return result
        finally:connection.close()

    def capture(self,request:CaptureRequest,frozen=None,*,progress=None,on_wait=None):
        if request.delay_ms:raise ValueError('Use a cancellable QTimer countdown in the UI before capture')
        from loomrec.portal import is_wayland
        if is_wayland() and frozen is None:
            if request.mode=='region' and request.region is None:raise ValueError('Freeze the authorized monitor before selecting a region')
            from loomrec.portal_image import capture_frame
            if request.mode=='desktop' and request.include_cursor:
                image=capture_frame('desktop',True,progress=progress,on_wait=on_wait)
            else:image=capture_frame('window' if request.mode=='window' else 'desktop' if request.mode=='desktop' else 'monitor',request.include_cursor)
            bounds=Rect(0,0,image.width(),image.height())
            if request.mode=='region':
                if not bounds.contains(request.region):raise ValueError('Capture outside authorized image')
                r=request.region;image=image.copy(r.x,r.y,r.width,r.height);bounds=r
            warning=('Escritorio con cursor: monitores autorizados por separado, capturados en secuencia; no es un instante simultáneo. Salidas de menor escala remuestreadas a la mayor escala.' if request.include_cursor else 'Escritorio completo del portal Screenshot sin cursor.') if request.mode=='desktop' else 'Fuente autorizada por el portal. Coordenadas en píxeles de imagen; ventana independiente solo si el portal ofrece WINDOW.'
            return CaptureResult(image,bounds,request.mode,warning)
        if request.delay_ms:raise ValueError('Use a cancellable QTimer countdown in the UI before capture')
        bounds=frozen.geometry if frozen else self._geometry()
        warning=''
        if request.mode=='region':
            if request.region is None:raise ValueError('Select a nonempty region')
            region=request.region
        elif request.mode=='desktop':region=bounds
        elif request.mode=='monitor':
            monitors=frozen.monitors if frozen else tuple(Rect(s.geometry().x(),s.geometry().y(),s.geometry().width(),s.geometry().height()) for s in self._screens())
            if request.monitor>=len(monitors):raise ValueError('Monitor unavailable')
            region=monitors[request.monitor]
        else:
            if frozen:raise ValueError('Choose a window before freezing desktop')
            chosen=next((w for w in self.windows() if w['id']==request.window_id),None)
            if not chosen:raise ValueError('Window is hidden, closed or outside desktop')
            region=chosen['geometry'];warning='Recorte de píxeles visibles; incluye otras ventanas que la cubran.'
        if not bounds.contains(region):raise ValueError('Capture outside frozen desktop')
        if frozen:
            if frozen.cursor_embedded and not request.include_cursor:raise ValueError('El cursor ya está incrustado por el portal; vuelve a capturar sin cursor')
            source=frozen.cursor_image if request.include_cursor else frozen.image
            if source is None:raise RuntimeError('Cursor was unavailable when desktop was frozen')
            image=source.copy(region.x-bounds.x,region.y-bounds.y,region.width,region.height)
        else:
            image=self._grab(region)
            if request.include_cursor:self._cursor(image,region)
        return CaptureResult(image,region,request.mode,warning)

    def _cursor(self,image,region):
        """Real cursor bitmap/hotspot from XFixes, no invented arrow substitution."""
        class Cursor(ctypes.Structure):
            _fields_=[('x',ctypes.c_short),('y',ctypes.c_short),('width',ctypes.c_ushort),('height',ctypes.c_ushort),('xhot',ctypes.c_ushort),('yhot',ctypes.c_ushort),('serial',ctypes.c_ulong),('pixels',ctypes.POINTER(ctypes.c_ulong)),('atom',ctypes.c_ulong),('name',ctypes.c_char_p)]
        x11=ctypes.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
        fixes=ctypes.CDLL(ctypes.util.find_library('Xfixes') or 'libXfixes.so.3')
        x11.XOpenDisplay.argtypes=[ctypes.c_char_p];x11.XOpenDisplay.restype=ctypes.c_void_p
        x11.XCloseDisplay.argtypes=[ctypes.c_void_p];x11.XFree.argtypes=[ctypes.c_void_p]
        fixes.XFixesGetCursorImage.argtypes=[ctypes.c_void_p];fixes.XFixesGetCursorImage.restype=ctypes.POINTER(Cursor)
        d=x11.XOpenDisplay(None)
        if not d:raise RuntimeError('Cannot access X11 cursor')
        pointer=None
        try:
            pointer=fixes.XFixesGetCursorImage(d)
            if not pointer:raise RuntimeError('XFixes cursor unavailable')
            c=pointer.contents
            if c.width*c.height>1024*1024:raise RuntimeError('Unexpected cursor size')
            cursor=QImage(c.width,c.height,QImage.Format_ARGB32_Premultiplied)
            for y in range(c.height):
                for x in range(c.width):cursor.setPixel(x,y,int(c.pixels[y*c.width+x])&0xffffffff)
            p=QPainter(image);p.drawImage(c.x-c.xhot-region.x,c.y-c.yhot-region.y,cursor);p.end()
        finally:
            if pointer:x11.XFree(pointer)
            x11.XCloseDisplay(d)

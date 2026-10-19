"""Consent per output, with Hyprland inventory used only to place authorized pixels.

XDPH 1.4.1 supplies mapping_id, but position=(0,0) and size=raw SHM pixels.
Never infer an output from a node ID, its dimensions, or an unqualified position.
"""
from dataclasses import dataclass
import json
import math
import os
import subprocess
from types import SimpleNamespace
from .wayland_capture import PipeWireCapture


@dataclass(frozen=True)
class Output:
    name: str
    identity: tuple
    position: tuple
    pixels: tuple
    scale: float
    transform: int
    @property
    def logical_size(self):
        w,h=self.pixels
        if self.transform%2:w,h=h,w
        return (round(w/self.scale),round(h/self.scale))
    def composition_metadata(self):return dict(position=self.position,size=self.logical_size)


def topology_from_hypr(rows):
    outputs=[]
    for row in rows:
        if row.get('disabled',False):continue
        name=row.get('name');scale=float(row.get('scale',1));transform=row.get('transform',0)
        values=[row.get(k) for k in ('x','y','width','height')]
        if not isinstance(name,str) or not name or len(name)>256 or not math.isfinite(scale) or not .25<=scale<=8:
            raise ValueError('Inventario de monitores inválido')
        if type(transform) is not int or not 0<=transform<=7 or any(type(v) is not int for v in values) or min(values[2:])<=0:
            raise ValueError('Geometría de monitores inválida')
        if row.get('mirrorOf') not in (None,'','none') or row.get('dpmsStatus') is False:
            raise RuntimeError('Salidas reflejadas o apagadas: usa un monitor o escritorio sin cursor')
        identity=tuple(str(row.get(k,'')) for k in ('id','make','model','serial'))
        output=Output(name,identity,tuple(values[:2]),tuple(values[2:]),scale,transform)
        if min(output.logical_size)<=0:raise ValueError('Escala de monitores inválida')
        outputs.append(output)
    if not 1<=len(outputs)<=16 or len({o.name for o in outputs})!=len(outputs):raise ValueError('Inventario de monitores vacío, repetido o demasiado grande')
    for index,a in enumerate(outputs):
        x,y=a.position;w,h=a.logical_size
        for b in outputs[index+1:]:
            bx,by=b.position;bw,bh=b.logical_size
            if x<bx+bw and bx<x+w and y<by+bh and by<y+h:raise RuntimeError('La topología solapada no identifica una composición independiente')
    scale=max(o.scale for o in outputs)
    left=min(o.position[0] for o in outputs);top=min(o.position[1] for o in outputs)
    right=max(o.position[0]+o.logical_size[0] for o in outputs);bottom=max(o.position[1]+o.logical_size[1] for o in outputs)
    if sum(o.pixels[0]*o.pixels[1] for o in outputs)>100_000_000 or round((right-left)*scale)*round((bottom-top)*scale)>100_000_000:
        raise ValueError('El escritorio supera el límite de 100 megapíxeles')
    return tuple(sorted(outputs,key=lambda o:o.name))


def read_topology():
    if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        raise RuntimeError('Escritorio con cursor requiere identidad de salidas Hyprland. Usa escritorio sin cursor o un monitor con cursor.')
    raw=subprocess.check_output(['hyprctl','-j','monitors','all'],text=True,timeout=3)
    if len(raw)>1024*1024:raise ValueError('Inventario de monitores demasiado grande')
    rows=json.loads(raw)
    if not isinstance(rows,list):raise ValueError('Inventario de monitores inválido')
    return topology_from_hypr(rows)


def match_output(metadata,outputs,seen):
    mapping=str(metadata.get('mapping_id',''))
    selected=next((o for o in outputs if o.name==mapping),None)
    if selected is None or int(metadata.get('source_type',0))!=1:
        raise RuntimeError('El portal no confirma la identidad del monitor autorizado; usa escritorio sin cursor o un monitor.')
    if selected.name in seen:raise RuntimeError('Selección de monitor repetida. Se descartó el conjunto; selecciona cada monitor una sola vez.')
    if tuple(metadata.get('size',()))!=selected.pixels:raise RuntimeError('El tamaño de píxel del monitor autorizado no coincide con la topología')
    return selected


def coordinate_metadata(metadata,outputs):
    """Only the named, authorized monitor supplies coordinate provenance."""
    selected=match_output(metadata,outputs,set())
    result=dict(metadata)
    result['wysun_output']=dict(name=selected.name,identity=selected.identity,pixels=selected.pixels,transform=selected.transform)
    result['portal_position']=metadata.get('position');result['portal_size']=metadata.get('size')
    result.update(selected.composition_metadata())
    return result


def orient_frame(image,transform):
    # pipewiresrc 1.4.2 emits orientation tags; our videoconvert/raw bridge does
    # not rotate pixels. Apply that documented transform once, after raw checks.
    from PySide6.QtGui import QTransform
    if transform>=4:image=image.mirrored(True,False)
    angle={0:0,1:90,2:180,3:270,4:0,5:270,6:180,7:90}[transform]
    return image.transformed(QTransform().rotate(angle)) if angle else image


def read_frame(capture,on_wait=None):
    from .portal_image import read_frame as read
    return read(capture,on_wait)


def desktop_cursor_image(progress=None,on_wait=None):
    """Exactly N explicit monitor selections, no retry or partial publication."""
    from .portal_image import compose_frames
    check=on_wait or (lambda:None);check();snapshot=read_topology();frames=[];seen=set()
    def stable():
        check()
        if read_topology()!=snapshot:raise RuntimeError('Cambió la topología de monitores. Se descartó toda la captura; vuelve a empezar.')
    def notify(stage,index,remaining):
        check()
        if progress:progress(dict(stage=stage,index=index,total=len(snapshot),remaining=remaining))
        check()
    for index in range(1,len(snapshot)+1):
        stable();notify('select',index,[o.name for o in snapshot if o.name not in seen])
        config=SimpleNamespace(rect=[0,0,1,1],fps=15,source_type='monitor',cursor=True,normalize_coordinates=False)
        capture=PipeWireCapture(config,on_wait=check)
        try:
            stable();selected=match_output(capture.metadata,snapshot,seen)
            notify('capture',index,[selected.name])
            image=read_frame(capture,check)
            if (image.width(),image.height())!=selected.pixels:raise RuntimeError('El frame autorizado cambió de tamaño; se descartó el conjunto')
            stable();frames.append((orient_frame(image,selected.transform),selected.composition_metadata()));seen.add(selected.name)
        finally:capture.close()
    stable()
    if seen!={o.name for o in snapshot}:raise RuntimeError('Faltan monitores autorizados; no se guardó una captura parcial')
    image=compose_frames(frames);stable();notify('complete',len(snapshot),[])
    return image

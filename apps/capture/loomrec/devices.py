"""Read-only device discovery. Errors remain visible to callers."""
import json
import os
import re
import subprocess
import shutil
import time
from pathlib import Path

DEFAULT_SYSTEM_AUDIO = '@DEFAULT_MONITOR@'


def default_system_audio(sources=None):
    """Resolve the default output's monitor, never the default microphone."""
    sink_name = run(['pactl', 'get-default-sink']).strip()
    sinks = json.loads(run(['pactl', '-f', 'json', 'list', 'sinks']))
    sink = next((s for s in sinks if s['name'] == sink_name), None)
    if sources is None:
        sources = json.loads(run(['pactl', '-f', 'json', 'list', 'sources']))
    monitor = sink.get('monitor_source') if sink else None
    source = next((s for s in sources if monitor is not None and
                   (s['name'] == monitor or s.get('index') == monitor)), None)
    if not source:
        raise ValueError('La salida de audio actual no tiene un monitor disponible. Elige otra fuente de audio del equipo.')
    return dict(id=source['name'], output=sink_name, name=sink.get('description', sink_name))


def resolve_system_audio(device):
    """Explicit automatic mode resolves at each segment start, not mid-recording."""
    return default_system_audio()['id'] if device == DEFAULT_SYSTEM_AUDIO else device


def run(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=10)


def discover():
    from .portal import is_wayland
    monitors = []
    if is_wayland():
        if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            for m in json.loads(run(['hyprctl','-j','monitors'])):
                scale=m.get('scale',1);w,h=m['width'],m['height']
                if m.get('transform',0)%2:w,h=h,w
                monitors.append(dict(name=m['name'],rect=[m['x'],m['y'],round(w/scale)//2*2,round(h/scale)//2*2]))
        elif os.environ.get('SWAYSOCK'):
            for m in json.loads(run(['swaymsg','-r','-t','get_outputs'])):
                if m.get('active'):monitors.append(dict(name=m['name'],rect=[m['rect'][k] for k in ('x','y','width','height')]))
        else:monitors.append(dict(name='Elegir en el portal',rect=[0,0,1920,1080]))
    for line in ([] if is_wayland() else run(['xrandr', '--listmonitors']).splitlines()[1:]):
        m = re.search(r'(\d+)/\d+x(\d+)/\d+([+-]\d+)([+-]\d+)\s+(\S+)', line)
        if m:
            w, h, x, y, name = m.groups()
            monitors.append(dict(name=name, rect=[int(x), int(y), int(w), int(h)]))
    warnings=[]
    try:audio = json.loads(run(['pactl', '-f', 'json', 'list', 'sources']))
    except (OSError,ValueError,subprocess.SubprocessError):audio=[];warnings.append('Audio no disponible; activa PulseAudio o pipewire-pulse para fuentes de audio.')
    choices = [dict(id=s['name'], name=s.get('description', s['name']),
                kind='system' if s['name'].endswith('.monitor') else 'mic') for s in audio]
    try:
        current = default_system_audio(audio)
        description = 'Audio del equipo (salida actual: '+current['name']+')'
    except (OSError, ValueError, subprocess.SubprocessError):
        description = 'Audio del equipo (salida actual no disponible)'
    choices.insert(0, dict(id=DEFAULT_SYSTEM_AUDIO, name=description, kind='system'))
    return dict(monitors=monitors, audio=choices,warnings=warnings,
                cameras=[str(p) for p in sorted(Path('/dev').glob('video*'))])


def visible_window_rect(window_id):
    """Fixed root-screen crop, NOT isolated/offscreen window capture."""
    out = run(['xwininfo', '-id', str(window_id)])
    if not re.search(r'Map State:\s*IsViewable', out):
        raise ValueError('La ventana ya no está visible. Restáurala y vuelve a seleccionarla.')
    values = []
    for key in ['Absolute upper-left X', 'Absolute upper-left Y', 'Width', 'Height']:
        match = re.search(re.escape(key) + r':\s*(-?\d+)', out)
        if not match:
            raise ValueError('Cannot determine window geometry')
        values.append(int(match.group(1)))
    values[2]=values[2]//2*2;values[3]=values[3]//2*2
    return values


def clamp_rect(rect, bounds):
    """Intersect a monitor/selection with the current X root; even H.264 dimensions."""
    x,y,w,h = rect
    bw,bh = bounds
    left,top = max(0,x),max(0,y)
    right,bottom = min(bw,x+w),min(bh,y+h)
    width,height = (right-left)//2*2,(bottom-top)//2*2
    if width < 16 or height < 16:
        raise ValueError('Selected area is outside the current display')
    return [left,top,width,height]


def display_bounds(display):
    out = run(['xdpyinfo', '-display', display])
    match = re.search(r'dimensions:\s+(\d+)x(\d+)', out)
    if not match: raise ValueError('Cannot determine current X display dimensions')
    return [int(match[1]),int(match[2])]


def list_windows():
    """EWMH application windows on every desktop, including unmapped clients.

    Geometry is deliberately read only after activation: an off-desktop client
    is selectable but is not yet a valid root-pixel recording target.
    """
    output=run(['xprop','-root','_NET_CLIENT_LIST_STACKING'])
    windows=[]
    for window_id in re.findall(r'0x[0-9a-fA-F]+',output):
        try:
            info=run(['xprop','-id',window_id,'_NET_WM_NAME','WM_NAME','WM_CLASS','_NET_WM_WINDOW_TYPE','_NET_WM_STATE','_NET_WM_DESKTOP'])
            types=re.findall(r'_NET_WM_WINDOW_TYPE_[A-Z_]+',info)
            if types and '_NET_WM_WINDOW_TYPE_NORMAL' not in types:continue
            title=re.search(r'(?:_NET_WM_NAME|WM_NAME)[^=]*=\s*"(.*)"',info)
            app=re.search(r'WM_CLASS[^=]*=\s*"[^"]*",\s*"([^"]*)"',info)
            desktop=re.search(r'_NET_WM_DESKTOP\(CARDINAL\)\s*=\s*(\d+)',info)
            if title:
                windows.append(dict(id=window_id,title=title[1],app=app[1] if app else '',
                                    desktop=int(desktop[1]) if desktop else None,
                                    hidden='_NET_WM_STATE_HIDDEN' in info))
        except (OSError,ValueError,subprocess.SubprocessError):continue
    return windows


def activate_window(window_id):
    """Explicit user selection: restore/focus the client on its own desktop.

    Run off the UI thread. Never move the client's desktop or trust cached
    geometry; a WM refusing activation is an error, not a successful selection.
    """
    window_id=hex(int(window_id,0))
    if not shutil.which('wmctrl'):
        raise ValueError('No se pudo activar la ventana. Instala wmctrl para cambiar a su escritorio.')
    run(['wmctrl','-ia',window_id])
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        active=run(['xprop','-root','_NET_ACTIVE_WINDOW'])
        ids=re.findall(r'0x[0-9a-fA-F]+',active)
        if ids and int(ids[-1],16)==int(window_id,16):
            try:return visible_window_rect(window_id)
            except ValueError:pass
        time.sleep(.05)
    raise ValueError('No se pudo mostrar la ventana elegida. Vuelve a seleccionarla.')

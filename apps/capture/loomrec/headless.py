"""Start a recording without any Qt window, for the shell's recorder module.

The detached worker does the capture; the shell only needs the project folder
to follow its status.json and send pause/resume/stop commands.
"""
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def default_mic():
    """Default microphone source id, or None when Pulse/PipeWire has no input."""
    from .devices import run
    try:name=run(['pactl','get-default-source']).strip()
    except Exception:return None
    return None if not name or name.endswith('.monitor') else name


def devices():
    """Microphones and cameras to choose from (names a person can read)."""
    import json
    from pathlib import Path
    from .devices import run
    mics = []
    try:
        default = run(['pactl', 'get-default-source']).strip()
        for source in json.loads(run(['pactl', '-f', 'json', 'list', 'sources'])):
            if source['name'].endswith('.monitor'):
                continue
            mics.append(dict(id=source['name'], name=source.get('description') or source['name'], default=source['name'] == default))
    except Exception:
        pass
    cameras = []
    for node in sorted(Path('/sys/class/video4linux').glob('video*'), key=lambda p: int(p.name[5:] or 0)):
        try:
            if (node / 'index').read_text().strip() != '0':
                continue
            cameras.append(dict(id='/dev/' + node.name, name=(node / 'name').read_text().strip()))
        except (OSError, ValueError):
            continue
    return dict(mics=mics, cameras=cameras)


def monitor_rect(name):
    from .devices import discover
    for monitor in discover()['monitors']:
        if monitor['name']==name:return list(monitor['rect'])
    raise ValueError('Pantalla desconocida: '+str(name))


def start(spec):
    """spec: source ('monitor'|'region'), output, rect [x,y,w,h], mic, system, cursor, fps."""
    from .capture import CaptureConfig,CaptureSession
    from .devices import DEFAULT_SYSTEM_AUDIO
    from .videolibrary import VideoLibrary,preferences
    source=spec.get('source','region')
    if source not in ('monitor','region'):raise ValueError('Fuente no admitida')
    if not all(shutil.which(tool) for tool in ('ffmpeg','ffprobe')):raise ValueError('Falta instalar ffmpeg')
    rect=monitor_rect(spec['output']) if source=='monitor' else [int(v) for v in spec['rect']]
    rect[2]-=rect[2]%2;rect[3]-=rect[3]%2
    prefs=preferences();library=VideoLibrary()
    if shutil.disk_usage(library.root).free<512*1024*1024:raise ValueError('Libera al menos 512 MiB antes de grabar')
    config=CaptureConfig(str(library.new_directory()),os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY','portal'),rect,
        int(spec.get('fps') or prefs.get('fps') or 30),(spec.get('mic_device') or default_mic()) if spec.get('mic') else None,DEFAULT_SYSTEM_AUDIO if spec.get('system') else None,spec.get('camera_device') if spec.get('camera') else None,
        quality=prefs.get('quality') or 'standard',cursor=bool(spec.get('cursor',True)),auto_finalize=True,output_dir=str(library.videos),
        title='Grabación '+datetime.now().strftime('%d-%m-%Y %H-%M-%S'),source_type=source,remember_source=bool(prefs.get('remember_source',True)),camera_style=prefs.get('camera_style') or {})
    config.validate()
    CaptureSession(config).start()
    return dict(project_dir=config.project_dir)


SHELL_PREFS = dict(record_mic=False, record_system=True, record_cursor=True, record_camera=False)
TEXT_PREFS = ('record_mic_device', 'camera_device')
CAMERA_PREFS = {'camera_corner': 'corner', 'camera_shape': 'shape', 'camera_size': 'size'}


def shell_prefs():
    """Defaults the shell's recording bar starts from (and remembers)."""
    from .videolibrary import preferences
    prefs = preferences()
    values = {key: bool(prefs.get(key, default)) for key, default in SHELL_PREFS.items()}
    from .ui.capture_feedback_prefs import load_countdown
    values['countdown'] = load_countdown()
    for key in TEXT_PREFS:
        values[key] = prefs.get(key) or ''
    from .schema import camera_style
    try:values['camera_style'] = camera_style(prefs.get('camera_style'))
    except ValueError:values['camera_style'] = camera_style({})
    return values


def set_shell_pref(key, value):
    from .videolibrary import preferences, save_preferences
    if key in SHELL_PREFS:
        save_preferences(**{key: str(value).lower() in ('1', 'true', 'yes')})
    elif key in TEXT_PREFS:
        save_preferences(**{key: str(value)})
    elif key in CAMERA_PREFS:
        from .schema import camera_style
        style = camera_style(preferences().get('camera_style'))
        style[CAMERA_PREFS[key]] = str(value)
        camera_style(style)
        save_preferences(camera_style=style)
    elif key == 'countdown':
        from .ui.capture_feedback_prefs import save_countdown
        save_countdown(int(value))
    else:
        raise ValueError('Preferencia desconocida: ' + str(key))


def notify_when_ready(project_dir, timeout=1800):
    """Wait for the MP4 and tell the user where it is (detached, no GUI)."""
    import subprocess
    import time
    from .finalize import status
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = status(project_dir)
        if state['state'] == 'ready':
            subprocess.run(['notify-send', '-a', 'Wysun', '-i', 'video-x-generic', 'Grabación guardada', str(state['output'])], check=False)
            # The recording is what the person wants to see next: open Wysun Recorder on it.
            subprocess.Popen([sys.executable, '-P', '-m', 'loomrec', '--show', str(state['output'])], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parent.parent)))
            return state['output']
        if state['state'] == 'error':
            subprocess.run(['notify-send', '-a', 'Wysun', '-u', 'critical', 'No se pudo preparar el MP4', str(state.get('error') or '')], check=False)
            return None
        time.sleep(1)


def request_path():
    """Where a video to show is handed to the running window (or the next one to start)."""
    return Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / f'loomrec-show-{os.getuid()}.json'


def request_show(video):
    import json
    path = request_path()
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'video': str(video)}))
    os.replace(temporary, path)


def take_show_request():
    """The video to open, once; None when nobody asked."""
    import json
    path = request_path()
    try:
        video = json.loads(path.read_text()).get('video')
        path.unlink(missing_ok=True)
        return video if video and Path(video).is_file() else None
    except (OSError, ValueError, AttributeError):
        return None

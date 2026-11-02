"""Start a recording without any Qt window, for the shell's recorder module.

The detached worker does the capture; the shell only needs the project folder
to follow its status.json and send pause/resume/stop commands.
"""
import os
import shutil
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
        quality=prefs.get('quality') or 'standard',cursor=bool(spec.get('cursor',True)),cursor_effects=cursor_effects(prefs,accent_color()) if spec.get('cursor',True) else {},auto_finalize=True,output_dir=str(library.videos),
        title='Grabación '+datetime.now().strftime('%d-%m-%Y %H-%M-%S'),source_type=source,remember_source=bool(prefs.get('remember_source',True)),camera_style=prefs.get('camera_style') or {})
    config.validate()
    CaptureSession(config).start()
    return dict(project_dir=config.project_dir)


SHELL_PREFS = dict(record_mic=False, record_system=True, record_cursor=True, record_camera=False)
TEXT_PREFS = ('record_mic_device', 'camera_device')
CURSOR_PRESETS = ('simple', 'presentation', 'trail')
DEFAULT_CURSOR_PRESET = 'presentation'
DEFAULT_CURSOR_SIZE = 32


def accent_color():
    """The accent of the wallpaper's colour scheme as ``#rrggbb`` (the pointer's ring matches the desktop), or None."""
    import json
    import re
    from wysun_core import paths
    try:
        primary = json.loads(paths.state('wysun', 'scheme.json').read_text())['colours']['primary']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return '#' + primary.lower() if isinstance(primary, str) and re.fullmatch(r'[0-9A-Fa-f]{6}', primary) else None


def cursor_effects(prefs, accent=None):
    """The pointer highlight of a recording from the saved preferences: a ring (or a comet trail) around the native
    cursor. Clicks are never asked for: they need a root helper that prompts for a password at every recording."""
    from .cursor import effect_settings
    preset = prefs.get('cursor_preset', DEFAULT_CURSOR_PRESET)
    size = prefs.get('cursor_size', DEFAULT_CURSOR_SIZE)
    if preset not in CURSOR_PRESETS:
        preset = DEFAULT_CURSOR_PRESET
    if type(size) is not int or not 16 <= size <= 64:
        size = DEFAULT_CURSOR_SIZE
    options = dict(preset=preset, size=size, clicks=False)
    if accent:
        options['accent'] = accent
    return effect_settings(options)
CAMERA_PREFS = {'camera_corner': 'corner', 'camera_shape': 'shape', 'camera_size': 'size'}


def shell_prefs():
    """Defaults the shell's recording bar starts from (and remembers)."""
    from .videolibrary import preferences
    prefs = preferences()
    values = {key: bool(prefs.get(key, default)) for key, default in SHELL_PREFS.items()}
    from .ui.capture_feedback_prefs import load_countdown
    values['countdown'] = load_countdown()
    values['cursor_preset'] = prefs.get('cursor_preset') if prefs.get('cursor_preset') in CURSOR_PRESETS else DEFAULT_CURSOR_PRESET
    size = prefs.get('cursor_size')
    values['cursor_size'] = size if type(size) is int and 16 <= size <= 64 else DEFAULT_CURSOR_SIZE
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
    elif key == 'cursor_preset':
        if str(value) not in CURSOR_PRESETS:
            raise ValueError('Estilo de puntero desconocido: ' + str(value))
        save_preferences(cursor_preset=str(value))
    elif key == 'cursor_size':
        try:
            size = int(value)
        except (TypeError, ValueError):
            raise ValueError('Tamaño de puntero inválido: ' + str(value)) from None
        if not 16 <= size <= 64:
            raise ValueError('El tamaño del puntero va de 16 a 64')
        save_preferences(cursor_size=size)
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


def open_in_player(video):
    """Open a finished recording in Wysun Player (xdg-open when the launcher is missing); False when neither starts.

    The release never imports Wysun's app code: it calls the ``wysun`` launcher, which knows where the player is."""
    import shutil
    import subprocess
    launcher = shutil.which('wysun')
    if not launcher and (Path.home() / '.local/bin/wysun').is_file():
        launcher = str(Path.home() / '.local/bin/wysun')
    commands = ([[launcher, 'player', '--', str(video)]] if launcher else []) + [['xdg-open', str(video)]]
    # This process runs on a release: its launcher points PYTHONPATH and WYSUN_QML_LIB at that release, which would
    # make the Player look for its code and its QML there.
    env = {key: value for key, value in os.environ.items() if key not in ('PYTHONPATH', 'WYSUN_QML_LIB')}
    for command in commands:
        try:
            subprocess.Popen(command, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, env=env)
            return True
        except OSError:
            continue
    return False


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
            # The recording is what the person wants to see next: open it in Wysun Player.
            open_in_player(state['output'])
            return state['output']
        if state['state'] == 'error':
            subprocess.run(['notify-send', '-a', 'Wysun', '-u', 'critical', 'No se pudo preparar el MP4', str(state.get('error') or '')], check=False)
            return None
        time.sleep(1)

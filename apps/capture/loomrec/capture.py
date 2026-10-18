"""Detached capture controller. Atomic command files survive GUI disconnects."""
from dataclasses import dataclass, asdict, field
from pathlib import Path
import json
import math
import os
import subprocess
import sys
import time
import uuid
from .schema import Project, Source, Clip, atomic_json, save_project, load_project

@dataclass
class CaptureConfig:
    project_dir: str
    display: str
    rect: list[int]  # root pixels x,y,width,height
    fps: int = 30
    mic: str | None = None
    system_audio: str | None = None
    camera: str | None = None
    quality: str = "standard"
    cursor: bool = True
    cursor_effects: dict = field(default_factory=dict)
    cursor_live: bool = True
    auto_finalize: bool = True
    output_dir: str | None = None
    title: str | None = None
    mic_gain: float = 1.0
    system_gain: float = 1.0

    def validate(self):
        from .cursor import effect_settings
        if type(self.cursor) is not bool:raise ValueError('Cursor visibility must be boolean')
        if type(self.cursor_live) is not bool:raise ValueError('Cursor live mode must be boolean')
        effect_settings(self.cursor_effects)
        if type(self.auto_finalize) is not bool:raise ValueError('Automatic MP4 must be boolean')
        if self.output_dir is not None and (not isinstance(self.output_dir,str) or not Path(self.output_dir).is_absolute()):raise ValueError('Output directory must be absolute')
        if self.title is not None and not isinstance(self.title,str):raise ValueError('Invalid recording title')
        if any(type(g) not in (float,int) or not math.isfinite(g) or not 0<=g<=8 for g in (self.mic_gain,self.system_gain)):raise ValueError('Capture gain must be between0 and8')
        if len(self.rect) != 4 or any(type(v) is not int for v in self.rect):
            raise ValueError('Capture rectangle requires integer pixels')
        x, y, w, h = self.rect
        if x < 0 or y < 0 or w < 16 or h < 16 or w % 2 or h % 2:
            raise ValueError('Capture needs nonnegative position and even dimensions >=16')
        if self.quality not in {'compact', 'standard', 'high'}:
            raise ValueError('Unknown capture quality')
        if not 1 <= self.fps <= 60 or not self.display:
            raise ValueError('Invalid display or frame rate')


class CaptureSession:
    def __init__(self, config):
        self.config = config
        self.root = Path(config.project_dir).resolve()

    @classmethod
    def attach(cls, project_dir):
        root = Path(project_dir).resolve()
        data = json.loads((root/'capture.json').read_text())
        data['project_dir'] = str(root)
        data.setdefault('auto_finalize',False)
        return cls(CaptureConfig(**data))

    def start(self):
        if self.config.output_dir is None and self.config.auto_finalize:
            from .videolibrary import videos_root
            self.config.output_dir=str(videos_root().resolve())
        self.config.validate()
        from .cursor import effect_settings,check_available
        if self.config.cursor and not self.config.cursor_live and effect_settings(self.config.cursor_effects):check_available()
        from .devices import clamp_rect, display_bounds
        if clamp_rect(self.config.rect, display_bounds(self.config.display)) != self.config.rect:
            raise ValueError('Display geometry changed; select an area inside the current display')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if (self.root/'capture.json').exists() or (self.root/'project.json').exists():
            raise ValueError('Use a new project directory for each recording')
        with (self.root/'capture.json').open('x') as config_file:
            json.dump(asdict(self.config),config_file)
            config_file.flush()
            os.fsync(config_file.fileno())
        environment = os.environ.copy()
        package_root = str(Path(__file__).resolve().parent.parent)
        environment['PYTHONPATH'] = package_root + (os.pathsep+environment['PYTHONPATH'] if environment.get('PYTHONPATH') else '')
        with (self.root/'worker.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-P', '-m', 'loomrec.worker', str(self.root)],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             start_new_session=True, env=environment)
        return self.status()

    def _command(self, name, **values):
        atomic_json(self.root/('command-'+str(time.time_ns())+'-'+uuid.uuid4().hex+'.json'), {'command': name, **values})

    def pause(self): self._command('pause')
    def resume(self): self._command('resume')
    def stop(self, *, discard=False):
        if discard:
            from .finalize import cancel
            cancel(self.root/'project.json',discard=True)
        self._command('stop',discard=bool(discard))

    def rewind(self, seconds=10):
        if not isinstance(seconds,(int,float)) or not 0 < seconds <= 600:
            raise ValueError('Rewind must be between 0 and 600 seconds')
        self._command('rewind', seconds=seconds)

    def status(self):
        try:
            result = json.loads((self.root/'status.json').read_text())
        except FileNotFoundError:
            # Only a newly launched worker gets a startup grace period. An old
            # recovered/copied recording without status is not a live capture.
            age=time.time()-(self.root/'capture.json').stat().st_mtime
            return {'state': 'starting' if age<=15 else 'interrupted',
                    'error': None if age<=15 else 'Recorder status is missing; recover finalized media',
                    'project_path': str(self.root/'project.json')}
        if result['state'] in {'recording', 'paused', 'starting', 'stopping'}:
            if time.time() - result.get('heartbeat', 0) > 15:
                result.update(state='interrupted', error='Recorder stopped responding; recover finalized media')
        from .finalize import status as finalization_status
        result['finalization']=finalization_status(self.root/'project.json')
        return result


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                    '-show_format', '-of', 'json', str(path)], text=True, timeout=20))


def append_segment(project, root, stem, config):
    path = root / (stem+'.mkv')
    info = probe(path)
    videos = [s for s in info['streams'] if s['codec_type'] == 'video']
    if not videos:
        raise ValueError('Segment contains no video')
    duration = float(info['format'].get('duration', 0))
    if duration <= 0:
        raise ValueError('Segment has no finalized duration')
    trace = root/(stem.replace('.recovered','')+'.cursor.jsonl')
    marker=root/(stem.replace('.recovered','')+'.cursor-live.json')
    baked=marker.is_file() and json.loads(marker.read_text()).get('baked') is True
    from fractions import Fraction
    try:fps=float(Fraction(videos[0].get('avg_frame_rate','0/1')))
    except (ValueError,ZeroDivisionError):fps=float(config.fps)
    project.sources.append(Source(stem, path.name, 'screen', duration=duration, group=stem,
        cursor_path=trace.name if trace.is_file() and not baked else None,
        cursor_effects=dict(config.cursor_effects) if trace.is_file() or baked else {},cursor_baked=baked,
        width=videos[0].get('width',config.rect[2]),height=videos[0].get('height',config.rect[3]),fps=fps,quality=config.quality))
    starts = [float(s.get('start_time',0)) for s in info['streams']]
    audio = [s for s in info['streams'] if s['codec_type'] == 'audio']
    kinds = [kind for kind, device in [('mic', config.mic), ('system', config.system_audio)] if device]
    if len(audio) != len(kinds):
        raise ValueError('Recorded audio stream count differs from selected devices')
    for i, kind in enumerate(kinds):
        project.sources.append(Source(stem+'-'+kind, path.name, kind, i, gain=config.mic_gain if kind=='mic' else config.system_gain, duration=duration, group=stem))
    camera = root/(stem+'-camera.mkv')
    if config.camera and camera.exists():
        cam_info = probe(camera)
        project.sources.append(Source(stem+'-camera', camera.name, 'camera', duration=float(cam_info['format']['duration']), group=stem))
        starts.extend(float(s.get('start_time',0)) for s in cam_info['streams'])
    common_start = max([0.0, *starts])
    if common_start >= duration: raise ValueError('Selected sources have no common recorded interval')
    project.clips.append(Clip(stem, common_start, duration))


def recover_project(directory):
    root = Path(directory).resolve()
    import fcntl
    with (root/'capture.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Capture is still running; stop it before recovery')
        config = CaptureConfig(**json.loads((root/'capture.json').read_text()))
        path = root/'project.json'
        project = load_project(path) if path.exists() else Project()
        known = {s.id for s in project.sources}
        errors = []
        for media in sorted(root.glob('segment-*.mkv')):
            if media.stem.endswith('-camera') or '.recovered' in media.stem or media.stem in known:
                continue
            # Remux interrupted Matroska to reconstruct duration without touching original.
            repaired = root/(media.stem+'.recovered.mkv')
            result = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(media), '-map', '0',
                                     '-c', 'copy', str(repaired)], capture_output=True, text=True)
            if result.returncode:
                errors.append(media.name+': '+result.stderr[-300:])
                continue
            temporary = Project()
            camera = root/(media.stem+'-camera.mkv')
            if config.camera and camera.exists():
                camera_repaired = root/(media.stem+'.recovered-camera.mkv')
                camera_result = subprocess.run(['ffmpeg','-v','error','-y','-i',str(camera),'-map','0:v:0','-c','copy',str(camera_repaired)],capture_output=True,text=True)
                if camera_result.returncode:
                    errors.append(camera.name+': camera recovery failed')
                    camera_repaired.unlink(missing_ok=True)
            try:
                append_segment(temporary, root, media.stem+'.recovered', config)
                # Keep original group ID, repaired file path; camera recovered independently later.
                for source in temporary.sources:
                    source.id = source.id.replace('.recovered', '')
                    source.group = media.stem
                temporary.clips[0].source_id = media.stem
                project.sources.extend(temporary.sources)
                project.clips.extend(temporary.clips)
            except Exception as exc:
                errors.append(media.name+': '+str(exc))
        save_project(project, path)
        return {'project_path': str(path), 'clips': len(project.clips), 'errors': errors}


def trim_tail(project, seconds):
    """Non-destructively remove the latest timeline seconds; keep every source."""
    remaining = seconds
    while project.clips and remaining > 0:
        clip = project.clips[-1]
        duration = clip.out_s - clip.in_s
        if remaining >= duration:
            project.clips.pop()
            remaining -= duration
        else:
            clip.out_s -= remaining
            remaining = 0

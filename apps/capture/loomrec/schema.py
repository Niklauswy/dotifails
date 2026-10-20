"""Versioned, non-destructive project contract; seconds and normalized rectangles."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import math
import os
import tempfile
import uuid

@dataclass
class Source:
    id: str
    path: str
    kind: str = "screen"  # screen, mic, system, camera
    stream: int = 0       # type-relative stream index (a:N or v:N)
    gain: float = 1.0
    duration: float = 0.0
    group: str = ""       # shared capture segment; sources start together
    cursor_path: str | None = None
    cursor_effects: dict = field(default_factory=dict)
    cursor_baked: bool = False
    width: int = 0
    height: int = 0
    fps: float = 0.0
    quality: str = 'standard'

@dataclass
class Clip:
    source_id: str
    in_s: float
    out_s: float

@dataclass
class Annotation:
    kind: str             # text, arrow, highlight, mask, blur
    start: float
    end: float
    rect: list[float] = field(default_factory=lambda: [0.1, 0.1, 0.3, 0.15])
    text: str = ""
    color: str = "yellow"

@dataclass
class Subtitle:
    start: float
    end: float
    text: str

@dataclass
class Camera:
    enabled: bool = True
    rect: list[float] = field(default_factory=lambda: [0.75, 0.7, 0.22, 0.27])
    shape: str = "circle"      # circle, rounded
    size: str = "medium"       # small, medium, large
    corner: str = "bottom-right"

CAMERA_SHAPES = ('circle', 'rounded')
CAMERA_SIZES = {'small': .20, 'medium': .28, 'large': .38}
CAMERA_CORNERS = ('bottom-right', 'bottom-left', 'top-right', 'top-left')


def camera_style(value):
    """Validated camera bubble style from preferences or a capture config."""
    value = value if isinstance(value, dict) else {}
    style = {'shape': value.get('shape', 'circle'), 'size': value.get('size', 'medium'),
             'corner': value.get('corner', 'bottom-right')}
    if style['shape'] not in CAMERA_SHAPES or style['size'] not in CAMERA_SIZES or style['corner'] not in CAMERA_CORNERS:
        raise ValueError('Estilo de cámara inválido')
    return style

@dataclass
class Project:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = "Untitled recording"
    sources: list[Source] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    crop: list[float] | None = None
    camera: Camera = field(default_factory=Camera)
    subtitles: list[Subtitle] = field(default_factory=list)
    version: int = 1

    @property
    def duration(self):
        return sum(c.out_s - c.in_s for c in self.clips)


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def validate_rect(rect):
    if len(rect) != 4 or not all(finite(v) for v in rect):
        raise ValueError("Rectangle must contain four finite numbers")
    x, y, w, h = rect
    if min(x, y) < 0 or min(w, h) <= 0 or x+w > 1.000001 or y+h > 1.000001:
        raise ValueError("Rectangle must fit within normalized image bounds")


def validate(project):
    if project.version != 1:
        raise ValueError("Unsupported project version")
    sources = {s.id: s for s in project.sources}
    if len(sources) != len(project.sources) or any(not isinstance(s.id,str) or not s.id for s in project.sources):
        raise ValueError("Duplicate source ID")
    for s in project.sources:
        if type(s.cursor_baked) is not bool:raise ValueError('Invalid cursor provenance')
        if any(type(v) is not int or not 0<=v<=32768 for v in (s.width,s.height)) or not finite(s.fps) or not 0<=s.fps<=1000:
            raise ValueError('Invalid source video metadata')
        if s.quality not in {'compact','standard','high'}:raise ValueError('Invalid source quality')
        from .cursor import effect_settings
        effect_settings(s.cursor_effects)
        if s.cursor_path is not None:
            trace=Path(s.cursor_path)
            if s.kind!='screen' or not s.cursor_path or trace.is_absolute() or '..' in trace.parts:
                raise ValueError('Cursor trace must be a relative screen-source path')
        p = Path(s.path)
        if p.is_absolute() or '..' in p.parts or not s.path:
            raise ValueError("Media paths must be relative to the project directory")
        if s.kind not in {'screen', 'mic', 'system', 'camera'}:
            raise ValueError("Unknown source kind")
        if not finite(s.gain) or not 0 <= s.gain <= 8 or type(s.stream) is not int or s.stream < 0:
            raise ValueError("Invalid source gain or stream")
        if not finite(s.duration) or s.duration < 0:
            raise ValueError("Invalid source duration")
    for c in project.clips:
        if c.source_id not in sources or sources[c.source_id].kind != 'screen':
            raise ValueError("Clip requires a screen source")
        if not finite(c.in_s) or not finite(c.out_s) or not 0 <= c.in_s < c.out_s:
            raise ValueError("Invalid clip range")
        if c.out_s > sources[c.source_id].duration + 0.1:
            raise ValueError("Clip exceeds source duration")
    for a in [*project.annotations, *project.subtitles]:
        if not finite(a.start) or not finite(a.end) or not 0 <= a.start < a.end:
            raise ValueError("Invalid annotation time")
    for a in project.annotations:
        if a.kind not in {'text', 'arrow', 'highlight', 'mask', 'blur'}:
            raise ValueError("Unknown annotation kind")
        validate_rect(a.rect)
        if a.color not in {'yellow', 'white', 'black', 'red', 'green', 'blue'}:
            raise ValueError("Unsupported annotation color")
    if project.crop is not None:
        validate_rect(project.crop)
    validate_rect(project.camera.rect)
    camera_style({'shape': project.camera.shape, 'size': project.camera.size, 'corner': project.camera.corner})


def project_from_dict(data):
    data = dict(data)
    for key, cls in [('sources', Source), ('clips', Clip), ('annotations', Annotation), ('subtitles', Subtitle)]:
        data[key] = [cls(**item) for item in data.get(key, [])]
    data['camera'] = Camera(**data.get('camera', {}))
    project = Project(**data)
    validate(project)
    return project


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
        dfd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_project(project, path):
    validate(project)
    atomic_json(path, asdict(project))


def load_project(path):
    return project_from_dict(json.loads(Path(path).read_text()))


def media_path(project_path, source):
    root = Path(project_path).resolve().parent
    path = (root / source.path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Media resolves outside project directory")
    return path

"""Version 1 interchange contract. All document coordinates are original-image pixels."""
from dataclasses import dataclass, field, asdict
from typing import Literal
import math
import uuid

Tool = Literal['text', 'arrow', 'rectangle', 'ellipse', 'pen', 'highlight', 'number', 'mask', 'blur']
TOOLS = frozenset(('text','arrow','rectangle','ellipse','pen','highlight','number','mask','blur'))

@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self):
        if any(type(v) is not int for v in (self.x,self.y,self.width,self.height)):
            raise ValueError('Rectangle requires integer pixels')
        if self.width <= 0 or self.height <= 0:
            raise ValueError('Rectangle must have positive size')

    def contains(self, other):
        return (self.x <= other.x and self.y <= other.y and
                self.x+self.width >= other.x+other.width and self.y+self.height >= other.y+other.height)

@dataclass(frozen=True)
class Layer:
    tool: Tool
    points: tuple[tuple[float, float], ...]
    color: str = '#2165d5'
    width: float = 3.0
    text: str = ''
    number: int = 1
    font_size: int = 24
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self):
        object.__setattr__(self, 'points', tuple(tuple(p) for p in self.points))
        if self.tool not in TOOLS or not self.points or len(self.points) > 100000:
            raise ValueError('Invalid annotation tool/points')
        if any(len(p)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in p) for p in self.points):
            raise ValueError('Invalid annotation coordinates')
        if self.tool in ('arrow','rectangle','ellipse','highlight','mask','blur') and len(self.points)<2:
            raise ValueError('Tool requires two endpoints')
        if not math.isfinite(self.width) or not 0 < self.width <= 256 or not 6 <= self.font_size <= 256:
            raise ValueError('Invalid annotation size')
        if not isinstance(self.number,int) or not 1 <= self.number <= 99999:
            raise ValueError('Invalid step number')
        if len(self.color)!=7 or self.color[0]!='#' or any(c not in '0123456789abcdefABCDEF' for c in self.color[1:]):
            raise ValueError('Use opaque #RRGGBB colors')
        if len(self.text)>100000:raise ValueError('Text too long')

@dataclass(frozen=True)
class CaptureRequest:
    mode: Literal['region','monitor','window','desktop'] = 'region'
    region: Rect | None = None
    monitor: int = 0
    window_id: int | None = None
    include_cursor: bool = False
    delay_ms: int = 0

    def __post_init__(self):
        if self.mode not in ('region','monitor','window','desktop'):raise ValueError('Unknown capture mode')
        if not 0 <= self.delay_ms <= 60000:raise ValueError('Delay outside 0..60000 ms')
        if self.monitor < 0:raise ValueError('Invalid monitor')

@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str = ''
    path: str | None = None
    cancelled: bool = False

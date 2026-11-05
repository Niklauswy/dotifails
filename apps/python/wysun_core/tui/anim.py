"""Token-driven motion: rectangles, easing curves and a small tween runner.

Durations and curves come from ``tokens.json`` (``anim.durations`` in milliseconds,
``anim.curves`` as cubic-bezier control points; the tokens ship multi-segment Material
curves and only the first four numbers are used). ``WYSUN_REDUCED_MOTION=1`` makes every
tween jump to its end when it is added, so screens paint their final state without motion.

Clocks: a ``Tween`` starts at the first ``Animator.step(now)`` after ``add()`` (it does not
read the clock itself), so the caller owns time and tests pass numbers. ``now`` is a
monotonic value in seconds, as ``time.monotonic()`` returns.
"""
import os
from collections import namedtuple

from .. import theme as core_theme

__all__ = ['Rect', 'lerp_rect', 'bezier', 'curve', 'duration', 'Tween', 'Animator',
           'reduced_motion', 'fade_steps']

Rect = namedtuple('Rect', ('x', 'y', 'w', 'h'))

_curves = {}


def lerp_rect(a, b, t):
    """Interpolate two rectangles, every field rounded to whole cells."""
    return Rect(round(a.x + (b.x - a.x) * t), round(a.y + (b.y - a.y) * t),
                round(a.w + (b.w - a.w) * t), round(a.h + (b.h - a.h) * t))


def _segment(t, first, second):
    """One cubic-bezier axis value with implicit endpoints 0 and 1."""
    rest = 1.0 - t
    return 3 * rest * rest * t * first + 3 * rest * t * t * second + t * t * t


def bezier(points):
    """Easing function for a cubic-bezier token curve; the first four numbers are (x1,y1,x2,y2).

    ``x`` (progress in 0..1) maps to ``y`` (eased progress). The x -> parameter inversion uses
    Newton's method, with bisection as the fallback for flat or looping segments.
    """
    x1, y1, x2, y2 = (float(value) for value in list(points)[:4])

    def ease(x):
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        t = x
        for _ in range(8):
            error = _segment(t, x1, x2) - x
            if abs(error) < 1e-7:
                break
            slope = (3 * (1 - t) ** 2 * x1 + 6 * (1 - t) * t * (x2 - x1)
                     + 3 * t * t * (1 - x2))
            if abs(slope) < 1e-9:
                break
            t = min(1.0, max(0.0, t - error / slope))
        low, high = 0.0, 1.0
        for _ in range(40):
            value = _segment(t, x1, x2)
            if abs(value - x) < 1e-7:
                break
            if value < x:
                low = t
            else:
                high = t
            t = (low + high) / 2
        return _segment(t, y1, y2)

    return ease


def curve(name):
    """The easing function of an ``anim.curves`` token (``'standard'``, ``'emphasizedDecel'``...)."""
    cached = _curves.get(name)
    if cached is None:
        cached = bezier(core_theme.data()['anim']['curves'][name])
        _curves[name] = cached
    return cached


def duration(name):
    """Seconds of an ``anim.durations`` token (the tokens are milliseconds)."""
    return core_theme.data()['anim']['durations'][name] / 1000.0


def reduced_motion(environ=None):
    """Whether ``WYSUN_REDUCED_MOTION=1`` asks for no animation right now."""
    env = os.environ if environ is None else environ
    return env.get('WYSUN_REDUCED_MOTION', '') == '1'


def fade_steps(t):
    """Quantise opacity to eighths: ``0.6`` -> ``0.625`` (the prototype's stepped fades)."""
    return round(t * 8) / 8


class Tween:
    """One eased 0..1 animation, driven by ``Animator``.

    ``on_step`` receives the eased value each step (and exactly 1.0 when it finishes);
    ``on_done`` runs once, after the last ``on_step``.
    """

    def __init__(self, duration, curve, on_step, on_done=None):
        self.duration = max(0.0, float(duration))
        self.curve = curve
        self.on_step = on_step
        self.on_done = on_done
        self.started = None
        self.running = True
        self.value = 0.0

    def step(self, now):
        """Advance to ``now``; ``True`` while it still runs."""
        if not self.running:
            return False
        if self.started is None:
            self.started = now
        progress = 1.0 if self.duration <= 0 else (now - self.started) / self.duration
        progress = min(1.0, max(0.0, progress))
        self.value = 1.0 if progress >= 1.0 else self.curve(progress)
        self.on_step(self.value)
        if progress >= 1.0:
            self.running = False
            if self.on_done is not None:
                self.on_done()
        return self.running


class Animator:
    """Runs tweens against a caller-supplied monotonic clock."""

    def __init__(self):
        self.tweens = []

    def __len__(self):
        return len(self.tweens)

    def __bool__(self):
        return bool(self.tweens)

    def add(self, tween):
        """Queue a tween, or finish it at once under reduced motion."""
        if reduced_motion():
            tween.started = 0.0
            tween.value = 1.0
            tween.running = False
            tween.on_step(1.0)
            if tween.on_done is not None:
                tween.on_done()
        else:
            self.tweens.append(tween)
        return tween

    def step(self, now):
        """Advance every tween to ``now``; ``True`` while any still runs."""
        for tween in list(self.tweens):
            if tween.step(now):
                continue
            try:
                self.tweens.remove(tween)
            except ValueError:
                pass
        return bool(self.tweens)

    def finish_all(self):
        """Snap every running tween to its end (a resize or a key during an animation)."""
        for tween in list(self.tweens):
            if not tween.running:
                continue
            tween.value = 1.0
            tween.running = False
            tween.on_step(1.0)
            if tween.on_done is not None:
                tween.on_done()
        self.tweens = [tween for tween in self.tweens if tween.running]

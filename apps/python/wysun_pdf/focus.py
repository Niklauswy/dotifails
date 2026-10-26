"""A study clock with explicit transitions and one owner across reader processes."""
import fcntl
import math
import os
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication
from wysun_core import paths, jsonio


class FocusClock:
    def __init__(self, monotonic=time.monotonic, wall=time.time):
        self.monotonic, self.wall = monotonic, wall
        self.phase, self.state = 'study', 'idle'
        self.duration = self.remaining = 25 * 60
        self.last = self.monotonic()
        self.last_wall = self.wall()

    def start(self, minutes=25, phase='study'):
        self.phase, self.state = phase, 'running'
        self.duration = self.remaining = max(1, min(180, int(minutes))) * 60
        self.last, self.last_wall = self.monotonic(), self.wall()

    def tick(self):
        if self.state != 'running':
            return
        now, wall = self.monotonic(), self.wall()
        elapsed, wall_elapsed = now - self.last, wall - self.last_wall
        self.last, self.last_wall = now, wall
        # A suspended process or a sleeping machine cannot attest to study time.
        if elapsed > 5 or elapsed < 0 or wall_elapsed - elapsed > 5:
            self.state = 'paused'
            return
        self.remaining = max(0., self.remaining - elapsed)
        if not self.remaining:
            self.state = 'finished'

    def pause(self):
        self.tick()
        if self.state == 'running':
            self.state = 'paused'

    def resume(self):
        if self.state == 'paused':
            self.last, self.last_wall = self.monotonic(), self.wall()
            self.state = 'running'

    def snapshot(self):
        return dict(phase=self.phase, state=self.state, duration=self.duration, remaining=self.remaining)

    def restore(self, value):
        if not isinstance(value, dict):
            return
        try:
            duration = float(value['duration'])
            remaining = float(value['remaining'])
            if not (60 <= duration <= 180*60 and 0 <= remaining <= duration):
                return
        except (KeyError, ValueError, TypeError):
            return
        self.duration, self.remaining = duration, remaining
        self.phase = 'break' if value.get('phase') == 'break' else 'study'
        self.state = 'paused' if value.get('state') in ('running', 'paused') else 'idle'


class FocusController(QObject):
    changed = Signal()
    message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.clock = FocusClock()
        self.path = paths.state('wysun', 'pdf-reader', 'focus.json')
        self.lock_path = paths.runtime('wysun-pdf-focus.lock')
        self.owner = None
        self.windows = set()
        self.goal = ''
        self.minutes, self.break_minutes, self.long_break_minutes = 25, 5, 15
        self.completed_blocks, self.history = 0, []
        try:
            snapshot = jsonio.read_json(self.path, {})
            if isinstance(snapshot, dict):
                self.clock.restore(snapshot)
                self.goal = str(snapshot.get('goal', ''))[:500]
                for key, default in (('minutes', 25), ('break_minutes', 5), ('long_break_minutes', 15), ('completed_blocks', 0)):
                    value = snapshot.get(key, default)
                    if isinstance(value, int) and 0 <= value <= (100000 if key == 'completed_blocks' else 180):
                        setattr(self, key, value if key == 'completed_blocks' else max(1, value))
                history = snapshot.get('history', [])
                self.history = [h for h in history[-100:] if isinstance(h, dict) and
                    all(isinstance(h.get(k), (int, float)) and math.isfinite(h[k]) and h[k] >= 0
                        for k in ('seconds', 'ended'))] if isinstance(history, list) else []
        except OSError:
            pass
        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self.tick)
        self.persistence_ticks = 0

    def acquire(self):
        if self.owner is not None:
            return True
        self.lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            self.message.emit('Hay una sesión en otra instancia de Wysun PDF. Continúa desde esa ventana.')
            return False
        self.owner = fd
        return True

    def release(self):
        if self.owner is not None:
            os.close(self.owner)
            self.owner = None

    def persist(self):
        if self.owner is None:
            return
        try:
            jsonio.atomic_write_json(self.path, dict(self.clock.snapshot(), goal=self.goal,
                minutes=self.minutes, break_minutes=self.break_minutes, long_break_minutes=self.long_break_minutes,
                completed_blocks=self.completed_blocks, history=self.history[-100:]), mode=0o600)
        except OSError as error:
            self.message.emit('No se pudo guardar la sesión: ' + str(error))

    def start(self, minutes=25, goal='', phase='study'):
        try:
            if not self.acquire():
                return
        except OSError as error:
            self.message.emit('No se pudo iniciar la sesión: ' + str(error))
            return
        self.goal = goal[:500]
        self.clock.start(minutes, phase)
        self.persist()
        self.timer.start()
        self.changed.emit()

    def toggle(self):
        if self.clock.state == 'running':
            self.clock.pause()
            self.timer.stop()
        elif self.clock.state == 'paused':
            try:
                if not self.acquire():
                    return
            except OSError as error:
                self.message.emit(str(error))
                return
            self.clock.resume()
            self.timer.start()
        else:
            self.start(self.minutes, self.goal)
            return
        self.persist()
        self.changed.emit()

    def tick(self):
        before = self.clock.state
        self.clock.tick()
        self.persistence_ticks += 1
        if self.clock.state != 'running':
            self.timer.stop()
            if before == 'running':
                if self.clock.state == 'finished':
                    self.record(True)
                self.message.emit('Bloque completado. Puedes descansar o seguir leyendo.' if self.clock.state == 'finished'
                                  else 'Sesión pausada tras una interrupción. Reanuda cuando quieras.')
            self.persist()
        elif self.persistence_ticks % 15 == 0:
            self.persist()
        self.changed.emit()

    @property
    def next_break(self):
        return self.long_break_minutes if self.completed_blocks and self.completed_blocks % 4 == 0 else self.break_minutes

    def record(self, completed):
        if self.clock.phase != 'study':
            return
        elapsed = max(0, self.clock.duration - self.clock.remaining)
        if not elapsed:
            return
        if completed:
            self.completed_blocks += 1
        self.history.append(dict(goal=self.goal, seconds=round(elapsed), completed=completed, ended=time.time()))
        self.history = self.history[-100:]

    def finish(self):
        if self.clock.state in ('running', 'paused'):
            self.clock.pause()
            self.record(self.clock.state == 'finished')
        self.clock.state = 'idle'
        self.clock.duration = self.clock.remaining = self.minutes * 60
        self.timer.stop()
        self.persist()
        self.release()
        self.changed.emit()

    def detach(self, window):
        self.windows.discard(window)
        if not self.windows:
            self.clock.pause()
            self.timer.stop()
            self.persist()
            self.release()


def shared_focus(window):
    app = QApplication.instance()
    if not hasattr(app, '_pdf_focus'):
        app._pdf_focus = FocusController(app)
    controller = app._pdf_focus
    controller.windows.add(window)
    return controller

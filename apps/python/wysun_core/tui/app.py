"""The app loop: one ``selectors`` loop drives input, timers, children and frames.

The loop owns the clock. Every iteration waits for terminal input, a timer, a
child process or the next frame deadline, dispatches what is ready and then
paints a frame only when something asked for it (:meth:`App.invalidate`) or a
tween is running (capped at 60 fps). A tween is driven by the same loop, so a
screen never needs its own thread or timer.

``App`` is meant to be subclassed: override :meth:`App.draw` for the background,
:meth:`App.on_key` and friends for input, and add :class:`Layer` objects for
panels that animate over it. ``run()`` enters the real terminal and restores it
on the way out, whatever happened inside.

Tests drive the loop without a terminal by passing a ``VirtualTerminal`` and
calling :meth:`App.step` or :meth:`App.run_for`; the first call starts the app
lazily (loads the palette, installs the resize listener and calls ``on_start``).
"""
from __future__ import annotations

import heapq
import os
import selectors
import subprocess
import threading
import time

from .anim import Animator, Rect
from .canvas import Canvas, Style
from .keys import Key, Mouse, Parser, Paste, Resize
from .screen import Screen
from .terminal import Terminal
from .theme import Palette

__all__ = ['App', 'Child', 'Layer']

FRAME_INTERVAL = 1.0 / 60.0
ESCAPE_FLUSH = 0.03
THEME_CHECK_INTERVAL = 1.5
STDERR_TAIL = 20
KILL_GRACE = 1.0                         # seconds between SIGTERM and SIGKILL
MIN_WIDTH = 60
MIN_HEIGHT = 16
TOO_SMALL = 'Agranda la terminal'
READ_CHUNK = 65536
MIN_INTERVAL = 0.001


class Layer:
    """A panel painted into its own canvas and pasted onto the frame.

    ``rect`` is mutable on purpose: a tween changes it every frame. Layers are
    painted in ascending ``z`` order (stable for equal ``z``), each one into a
    fresh canvas of ``rect.w`` × ``rect.h`` whose background is the main
    canvas' (the palette's ``surface``), and then pasted at ``rect.x``,
    ``rect.y`` with ``opacity``. Invisible layers are skipped.
    """

    def __init__(self, rect: Rect, z: int = 0, opacity: float = 1.0,
                 visible: bool = True) -> None:
        self.rect = rect
        self.z = z
        self.opacity = float(opacity)
        self.visible = bool(visible)

    def draw(self, canvas: Canvas, palette: Palette) -> None:
        """Paint the layer's content; subclasses override this."""

    def compose(self, frame: Canvas, palette: Palette) -> None:
        """Put the layer on the frame: draw into its own canvas, paste with ``opacity``."""
        rect = self.rect
        if rect.w <= 0 or rect.h <= 0:
            return
        sub = Canvas(rect.w, rect.h, frame.bg)
        self.draw(sub, palette)
        frame.paste(sub, rect.x, rect.y, self.opacity)


class Dim(Layer):
    """Darkens what is underneath toward a palette role (a modal's scrim) by ``opacity``.

    Unlike a pasted layer it keeps every character below visible, only blended.
    """

    def __init__(self, rect: Rect, role: str = 'scrim', z: int = 0, opacity: float = 1.0,
                 visible: bool = True) -> None:
        super().__init__(rect, z=z, opacity=opacity, visible=visible)
        self.role = role

    def compose(self, frame: Canvas, palette: Palette) -> None:
        if self.opacity > 0.0:
            frame.blend(self.rect, palette[self.role], self.opacity)


class _Timer:
    """Opaque handle returned by ``App.after`` and ``App.every``."""

    __slots__ = ('fn', 'cancelled')

    def __init__(self, fn) -> None:
        self.fn = fn
        self.cancelled = False


def _decode_line(raw: bytes) -> str:
    return raw.decode('utf-8', errors='replace').rstrip('\r')


class Child:
    """A child process whose output is read line by line inside the app loop.

    ``stdout`` and ``stderr`` are pipes; every complete line reaches
    ``on_line`` (stdout) or ``on_err_line`` (stderr, when given) decoded as
    UTF-8 with replacement. The last 20 stderr lines are always kept in
    ``stderr_tail``. ``on_exit(returncode)`` runs once, after every line of
    both pipes was delivered. ``stdin`` bytes are written from a helper thread
    so a big payload can never block the loop, and stdin is closed afterwards.
    """

    def __init__(self, app: 'App', argv, on_line, on_exit, on_err_line=None) -> None:
        self.app = app
        self.argv = [str(part) for part in argv]
        self.on_line = on_line
        self.on_exit = on_exit
        self.on_err_line = on_err_line
        self.stderr_tail: list[str] = []
        self.pid: int | None = None
        self.running = True
        self._process: subprocess.Popen | None = None
        self._streams: dict[str, object] = {}
        self._fds: dict[str, int] = {}
        self._buffers = {'out': b'', 'err': b''}
        self._eof: set[str] = set()
        self._exited = False
        self._returncode: int | None = None
        self._delivered = False
        self._pidfd: int | None = None
        self._poll_scheduled = False

    # -- lifecycle --------------------------------------------------------
    def _start(self, stdin: bytes | None, env: dict | None) -> None:
        environment = None
        if env is not None:
            environment = dict(os.environ)
            environment.update({str(key): str(value) for key, value in env.items()})
        self._process = subprocess.Popen(
            self.argv,
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            env=environment,
            close_fds=True,
        )
        self.pid = self._process.pid
        for name, stream in (('out', self._process.stdout), ('err', self._process.stderr)):
            fd = stream.fileno()
            os.set_blocking(fd, False)
            self._streams[name] = stream
            self._fds[name] = fd
            self.app._selector.register(fd, selectors.EVENT_READ, ('child', self, name))
        self._watch_exit()
        if stdin is not None:
            threading.Thread(target=self._feed_stdin, args=(bytes(stdin),),
                             daemon=True).start()

    def _feed_stdin(self, data: bytes) -> None:
        pipe = self._process.stdin if self._process is not None else None
        if pipe is None:
            return
        try:
            view = memoryview(data)
            while view:
                written = pipe.write(view)
                if not written:
                    break
                view = view[written:]
            pipe.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            try:
                pipe.close()
            except (OSError, ValueError):
                pass

    def _watch_exit(self) -> None:
        """Wake the loop when the process exits (pidfd), or poll as a fallback."""
        try:
            fd = os.pidfd_open(self._process.pid)
        except (AttributeError, OSError):
            return
        os.set_blocking(fd, False)
        self._pidfd = fd
        self.app._selector.register(fd, selectors.EVENT_READ, ('child-exit', self, None))

    def kill(self) -> None:
        """Terminate the process without blocking the loop; SIGKILL follows after one second.

        The exit is reaped by the normal watcher (pidfd or poll), so ``on_exit`` still runs
        once, after the remaining output, even when both pipes had already closed.
        """
        process = self._process
        if process is None or self._exited:
            return
        if process.poll() is not None:
            self._returncode = process.returncode
            self._exited = True
            self._drop_pidfd()
            self._maybe_finish()
            return
        try:
            process.terminate()
        except OSError:
            pass
        self.app.after(KILL_GRACE, self._hard_kill)
        self._maybe_finish()               # no pidfd: start polling for the exit

    def _hard_kill(self) -> None:
        process = self._process
        if process is not None and not self._exited and process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass

    def _stop_now(self) -> None:
        """Shutdown path: terminate, wait briefly, kill, and reap (the loop is ending anyway)."""
        process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=KILL_GRACE)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=KILL_GRACE)
            except (OSError, subprocess.TimeoutExpired):
                pass
        except OSError:
            pass

    # -- reading ----------------------------------------------------------
    def _on_readable(self, name: str) -> None:
        fd = self._fds.get(name)
        if fd is None:
            return
        try:
            chunk = os.read(fd, READ_CHUNK)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            chunk = b''
        if chunk:
            self._buffers[name] += chunk
            self._drain_lines(name)
            return
        self._drain_lines(name, final=True)
        self._eof.add(name)
        self._close_stream(name)
        self._maybe_finish()

    def _drain_lines(self, name: str, final: bool = False) -> None:
        buffer = self._buffers[name]
        while True:
            index = buffer.find(b'\n')
            if index < 0:
                break
            line, buffer = buffer[:index], buffer[index + 1:]
            self._emit(name, _decode_line(line))
        if final and buffer:
            self._emit(name, _decode_line(buffer))
            buffer = b''
        self._buffers[name] = buffer

    def _emit(self, name: str, line: str) -> None:
        if name == 'out':
            self.on_line(line)
            return
        self.stderr_tail.append(line)
        if len(self.stderr_tail) > STDERR_TAIL:
            del self.stderr_tail[:-STDERR_TAIL]
        if self.on_err_line is not None:
            self.on_err_line(line)

    def _close_stream(self, name: str) -> None:
        fd = self._fds.pop(name, None)
        if fd is not None and self.app._selector is not None:
            try:
                self.app._selector.unregister(fd)
            except (KeyError, ValueError):
                pass
        stream = self._streams.pop(name, None)
        if stream is not None:
            try:
                stream.close()
            except (OSError, ValueError):
                pass

    # -- exit -------------------------------------------------------------
    def _on_exit_ready(self) -> None:
        self._drop_pidfd()
        if self._exited:
            return
        self._exited = True
        try:
            self._returncode = self._process.wait()
        except OSError:
            self._returncode = self._process.returncode
        self._maybe_finish()

    def _drop_pidfd(self) -> None:
        if self._pidfd is None:
            return
        fd, self._pidfd = self._pidfd, None
        if self.app._selector is not None:
            try:
                self.app._selector.unregister(fd)
            except (KeyError, ValueError):
                pass
        try:
            os.close(fd)
        except OSError:
            pass

    def _poll_exit(self) -> None:
        self._poll_scheduled = False
        if self._exited or not self.running or self._process is None:
            return
        code = self._process.poll()
        if code is None:
            self._schedule_poll()
            return
        self._returncode = code
        self._exited = True
        self._maybe_finish()

    def _schedule_poll(self) -> None:
        if self._poll_scheduled or self._exited:
            return
        self._poll_scheduled = True
        self.app.after(0.01, self._poll_exit)

    def _maybe_finish(self) -> None:
        if self._delivered or not self.running:
            return
        if self._eof != {'out', 'err'}:
            return
        if not self._exited:
            if self._pidfd is None:
                self._schedule_poll()
            return
        self._delivered = True
        self.running = False
        self.app._children.discard(self)
        code = self._returncode
        if code is None and self._process is not None:
            code = self._process.returncode
        self.on_exit(0 if code is None else code)

    def _teardown(self) -> None:
        """Close every descriptor this child owns; used when the loop shuts down."""
        for name in list(self._fds):
            self._close_stream(name)
        self._drop_pidfd()
        self._delivered = True
        self.running = False


class App:
    """A terminal app: input, timers, child processes, layers and frame scheduling.

    ``term`` is anything with the small terminal protocol (``Terminal`` or a
    ``VirtualTerminal``); when it is ``None`` a real ``Terminal`` is created
    inside :meth:`run`. ``home`` is the HOME the palette is read from (tests
    pass a temporary one).
    """

    # True leaves every cell painted with the palette's ``surface`` without a background, so a
    # translucent terminal (Ghostty's background-opacity and blur) shows the desktop behind it.
    transparent = False

    def __init__(self, term=None, home=None) -> None:
        self.term = term
        self.home = home
        self.layers: list[Layer] = []
        self.animator = Animator()
        self.palette: Palette | None = None
        self.size = (0, 0)
        self.parser = Parser()
        self.screen = Screen(truecolor=os.environ.get('COLORTERM') in ('truecolor', '24bit'))
        self._selector: selectors.BaseSelector | None = None
        self._wake_r: int | None = None
        self._wake_w: int | None = None
        self._timers: list[tuple[float, int, _Timer, float | None]] = []
        self._timer_seq = 0
        self._timer_lock = threading.Lock()
        self._children: set[Child] = set()
        self._started = False
        self._quitting = False
        self._dirty = False
        self._full_repaint = False
        self._prev: Canvas | None = None
        self._resized = False
        self._escape_due: float | None = None
        self._next_frame = 0.0
        self._next_theme_check = 0.0

    # -- overridables -----------------------------------------------------
    def on_start(self) -> None:
        """Called once, before the first frame."""

    def on_key(self, event: Key) -> None:
        """A key press; the default quits on Ctrl+C."""
        if event.ctrl and event.name == 'c':
            self.quit()

    def on_mouse(self, event: Mouse) -> None:
        """A mouse event."""

    def on_paste(self, event: Paste) -> None:
        """Bracketed paste content."""

    def on_resize(self, width: int, height: int) -> None:
        """The terminal changed size; the frame relayouts right after."""

    def draw(self, canvas: Canvas) -> None:
        """Paint the background, before the layers."""

    def on_theme(self) -> None:
        """The palette was reloaded after a wallpaper or mode change."""

    # -- scheduling -------------------------------------------------------
    def after(self, seconds: float, fn) -> _Timer:
        """Run ``fn`` once, ``seconds`` from now; safe from another thread."""
        return self._schedule(seconds, fn, None)

    def every(self, seconds: float, fn) -> _Timer:
        """Run ``fn`` every ``seconds`` until cancelled; safe from another thread."""
        interval = max(MIN_INTERVAL, float(seconds))
        return self._schedule(interval, fn, interval)

    def cancel(self, handle: _Timer) -> None:
        """Forget a timer; a cancelled handle never runs again."""
        handle.cancelled = True
        self._wake()

    def _schedule(self, seconds: float, fn, interval: float | None) -> _Timer:
        handle = _Timer(fn)
        due = time.monotonic() + max(0.0, float(seconds))
        with self._timer_lock:
            self._timer_seq += 1
            heapq.heappush(self._timers, (due, self._timer_seq, handle, interval))
        self._wake()
        return handle

    def _fire_timers(self, now: float) -> None:
        while True:
            with self._timer_lock:
                if not self._timers:
                    return
                due, _sequence, handle, interval = self._timers[0]
                if due > now:
                    return
                heapq.heappop(self._timers)
            if handle.cancelled:
                continue
            handle.fn()
            if interval is not None and not handle.cancelled:
                next_due = due + interval
                if next_due <= now:
                    next_due = now + interval
                with self._timer_lock:
                    self._timer_seq += 1
                    heapq.heappush(self._timers, (next_due, self._timer_seq, handle, interval))

    # -- child processes --------------------------------------------------
    def spawn(self, argv, on_line, on_exit, stdin: bytes | None = None,
              env: dict | None = None, on_err_line=None) -> Child:
        """Start a child process; normally called from ``on_start`` or a handler.

        With a ``VirtualTerminal`` it may be called before the first ``step``:
        the app starts lazily so the child has a selector to register in. ``env``
        entries are added on top of the current environment, so a caller can set
        one variable without losing ``PATH``.
        """
        if self._selector is None:
            if self.term is None:
                raise RuntimeError('App.spawn needs a terminal: call it from on_start or later')
            self._ensure_started()
        child = Child(self, argv, on_line, on_exit, on_err_line)
        child._start(stdin, env)
        self._children.add(child)
        return child

    # -- frame requests ---------------------------------------------------
    def invalidate(self) -> None:
        """Ask for a frame; safe from another thread."""
        self._dirty = True
        self._wake()

    def quit(self) -> None:
        """End :meth:`run` after the current iteration."""
        self._quitting = True
        self._wake()

    def _wake(self) -> None:
        fd = self._wake_w
        if fd is None:
            return
        try:
            os.write(fd, b'.')
        except (BlockingIOError, OSError):
            pass

    # -- lifecycle --------------------------------------------------------
    def run(self) -> int:
        """Enter the terminal, run the loop until ``quit`` and restore it."""
        term = self.term
        if term is None:
            term = Terminal()
            self.term = term
        with term:
            try:
                self._ensure_started()
                while not self._quitting:
                    self.step(None)
            finally:
                self._shutdown()
        return 0

    def close(self) -> None:
        """Release the loop's descriptors and kill any child still running."""
        self._shutdown()

    def step(self, timeout: float | None = 0.0) -> None:
        """Run one iteration, waiting at most ``timeout`` seconds (``None``: until due).

        The first call starts the app lazily: it loads the palette, installs the
        resize listener, calls ``on_start`` and requests the first frame. This is
        what lets tests drive an app without calling ``run``.
        """
        self._ensure_started()
        wait = self._compute_wait(timeout)
        for key, _mask in self._selector.select(wait):
            data = key.data
            if data == 'input':
                self._read_input()
            elif data == 'wake':
                self._read_wake()
            else:
                kind, child, name = data
                if kind == 'child':
                    child._on_readable(name)
                elif kind == 'child-exit':
                    child._on_exit_ready()
        now = time.monotonic()
        if self._resized:
            self._resized = False
            self._handle_resize()
        if self._escape_due is not None and now >= self._escape_due:
            self._escape_due = None
            for event in self.parser.flush():
                self._dispatch(event)
        self._fire_timers(now)
        self._step_animations()
        self._check_theme()
        self._paint()

    def run_for(self, seconds: float) -> None:
        """Step the loop until ``seconds`` of monotonic time pass or the app quits."""
        self._ensure_started()
        deadline = time.monotonic() + max(0.0, float(seconds))
        while not self._quitting:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            self.step(remaining)

    def _ensure_started(self) -> None:
        if self._started:
            return
        if self.term is None:
            raise RuntimeError('App needs a terminal before stepping')
        self._started = True
        now = time.monotonic()
        self.size = tuple(self.term.size())
        self.palette = Palette.load(self.home)
        self._wake_r, self._wake_w = os.pipe()
        os.set_blocking(self._wake_r, False)
        os.set_blocking(self._wake_w, False)
        self._selector = selectors.DefaultSelector()
        self._selector.register(self.term.fileno(), selectors.EVENT_READ, 'input')
        self._selector.register(self._wake_r, selectors.EVENT_READ, 'wake')
        self.term.resize_listener = self._on_resize_signal
        self._next_frame = 0.0
        self._next_theme_check = now + THEME_CHECK_INTERVAL
        self.on_start()
        self.invalidate()

    def _shutdown(self) -> None:
        if self._selector is None and not self._started:
            return
        self._started = False
        children = list(self._children)
        for child in children:              # SIGTERM to all first, so the waits overlap
            if child._process is not None and child._process.poll() is None:
                try:
                    child._process.terminate()
                except OSError:
                    pass
        for child in children:
            child._stop_now()
            child._teardown()
        self._children.clear()
        selector, self._selector = self._selector, None
        if selector is not None:
            try:
                selector.close()
            except OSError:
                pass
        self._close_wake()
        if self.term is not None:
            self.term.resize_listener = None
        self._prev = None
        self._escape_due = None

    def _close_wake(self) -> None:
        for attribute in ('_wake_r', '_wake_w'):
            fd = getattr(self, attribute)
            setattr(self, attribute, None)
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

    # -- one iteration ----------------------------------------------------
    def _compute_wait(self, timeout: float | None) -> float:
        now = time.monotonic()
        deadlines = [self._next_theme_check]
        if self._dirty and self._full_repaint:
            deadlines.append(now)
        elif self._dirty or self.animator:
            deadlines.append(max(now, self._next_frame))   # never faster than 60 fps
        if self._escape_due is not None:
            deadlines.append(self._escape_due)
        with self._timer_lock:
            if self._timers:
                deadlines.append(self._timers[0][0])
        wait = max(0.0, min(deadlines) - now)
        if timeout is not None:
            wait = min(wait, max(0.0, float(timeout)))
        return wait

    def _read_input(self) -> None:
        data = self.term.read(0)
        if not data:
            return
        for event in self.parser.feed(data):
            self._dispatch(event)
        self._escape_due = time.monotonic() + ESCAPE_FLUSH if self.parser.pending else None

    def _read_wake(self) -> None:
        fd = self._wake_r
        if fd is None:
            return
        while True:
            try:
                chunk = os.read(fd, 4096)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            if not chunk:
                return
            if b'r' in chunk:
                self._resized = True

    def _dispatch(self, event) -> None:
        if isinstance(event, Key):
            self.on_key(event)
        elif isinstance(event, Mouse):
            self.on_mouse(event)
        elif isinstance(event, Paste):
            self.on_paste(event)
        elif isinstance(event, Resize):
            self.size = (event.width, event.height)
            self._full_repaint = True
            self._dirty = True
            self.on_resize(event.width, event.height)

    def _on_resize_signal(self) -> None:
        """The terminal's resize listener: signal-safe (a flag and one pipe byte)."""
        self._resized = True
        self._wake()

    def _handle_resize(self) -> None:
        self.animator.finish_all()
        self.size = tuple(self.term.size())
        self._prev = None
        self._full_repaint = True
        self._dirty = True
        self.on_resize(*self.size)

    def _step_animations(self) -> None:
        if not self.animator:
            return
        if not self.animator.step(time.monotonic()):
            self._dirty = True  # paint the final state even if nothing invalidated

    def _check_theme(self) -> None:
        now = time.monotonic()
        if now < self._next_theme_check:
            return
        self._next_theme_check = now + THEME_CHECK_INTERVAL
        if self.palette is None or not self.palette.changed(self.home):
            return
        self.palette = Palette.load(self.home)
        self.on_theme()
        self._full_repaint = True
        self._dirty = True

    # -- painting ---------------------------------------------------------
    def _paint(self) -> None:
        now = time.monotonic()
        # A resize or theme change repaints at once; everything else keeps the 60 fps cap.
        if (self._dirty or self.animator) and (now >= self._next_frame or self._full_repaint):
            self._render(now)

    def _render(self, now: float) -> None:
        # Consumed before drawing: an invalidate() from a worker thread during this
        # frame keeps the flag set and gets its own frame.
        self._dirty = False
        width, height = self.size
        background = self.palette['surface']
        canvas = Canvas(width, height, background)
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            style = Style(fg=self.palette['onSurface'], bg=background)
            x = max(0, (width - len(TOO_SMALL)) // 2)
            y = max(0, (height - 1) // 2)
            canvas.text(x, y, TOO_SMALL, style)
        else:
            self.draw(canvas)
            for layer in sorted((item for item in self.layers if item.visible),
                                key=lambda item: item.z):
                layer.compose(canvas, self.palette)
        previous = None if self._full_repaint else self._prev
        self.term.write(self.screen.render(previous, canvas, background if self.transparent else None))
        self._prev = canvas
        self._full_repaint = False
        self._next_frame = now + FRAME_INTERVAL

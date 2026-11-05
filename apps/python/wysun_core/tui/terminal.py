"""The real terminal: raw mode, alternate screen, mouse and guaranteed restore.

Everything the terminal changes (termios attributes, alternate screen, cursor,
SGR mouse, bracketed paste, signal handlers) is undone by ``restore()``, which
is idempotent and runs on normal exit, on any exception, from ``atexit`` and
from a SIGTERM handler. The SIGTERM handler restores and exits with 143.
"""
from __future__ import annotations

import atexit
import os
import select
import signal
import termios
import tty
from typing import Callable

ENTER_SEQUENCES = (
    '\x1b[?1049h'        # alternate screen
    '\x1b[?25l'          # hide the cursor
    '\x1b[?1000;1002;1006h'  # press, drag and SGR mouse reporting
    '\x1b[?2004h'        # bracketed paste
)

LEAVE_SEQUENCES = (
    '\x1b[?2004l'        # bracketed paste off
    '\x1b[?1006l\x1b[?1002l\x1b[?1000l'  # mouse reporting off
    '\x1b[?25h'          # show the cursor
    '\x1b[?1049l'        # back to the main screen
)

DEFAULT_SIZE = (80, 24)
SIGTERM_EXIT_CODE = 143


class Terminal:
    """Raw terminal with an alternate screen, as a context manager."""

    def __init__(self, fd_in: int = 0, fd_out: int = 1) -> None:
        self.fd_in = fd_in.fileno() if hasattr(fd_in, 'fileno') else int(fd_in)
        self.fd_out = fd_out.fileno() if hasattr(fd_out, 'fileno') else int(fd_out)
        self.resize_listener: Callable[[], None] | None = None
        self._active = False
        self._original_attrs: list | None = None
        self._previous_handlers: dict[int, object] = {}

    # -- the selectors contract -------------------------------------------
    def fileno(self) -> int:
        """The input descriptor, for ``selectors``."""
        return self.fd_in

    def size(self) -> tuple[int, int]:
        """Current size as ``(columns, rows)``."""
        for fd in (self.fd_out, self.fd_in):
            try:
                size = os.get_terminal_size(fd)
            except OSError:
                continue
            return size.columns, size.lines
        columns = os.environ.get('COLUMNS')
        lines = os.environ.get('LINES')
        if columns and lines:
            try:
                return int(columns), int(lines)
            except ValueError:
                pass
        return DEFAULT_SIZE

    def write(self, data: bytes) -> None:
        """Write all of ``data`` to the output descriptor."""
        view = memoryview(bytes(data))
        while view:
            written = os.write(self.fd_out, view)
            view = view[written:]

    def read(self, timeout: float | None = None) -> bytes:
        """Read what is available; ``b''`` when the timeout expires."""
        try:
            ready, _, _ = select.select([self.fd_in], [], [], timeout)
        except (OSError, ValueError):
            return b''
        if not ready:
            return b''
        try:
            return os.read(self.fd_in, 65536)
        except (BlockingIOError, InterruptedError):
            return b''
        except OSError:
            return b''

    # -- lifecycle --------------------------------------------------------
    def __enter__(self) -> 'Terminal':
        if self._active:
            return self
        self._active = True
        if os.isatty(self.fd_in):
            self._original_attrs = termios.tcgetattr(self.fd_in)
            tty.setraw(self.fd_in)
        self.write(ENTER_SEQUENCES.encode())
        self._install_signal_handlers()
        atexit.register(self.restore)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.restore()

    def restore(self) -> None:
        """Undo everything, once. Safe to call at any time, from anywhere."""
        if not self._active:
            return
        self._active = False
        self._remove_signal_handlers()
        atexit.unregister(self.restore)
        try:
            self.write(LEAVE_SEQUENCES.encode())
        except OSError:
            pass
        finally:
            if self._original_attrs is not None:
                try:
                    termios.tcsetattr(self.fd_in, termios.TCSADRAIN, self._original_attrs)
                except (OSError, termios.error):
                    pass
                self._original_attrs = None

    # -- signals ----------------------------------------------------------
    def _install_signal_handlers(self) -> None:
        handlers = [(getattr(signal, 'SIGWINCH', None), self._on_winch),
                    (getattr(signal, 'SIGTERM', None), self._on_term)]
        for signum, handler in handlers:
            if signum is None:
                continue
            try:
                previous = signal.getsignal(signum)
                signal.signal(signum, handler)
            except (OSError, ValueError, TypeError):
                continue  # not the main thread, or a signal we cannot touch
            self._previous_handlers[signum] = previous

    def _remove_signal_handlers(self) -> None:
        for signum, previous in list(self._previous_handlers.items()):
            try:
                signal.signal(signum, previous)
            except (OSError, ValueError, TypeError):
                pass
        self._previous_handlers.clear()

    def _on_winch(self, signum, frame) -> None:
        listener = self.resize_listener
        if listener is None:
            return
        try:
            listener()
        except Exception:  # a listener must never break terminal handling
            pass

    def _on_term(self, signum, frame) -> None:
        self.restore()
        os._exit(SIGTERM_EXIT_CODE)

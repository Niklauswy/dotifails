"""An in-memory terminal for tests and for ``App(term=...)``.

``VirtualTerminal`` speaks the same little protocol as ``Terminal`` (``fileno``,
``size``, ``write``, ``read``, ``feed_input``, ``resize_listener``) but keeps
its input in an ``os.pipe`` and decodes what is written back into a grid, so a
test can assert on the frame the app produced.
"""
from __future__ import annotations

import os
import select
from typing import Callable

DEFAULT_SIZE = (80, 24)


class VirtualTerminal:
    """A terminal that never leaves the process."""

    def __init__(self, width: int = DEFAULT_SIZE[0], height: int = DEFAULT_SIZE[1]) -> None:
        self.width = int(width)
        self.height = int(height)
        self.output = bytearray()
        self.resize_listener: Callable[[], None] | None = None
        self.closed = False
        self._read_fd, self._write_fd = os.pipe()
        self._grid = [[' '] * self.width for _ in range(self.height)]
        self._row = 0
        self._col = 0
        # Bytes of an escape sequence or a UTF-8 character still arriving.
        self._pending = b''

    # -- the selectors contract -------------------------------------------
    def fileno(self) -> int:
        """The read end of the input pipe, for ``selectors``."""
        return self._read_fd

    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def write(self, data: bytes) -> None:
        """Record the bytes and paint the ones that are printable text."""
        data = bytes(data)
        self.output += data
        self._pending += data
        self._parse()

    def read(self, timeout: float | None = None) -> bytes:
        """Read fed input; ``b''`` when the timeout expires or it is closed."""
        if self.closed:
            return b''
        try:
            ready, _, _ = select.select([self._read_fd], [], [], timeout)
        except (OSError, ValueError):
            return b''
        if not ready:
            return b''
        try:
            return os.read(self._read_fd, 65536)
        except OSError:
            return b''

    # -- test driving -----------------------------------------------------
    def feed_input(self, data: bytes) -> None:
        """Make ``data`` available to ``read`` as if it had been typed."""
        if self.closed:
            raise OSError('virtual terminal is closed')
        os.write(self._write_fd, bytes(data))

    def resize(self, width: int, height: int) -> None:
        """Change the size: a real resize leaves the screen blank."""
        self.width = int(width)
        self.height = int(height)
        self._grid = [[' '] * self.width for _ in range(self.height)]
        self._row = 0
        self._col = 0
        self._pending = b''
        listener = self.resize_listener
        if listener is not None:
            listener()

    def canvas_text(self) -> list[str]:
        """The last rendered frame as one string per row."""
        return [''.join(row) for row in self._grid]

    def close(self) -> None:
        """Close the input pipe. Safe to call twice."""
        if self.closed:
            return
        self.closed = True
        for fd in (self._read_fd, self._write_fd):
            try:
                os.close(fd)
            except OSError:
                pass

    def __enter__(self) -> 'VirtualTerminal':
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    # -- a tiny screen emulator -------------------------------------------
    def _parse(self) -> None:
        buffer = self._pending
        while buffer:
            first = buffer[0]
            if first == 0x1b:
                consumed = self._escape(buffer)
                if consumed == 0:
                    break  # sequence still arriving
                buffer = buffer[consumed:]
            elif first < 0x20:
                self._control(first)
                buffer = buffer[1:]
            else:
                length = _utf8_length(first)
                if len(buffer) < length:
                    break
                self._put(buffer[:length].decode('utf-8', errors='replace'))
                buffer = buffer[length:]
        self._pending = buffer

    def _escape(self, buffer: bytes) -> int:
        """Consume one escape sequence; 0 means it is incomplete."""
        if len(buffer) < 2:
            return 0
        second = buffer[1]
        if second == ord('['):
            index = 2
            while index < len(buffer) and not 0x40 <= buffer[index] <= 0x7E:
                index += 1
            if index >= len(buffer):
                return 0
            self._csi(buffer[2:index].decode('ascii', errors='replace'), chr(buffer[index]))
            return index + 1
        if second == ord(']'):
            # OSC: ends with BEL or ST; it never paints anything.
            end = buffer.find(b'\x07', 2)
            stop = buffer.find(b'\x1b\\', 2)
            if end < 0 or (0 <= stop < end):
                end = stop
            if end < 0:
                return 0
            return end + (2 if buffer[end:end + 1] == b'\x1b' else 1)
        if second in (ord('('), ord(')'), ord('*'), ord('+')):
            return 3 if len(buffer) >= 3 else 0  # charset designation
        return 2  # two-byte escape (keypad modes and the like)

    def _csi(self, parameters: str, final: str) -> None:
        if final in ('H', 'f'):
            self._cursor(parameters)
        elif final == 'J' and parameters in ('', '2', '3'):
            if parameters in ('2', '3'):
                self._grid = [[' '] * self.width for _ in range(self.height)]
        # SGR (m), private modes (?) and everything else change no cells.

    def _cursor(self, parameters: str) -> None:
        parts = parameters.split(';') if parameters else []
        try:
            row = int(parts[0]) if parts and parts[0] else 1
            column = int(parts[1]) if len(parts) > 1 and parts[1] else 1
        except ValueError:
            return
        self._row = max(0, min(self.height - 1, row - 1))
        self._col = max(0, min(self.width - 1, column - 1))

    def _control(self, byte: int) -> None:
        if byte == 0x0d:  # carriage return
            self._col = 0
        elif byte == 0x0a:  # line feed
            self._row = min(self.height - 1, self._row + 1)
        elif byte == 0x08:  # backspace
            self._col = max(0, self._col - 1)
        elif byte == 0x09:  # tab
            self._col = min(self.width - 1, (self._col // 8 + 1) * 8)

    def _put(self, char: str) -> None:
        if 0 <= self._row < self.height and 0 <= self._col < self.width:
            self._grid[self._row][self._col] = char
        self._col += 1
        if self._col >= self.width:
            self._col = 0
            self._row += 1
            if self._row >= self.height:  # stay on the last cell at the bottom
                self._row = self.height - 1
                self._col = self.width - 1


def _utf8_length(first: int) -> int:
    if first < 0x80:
        return 1
    if first >> 5 == 0b110:
        return 2
    if first >> 4 == 0b1110:
        return 3
    if first >> 3 == 0b11110:
        return 4
    return 1

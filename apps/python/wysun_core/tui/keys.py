"""Input events and an incremental parser over raw terminal bytes.

``Parser.feed`` is a small state machine: it keeps the bytes of a sequence
that arrived incomplete and finishes it on the next feed. A lone ``ESC`` can
only be told apart from the start of a sequence by waiting, so the application
calls ``Parser.flush`` when 30 ms pass with no more input.
"""
from __future__ import annotations

from dataclasses import dataclass

ESC = 0x1b


@dataclass(frozen=True)
class Key:
    """A key press. ``name`` is ``'char'`` for printable keys."""

    name: str
    char: str = ''
    alt: bool = False
    ctrl: bool = False


@dataclass(frozen=True)
class Mouse:
    """A mouse event in 0-based cells."""

    kind: str  # 'press' | 'release' | 'drag' | 'wheelup' | 'wheeldown'
    button: int
    x: int
    y: int


@dataclass(frozen=True)
class Paste:
    """Bracketed paste content, inserted as text rather than as keys."""

    text: str


@dataclass(frozen=True)
class Resize:
    """A new terminal size in cells."""

    width: int
    height: int


Event = Key | Mouse | Paste | Resize

# CSI final letters that are a key on their own.
_CSI_FINALS = {
    'A': 'up',
    'B': 'down',
    'C': 'right',
    'D': 'left',
    'H': 'home',
    'F': 'end',
    'Z': 'backtab',
}

# ``CSI <number> ~`` keys. Insert (2) is not part of the public key names.
_CSI_TILDE = {
    1: 'home',
    3: 'delete',
    4: 'end',
    5: 'pageup',
    6: 'pagedown',
    7: 'home',
    8: 'end',
    11: 'f1',
    12: 'f2',
    13: 'f3',
    14: 'f4',
    15: 'f5',
    17: 'f6',
    18: 'f7',
    19: 'f8',
    20: 'f9',
    21: 'f10',
    23: 'f11',
    24: 'f12',
}

# ``ESC O <letter>`` (application cursor keys, SS3 function keys).
_SS3_FINALS = {
    'A': 'up',
    'B': 'down',
    'C': 'right',
    'D': 'left',
    'H': 'home',
    'F': 'end',
    'P': 'f1',
    'Q': 'f2',
    'R': 'f3',
    'S': 'f4',
}

_PASTE_END = b'\x1b[201~'


def _utf8_length(first: int) -> int:
    """How many bytes the UTF-8 sequence starting with ``first`` needs."""
    if first < 0x80:
        return 1
    if first >> 5 == 0b110:
        return 2
    if first >> 4 == 0b1110:
        return 3
    if first >> 3 == 0b11110:
        return 4
    return 1


def _decode(buffer: bytes) -> str:
    return buffer.decode('utf-8', errors='replace')


class Parser:
    """Turn terminal input bytes into ``Key``, ``Mouse`` and ``Paste`` events."""

    def __init__(self) -> None:
        self._buffer = b''

    @property
    def pending(self) -> bool:
        """True while an incomplete sequence waits for more bytes."""
        return bool(self._buffer)

    def feed(self, data: bytes) -> list[Event]:
        """Consume ``data`` and return every event it completed."""
        self._buffer += bytes(data)
        events: list[Event] = []
        while self._buffer:
            event, consumed = self._parse_one(self._buffer)
            if consumed == 0:
                break  # incomplete: wait for the next feed
            self._buffer = self._buffer[consumed:]
            if event is not None:
                events.append(event)
        return events

    def flush(self) -> list[Event]:
        """Resolve what a 30 ms silence means: a lone ESC is the Escape key."""
        buffer, self._buffer = self._buffer, b''
        if buffer == b'\x1b':
            return [Key('escape')]
        return []

    # -- one event --------------------------------------------------------
    def _parse_one(self, buffer: bytes) -> tuple[Event | None, int]:
        first = buffer[0]

        if first == ESC:
            return self._parse_escape(buffer)
        if first in (0x0d, 0x0a):
            return Key('enter'), 1
        if first == 0x09:
            return Key('tab'), 1
        if first in (0x08, 0x7f):
            return Key('backspace'), 1
        if 0x01 <= first <= 0x1A:
            # Control letters: 0x01 is Ctrl+A, 0x1a is Ctrl+Z.
            return Key(chr(0x60 + first), ctrl=True), 1
        if first < 0x20:
            return None, 1  # other control bytes carry no meaning here

        length = _utf8_length(first)
        if len(buffer) < length:
            return None, 0
        chunk = buffer[:length]
        return Key('char', char=_decode(chunk)), length

    def _parse_escape(self, buffer: bytes) -> tuple[Event | None, int]:
        if len(buffer) == 1:
            return None, 0  # a lone ESC is only settled by flush()
        second = buffer[1]

        if second == 0x1b:  # ESC ESC: one escape now, the next one waits again
            return Key('escape'), 1
        if second == ord('['):
            return self._parse_csi(buffer)
        if second == ord('O'):
            if len(buffer) < 3:
                return None, 0
            name = _SS3_FINALS.get(chr(buffer[2]))
            return (Key(name) if name else None), 3
        if second < 0x20:
            # ESC before a control byte: the escape ended early.
            return Key('escape'), 1

        length = _utf8_length(second)
        if len(buffer) < 1 + length:
            return None, 0
        char = _decode(buffer[1:1 + length])
        return Key('char', char=char, alt=True), 1 + length

    # -- CSI --------------------------------------------------------------
    def _parse_csi(self, buffer: bytes) -> tuple[Event | None, int]:
        if buffer.startswith(b'\x1b[200~'):
            return self._parse_paste(buffer)

        index = 2
        while index < len(buffer) and not 0x40 <= buffer[index] <= 0x7E:
            index += 1
        if index >= len(buffer):
            return None, 0  # parameters still arriving
        final = chr(buffer[index])
        parameters = buffer[2:index].decode('ascii', errors='replace')
        consumed = index + 1

        if final in ('M', 'm') and parameters.startswith('<'):
            return self._parse_mouse(parameters[1:], final), consumed
        if final == '~':
            name = _CSI_TILDE.get(_first_number(parameters))
            return (Key(name) if name else None), consumed
        name = _CSI_FINALS.get(final)
        return (Key(name) if name else None), consumed

    def _parse_mouse(self, parameters: str, final: str) -> Mouse | None:
        parts = parameters.split(';')
        if len(parts) != 3:
            return None
        try:
            bits, x, y = (int(part) for part in parts)
        except ValueError:
            return None
        if bits & 64:  # wheel
            kind = 'wheelup' if not bits & 1 else 'wheeldown'
            return Mouse(kind, 0, x - 1, y - 1)
        if bits & 32:  # motion with a button held
            return Mouse('drag', bits & 3, x - 1, y - 1)
        if final == 'm':
            return Mouse('release', bits & 3, x - 1, y - 1)
        return Mouse('press', bits & 3, x - 1, y - 1)

    def _parse_paste(self, buffer: bytes) -> tuple[Event | None, int]:
        start = len(b'\x1b[200~')
        end = buffer.find(_PASTE_END, start)
        if end < 0:
            return None, 0  # paste body still arriving
        return Paste(_decode(buffer[start:end])), end + len(_PASTE_END)


def _first_number(parameters: str) -> int:
    head = parameters.split(';', 1)[0]
    try:
        return int(head)
    except ValueError:
        return 0

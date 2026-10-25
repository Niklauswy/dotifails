"""What the embedding application lends the player: theme, symbols and motion preference.

The package never imports a host module. Wysun apps and Recorder each install
an adapter built from their own theme runtime, so the same widgets follow
either one (and the immutable Recorder release stays self-contained).
"""
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Host:
    color: Callable[..., Any]            # (token, alpha=None) -> QColor
    token: Callable[[str], Any]          # (name) -> value of a shape/space/motion/font token
    font: Callable[..., Any]             # (role, weight=400) -> QFont
    symbol: Callable[..., None]          # (painter, rect, ligature, tint, size, filled=False)
    reduced_motion: Callable[[], bool]
    on_theme_changed: Callable[[Callable[[], None]], Any]


_host = None


def install(host):
    global _host
    _host = host


def get():
    if _host is None:
        raise RuntimeError('wysun_media.install_host() debe llamarse antes de crear widgets')
    return _host


def installed():
    return _host is not None

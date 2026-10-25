"""Connects the shared wysun_media player to Recorder's theme runtime, fonts and motion preference."""
from PySide6.QtGui import QFont

import wysun_media
from wysun_media import symbols

from . import motion, tokens
from .material import load_fonts


def _font(role, weight=400):
    font = QFont(tokens.family())
    font.setPixelSize(int(tokens.tokens()['font_' + role]))
    font.setWeight(QFont.Weight(int(weight)))
    return font


def _symbol(painter, rect, name, tint, size, filled=False):
    ink = tokens.color(tint) if isinstance(tint, str) else tint
    symbols.paint(painter, rect, name, ink, size, filled)


def install():
    """Idempotent; call once after the QApplication exists."""
    from wysun_media import host
    if host.installed():
        return
    load_fonts()
    wysun_media.install_host(wysun_media.Host(
        color=lambda name, alpha=None: tokens.color(name, alpha),
        token=lambda name: tokens.tokens()[name],
        font=_font,
        symbol=_symbol,
        reduced_motion=motion.reduced_motion,
        on_theme_changed=tokens.on_theme_changed))

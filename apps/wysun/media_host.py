"""Connects wysun_media to the Wysun theme runtime, symbols and motion preference."""
import wysun_media
from ui_motion import reduced_motion
from theme_tokens import color, on_theme_changed, tokens
from music_material import load_fonts
from wysun_music.ui.style import paint_symbol, text_font


def install():
    """Idempotent: apps call this once after creating their QApplication."""
    from wysun_media import host
    if host.installed():
        return
    load_fonts()          # the symbols are ligatures of the packaged Material Symbols font
    wysun_media.install_host(wysun_media.Host(
        color=lambda name, alpha=None: color(name, alpha),
        token=lambda name: tokens()[name],
        font=lambda role, weight=400: text_font(role, weight),
        symbol=paint_symbol,
        reduced_motion=reduced_motion,
        on_theme_changed=on_theme_changed))

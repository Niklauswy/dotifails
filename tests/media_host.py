"""The Wysun host (theme, symbols, motion) for wysun_media's widget player in tests and tools; no side effects."""


def install_host():
    """The Wysun theme, symbols and motion for wysun_media's widget player (the Recorder's embedded preview; Wysun
    Player itself is QML). Idempotent."""
    import wysun_media
    from wysun_media import host
    if host.installed():
        return
    from wysun_core import icons  # noqa: F401  (registers the Lucide fallback for symbols the font lacks)
    from wysun_core.qt_theme import color, on_theme_changed, tokens
    from wysun_core.ui.fonts import load_fonts
    from wysun_core.ui.motion import reduced_motion
    from wysun_core.ui.style import paint_symbol, text_font
    load_fonts()
    wysun_media.install_host(wysun_media.Host(
        color=lambda name, alpha=None: color(name, alpha), token=lambda name: tokens()[name],
        font=lambda role, weight=None: text_font(role, weight), symbol=paint_symbol, reduced_motion=reduced_motion,
        on_theme_changed=on_theme_changed))

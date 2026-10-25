"""The reader's one theme choice of its own: the sun/moon menu, a thin layer over wysun_core.qt_theme.

Until a mode is pinned the reader follows the desktop like every Wysun app. A pinned mode equal to the
desktop's changes nothing (the wallpaper's colours stay). A pinned mode different from the desktop's sets
``WYSUN_THEME`` (the theme's existing base-palette switch) in this process only and repaints, so the kit
widgets need no reader-specific colours. Programs the reader launches get the original environment.
"""
import os

from wysun_core import qt_theme, theme

MODES = ('light', 'dark')
# Every Material symbol the reader paints; tests check the bundled font has them all.
SYMBOLS = ('close', 'left_panel_open', 'left_panel_close', 'search', 'keyboard_arrow_up', 'keyboard_arrow_down',
           'remove', 'add', 'fit_width', 'fit_screen', 'view_agenda', 'auto_stories', 'menu_book', 'edit_note',
           'sticky_note_2', 'save', 'more_vert', 'folder_open', 'content_copy', 'ink_highlighter',
           'format_underlined', 'palette', 'toc', 'grid_view', 'delete', 'light_mode', 'dark_mode',
           'brightness_auto', 'open_in_new', 'keyboard', 'check', 'description')


class ReaderMode:
    def __init__(self, preferences):
        self.preferences = preferences
        self.original = os.environ.get('WYSUN_THEME')
        self._applying = False
        qt_theme.on_theme_changed(self.apply)
        self.apply()

    @property
    def pinned(self):
        value = self.preferences.get('mode')
        return value if value in MODES else None

    def desktop_mode(self):
        return theme.active_mode(environ={'WYSUN_THEME': self.original} if self.original else {})

    @property
    def mode(self):
        return self.pinned or self.desktop_mode()

    def set(self, mode):
        """Pin 'light' or 'dark', or None to follow the desktop again; saved for the next launch."""
        self.preferences.set(mode=mode if mode in MODES else None)
        self.apply()

    def environment(self):
        """os.environ as the reader received it, for the programs it launches."""
        result = dict(os.environ)
        result.pop('WYSUN_THEME', None)
        if self.original is not None:
            result['WYSUN_THEME'] = self.original
        return result

    def _set_environment(self, value):
        if value is None:
            os.environ.pop('WYSUN_THEME', None)
        else:
            os.environ['WYSUN_THEME'] = value

    def apply(self):
        if self._applying:
            return
        pinned = self.pinned
        target = pinned if pinned and pinned != self.desktop_mode() else self.original
        if os.environ.get('WYSUN_THEME') == target:
            return
        self._set_environment(target)
        self._applying = True
        try:
            qt_theme.refresh_widgets()
        finally:
            self._applying = False

    def release(self):
        """Give the process its original environment back (tests, last window closed)."""
        self._set_environment(self.original)
        qt_theme.invalidate()

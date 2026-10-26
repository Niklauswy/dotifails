"""Feeds the QML ``Theme`` (WysunM3) from scheme.json, theme.json, tokens.json and appearance.json, live.

QML side::

    ThemeFeed { scheme: bridge.scheme; tokens: bridge.tokens; reducedMotion: bridge.reducedMotion }

The scheme is always complete (``wysun_core.theme.active_scheme``): the wallpaper's Material roles, or the base
palette of the active mode while ``scheme.json`` is missing or broken. Atomic replacement and late creation of the
files are followed the way ``wysun_core.qt_theme.watch_theme`` does for the Widgets apps.
"""
import copy

from . import bootstrap

bootstrap.preload_qt()                    # PySide6 must find the runtime's Qt already loaded

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QTimer, Signal, Slot

from wysun_core import appearance, theme

TOKEN_GROUPS = ('rounding', 'spacing', 'padding', 'font', 'anim', 'border', 'icon')


def load_tokens():
    """The shape/type/motion tokens plus each mode's base scheme (the fallback for roles a scheme lacks)."""
    data = theme.data()
    tokens = {group: copy.deepcopy(data[group]) for group in TOKEN_GROUPS if group in data}
    tokens['palettes'] = {mode: {'scheme': dict(data['palettes'][mode]['scheme'])} for mode in ('light', 'dark')}
    return tokens


def valid_scheme(value):
    colours = value.get('colours') if isinstance(value, dict) else None
    return (isinstance(colours, dict) and bool(colours) and value.get('mode') in ('light', 'dark')
            and all(isinstance(k, str) and isinstance(v, str) for k, v in colours.items()))


class ThemeBridge(QObject):
    schemeChanged = Signal()
    tokensChanged = Signal()
    reducedMotionChanged = Signal()

    def __init__(self, home=None, parent=None):
        super().__init__(parent)
        self._home = home
        self._preview = None
        self._preview_tokens = None
        self._reduced_override = None
        self._base_tokens = load_tokens()
        self._scheme = self._compute_scheme()
        self._reduced = self._compute_reduced()
        self._revision = theme.revision(home)
        self._watcher = QFileSystemWatcher(self)
        self._timer = QTimer(self, singleShot=True, interval=40)
        self._watcher.fileChanged.connect(self._timer.start)
        self._watcher.directoryChanged.connect(self._timer.start)
        self._timer.timeout.connect(self.reload)
        self._arm()

    # -- values --------------------------------------------------------------------------------------------
    def _compute_scheme(self):
        return self._preview if self._preview is not None else theme.active_scheme(self._home)

    def _compute_reduced(self):
        if self._reduced_override is not None:
            return self._reduced_override
        return bool(appearance.reduced_motion(self._home))

    def _get_scheme(self):
        return self._scheme

    def _get_tokens(self):
        return self._preview_tokens if self._preview_tokens is not None else self._base_tokens

    def _get_reduced(self):
        return self._reduced

    scheme = Property('QVariantMap', _get_scheme, notify=schemeChanged)
    tokens = Property('QVariantMap', _get_tokens, notify=tokensChanged)
    reducedMotion = Property(bool, _get_reduced, notify=reducedMotionChanged)

    # -- following the files -------------------------------------------------------------------------------
    def _targets(self):
        for path in (theme.selection_path(self._home), theme.scheme_path(self._home),
                     appearance.preference_path(self._home)):
            if path.exists():
                yield str(path)
            parent = path.parent
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            yield str(parent)

    def _arm(self):
        targets = set(self._targets())
        current = set(self._watcher.files() + self._watcher.directories())
        if current - targets:
            self._watcher.removePaths(list(current - targets))
        if targets - current:
            self._watcher.addPaths(list(targets - current))

    @Slot()
    def reload(self):
        """Re-read the files and emit what changed (also called by the debounced watcher)."""
        self._arm()
        theme.invalidate()
        appearance.invalidate()
        revision = theme.revision(self._home)
        if revision != self._revision:
            self._revision = revision
            self._refresh_scheme()
        reduced = self._compute_reduced()
        if reduced != self._reduced:
            self._reduced = reduced
            self.reducedMotionChanged.emit()

    def _refresh_scheme(self):
        scheme = self._compute_scheme()
        if scheme != self._scheme:
            self._scheme = scheme
            self.schemeChanged.emit()

    # -- overrides (previews, tests, the gallery) ----------------------------------------------------------
    @Slot('QVariant')
    def setPreview(self, scheme):
        """Show this ``{'mode', 'colours'}`` instead of the files' scheme; ``None`` goes back to the files."""
        self._preview = scheme if valid_scheme(scheme) else None
        self._refresh_scheme()

    @Slot('QVariant')
    def setPreviewTokens(self, tokens):
        self._preview_tokens = tokens if isinstance(tokens, dict) else None
        self.tokensChanged.emit()

    @Slot('QVariant')
    def setReducedMotion(self, value):
        """Force reduced motion on/off (``None`` follows appearance.json / WYSUN_REDUCED_MOTION)."""
        self._reduced_override = None if value is None else bool(value)
        reduced = self._compute_reduced()
        if reduced != self._reduced:
            self._reduced = reduced
            self.reducedMotionChanged.emit()

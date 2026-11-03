"""Real icons and names for the apps Wysun Processes shows: the app id of a process (its systemd scope or its
window class) is matched with an installed .desktop file, its Icon is looked up in the icon theme, and a tint is
taken from the icon's dominant saturated colour (mixed with the Material You roles in QML)."""
import configparser
import os
from pathlib import Path
import subprocess

SIZES = ('scalable', '512x512', '256x256', '128x128', '96x96', '64x64', '48x48', '32x32')
FALLBACK = 'application-x-executable'


def data_dirs():
    from wysun_core.paths import data_home
    return [data_home()] + [Path(d) for d in (os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share').split(':') if d]


def icon_theme():
    try:
        name = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.interface', 'icon-theme'], capture_output=True,
                              text=True, timeout=1).stdout.strip().strip("'")
    except (OSError, subprocess.SubprocessError):
        name = ''
    return name


class Catalog:
    def __init__(self, dirs=None, theme=None):
        self.dirs = dirs or data_dirs()
        self.themes = [t for t in (theme if theme is not None else icon_theme(), 'hicolor', 'Adwaita') if t]
        self._entries = None
        self._icons = {}
        self._tints = {}

    def _load(self):
        self._entries = {}
        for folder in reversed(self.dirs):
            for path in (folder / 'applications').glob('*.desktop'):
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                try:
                    parser.read(path, encoding='utf-8')
                    entry = parser['Desktop Entry']
                except (configparser.Error, KeyError, UnicodeDecodeError):
                    continue
                if entry.get('NoDisplay', 'false').lower() == 'true' and entry.get('StartupWMClass') is None:
                    continue
                data = dict(name=entry.get('Name', path.stem), icon=entry.get('Icon', ''), desktop=path.stem)
                aliases = {path.stem.lower(), path.stem.rsplit('.', 1)[-1].lower()}
                if entry.get('StartupWMClass'):
                    aliases.add(entry['StartupWMClass'].lower())
                exe = (entry.get('Exec') or '').split()
                if exe:
                    aliases.add(os.path.basename(exe[0]).lower())
                    if exe[0] == 'wysun' and len(exe) > 1:
                        aliases.add('wysun-' + exe[1].lower())
                for alias in aliases:
                    self._entries[alias] = data

    def entry(self, app_id):
        if self._entries is None:
            self._load()
        key = (app_id or '').lower()
        return self._entries.get(key) or self._entries.get(key.rsplit('.', 1)[-1])

    def name(self, app_id):
        entry = self.entry(app_id)
        if entry:
            return entry['name']
        base = (app_id or '').rsplit('.', 1)[-1] if '.' in (app_id or '') and ' ' not in app_id else (app_id or '')
        return base[:1].upper() + base[1:] if '.' in (app_id or '') else (app_id or '')

    def _find(self, icon):
        if not icon:
            return ''
        if os.path.isabs(icon):
            return icon if os.path.exists(icon) else ''
        for theme in self.themes:
            for folder in self.dirs + [Path.home() / '.icons']:
                base = folder / 'icons' / theme if folder != Path.home() / '.icons' else folder / theme
                if not base.is_dir():
                    continue
                for size in SIZES:
                    for sub in ('apps', ''):
                        for ext in ('.svg', '.png'):
                            for candidate in (base / size / sub / (icon + ext), base / sub / size / (icon + ext)):
                                if candidate.is_file():
                                    return str(candidate)
        for folder in self.dirs:
            for ext in ('.svg', '.png', '.xpm'):
                candidate = folder / 'pixmaps' / (icon + ext)
                if candidate.is_file():
                    return str(candidate)
        return ''

    def icon(self, app_id):
        """Absolute path of the app's icon, '' when none is installed."""
        if app_id not in self._icons:
            entry = self.entry(app_id)
            self._icons[app_id] = self._find(entry['icon'] if entry else app_id) or self._find((app_id or '').lower())
        return self._icons[app_id]

    def tint(self, app_id):
        """Dominant saturated colour of the icon as '#rrggbb', '' without an icon (theme-exception: tinte derivado
        del icono). Needs a QGuiApplication."""
        if app_id in self._tints:
            return self._tints[app_id]
        path = self.icon(app_id)
        colour = ''
        if path:
            from PySide6.QtGui import QColor, QImage
            image = QImage(path)
            if not image.isNull():
                image = image.scaled(32, 32)
                buckets = {}
                for y in range(image.height()):
                    for x in range(image.width()):
                        c = QColor.fromRgba(image.pixel(x, y))
                        hue, sat, val, alpha = c.hsvHueF(), c.hsvSaturationF(), c.valueF(), c.alphaF()
                        if alpha < 0.5 or sat < 0.25 or val < 0.2 or hue < 0:
                            continue
                        b = int(hue * 24) % 24
                        w, h, s, v = buckets.get(b, (0, 0, 0, 0))
                        weight = sat * val * alpha
                        buckets[b] = (w + weight, h + hue * weight, s + sat * weight, v + val * weight)
                if buckets:
                    w, h, s, v = max(buckets.values(), key=lambda t: t[0])
                    colour = QColor.fromHsvF(h / w, min(1, s / w), min(1, v / w)).name()
        self._tints[app_id] = colour
        return colour

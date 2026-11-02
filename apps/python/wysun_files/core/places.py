"""The places of the Files navigation: favourites, bookmarks, devices (with disk usage) and the trash, as plain
data (the same rules as the Widgets sidebar had)."""
import shutil
from pathlib import Path

from wysun_files.core.listing import size_text


SYSTEM_FS = {'tmpfs', 'devtmpfs', 'overlay', 'squashfs', 'proc', 'sysfs', 'cgroup2', 'efivarfs', 'ramfs'}
# (title, QStandardPaths location name or None for home, Material symbol)
LOCATIONS = (('Inicio', None, 'home'), ('Escritorio', 'DesktopLocation', 'desktop_windows'),
             ('Descargas', 'DownloadLocation', 'download'), ('Documentos', 'DocumentsLocation', 'description'),
             ('Imágenes', 'PicturesLocation', 'photo_library'), ('Vídeos', 'MoviesLocation', 'video_library'),
             ('Música', 'MusicLocation', 'library_music'))
TRASH = Path.home() / '.local/share/Trash/files'


def favourites():
    from PySide6.QtCore import QStandardPaths
    home = str(Path.home())
    out = []
    for title, location, symbol in LOCATIONS:
        path = home if location is None else QStandardPaths.writableLocation(getattr(QStandardPaths, location))
        if path and Path(path).is_dir() and (location is None or path != home):
            out.append({'path': path, 'label': title, 'icon': symbol})
    return out


def usage(path):
    """``(used fraction, «N libres»)``, or ``(0, '')`` when the disk cannot be read."""
    try:
        disk = shutil.disk_usage(path)
        return (disk.used / disk.total if disk.total else 0.0), f'{size_text(disk.free)} libres'
    except OSError:
        return 0.0, ''


def devices():
    """The system disk, then mounted volumes worth showing (removable media and other real disks)."""
    from PySide6.QtCore import QStorageInfo
    out = [{'path': '/', 'label': 'Sistema', 'icon': 'hard_drive', 'removable': False}]
    seen = {'/'}
    for volume in QStorageInfo.mountedVolumes():
        root = volume.rootPath()
        fs = bytes(volume.fileSystemType()).decode(errors='ignore')
        device = bytes(volume.device()).decode(errors='ignore')
        removable = root.startswith(('/run/media', '/media', '/mnt'))
        if (not volume.isValid() or not volume.isReady() or root in seen or fs in SYSTEM_FS or Path(root).name.startswith('.')
                or not (removable or device.startswith('/dev/') and not root.startswith(('/home', '/boot', '/var', '/tmp', '/snap', '/run')))):
            continue
        seen.add(root)
        name = volume.displayName() if volume.displayName() != root else Path(root).name or root
        out.append({'path': root, 'label': name, 'icon': 'usb' if removable else 'storage', 'removable': removable, 'device': device})
    return out


def most_specific(path, targets):
    """The target that contains ``path`` most closely (the place to highlight), or ''."""
    best = ''
    for target in targets:
        inside = path == target or (target != '/' and path.startswith(target.rstrip('/') + '/')) or target == '/'
        if inside and len(target) > len(best):
            best = target
    return best

"""Places column: favourites, bookmarks and devices on the window material."""
import shutil
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QRect, QRectF, QStandardPaths, QStorageInfo, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from file_media import human_size
from theme_tokens import color
from wysun_music.ui.sidebar import NavItem, section_label
from ui_motion import reduced_motion
from .kit import IconButton, metric, paint_symbol, text_font

SYSTEM_FS = {'tmpfs', 'devtmpfs', 'overlay', 'squashfs', 'proc', 'sysfs', 'cgroup2', 'efivarfs', 'ramfs'}
LOCATIONS = (('Inicio', None, 'home'),
             ('Escritorio', QStandardPaths.DesktopLocation, 'desktop_windows'),
             ('Descargas', QStandardPaths.DownloadLocation, 'download'),
             ('Documentos', QStandardPaths.DocumentsLocation, 'description'),
             ('Imágenes', QStandardPaths.PicturesLocation, 'photo_library'),
             ('Vídeos', QStandardPaths.MoviesLocation, 'video_library'),
             ('Música', QStandardPaths.MusicLocation, 'library_music'))


class PlaceItem(NavItem):
    """Row without its own selection background: the sidebar's gliding indicator sits behind it."""

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        if self.layer.amount and not self.active:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('tint', round(12 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        pad = metric('space_m')
        paint_symbol(painter, QRect(pad - 4, 0, 28, self.height()), self.symbol, 'accent' if self.active else 'glyph', 21,
                     filled=self.active and self.symbol not in ('delete',))
        left = pad + 24 + metric('space_s')
        painter.setFont(text_font('body', 600 if self.active else 450))
        painter.setPen(color('text_strong' if self.active else 'text'))
        painter.drawText(QRect(left, 0, self.width() - left - pad, self.height()), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self.label, Qt.ElideRight, self.width() - left - pad))
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(color('focus'))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)


class Rail(QWidget):
    """Scroll content that paints the selection pill behind the rows and glides it between them."""

    def __init__(self):
        super().__init__()
        self.pill = QRectF()
        self.anim = QVariantAnimation(self, duration=tokens_motion())
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self._step)
        self._from = self._to = QRectF()

    def glide(self, target, animate=True):
        self.anim.stop()
        if target is None:
            self.pill = QRectF()
            self.update()
            return
        if self.pill.isNull() or not animate or reduced_motion(self.window()) or not self.isVisible():
            self.pill = QRectF(target)
            self.update()
            return
        self._from, self._to = QRectF(self.pill), QRectF(target)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def _step(self, t):
        t = float(t)
        a, b = self._from, self._to
        self.pill = QRectF(a.left() + (b.left() - a.left()) * t, a.top() + (b.top() - a.top()) * t,
                           a.width() + (b.width() - a.width()) * t, a.height() + (b.height() - a.height()) * t)
        self.update()

    def paintEvent(self, _event):
        if self.pill.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('nav_selected'))
        painter.drawRoundedRect(self.pill, min(22, self.pill.height() / 2), min(22, self.pill.height() / 2))


def tokens_motion():
    from theme_tokens import tokens
    return tokens()['motion_enter'] + 60


class DeviceItem(NavItem):
    """Device row: symbol, name and a usage meter."""

    def __init__(self, symbol, label, path, parent=None):
        super().__init__(symbol, label, parent)
        self.path = path
        self.used = 0.0
        self.caption = ''
        self.setFixedHeight(52)
        self.refresh()

    def refresh(self):
        try:
            usage = shutil.disk_usage(self.path)
            self.used = usage.used / usage.total if usage.total else 0.0
            self.caption = f'{human_size(usage.free)} libres'
        except OSError:
            self.used, self.caption = 0.0, ''
        self.setToolTip(f'{self.label} · {self.caption}' if self.caption else self.label)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = 22
        if self.layer.amount and not self.active:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('tint', round(12 * self.layer.amount)))
            painter.drawRoundedRect(rect, radius, radius)
        pad = metric('space_m')
        paint_symbol(painter, QRect(pad - 4, 0, 28, self.height() - 8), self.symbol, 'accent' if self.active else 'glyph', 21, filled=True)
        left = pad + 24 + metric('space_s')
        painter.setFont(text_font('body', 600 if self.active else 450))
        painter.setPen(color('text_strong' if self.active else 'text'))
        painter.drawText(QRect(left, 7, self.width() - left - pad, 20), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self.label, Qt.ElideRight, self.width() - left - pad))
        track = QRectF(left, 31, self.width() - left - pad, 5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('track'))
        painter.drawRoundedRect(track, 2.5, 2.5)
        if self.used:
            painter.setBrush(color('danger' if self.used > .92 else 'accent'))
            painter.drawRoundedRect(QRectF(track.left(), track.top(), max(5, track.width() * self.used), 5), 2.5, 2.5)
        painter.setFont(text_font('caption', 400))
        painter.setPen(color('muted'))
        painter.drawText(QRect(left, 36, self.width() - left - pad, 14), Qt.AlignLeft | Qt.AlignVCenter, self.caption)
        if self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(color('focus'))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)


class Sidebar(QWidget):
    navigate = Signal(str)
    bookmark_menu = Signal(str, object)     # path, global position
    remove_bookmark = Signal(str)

    def __init__(self, bookmarks, parent=None):
        super().__init__(parent)
        self.bookmarks = list(bookmarks)
        self.items = []
        self.current = ''
        layout = QVBoxLayout(self)
        layout.setContentsMargins(metric('space_xs'), 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = self.rail = Rail()
        self.column = QVBoxLayout(content)
        self.column.setContentsMargins(0, 0, metric('space_xs'), metric('space_m'))
        self.column.setSpacing(1)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.timer = QTimer(self, interval=20000)
        self.timer.timeout.connect(self._refresh_usage)
        self.timer.start()
        self.rebuild()

    def _add(self, item, path):
        item.target = path
        item.clicked.connect(lambda path=path: self.navigate.emit(path))
        self.items.append(item)
        self.column.addWidget(item)
        return item

    def rebuild(self):
        while self.column.count():
            entry = self.column.takeAt(0)
            if entry.widget():
                entry.widget().deleteLater()
        self.items = []
        self.column.addWidget(section_label('Favoritos'))
        for title, location, symbol in LOCATIONS:
            path = str(Path.home()) if location is None else QStandardPaths.writableLocation(location)
            if path and Path(path).is_dir() and (location is None or path != str(Path.home())):
                self._add(PlaceItem(symbol, title), path)
        if self.bookmarks:
            self.column.addWidget(section_label('Marcadores'))
            for path in self.bookmarks:
                item = self._add(PlaceItem('bookmark', Path(path).name or path), path)
                item.setToolTip(path)
                item.menu_requested.connect(lambda position, path=path: self.bookmark_menu.emit(path, position))
        self.column.addWidget(section_label('Dispositivos'))
        self._add(DeviceItem('hard_drive', 'Sistema', '/'), '/')
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
            self._add(DeviceItem('usb' if root.startswith(('/run/media', '/media', '/mnt')) else 'storage', name, root), root)
        trash = Path.home() / '.local/share/Trash/files'
        if trash.is_dir():
            self.column.addWidget(section_label('Papelera'))
            self._add(PlaceItem('delete', 'Papelera'), str(trash))
        self.column.addStretch()
        self.rail.pill = QRectF()
        self.set_current(self.current)

    def set_bookmarks(self, bookmarks):
        self.bookmarks = list(bookmarks)
        self.rebuild()

    def set_current(self, path):
        self.current = path
        best, size = None, -1
        for item in self.items:
            target = item.target
            inside = path == target or (target != '/' and path.startswith(target.rstrip('/') + '/'))
            # Highlight the most specific place that contains the folder, not every ancestor.
            if inside and len(target) > size:
                best, size = item, len(target)
        for item in self.items:
            item.set_active(item is best)
        self.active_item = best
        QTimer.singleShot(0, self, self._glide)

    def _glide(self, animate=True):
        item = getattr(self, 'active_item', None)
        if item is None or not item.isVisible():
            self.rail.glide(None)
            return
        self.rail.glide(QRectF(item.geometry()), animate)

    def _refresh_usage(self):
        for item in self.items:
            if isinstance(item, DeviceItem):
                item.refresh()

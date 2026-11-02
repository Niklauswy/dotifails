"""The places of the Files navigation for QML (F-10, F-11): destinations for AdaptiveNavigation (favourites,
bookmarks, devices with their free space refreshed every 20 s and eject for removable media, the trash) and the
place that holds a folder. Bookmarks persist in QSettings('Wysun', 'Files') under ``bookmarks``, as before."""
import os
from pathlib import Path
import shutil

from PySide6.QtCore import Property, QObject, QProcess, QSettings, QTimer, Signal, Slot

from wysun_files.core import places

RAIL = {'Inicio': 0, 'Descargas': 1, 'Documentos': 2, 'Imágenes': 3}
REFRESH_MS = 20_000


def _run(argv, done):
    """Run ``argv`` without blocking; ``done(exit code, error text)`` (127 when it could not start)."""
    process = QProcess()
    process.setProgram(argv[0])
    process.setArguments(argv[1:])

    def finished(code, _status):
        done(code, bytes(process.readAllStandardError()).decode(errors='replace').strip())
        process.deleteLater()

    def failed(error):
        if error == QProcess.FailedToStart:
            done(127, f'{argv[0]} no está disponible')
            process.deleteLater()

    process.finished.connect(finished)
    process.errorOccurred.connect(failed)
    _run.alive.add(process)                      # keep it until it ends
    process.destroyed.connect(lambda *_: _run.alive.discard(process))
    process.start()


_run.alive = set()


class Places(QObject):
    changed = Signal()
    message = Signal(str)

    def __init__(self, settings=None, run=None, parent=None):
        super().__init__(parent)
        self.settings = settings if settings is not None else QSettings('Wysun', 'Files')
        self.run = run or _run
        value = self.settings.value('bookmarks', [])
        self._bookmarks = [str(v) for v in (value if isinstance(value, list) else [value] if value else [])]
        self._favourites = places.favourites()
        self._devices = []
        self._load_devices()
        self.refresher = QTimer(self, interval=REFRESH_MS)
        self.refresher.timeout.connect(self.refresh)
        self.refresher.start()

    def _load_devices(self):
        devices = []
        for device in places.devices():
            fraction, free = places.usage(device['path'])
            devices.append(dict(device, progress=round(fraction, 3), free=free))
        self._devices = devices

    @Slot()
    def refresh(self):
        before = self._devices
        self._load_devices()
        if self._devices != before:
            self.changed.emit()

    # ---------------------------------------------------------------- destinations
    def _favourite_paths(self):
        return {p['path'] for p in self._favourites}

    def _shown_bookmarks(self):
        favourites = self._favourite_paths()
        return [b for b in self._bookmarks if b not in favourites]

    def _targets(self):
        return ([p['path'] for p in self._favourites] + self._shown_bookmarks() + [d['path'] for d in self._devices]
                + [str(places.TRASH)])

    @Property('QVariantList', notify=changed)
    def destinations(self):
        out = [{'header': 'Favoritos'}]
        for place in self._favourites:
            entry = {'id': place['path'], 'icon': place['icon'], 'label': place['label']}
            if place['label'] in RAIL:
                entry['railOrder'] = RAIL[place['label']]
                if place['label'] == 'Documentos':
                    entry['railLabel'] = 'Docs'
            else:
                entry['rail'] = False
            out.append(entry)
        bookmarks = self._shown_bookmarks()
        if bookmarks:
            out.append({'header': 'Marcadores'})
            out.extend({'id': path, 'icon': 'bookmark', 'label': os.path.basename(path.rstrip('/')) or path, 'rail': False}
                       for path in bookmarks)
        out.append({'header': 'Dispositivos'})
        for device in self._devices:
            entry = {'id': device['path'], 'icon': device['icon'], 'label': device['label'], 'rail': False,
                     'progress': device['progress'], 'trailing': device['free'].removesuffix(' libres')}
            if device.get('removable'):
                entry.update(trailingAction='eject', trailingActionLabel='Expulsar')
            out.append(entry)
        out.append({'divider': True})
        out.append({'id': str(places.TRASH), 'icon': 'delete', 'label': 'Papelera', 'railOrder': 9})
        return out

    @Slot(str, result=str)
    def placeOf(self, path):
        """The destination that holds ``path`` most closely ('' when none does)."""
        return places.most_specific(path, self._targets())

    @Property(str, constant=True)
    def trash(self):
        return str(places.TRASH)

    # ---------------------------------------------------------------- bookmarks
    @Slot(str, result=bool)
    def isBookmark(self, path):
        return path in self._bookmarks

    @Slot(str, result=bool)
    def toggleBookmark(self, path):
        """Add or remove a bookmark; True when it is now a bookmark."""
        if path in self._bookmarks:
            self._bookmarks.remove(path)
            added = False
        else:
            self._bookmarks.append(path)
            added = True
        self.settings.setValue('bookmarks', list(self._bookmarks))
        self.changed.emit()
        return added

    # ---------------------------------------------------------------- devices
    @Slot(str)
    def eject(self, path):
        device = next((d for d in self._devices if d['path'] == path and d.get('removable')), None)
        if device is None:
            return
        name = device['label']

        def done(code, error):
            if code == 127 and device.get('device') and shutil.which('udisksctl'):
                self.run(['udisksctl', 'unmount', '-b', device['device']], done)
                return
            if code == 0:
                self.message.emit(f'{name} se puede retirar')
                self.refresh()
            else:
                self.message.emit(f'No se pudo expulsar {name}: {error or "el dispositivo está en uso"}')

        self.run(['gio', 'mount', '-u', path], done)

    @Slot()
    def close(self):
        self.refresher.stop()

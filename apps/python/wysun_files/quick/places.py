"""The places of the Files navigation for QML: destinations for AdaptiveNavigation (favourites, bookmarks, devices
with their free space, the trash) and which one holds a folder. Task 4 of the plan fills bookmarks and devices."""
import os

from PySide6.QtCore import Property, QObject, Signal, Slot

from wysun_files.core import places

RAIL = {'Inicio': 0, 'Descargas': 1, 'Documentos': 2, 'Imágenes': 3}


class Places(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._favourites = places.favourites()

    def _targets(self):
        return [p['path'] for p in self._favourites] + [str(places.TRASH)]

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

    @Slot(str, result=bool)
    def exists(self, path):
        return os.path.isdir(path)

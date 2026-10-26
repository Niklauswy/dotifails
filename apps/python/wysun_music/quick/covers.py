"""Artwork for QML as file URLs. CoverStore finds or fetches each image (embedded, Spotify, YouTube, Wikimedia);
QML loads the file itself, so no image provider is needed. ``revision`` rises whenever a new image arrives, which
re-evaluates the bindings that asked for one."""
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot


class CoverUrls(QObject):
    revisionChanged = Signal()

    def __init__(self, covers, parent=None):
        super().__init__(parent)
        self.covers = covers
        self._revision = 0
        covers.updated.connect(self._updated)

    def _updated(self, _key):
        self._revision += 1
        self.revisionChanged.emit()

    @Property(int, notify=revisionChanged)
    def revision(self):
        return self._revision

    @Slot(str, result=str)
    def url(self, key):
        """``file://`` URL of a track's, collection's or ``artist:<name>``'s image, or "" (asked for once)."""
        path = self.covers.path(key) if key else None
        return QUrl.fromLocalFile(path).toString() if path and Path(path).is_file() else ''

    @Slot(str, result='QVariantList')
    def collection(self, collection_id):
        """The collection's own image, else up to four distinct covers of its first songs (a 2×2 mosaic)."""
        own = self.url(collection_id)
        if own:
            return [own]
        collection = self.covers.library.collection(collection_id)
        found = []
        for key in (collection.keys[:12] if collection else []):
            url = self.url(key)
            if url and url not in found:
                found.append(url)
            if len(found) == 4:
                break
        return found if len(found) == 4 else found[:1]

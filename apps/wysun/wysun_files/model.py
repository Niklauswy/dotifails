"""File system model with async thumbnails and Spanish column titles."""
from PySide6.QtCore import QDir, Qt
from PySide6.QtWidgets import QFileSystemModel

from file_media import AUDIO, CODE, IMAGES, VIDEOS, human_size
from files_thumbnails import ThumbnailCache

COLUMNS = ('Nombre', 'Modificado', 'Tamaño', 'Tipo')
NAME, SIZE, KIND, DATE = 0, 1, 2, 3          # QFileSystemModel column ids
ROLE_PATH = Qt.UserRole + 1
DOCUMENTS = {'.pdf', '.doc', '.docx', '.odt', '.rtf', '.txt', '.md', '.rst', '.csv', '.xls', '.xlsx', '.ppt', '.pptx', '.tex'}
KINDS = {'all': None, 'folders': (), 'images': IMAGES, 'videos': VIDEOS, 'audio': AUDIO, 'documents': DOCUMENTS, 'code': CODE}


class FileModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnails = ThumbnailCache(self)
        self.show_thumbnails = True
        self.thumbnails.ready.connect(self._thumbnail_ready)
        self.setReadOnly(True)
        self.setNameFilterDisables(False)

    def _thumbnail_ready(self, path):
        index = self.index(path)
        if index.isValid():
            self.dataChanged.emit(index, index, [Qt.DecorationRole])

    def thumbnail(self, index):
        if not self.show_thumbnails or self.isDir(index):
            return None
        icon = self.thumbnails.get(self.filePath(index))
        return icon.pixmap(160, 160) if icon is not None else None

    def set_hidden(self, enabled):
        self.hidden = enabled
        self._apply()

    def set_kind(self, kind, text=''):
        """Filter by name text and by kind; folders stay visible except under «Carpetas»/«all» rules."""
        self.kind, self.text = kind, text
        self._apply()

    def _apply(self):
        kind, text = getattr(self, 'kind', 'all'), getattr(self, 'text', '')
        flags = QDir.AllEntries | QDir.AllDirs | QDir.NoDotAndDotDot | QDir.System    # AllDirs: name filters never hide folders
        if getattr(self, 'hidden', False):
            flags |= QDir.Hidden
        extensions = KINDS.get(kind)
        if extensions is not None and not extensions:
            flags = QDir.AllDirs | QDir.NoDotAndDotDot | (QDir.Hidden if getattr(self, 'hidden', False) else QDir.Dirs)
        self.setFilter(flags)
        if extensions:
            self.setNameFilters([f'*{text}*{ext}' for ext in sorted(extensions)])
        else:
            self.setNameFilters([f'*{text}*'] if text else [])

    def size_text(self, index):
        return '' if self.isDir(index) else human_size(self.size(index))

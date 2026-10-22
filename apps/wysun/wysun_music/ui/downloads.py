"""Add music: YouTube search, Spotify public links, local files and the download queue."""
import json
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QProcess, QRect, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QScrollArea, QStyle, QStyledItemDelegate,
                               QVBoxLayout, QWidget)

import music_data
from theme_tokens import color, tokens
from .style import metric, songs, stamp, text_font

STATUS = {'pending': 'En cola', 'downloading': 'Descargando', 'error': 'Error', 'review': 'Revisar versión'}
STATUS_TONE = {'pending': 'muted', 'downloading': 'accent', 'error': 'danger', 'review': 'warning'}
AUDIO_FILTER = 'Audio (*.m4a *.opus *.mp3 *.flac *.ogg *.wav *.aac)'


class ImportJob(QThread):
    """Probes tags off the UI thread: a large folder must not freeze the window."""

    done = Signal(int)

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = paths

    def run(self):
        try:
            count = len(music_data.import_files(self.paths))
        except OSError:
            count = 0
        self.done.emit(count)


class TwoLineDelegate(QStyledItemDelegate):
    """Title over a muted detail line; an optional status tone colours the detail."""

    def sizeHint(self, option, index):
        return QSize(200, 56)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(0, 1, 0, -1)
        selected = bool(option.state & QStyle.State_Selected)
        if selected or option.state & QStyle.State_MouseOver:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('row_selected' if selected else 'row_hover'))
            painter.drawRoundedRect(rect, tokens()['radius_s'], tokens()['radius_s'])
        title, _, detail = index.data(Qt.DisplayRole).partition('\n')
        pad = metric('space_m')
        width = rect.width() - 2 * pad
        painter.setFont(text_font('body', 500))
        metrics = painter.fontMetrics()
        painter.setPen(color('text'))
        painter.drawText(QRect(rect.left() + pad, rect.center().y() - metrics.height(), width, metrics.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(title, Qt.ElideRight, width))
        painter.setFont(text_font('small'))
        small = painter.fontMetrics()
        painter.setPen(color(index.data(Qt.UserRole + 2) or 'muted'))
        painter.drawText(QRect(rect.left() + pad, rect.center().y() + 2, width, small.height()),
                         Qt.AlignLeft | Qt.AlignVCenter, small.elidedText(detail, Qt.ElideRight, width))
        painter.restore()


def two_line_list(name):
    widget = QListWidget()
    widget.setItemDelegate(TwoLineDelegate(widget))
    widget.setUniformItemSizes(True)
    widget.setMouseTracking(True)
    widget.setAccessibleName(name)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return widget


def section(title):
    label = QLabel(title)
    label.setFont(text_font('heading', 700, 1.2))
    return label


class DownloadsPage(QScrollArea):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.actions = actions
        self.library = actions.library
        self.metadata = actions.covers.metadata
        self.importer = None
        self.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        pad = metric('space_xl')
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(metric('space_l'))
        title = QLabel('Añadir música')
        title.setFont(text_font('title', 800, 1.3))
        layout.addWidget(title)

        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText('Canción y artista, enlace de YouTube o playlist/álbum público de Spotify')
        self.query.setAccessibleName('Buscar música para descargar')
        self.query.returnPressed.connect(self.search)
        row.addWidget(self.query, 1)
        self.search_button = QPushButton('Buscar')
        self.search_button.setObjectName('primary')
        self.search_button.clicked.connect(self.search)
        row.addWidget(self.search_button)
        layout.addLayout(row)
        self.status = QLabel('Los enlaces de Spotify importan la lista completa y descargan el mejor audio disponible.')
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.results = two_line_list('Resultados de YouTube')
        self.results.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.results.itemDoubleClicked.connect(lambda _: self.enqueue())
        self.results.setMinimumHeight(56 * 5)
        self.results.hide()
        layout.addWidget(self.results)
        self.download_button = QPushButton('Descargar selección')
        self.download_button.setObjectName('primary')
        self.download_button.clicked.connect(self.enqueue)
        self.download_button.hide()
        layout.addWidget(self.download_button, 0, Qt.AlignLeft)

        layout.addWidget(section('Desde este equipo'))
        local = QHBoxLayout()
        for label, callback in (('Importar archivos', self.import_files), ('Importar carpeta', self.import_folder),
                                ('Abrir carpeta de música', self.open_folder)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            local.addWidget(button)
        local.addStretch()
        layout.addLayout(local)

        layout.addWidget(section('Descargas'))
        self.summary = QLabel()
        self.summary.setObjectName('muted')
        layout.addWidget(self.summary)
        controls = QHBoxLayout()
        self.resume_button = QPushButton('Continuar')
        self.resume_button.clicked.connect(self.resume)
        self.pause_button = QPushButton('Pausar cola')
        self.pause_button.clicked.connect(self.pause)
        self.retry_button = QPushButton('Reintentar errores')
        self.retry_button.clicked.connect(self.retry)
        for button in (self.resume_button, self.pause_button, self.retry_button):
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)
        self.queue = two_line_list('Estado de las descargas')
        self.queue.setMinimumHeight(56 * 4)
        layout.addWidget(self.queue, 1)
        self.setWidget(content)

        self.process = QProcess(self)
        self.process.finished.connect(self._search_finished)
        self.process.errorOccurred.connect(lambda _: self._search_failed('No se pudo iniciar la búsqueda.'))
        self.timeout = QTimer(self, singleShot=True, interval=90000)
        self.timeout.timeout.connect(self._search_timeout)
        self.metadata.ready.connect(self._metadata_ready)
        self.library.changed.connect(self.render_queue)
        self.render_queue()

    # ----------------------------------------------------------------- search
    def search(self):
        text = self.query.text().strip()
        if not text or self.process.state() != QProcess.NotRunning:
            return
        if 'open.spotify.com' in text or text.startswith('spotify:'):
            self._import_spotify(text)
            return
        if '://' in text:
            host = urlparse(text).hostname or ''
            if urlparse(text).scheme not in ('http', 'https') or not (host in ('youtu.be', 'youtube.com') or host.endswith('.youtube.com')):
                self.status.setText('Usa un enlace de YouTube o Spotify, o escribe el nombre de la canción.')
                return
            target = text
        else:
            target = 'ytsearch10:' + text
        try:
            args = music_data.ytdlp() + ['--flat-playlist', '--dump-single-json', '--no-playlist', '--', target]
        except RuntimeError as error:
            self.status.setText(str(error))
            return
        self.search_button.setEnabled(False)
        self.results.clear()
        self.status.setText('Buscando en YouTube…')
        self.process.start(args[0], args[1:])
        self.timeout.start()

    def _search_timeout(self):
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self._search_failed('La conexión tardó demasiado. Vuelve a intentarlo.')

    def _search_failed(self, message):
        self.search_button.setEnabled(True)
        self.status.setText(message)

    def _search_finished(self, code, *_):
        self.timeout.stop()
        self.search_button.setEnabled(True)
        if code:
            error = bytes(self.process.readAllStandardError()).decode(errors='replace')
            self.status.setText('No se pudo buscar: ' + error[-300:].strip())
            return
        try:
            data = json.loads(bytes(self.process.readAllStandardOutput()))
        except ValueError:
            self.status.setText('La respuesta de YouTube no se pudo leer.')
            return
        for entry in data.get('entries') or [data]:
            if not entry or not entry.get('id'):
                continue
            track = {'id': 'yt-' + entry['id'], 'title': entry.get('title', 'Sin título'),
                     'artist': entry.get('channel') or entry.get('uploader') or 'YouTube',
                     'duration': entry.get('duration') or 0,
                     'youtube_url': 'https://www.youtube.com/watch?v=' + entry['id']}
            item = QListWidgetItem(f"{track['title']}\n{track['artist']} · {stamp(track['duration'])}")
            item.setData(Qt.UserRole, track)
            self.results.addItem(item)
        count = self.results.count()
        self.results.setVisible(bool(count))
        self.download_button.setVisible(bool(count))
        self.status.setText(f'{count} resultados · selecciona (Ctrl para varias) y pulsa Descargar.')

    def enqueue(self):
        tracks = [item.data(Qt.UserRole) for item in self.results.selectedItems()]
        if not tracks:
            return
        music_data.enqueue({'collections': [{'id': 'personal', 'title': 'Tus descargas', 'append': True,
                                             'source': 'YouTube', 'tracks': tracks}]})
        music_data.start_worker()
        self.library.reload(force=True)
        self.status.setText(f'{len(tracks)} añadidas a la cola de descargas.')

    def _import_spotify(self, link):
        from music_spotify import import_link, spotify_entity
        try:
            spotify_entity(link)
        except ValueError as error:
            self.status.setText(str(error))
            return
        self.search_button.setEnabled(False)
        self.status.setText('Leyendo la lista de Spotify…')
        self.metadata.request('spotify-import', link, lambda: import_link(link))

    def _metadata_ready(self, kind, _key, data):
        if kind != 'spotify-import':
            return
        self.search_button.setEnabled(True)
        if data.get('error'):
            self.status.setText(data['error'])
            return
        collection = data['collections'][0]
        state = self.library.state
        existing = sum(music_data.equivalent_track(state, t) in state['tracks'] for t in collection['tracks'])
        self.library.store.import_references(data)
        music_data.enqueue(data)
        music_data.start_worker()
        self.library.reload(force=True)
        self.library.refresh_references()
        total = len(collection['tracks'])
        self.status.setText(f'{total} canciones de Spotify · {existing} ya estaban · {total - existing} en cola')
        self.actions.navigate.emit(('collection', collection['id']))

    # ------------------------------------------------------------------ local
    def import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Importar música', str(Path.home() / 'Music'), AUDIO_FILTER)
        self._import(paths)

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Importar carpeta de música', str(Path.home() / 'Music'))
        self._import([folder] if folder else [])

    def _import(self, paths):
        if not paths or self.importer is not None:
            return
        self.status.setText('Leyendo etiquetas…')
        self.importer = ImportJob(paths, self)
        self.importer.done.connect(self._imported)
        self.importer.start()

    def _imported(self, count):
        self.importer.wait()
        self.importer.deleteLater()
        self.importer = None
        self.library.reload(force=True)
        self.status.setText(f'{songs(count)} importadas a tu biblioteca.')

    def open_folder(self):
        music_data.LIBRARY.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(music_data.LIBRARY)))

    # ------------------------------------------------------------------ queue
    def render_queue(self):
        counts = self.library.download_counts()
        queued = counts['pending'] + counts['downloading']
        attention = counts['error'] + counts['review']
        paused = self.library.state.get('paused')
        self.summary.setText(f"{counts['ready']} guardadas · {queued} en cola · {attention} requieren atención"
                             + (' · cola pausada' if paused else ''))
        self.resume_button.setEnabled(bool(queued) and bool(paused or counts['pending']))
        self.pause_button.setEnabled(bool(queued) and not paused)
        self.retry_button.setEnabled(bool(attention))
        self.queue.clear()
        for _key, track in self.library.unfinished():
            status = track.get('status')
            detail = track.get('progress') or track.get('error') or 'Esperando turno'
            item = QListWidgetItem(f"{track.get('title', '')} · {track.get('artist', '')}\n{STATUS.get(status, status)} · {detail}")
            item.setData(Qt.UserRole + 2, STATUS_TONE.get(status, 'muted'))
            item.setToolTip(track.get('error') or track.get('progress') or '')
            self.queue.addItem(item)
        if not self.queue.count():
            self.queue.addItem('Todo listo\nTu música está descargada y lista para escuchar.')

    def resume(self):
        music_data.set_paused(False)
        music_data.start_worker()
        self.library.reload(force=True)

    def pause(self):
        music_data.set_paused(True)
        self.library.reload(force=True)

    def retry(self):
        music_data.retry_failed()
        music_data.start_worker()
        self.library.reload(force=True)

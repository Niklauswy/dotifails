"""«Añadir música» for QML: YouTube search (yt-dlp in a QProcess), public Spotify links, importing files or a
folder through Wysun Files' selector, the music folder, and the download queue. Rules and wording follow the
Widgets page it replaces (M-62…M-67)."""
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

from PySide6.QtCore import Property, QObject, QProcess, QProcessEnvironment, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from wysun_core import launch
from wysun_music import data as music_data
from .models import _KeyedModel
from .text import clock, songs

STATUS = {'pending': 'En cola', 'downloading': 'Descargando', 'error': 'Error', 'review': 'Revisar versión'}
TONE = {'pending': 'muted', 'downloading': 'accent', 'error': 'error', 'review': 'warning'}
SEARCH_TIMEOUT_MS = 90000
HINT = 'Los enlaces de Spotify importan la lista completa y descargan el mejor audio disponible.'


def system_python():
    """The selector is a Widgets app: it runs on the system Python, not on the qml-runtime venv."""
    return str(Path(sys.base_prefix) / 'bin/python3')


class ResultModel(_KeyedModel):
    NAMES = ('id', 'title', 'detail', 'selected')

    def value(self, row, name, number):
        if name == 'id':
            return row['track']['id']
        if name == 'title':
            return row['track']['title']
        if name == 'detail':
            return f"{row['track']['artist']} · {clock(row['track']['duration'])}"
        if name == 'selected':
            return row['selected']
        return None

    def set(self, tracks):
        self._reset([{'track': t, 'selected': False} for t in tracks])

    def toggle(self, row):
        if 0 <= row < len(self._rows):
            self._rows[row]['selected'] = not self._rows[row]['selected']
            self.dataChanged.emit(self.index(row), self.index(row))

    def chosen(self):
        return [r['track'] for r in self._rows if r['selected']]


class DownloadModel(_KeyedModel):
    NAMES = ('title', 'detail', 'status', 'statusText', 'tone')

    def value(self, row, name, number):
        key, track = row
        status = track.get('status')
        if name == 'title':
            return f"{track.get('title', '')} · {track.get('artist', '')}"
        if name == 'detail':
            return track.get('progress') or track.get('error') or 'Esperando turno'
        if name == 'status':
            return status
        if name == 'statusText':
            return STATUS.get(status, status or '')
        if name == 'tone':
            return TONE.get(status, 'muted')
        return None

    def set(self, rows):
        self._reset(rows)


class _Import(QThread):
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


class AddMusic(QObject):
    changed = Signal()
    navigateRequested = Signal(str)

    def __init__(self, library, metadata, parent=None):
        super().__init__(parent)
        self.library, self.metadata = library, metadata
        self._status = HINT
        self._busy = False
        self._summary = ''
        self._counts = {}
        self.results = ResultModel(self)
        self.downloads = DownloadModel(self)
        self.importer = None
        self.picker = None
        self.process = QProcess(self)
        self.process.finished.connect(self._search_finished)
        self.process.errorOccurred.connect(lambda _: self._failed('No se pudo iniciar la búsqueda.'))
        self.timeout = QTimer(self, singleShot=True, interval=SEARCH_TIMEOUT_MS)
        self.timeout.timeout.connect(self._timed_out)
        metadata.ready.connect(self._metadata_ready)
        library.changed.connect(self.render_queue)
        self.render_queue()

    # ------------------------------------------------------------ properties
    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def summary(self):
        return self._summary

    @Property('QVariantMap', notify=changed)
    def counts(self):
        return self._counts

    @Property(QObject, constant=True)
    def resultsModel(self):
        return self.results

    @Property(QObject, constant=True)
    def downloadsModel(self):
        return self.downloads

    def _say(self, text, busy=None):
        self._status = text
        if busy is not None:
            self._busy = busy
        self.changed.emit()

    # ---------------------------------------------------------------- search
    @Slot(str)
    def search(self, text):
        text = text.strip()
        if not text or self.process.state() != QProcess.NotRunning:
            return
        if 'open.spotify.com' in text or text.startswith('spotify:'):
            self._import_spotify(text)
            return
        if '://' in text:
            url = urlparse(text)
            host = url.hostname or ''
            if url.scheme not in ('http', 'https') or not (host in ('youtu.be', 'youtube.com') or host.endswith('.youtube.com')):
                self._say('Usa un enlace de YouTube o Spotify, o escribe el nombre de la canción.')
                return
            target = text
        else:
            target = 'ytsearch10:' + text
        try:
            args = music_data.ytdlp() + ['--flat-playlist', '--dump-single-json', '--no-playlist', '--', target]
        except RuntimeError as error:
            self._say(str(error))
            return
        self.results.set([])
        self._say('Buscando en YouTube…', True)
        self.process.start(args[0], args[1:])
        self.timeout.start()

    def _timed_out(self):
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self._failed('La conexión tardó demasiado. Vuelve a intentarlo.')

    def _failed(self, message):
        self.timeout.stop()
        self._say(message, False)

    def _search_finished(self, code, *_):
        self.timeout.stop()
        if code:
            error = bytes(self.process.readAllStandardError()).decode(errors='replace')
            self._say('No se pudo buscar: ' + error[-300:].strip(), False)
            return
        try:
            found = json.loads(bytes(self.process.readAllStandardOutput()))
        except ValueError:
            self._say('La respuesta de YouTube no se pudo leer.', False)
            return
        tracks = []
        for entry in found.get('entries') or [found]:
            if entry and entry.get('id'):
                tracks.append({'id': 'yt-' + entry['id'], 'title': entry.get('title', 'Sin título'),
                               'artist': entry.get('channel') or entry.get('uploader') or 'YouTube',
                               'duration': entry.get('duration') or 0,
                               'youtube_url': 'https://www.youtube.com/watch?v=' + entry['id']})
        self.results.set(tracks)
        self._say(f'{len(tracks)} resultados · selecciona (Ctrl+Enter descarga la selección).', False)

    @Slot(int)
    def toggleResult(self, row):
        self.results.toggle(row)

    @Slot()
    def downloadSelected(self):
        tracks = self.results.chosen()
        if not tracks:
            return
        music_data.enqueue({'collections': [{'id': 'personal', 'title': 'Tus descargas', 'append': True,
                                             'source': 'YouTube', 'tracks': tracks}]})
        music_data.start_worker()
        self.library.reload(force=True)
        self._say(f'{len(tracks)} añadidas a la cola de descargas.')

    def _import_spotify(self, link):
        from wysun_music.spotify import import_link, spotify_entity
        try:
            spotify_entity(link)
        except ValueError as error:
            self._say(str(error))
            return
        self._say('Leyendo la lista de Spotify…', True)
        self.metadata.request('spotify-import', link, lambda: import_link(link))

    def _metadata_ready(self, kind, _key, result):
        if kind != 'spotify-import':
            return
        if result.get('error'):
            self._say(result['error'], False)
            return
        collection = result['collections'][0]
        state = self.library.state
        existing = sum(music_data.equivalent_track(state, t) in state['tracks'] for t in collection['tracks'])
        self.library.store.import_references(result)
        music_data.enqueue(result)
        music_data.start_worker()
        self.library.reload(force=True)
        self.library.refresh_references()
        total = len(collection['tracks'])
        self._say(f'{total} canciones de Spotify · {existing} ya estaban · {total - existing} en cola', False)
        self.navigateRequested.emit('collection:' + collection['id'])

    # ----------------------------------------------------------------- local
    @Slot()
    def importFiles(self):
        self._pick(directory=False)

    @Slot()
    def importFolder(self):
        self._pick(directory=True)

    def _pick(self, directory):
        if self.picker is not None or self.importer is not None:
            return
        self.picker = QProcess(self)
        env = QProcessEnvironment()
        for key, value in launch.environment().items():
            env.insert(key, value)
        self.picker.setProcessEnvironment(env)
        command = launch.argv('wysun_files.picker', python=system_python())
        self.picker.finished.connect(self._picked)
        self.picker.start(command[0], command[1:])
        request = dict(kind='audio', multiple=not directory, directory=directory,
                       title='Importar carpeta de música' if directory else 'Importar música',
                       initial=str(Path.home() / 'Music'))
        self.picker.write(json.dumps(request).encode() + b'\n')
        self.picker.closeWriteChannel()

    def _picked(self, code, *_):
        process, self.picker = self.picker, None
        raw = bytes(process.readAllStandardOutput())
        process.deleteLater()
        try:
            result = json.loads(raw) if code == 0 and len(raw) <= 1 << 20 else {}
        except ValueError:
            result = {}
        paths = [QUrl(u).toLocalFile() for u in result.get('uris', [])] if result.get('code') == 0 else []
        self.import_paths([p for p in paths if p])

    def import_paths(self, paths):
        if not paths or self.importer is not None:
            return
        self._say('Leyendo etiquetas…', True)
        self.importer = _Import(paths, self)
        self.importer.done.connect(self._imported)
        self.importer.start()

    def _imported(self, count):
        self.importer.wait()
        self.importer.deleteLater()
        self.importer = None
        self.library.reload(force=True)
        self._say(f'{songs(count)} importadas a tu biblioteca.', False)

    @Slot()
    def openFolder(self):
        music_data.LIBRARY.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(music_data.LIBRARY)))

    # ----------------------------------------------------------------- queue
    @Slot()
    def render_queue(self):
        counts = self.library.download_counts()
        queued = counts['pending'] + counts['downloading']
        attention = counts['error'] + counts['review']
        paused = bool(self.library.state.get('paused'))
        self._summary = (f"{counts['ready']} guardadas · {queued} en cola · {attention} requieren atención"
                         + (' · cola pausada' if paused else ''))
        self._counts = dict(queued=queued, attention=attention, paused=paused,
                            canResume=bool(queued) and bool(paused or counts['pending']),
                            canPause=bool(queued) and not paused, canRetry=bool(attention))
        self.downloads.set(self.library.unfinished())
        self.changed.emit()

    @Slot()
    def resume(self):
        music_data.set_paused(False)
        music_data.start_worker()
        self.library.reload(force=True)

    @Slot()
    def pause(self):
        music_data.set_paused(True)
        self.library.reload(force=True)

    @Slot()
    def retry(self):
        music_data.retry_failed()
        music_data.start_worker()
        self.library.reload(force=True)

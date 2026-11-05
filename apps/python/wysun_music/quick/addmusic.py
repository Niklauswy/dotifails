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

HINT = 'Busca una canción, o pega un enlace de Spotify o YouTube para elegir qué guardar.'
SEARCH_TIMEOUT_MS = 90000
FAILED_TEXT = {'error': 'Falló la descarga', 'missing': 'No encontrada en YouTube'}


def system_python():
    """The selector is a Widgets app: it runs on the system Python, not on the qml-runtime venv."""
    return str(Path(sys.base_prefix) / 'bin/python3')


class ResultModel(_KeyedModel):
    """YouTube results: a click plays it (streaming), the check selects it for download."""
    NAMES = ('id', 'key', 'title', 'detail', 'selected', 'current')

    def value(self, row, name, number):
        track = row['track']
        if name == 'id':
            return track['id']
        if name == 'key':
            return row['key']
        if name == 'title':
            return track['title']
        if name == 'detail':
            return f"{track['artist']} · {clock(track['duration'])}"
        if name == 'selected':
            return row['selected']
        if name == 'current':
            return row.get('current', False)
        return None

    def set(self, tracks, keys=None):
        keys = keys or [t['id'] for t in tracks]
        self._reset([{'track': t, 'key': k, 'selected': False} for t, k in zip(tracks, keys)])

    def toggle(self, row):
        if 0 <= row < len(self._rows):
            self._rows[row]['selected'] = not self._rows[row]['selected']
            self.dataChanged.emit(self.index(row), self.index(row))

    def chosen(self):
        return [r['track'] for r in self._rows if r['selected']]

    def keys(self):
        return [r['key'] for r in self._rows]

    def track(self, row):
        return self._rows[row]['track'] if 0 <= row < len(self._rows) else None


class PreviewModel(_KeyedModel):
    """The songs of a pasted list before anything downloads: check the ones to keep."""
    NAMES = ('key', 'title', 'detail', 'selected', 'owned')

    def value(self, row, name, number):
        track = row['track']
        if name == 'key':
            return row['key']
        if name == 'title':
            return track.get('title', '')
        if name == 'detail':
            return f"{track.get('artist', '')} · {clock(track.get('duration') or 0)}"
        if name in ('selected', 'owned'):
            return row[name]
        return None

    def set(self, rows):
        self._reset(rows)

    def _same(self, rows):
        return False

    def rows(self):
        return self._rows

    def toggle(self, row):
        if 0 <= row < len(self._rows) and not self._rows[row]['owned']:
            self._rows[row]['selected'] = not self._rows[row]['selected']
            self.dataChanged.emit(self.index(row), self.index(row))

    def select(self, mode):
        for row in self._rows:
            row['selected'] = not row['owned'] and mode != 'none'
        if self._rows:
            self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1))


class BatchModel(_KeyedModel):
    NAMES = ('id', 'title', 'detail', 'fraction', 'failed')

    def value(self, batch, name, number):
        if name == 'detail':
            done = f"{batch['done']} de {batch['total']}"
            if batch['active']:
                return f"{done} · {batch['active']}"
            return done + (' · en pausa' if batch.get('paused') else ' · en cola')
        if name == 'fraction':
            return batch['done'] / batch['total'] if batch['total'] else 0.0
        return batch.get(name)

    def set(self, rows):
        self._reset(rows)


class FailedModel(_KeyedModel):
    NAMES = ('key', 'title', 'detail')

    def value(self, row, name, number):
        key, track = row
        if name == 'key':
            return key
        if name == 'title':
            return f"{track.get('title', '')} · {track.get('artist', '')}"
        if name == 'detail':
            return FAILED_TEXT.get(track.get('status'), 'Error')
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
    """Search and links lead to a choice (what to play, what to keep); downloads show as batches with progress,
    and songs that could not be downloaded fold into one line with «Reintentar» and «Elegir otra versión»."""
    changed = Signal()
    previewChanged = Signal()
    navigateRequested = Signal(str)

    def __init__(self, library, metadata, player=None, parent=None):
        super().__init__(parent)
        self.library, self.metadata, self.player = library, metadata, player
        self._status = HINT
        self._busy = False
        self._summary = ''
        self._counts = {}
        self._choosing = ''           # key of the song whose version is being chosen
        self._preview = {}
        self._search_kind = 'search'
        self._link = ''
        self._preview_source, self._preview_keys = {}, []
        self.results = ResultModel(self)
        self.previewRows = PreviewModel(self)
        self.batches = BatchModel(self)
        self.failures = FailedModel(self)
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

    @Property(str, notify=changed)
    def choosing(self):
        """Title of the song whose version is being chosen, or ""."""
        return self.library.track(self._choosing).get('title', '') if self._choosing else ''

    @Property('QVariantMap', notify=previewChanged)
    def preview(self):
        return self._preview

    @Property(QObject, constant=True)
    def resultsModel(self):
        return self.results

    @Property(QObject, constant=True)
    def previewModel(self):
        return self.previewRows

    @Property(QObject, constant=True)
    def batchesModel(self):
        return self.batches

    @Property(QObject, constant=True)
    def failedModel(self):
        return self.failures

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
        playlist = False
        if '://' in text:
            url = urlparse(text)
            host = url.hostname or ''
            if url.scheme not in ('http', 'https') or not (host in ('youtu.be', 'youtube.com') or host.endswith('.youtube.com')):
                self._say('Usa un enlace de YouTube o Spotify, o escribe el nombre de la canción.')
                return
            target = text
            playlist = 'list=' in (url.query or '')
        else:
            target = 'ytsearch10:' + text
            self._choosing = ''
        self._run(target, 'playlist' if playlist else 'search', text)

    def _run(self, target, kind, text):
        try:
            args = music_data.ytdlp() + ['--flat-playlist', '--dump-single-json']
        except RuntimeError as error:
            self._say(str(error))
            return
        if kind != 'playlist':
            args.append('--no-playlist')
        self._search_kind = kind
        self._link = text
        self.results.set([])
        self._say('Leyendo la lista de YouTube…' if kind == 'playlist' else 'Buscando en YouTube…', True)
        self.process.start(args[0], args[1:] + ['--', target])
        self.timeout.start()

    def _timed_out(self):
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
            self._failed('La conexión tardó demasiado. Vuelve a intentarlo.')

    def _failed(self, message):
        self.timeout.stop()
        self._say(message, False)

    def _search_finished(self, code, *_):
        from wysun_music.stream import entry_track
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
        tracks = [entry_track(e) for e in (found.get('entries') or [found]) if e and e.get('id')]
        if self._search_kind == 'playlist':
            self._show_preview(dict(id='youtube-' + (found.get('id') or 'lista'), title=found.get('title') or 'Lista de YouTube',
                                    source=self._link, cover_url='', kind='YouTube', tracks=tracks))
            self._say(HINT, False)
            return
        keys = self.library.register(tracks)
        self.results.set(tracks, keys)
        if self._choosing:
            self._say(f'Elige la versión de «{self.choosing}».', False)
        elif tracks:
            self._say(f'{len(tracks)} resultados · toca uno para escucharlo, marca los que quieras guardar.', False)
        else:
            self._say('YouTube no encontró nada con esas palabras.', False)

    @Slot(int)
    def toggleResult(self, row):
        self.results.toggle(row)

    @Slot(int)
    def playResult(self, row):
        """Listen to a result right away (streaming)."""
        keys = self.results.keys()
        if self.player is not None and 0 <= row < len(keys):
            self.player.play(keys[row], keys, 'youtube:results')

    @Slot()
    def downloadSelected(self):
        tracks = self.results.chosen()
        if not tracks:
            return
        music_data.enqueue({'collections': [{'id': 'personal', 'title': 'Tus descargas', 'append': True,
                                             'source': 'YouTube', 'tracks': tracks}]})
        music_data.start_worker()
        self.library.reload(force=True)
        for row in range(self.results.rowCount()):
            if self.results._rows[row]['selected']:
                self.results.toggle(row)
        self._say(f'{songs(len(tracks))} en camino a tu biblioteca.')

    # --------------------------------------------------------- choose version
    @Slot(str)
    def chooseVersion(self, key):
        track = self.library.track(key)
        if not track or self.process.state() != QProcess.NotRunning:
            return
        self._choosing = key
        self._run(f"ytsearch10:{track.get('artist', '').split(',')[0]} {track.get('title', '')}", 'search', '')

    @Slot(int)
    def useVersion(self, row):
        track = self.results.track(row)
        if not self._choosing or track is None:
            return
        music_data.use_version(self._choosing, track['youtube_url'])
        music_data.start_worker()
        title = self.choosing
        self._choosing = ''
        self.results.set([])
        self.library.reload(force=True)
        self._say(f'Descargando «{title}» con la versión elegida.')

    @Slot()
    def cancelChoice(self):
        self._choosing = ''
        self.results.set([])
        self._say(HINT)

    # --------------------------------------------------------------- preview
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
        self._show_preview(dict(collection, kind='Spotify'))
        self._say(HINT, False)

    @Slot(str)
    def previewCollection(self, collection_id):
        """«Descargar…» on a list heard online: the same choice as a pasted link."""
        collection = self.library.collection(collection_id)
        if collection is None:
            return
        raw = self.library.raw_collection(collection_id) or {}
        tracks = [dict(self.library.track(k), id=k) for k in collection.keys]
        self._show_preview(dict(id=collection_id.replace(':', '-'), title=collection.title, source=collection.source,
                                cover_url=raw.get('cover_url', ''), kind='YouTube' if collection.source == 'YouTube'
                                else 'Spotify', tracks=tracks, collection=collection_id))

    def _show_preview(self, collection):
        tracks = collection['tracks']
        keys = self.library.register(tracks)
        rows = []
        for key, track in zip(keys, tracks):
            owned = self.library.available(key) or self.library.track(key).get('status') in ('pending', 'downloading')
            rows.append({'key': key, 'track': track, 'owned': owned, 'selected': not owned})
        self.previewRows.set(rows)
        self._preview_source = collection
        self._preview_keys = keys
        owned = sum(r['owned'] for r in rows)
        self._preview = dict(visible=True, title=collection.get('title', 'Lista'), kind=collection.get('kind', ''),
                             collection=collection.get('collection', ''), cover=collection.get('cover_url') or '',
                             total=len(rows), owned=owned,
                             subtitle=songs(len(rows)) + (f' · {owned} ya en tu biblioteca' if owned else ''))
        self._update_preview()


    def _update_preview(self):
        chosen = sum(r['selected'] for r in self.previewRows.rows())
        self._preview = dict(self._preview, chosen=chosen,
                             action=f'Descargar {chosen}' if chosen else 'Nada que descargar')
        self.previewChanged.emit()

    @Slot(int)
    def togglePreview(self, row):
        self.previewRows.toggle(row)
        self._update_preview()

    @Slot(str)
    def selectPreview(self, mode):
        self.previewRows.select(mode)
        self._update_preview()

    @Slot()
    def playPreview(self):
        if self.player is not None and self._preview_keys:
            self.player.play_collection(self._preview_keys, None, 'preview:' + self._preview.get('title', ''))

    @Slot(int)
    def playPreviewRow(self, row):
        if self.player is not None and 0 <= row < len(self._preview_keys):
            self.player.play(self._preview_keys[row], self._preview_keys, 'preview:' + self._preview.get('title', ''))

    @Slot()
    def closePreview(self):
        self._preview = {}
        self.previewRows.set([])
        self.previewChanged.emit()

    @Slot()
    def downloadPreview(self):
        rows = [r for r in self.previewRows.rows() if r['selected']]
        if not rows:
            return
        source = self._preview_source
        cid = source.get('id') or 'lista'
        manifest = {'collections': [{'id': cid, 'title': source.get('title', 'Lista'), 'append': True,
                                     'source': source.get('source', ''), 'cover_url': source.get('cover_url') or None,
                                     'tracks': [r['track'] for r in rows]}]}
        if source.get('kind') == 'Spotify':
            self.library.store.import_references(manifest)
        music_data.enqueue(manifest)
        music_data.start_worker()
        self.library.reload(force=True)
        self.library.refresh_references()
        self._say(f'{songs(len(rows))} de «{source.get("title", "la lista")}» en camino a tu biblioteca.', False)
        self.closePreview()

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
        self.picker.errorOccurred.connect(self._picker_failed)
        self.picker.start(command[0], command[1:])
        request = dict(kind='audio', multiple=not directory, directory=directory,
                       title='Importar carpeta de música' if directory else 'Importar música',
                       initial=str(Path.home() / 'Music'))
        self.picker.write(json.dumps(request).encode() + b'\n')
        self.picker.closeWriteChannel()

    def _picker_failed(self, error):
        if error == QProcess.FailedToStart and self.picker is not None:
            self.picker.deleteLater()
            self.picker = None
            self._say('No se pudo abrir el selector de Wysun Files.', False)

    def _picked(self, code, *_):
        process, self.picker = self.picker, None
        if process is None:
            return
        raw = bytes(process.readAllStandardOutput())
        process.deleteLater()
        if code not in (0, 1):                  # 1 = cancelled by the user
            self._say('El selector de Wysun Files se cerró con un error.', False)
            return
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
        state = self.library.state
        counts = self.library.download_counts()
        paused = bool(state.get('paused'))
        queued = counts['pending'] + counts['downloading']
        failed = counts['error'] + counts['missing']
        batches = music_data.batches(state)
        for batch in batches:
            batch['paused'] = paused
        self.batches.set([b for b in batches if b['done'] + b['failed'] < b['total']])
        self.failures.set([(k, t) for k, t in state['tracks'].items() if t.get('status') in music_data.FAILED])
        self._summary = (f'{songs(queued)} en camino' if queued else 'No hay descargas en curso') + \
            (' · en pausa' if paused and queued else '')
        self._counts = dict(queued=queued, failed=failed, paused=paused, ready=counts['ready'],
                            canResume=bool(queued) and paused, canPause=bool(queued) and not paused,
                            canRetry=bool(failed),
                            failedText=(f'{songs(failed)} no se pudo descargar' if failed == 1
                                        else f'{songs(failed)} no se pudieron descargar'))
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

    @Slot(str)
    def cancelBatch(self, token):
        music_data.cancel_batch(token)
        self.library.reload(force=True)

    @Slot(str)
    def forget(self, key):
        """Drop a song that could not be downloaded."""
        music_data.forget_track(key)
        self.library.reload(force=True)

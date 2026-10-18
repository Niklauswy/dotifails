"""Native local music player, sharing Wysun's surfaces and controls."""
import json
import os
from pathlib import Path
import random
import shutil
import socket
import tempfile
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QProcess, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView,
    QSlider, QFileDialog, QPlainTextEdit, QSplitter, QStackedWidget)
from desktop_common import Surface, button, text_label, ElidedLabel
from icons import icon
from theme_tokens import apply_style
import music_data as music

STATUS = {'ready': 'Disponible', 'pending': 'En cola', 'downloading': 'Descargando',
          'error': 'Error', 'review': 'Revisar versión'}


def stamp(seconds):
    seconds = max(0, int(seconds or 0))
    return f'{seconds//60}:{seconds%60:02}'


class MusicWindow(Surface):
    def __init__(self, test=False):
        super().__init__('Wysun Music', 'Tu biblioteca local · listas de Spotify, audio de YouTube', width=1060, height=710)
        self.test = test
        self.state = music.empty()
        self.current_key = None
        self.collection = 'all'
        self.queue = []
        self.duration = 0
        self.paused = True
        self.last_mtime = None
        self.buffer = b''
        self.pending_path = None
        self.connect_attempts = 0
        self.temp = None
        self.stopping = False
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.player_output)
        self.process.errorOccurred.connect(lambda _: self.player_error('No se pudo iniciar mpv. Comprueba que esté instalado.'))
        self.process.finished.connect(self.player_finished)
        self.search_process = QProcess(self)
        self.search_process.finished.connect(self.search_finished)
        self.search_process.errorOccurred.connect(lambda _: self.status.setText('No se pudo iniciar la búsqueda.'))
        self.socket = None
        self.outbox = b''
        self.ipc_timer = QTimer(self)
        self.ipc_timer.setInterval(200)
        self.ipc_timer.timeout.connect(self.read_player)
        self.build()
        self.refresh()
        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.refresh)
        if not test:
            self.timer.start()

    def build(self):
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Buscar canción o artista en tu biblioteca…')
        self.search.setAccessibleName('Buscar en la biblioteca')
        self.search.textChanged.connect(self.render_tracks)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(button('Buscar en YouTube', lambda: self.pages.setCurrentIndex(2), symbol='search'))
        toolbar.addWidget(button('Añadir archivos', self.import_files, symbol='folder-open'))
        toolbar.addWidget(button('Carpeta', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(music.LIBRARY))), symbol='folder-open'))
        self.outer.addLayout(toolbar)
        split = QSplitter(Qt.Horizontal)
        self.collections = QListWidget()
        self.collections.setMinimumWidth(180)
        self.collections.setMaximumWidth(280)
        self.collections.setAccessibleName('Listas de música')
        self.collections.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.collections.currentItemChanged.connect(self.select_collection)
        split.addWidget(self.collections)
        page = QWidget()
        content = QVBoxLayout(page)
        content.setContentsMargins(10, 0, 0, 0)
        content.setSpacing(12)
        heading = QHBoxLayout()
        self.heading = text_label('Toda tu música', 'previewTitle')
        heading.addWidget(self.heading, 1)
        self.library_button = button('Biblioteca', lambda: self.pages.setCurrentIndex(0))
        self.download_button = button('Descargas', lambda: self.pages.setCurrentIndex(1), symbol='download')
        heading.addWidget(self.library_button)
        heading.addWidget(self.download_button)
        content.addLayout(heading)
        self.summary = text_label('', 'subtitle')
        content.addWidget(self.summary)
        self.pages = QStackedWidget()
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(['#', 'Canción', 'Artista', 'Calidad', 'Estado'])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setAccessibleName('Canciones de la lista')
        apply_style(self.tree, 'QTreeWidget::item{padding:6px 0;} QTreeWidget::item:selected{background:#2C3D57;}')
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        for column, width in [(0, 34), (2, 175), (3, 100), (4, 100)]:
            self.tree.setColumnWidth(column, width)
        self.tree.itemDoubleClicked.connect(lambda item, _: self.play_key(item.data(0, Qt.UserRole)))
        self.tree.itemSelectionChanged.connect(self.update_actions)
        self.pages.addWidget(self.tree)
        downloads = QWidget()
        dl = QVBoxLayout(downloads)
        dl.setContentsMargins(0, 0, 0, 0)
        self.download_status = text_label('', 'subtitle')
        dl.addWidget(self.download_status)
        controls = QHBoxLayout()
        self.resume_button = button('Continuar descargas', self.resume_downloads, 'primary', 'download')
        controls.addWidget(self.resume_button)
        self.pause_downloads_button = button('Pausar cola', self.pause_downloads)
        self.pause_downloads_button.setToolTip('Termina la canción actual y pausa las siguientes descargas.')
        controls.addWidget(self.pause_downloads_button)
        controls.addWidget(button('Reintentar errores', self.retry_downloads))
        controls.addStretch()
        dl.addLayout(controls)
        self.download_log = QPlainTextEdit()
        self.download_log.setReadOnly(True)
        self.download_log.setAccessibleName('Estado de las descargas')
        dl.addWidget(self.download_log, 1)
        self.pages.addWidget(downloads)
        online = QWidget()
        ol = QVBoxLayout(online)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.addWidget(text_label('Encuentra audio y guárdalo en tu biblioteca', 'previewTitle'))
        row = QHBoxLayout()
        self.online_query = QLineEdit()
        self.online_query.setPlaceholderText('Nombre de canción y artista, o enlace de YouTube')
        self.online_query.setAccessibleName('Buscar música en YouTube')
        self.online_query.returnPressed.connect(self.search_online)
        row.addWidget(self.online_query, 1)
        self.online_button = button('Buscar', self.search_online, 'primary', 'search')
        row.addWidget(self.online_button)
        ol.addLayout(row)
        self.online_results = QListWidget()
        self.online_results.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.online_results.setAccessibleName('Resultados de YouTube')
        self.online_results.itemDoubleClicked.connect(lambda _: self.enqueue_results())
        ol.addWidget(self.online_results, 1)
        self.online_status = text_label('Selecciona canciones y pulsa Descargar. Se guardará el mejor audio disponible.', 'subtitle')
        ol.addWidget(self.online_status)
        ol.addWidget(button('Descargar selección', self.enqueue_results, 'primary', 'download'))
        self.pages.addWidget(online)
        content.addWidget(self.pages, 1)
        self.source = text_label('', 'subtitle')
        self.source.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content.addWidget(self.source)
        split.addWidget(page)
        split.setSizes([225, 780])
        self.outer.addWidget(split, 1)
        player = QWidget()
        player.setObjectName('musicPlayer')
        apply_style(player, 'QWidget#musicPlayer{background:rgba(155,191,247,8);border:1px solid #344761;border-radius:16px;}')
        layout = QVBoxLayout(player)
        layout.setContentsMargins(18, 15, 18, 15)
        now = QHBoxLayout()
        titles = QVBoxLayout()
        self.now_title = ElidedLabel('Elige una canción para escuchar')
        apply_style(self.now_title, 'font-size:16px;font-weight:600;')
        self.now_artist = ElidedLabel('Doble clic en una canción disponible')
        apply_style(self.now_artist, 'color:#A0ACC0;font-size:12px;')
        titles.addWidget(self.now_title)
        titles.addWidget(self.now_artist)
        now.addLayout(titles, 1)
        self.previous_button = button('Anterior', lambda: self.advance(-1), symbol='skip-back')
        self.play_button = button('Reproducir', self.toggle_play, 'primary', 'play')
        self.next_button = button('Siguiente', lambda: self.advance(1), symbol='skip-forward')
        now.addWidget(self.previous_button)
        now.addWidget(self.play_button)
        now.addWidget(self.next_button)
        layout.addLayout(now)
        timeline = QHBoxLayout()
        self.elapsed = text_label('0:00', 'subtitle')
        timeline.addWidget(self.elapsed)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setAccessibleName('Posición de reproducción')
        self.seek.setEnabled(False)
        self.seek.sliderReleased.connect(lambda: self.command(['seek', self.seek.value(), 'absolute']))
        timeline.addWidget(self.seek, 1)
        self.total = text_label('0:00', 'subtitle')
        timeline.addWidget(self.total)
        layout.addLayout(timeline)
        options = QHBoxLayout()
        self.shuffle = button('Aleatorio', lambda: None, symbol='shuffle')
        self.shuffle.setCheckable(True)
        self.repeat = button('Repetir lista', lambda: None, symbol='repeat')
        self.repeat.setCheckable(True)
        options.addWidget(self.shuffle)
        options.addWidget(self.repeat)
        options.addStretch()
        options.addWidget(text_label('Volumen', 'subtitle'))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setFixedWidth(120)
        self.volume.setRange(0, 100)
        self.volume.setValue(60)
        self.volume.setAccessibleName('Volumen')
        self.volume.valueChanged.connect(lambda value: self.command(['set_property', 'volume', value]))
        options.addWidget(self.volume)
        layout.addLayout(options)
        self.outer.addWidget(player)
        self.status = text_label('Reproducción local · puedes cerrar el panel y seguir escuchando', 'subtitle')
        self.outer.addWidget(self.status)
        QShortcut(QKeySequence('Ctrl+F'), self).activated.connect(self.search.setFocus)
        QShortcut(QKeySequence('Ctrl+Space'), self).activated.connect(self.toggle_play)
        QShortcut(QKeySequence('Ctrl+Right'), self).activated.connect(lambda: self.advance(1))
        QShortcut(QKeySequence('Ctrl+Left'), self).activated.connect(lambda: self.advance(-1))
        QShortcut(QKeySequence('Return'), self.tree).activated.connect(self.play_selection)

    def refresh(self, force=False):
        try:
            mtime = (music.DATA/'library.json').stat().st_mtime_ns
        except FileNotFoundError:
            mtime = 0
        if not force and mtime == self.last_mtime:
            return
        try:
            self.state = music.read_state()
        except (OSError, ValueError) as error:
            self.status.setText('No se pudo leer la biblioteca: '+str(error))
            return
        self.last_mtime = mtime
        self.collections.blockSignals(True)
        self.collections.clear()
        all_ready = sum(t['status'] == 'ready' for t in self.state['tracks'].values())
        item = QListWidgetItem(f'Toda tu música\n{all_ready} disponibles')
        item.setData(Qt.UserRole, 'all')
        self.collections.addItem(item)
        for key, collection in self.state['collections'].items():
            ready = sum(self.state['tracks'][k]['status'] == 'ready' for k in collection['tracks'])
            title = 'Nadie sabe…' if key == 'nadie-sabe' else collection['title']
            item = QListWidgetItem(f"{title}\n{ready} / {len(collection['tracks'])} disponibles")
            item.setToolTip(collection['title'])
            item.setData(Qt.UserRole, key)
            self.collections.addItem(item)
        for i in range(self.collections.count()):
            if self.collections.item(i).data(Qt.UserRole) == self.collection:
                self.collections.setCurrentRow(i)
        self.collections.blockSignals(False)
        self.render_tracks()
        self.render_downloads()

    def selected_keys(self):
        if self.collection == 'all':
            return list(self.state['tracks'])
        return self.state['collections'].get(self.collection, {}).get('tracks', [])

    def select_collection(self, item, previous=None):
        if item:
            self.collection = item.data(Qt.UserRole)
            self.pages.setCurrentIndex(0)
            self.render_tracks()

    def render_tracks(self):
        selected = self.tree.currentItem()
        selected = selected.data(0, Qt.UserRole) if selected else None
        self.tree.blockSignals(True)
        self.tree.clear()
        collection = self.state['collections'].get(self.collection, {})
        self.heading.setText(collection.get('title', 'Toda tu música'))
        query = self.search.text().casefold()
        keys = self.selected_keys()
        ready = sum(self.state['tracks'][key]['status'] == 'ready' for key in keys)
        self.summary.setText(f'{ready} disponibles · {len(keys)} canciones')
        source = collection.get('source', '')
        self.source.setText(('Ranking de Spotify · '+collection.get('date', '')+' · publicado por Spotify Top')
                            if collection.get('date') else ('Selección de Spotify' if source else 'Archivos guardados en este equipo'))
        self.source.setToolTip(source)
        for index, key in enumerate(keys, 1):
            track = self.state['tracks'][key]
            if query and query not in (track['title']+' '+track['artist']).casefold():
                continue
            quality = (track.get('codec', '').upper()+' '+str(round(track.get('bitrate', 0)/1000))+' kb/s') if track.get('codec') else '—'
            item = QTreeWidgetItem([str(index), track['title'], track['artist'], quality, STATUS.get(track['status'], track['status'])])
            item.setData(0, Qt.UserRole, key)
            item.setToolTip(1, track['title'])
            item.setToolTip(2, track['artist'])
            item.setToolTip(4, track.get('error') or track.get('progress') or track.get('path', ''))
            if key == self.current_key:
                item.setIcon(1, icon('volume-2'))
            self.tree.addTopLevelItem(item)
            if key == selected:
                self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)
        self.update_actions()

    def render_downloads(self):
        counts = {status: sum(t['status'] == status for t in self.state['tracks'].values()) for status in STATUS}
        paused = self.state.get('paused')
        self.download_status.setText(f"{counts['ready']} descargadas · {counts['pending']} pendientes · {counts['error']} errores · {counts['review']} para revisar" + (' · Cola pausada' if paused else ''))
        lines = []
        for track in self.state['tracks'].values():
            if track['status'] != 'ready':
                lines.append(f"{STATUS.get(track['status'])} · {track['artist']} — {track['title']}\n{track.get('progress') or track.get('error') or ''}")
        self.download_log.setPlainText('\n\n'.join(lines) or 'Tu biblioteca está descargada y lista para escuchar.')
        self.resume_button.setEnabled(bool(counts['pending'] or counts['downloading']))
        self.pause_downloads_button.setEnabled(not paused and bool(counts['pending'] or counts['downloading']))
        self.download_button.setText(f"Descargas · {counts['pending']+counts['downloading']}")

    def update_actions(self):
        item = self.tree.currentItem()
        selected = self.state['tracks'].get(item.data(0, Qt.UserRole), {}) if item else {}
        self.play_button.setEnabled(bool(self.current_key or selected.get('status') == 'ready'))
        self.previous_button.setEnabled(bool(self.queue))
        self.next_button.setEnabled(bool(self.queue))

    def play_selection(self):
        item = self.tree.currentItem()
        if item:
            self.play_key(item.data(0, Qt.UserRole))

    def play_key(self, key, keep_queue=False):
        track = self.state['tracks'].get(key, {})
        if track.get('status') != 'ready':
            self.status.setText('Esta canción todavía no está descargada. Revisa la pestaña Descargas.')
            return
        path = track.get('path', '')
        if not Path(path).is_file():
            self.status.setText('El archivo ya no está en su ubicación. Añádelo de nuevo o vuelve a descargarlo.')
            return
        if not keep_queue:
            self.queue = [self.tree.topLevelItem(i).data(0, Qt.UserRole) for i in range(self.tree.topLevelItemCount())
                          if self.state['tracks'][self.tree.topLevelItem(i).data(0, Qt.UserRole)]['status'] == 'ready']
        self.current_key = key
        self.pending_path = path
        self.now_title.setText(track['title'])
        self.now_artist.setText(track['artist'])
        self.status.setText('Reproducción local · puedes cerrar el panel y seguir escuchando')
        if self.socket is not None:
            self.load_pending()
        elif self.process.state() == QProcess.NotRunning:
            self.start_player()
        self.render_tracks()

    def start_player(self):
        if not shutil.which('mpv'):
            self.player_error('Falta mpv para reproducir audio.')
            return
        self.temp = tempfile.TemporaryDirectory(prefix='orbit-music-')
        self.endpoint = str(Path(self.temp.name)/'player.sock')
        self.buffer = b''
        self.stopping = False
        self.process.start('mpv', ['--no-config', '--no-video', '--audio-display=no', '--idle=yes',
            '--no-terminal', '--input-ipc-server='+self.endpoint, '--volume='+str(self.volume.value())])
        self.connect_attempts = 0
        QTimer.singleShot(100, self.connect_player)

    def connect_player(self):
        if self.process.state() == QProcess.NotRunning:
            return
        if self.socket is not None:
            return
        if Path(self.endpoint).exists():
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(.05)
            try:
                client.connect(self.endpoint)
                client.setblocking(False)
                self.socket = client
                self.ipc_timer.start()
                self.player_connected()
                return
            except OSError:
                client.close()
        self.connect_attempts += 1
        if self.connect_attempts < 40:
            QTimer.singleShot(100, self.connect_player)
        else:
            self.player_error('No se pudo conectar con el reproductor de audio.')

    def player_connected(self):
        for i, prop in enumerate(('time-pos', 'duration', 'pause')):
            self.command(['observe_property', i, prop])
        self.load_pending()

    def command(self, command):
        if self.socket is not None:
            self.outbox += (json.dumps({'command': command})+'\n').encode()
            self.flush_commands()

    def flush_commands(self):
        if self.socket is not None and self.outbox:
            try:
                sent = self.socket.send(self.outbox)
                self.outbox = self.outbox[sent:]
            except BlockingIOError:
                pass
            except OSError:
                self.disconnect_player()

    def disconnect_player(self):
        self.ipc_timer.stop()
        if self.socket is not None:
            self.socket.close()
            self.socket = None
        self.outbox = b''

    def load_pending(self):
        if self.pending_path:
            self.command(['loadfile', self.pending_path, 'replace'])
            self.command(['set_property', 'pause', False])
            self.pending_path = None
            self.set_paused(False)

    def read_player(self):
        if self.socket is None:
            return
        self.flush_commands()
        if self.socket is None:
            return
        try:
            for _ in range(32):
                chunk = self.socket.recv(65536)
                if not chunk:
                    self.disconnect_player()
                    break
                self.buffer += chunk
        except BlockingIOError:
            pass
        except OSError:
            self.disconnect_player()
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if data.get('event') == 'property-change':
                prop, value = data.get('name'), data.get('data')
                if prop == 'time-pos' and value is not None:
                    self.elapsed.setText(stamp(value))
                    if hasattr(self,'position_changed'):self.position_changed(value)
                    if not self.seek.isSliderDown():
                        self.seek.setValue(int(value))
                elif prop == 'duration' and value:
                    self.duration = value
                    self.seek.setRange(0, int(value))
                    self.seek.setEnabled(True)
                    self.total.setText(stamp(value))
                elif prop == 'pause' and value is not None:
                    self.set_paused(value)
            elif data.get('event') == 'end-file':
                if data.get('reason') == 'eof':
                    self.advance(1, automatic=True)
                elif data.get('reason') == 'error':
                    self.player_error('No se pudo reproducir este archivo de audio.')

    def set_paused(self, value):
        self.paused = bool(value)
        self.play_button.setText('Reproducir' if self.paused else 'Pausar')
        self.play_button.setIcon(icon('play' if self.paused else 'pause', 17, '#162436'))

    def toggle_play(self):
        if self.current_key and self.socket is not None:
            self.command(['cycle', 'pause'])
        else:
            self.play_selection()

    def advance(self, direction, automatic=False):
        queue = [key for key in self.queue if self.state['tracks'].get(key, {}).get('status') == 'ready']
        if not queue:
            return
        if self.shuffle.isChecked():
            candidates = [key for key in queue if key != self.current_key]
            key = random.choice(candidates or queue)
        else:
            index = queue.index(self.current_key) if self.current_key in queue else -1
            index += direction
            if index >= len(queue) and automatic and not self.repeat.isChecked():
                self.command(['set_property', 'pause', True])
                self.set_paused(True)
                self.status.setText('Terminó la lista. Elige otra canción para continuar.')
                return
            key = queue[index % len(queue)]
        self.play_key(key, keep_queue=True)

    def player_output(self):
        output = bytes(self.process.readAllStandardOutput()).decode(errors='replace')
        if 'Failed to open' in output or 'No audio' in output:
            self.status.setText(output[-250:].strip())

    def player_error(self, message):
        self.status.setText(message)
        self.set_paused(True)

    def player_finished(self, *args):
        self.disconnect_player()
        if self.temp:
            self.temp.cleanup()
            self.temp = None
        if not self.stopping:
            self.player_error('El reproductor se detuvo. Selecciona una canción para volver a iniciarlo.')
            self.current_key = None

    def import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Añadir música local', str(Path.home()/'Music'),
                                               'Audio (*.m4a *.opus *.mp3 *.flac *.ogg *.wav *.aac)')
        if paths:
            music.import_files(paths)
            self.refresh(True)

    def search_online(self):
        if self.search_process.state() != QProcess.NotRunning:
            return
        query = self.online_query.text().strip()
        if not query:
            return
        if '://' in query:
            parsed = urlparse(query)
            host = parsed.hostname or ''
            if parsed.scheme not in {'https', 'http'} or not (host == 'youtu.be' or host == 'youtube.com' or host.endswith('.youtube.com')):
                self.online_status.setText('Usa un enlace de YouTube o escribe el nombre de la canción.')
                return
            target = query
        else:
            target = 'ytsearch10:'+query
        try:
            args = music.ytdlp()+['--flat-playlist', '--dump-single-json', '--no-playlist', '--', target]
        except RuntimeError as error:
            self.online_status.setText(str(error))
            return
        self.online_button.setEnabled(False)
        self.online_results.clear()
        self.online_status.setText('Buscando en YouTube…')
        self.search_process.start(args[0], args[1:])
        QTimer.singleShot(90000, self.search_timeout)

    def search_timeout(self):
        if self.search_process.state() != QProcess.NotRunning:
            self.search_process.kill()
            self.online_status.setText('La conexión tardó demasiado. Vuelve a intentar.')

    def search_finished(self, code, *args):
        self.online_button.setEnabled(True)
        if code:
            message = bytes(self.search_process.readAllStandardError()).decode(errors='replace')
            self.online_status.setText('No se pudo buscar: '+message[-300:].strip())
            return
        try:
            data = json.loads(bytes(self.search_process.readAllStandardOutput()))
            entries = data.get('entries') or [data]
            for entry in entries:
                if not entry or not entry.get('id'):
                    continue
                track = {'id': 'yt-'+entry['id'], 'title': entry.get('title', 'Sin título'),
                         'artist': entry.get('channel') or entry.get('uploader') or 'YouTube',
                         'duration': entry.get('duration') or 0,
                         'youtube_url': 'https://www.youtube.com/watch?v='+entry['id']}
                item = QListWidgetItem(track['title']+'\n'+track['artist']+' · '+stamp(track['duration']))
                item.setData(Qt.UserRole, track)
                self.online_results.addItem(item)
            self.online_status.setText(f'{self.online_results.count()} resultados. Selecciona y descarga; Ctrl permite marcar varias.')
        except (ValueError, TypeError, KeyError):
            self.online_status.setText('La respuesta de YouTube no se pudo leer.')

    def enqueue_results(self):
        tracks = [item.data(Qt.UserRole) for item in self.online_results.selectedItems()]
        if not tracks or self.test:
            return
        music.enqueue({'collections': [{'id': 'personal', 'title': 'Tus descargas', 'append': True,
                                      'source': 'YouTube', 'tracks': tracks}]})
        music.start_worker()
        self.refresh(True)
        self.pages.setCurrentIndex(1)

    def resume_downloads(self):
        if self.test:
            return
        music.set_paused(False)
        music.start_worker()
        self.refresh(True)

    def pause_downloads(self):
        if not self.test:
            music.set_paused(True)
            self.refresh(True)

    def retry_downloads(self):
        if not self.test:
            music.retry_failed()
            music.start_worker()
            self.refresh(True)

    def shutdown_jobs(self):
        self.stopping = True
        self.timer.stop()
        self.search_process.kill()
        self.search_process.waitForFinished(500)
        self.command(['quit'])
        if self.process.state() != QProcess.NotRunning:
            if not self.process.waitForFinished(700):
                self.process.terminate()
                self.process.waitForFinished(700)
        self.disconnect_player()

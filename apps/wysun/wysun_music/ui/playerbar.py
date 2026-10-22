"""Bottom player capsule: the song, transport with the wavy progress, and tools.

It floats under the content as one rounded capsule; the artwork opens the
immersive «Ahora suena». The play button morphs while playing (M3 Expressive).
"""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from music_library import artists
from theme_tokens import color, tokens
from .style import metric, stamp, text_font
from .widgets import CoverArt, ElidedLabel, IconButton, LinkLabel, Slider

REPEAT_LABELS = {'off': 'Repetir', 'all': 'Repetir lista', 'one': 'Repetir canción'}
HEIGHT = 80


class TimeLabel(QLabel):
    def __init__(self, alignment):
        super().__init__('0:00')
        self.setFont(text_font('caption', 500))
        self.setObjectName('muted')
        self.setFixedWidth(44)
        self.setAlignment(alignment | Qt.AlignVCenter)


class PlayerBar(QWidget):
    panel_requested = Signal(str)     # 'now' | 'lyrics' | 'queue'
    artist_requested = Signal(str)
    cover_clicked = Signal()

    def __init__(self, library, covers, player, parent=None):
        super().__init__(parent)
        self.library, self.player = library, player
        self.setFixedHeight(HEIGHT)
        layout = QHBoxLayout(self)
        pad = (HEIGHT - 56) // 2
        layout.setContentsMargins(pad, pad, metric('space_m'), pad)
        layout.setSpacing(metric('space_l'))

        # Left: the song.
        now = QHBoxLayout()
        now.setContentsMargins(0, 0, 0, 0)
        now.setSpacing(metric('space_m'))
        self.cover = CoverArt(covers, 56)
        self.cover.setCursor(Qt.PointingHandCursor)
        self.cover.setToolTip('Abrir Ahora suena · Ctrl+P')
        self.cover.clicked.connect(self.cover_clicked)
        now.addWidget(self.cover)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addStretch()
        self.title = ElidedLabel('', 'body', 650, 'text_strong')
        self.artist = LinkLabel('', 'small', 400, 'muted')
        self.artist.activated.connect(self._open_artist)
        titles.addWidget(self.title)
        titles.addWidget(self.artist)
        titles.addStretch()
        now.addLayout(titles, 1)
        self.favorite = IconButton('favorite', 'Guardar en Tus me gusta · Ctrl+Shift+F', self._favorite,
                                   size=34, checkable=True)
        now.addWidget(self.favorite)
        left = QWidget()
        left.setLayout(now)
        layout.addWidget(left, 3)

        # Centre: transport over the timeline.
        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(2)
        transport = QHBoxLayout()
        transport.setSpacing(metric('space_xs'))
        transport.addStretch()
        self.shuffle = IconButton('shuffle', 'Aleatorio · Ctrl+S', lambda: player.set_shuffle(not player.shuffle),
                                  size=32, checkable=True, dot=True)
        self.previous = IconButton('skip_previous', 'Anterior · Ctrl+←', player.previous, size=34)
        self.play = IconButton('play_arrow', 'Reproducir · Espacio', player.toggle, 'filled', 40)
        self.next = IconButton('skip_next', 'Siguiente · Ctrl+→', player.next, size=34)
        self.repeat = IconButton('repeat', 'Repetir · Ctrl+R', player.cycle_repeat, size=32, checkable=True, dot=True)
        for button in (self.shuffle, self.previous, self.play, self.next, self.repeat):
            button.setFocusPolicy(Qt.TabFocus)
            transport.addWidget(button)
        transport.addStretch()
        center.addLayout(transport)
        timeline = QHBoxLayout()
        timeline.setSpacing(metric('space_s'))
        self.elapsed = TimeLabel(Qt.AlignRight)
        self.progress = Slider('Posición de reproducción', wavy=True, step=5 / 300)
        self.progress.setFixedHeight(14)  # 40 + 14 fits the 56 px row: no overlap, no shared repaints
        self.progress.moved.connect(self._preview_seek)
        self.progress.released.connect(self._seek)
        self.total = TimeLabel(Qt.AlignLeft)
        for label in (self.elapsed, self.total):
            label.setFixedHeight(14)
        timeline.addWidget(self.elapsed)
        timeline.addWidget(self.progress, 1)
        timeline.addWidget(self.total)
        center.addLayout(timeline)
        middle = QWidget()
        middle.setLayout(center)
        middle.setMaximumWidth(640)
        layout.addWidget(middle, 4)

        # Right: lyrics, queue, volume.
        tools = QHBoxLayout()
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(2)
        tools.addStretch()
        self.panel_buttons = {}
        for key, symbol, label in (('lyrics', 'lyrics', 'Letra · Ctrl+L'), ('queue', 'queue_music', 'Cola · Ctrl+Q')):
            button = IconButton(symbol, label, lambda key=key: self.panel_requested.emit(key), size=34, checkable=True)
            button.setAutoExclusive(False)
            self.panel_buttons[key] = button
            tools.addWidget(button)
        self.mute = IconButton('volume_up', 'Silenciar · M', player.toggle_mute, size=34)
        tools.addWidget(self.mute)
        self.volume = Slider('Volumen', step=.05)
        self.volume.setFixedWidth(100)
        self.volume.released.connect(lambda value: player.set_volume(round(value * 100)))
        self.volume.moved.connect(lambda value: player.set_volume(round(value * 100)))
        tools.addWidget(self.volume)
        right = QWidget()
        right.setLayout(tools)
        layout.addWidget(right, 3)

        player.track_changed.connect(lambda _: self.refresh_track())
        player.state_changed.connect(self.refresh_state)
        player.queue_changed.connect(self.refresh_state)
        player.position_changed.connect(self._position)
        player.duration_changed.connect(lambda _: self._position(player.position))
        library.favorites_changed.connect(self.refresh_track)
        self.refresh_track()
        self.refresh_state()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('surface'))
        radius = tokens()['radius_l']
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)

    # ---------------------------------------------------------------- render
    def refresh_track(self):
        key = self.player.current
        track = self.library.track(key) if key else {}
        self.cover.set_track(key)
        self.title.setText(track.get('title', 'Nada sonando'))
        self.artist.setText(track.get('artist', 'Elige una canción'))
        self.favorite.setEnabled(bool(key))
        self.favorite.setChecked(bool(key) and key in self.library.favorites)
        self.favorite.set_label('Quitar de Tus me gusta' if self.favorite.isChecked() else 'Guardar en Tus me gusta')
        self._position(self.player.position)

    def refresh_state(self):
        player = self.player
        self.play.set_symbol('play_arrow' if player.paused or player.ended else 'pause')
        self.play.set_label(('Reproducir' if player.paused else 'Pausar') + ' · Espacio')
        self.play.setEnabled(bool(player.current or self.library.all_keys()))
        self.shuffle.setChecked(player.shuffle)
        self.repeat.setChecked(player.repeat != 'off')
        self.repeat.set_symbol('repeat_one' if player.repeat == 'one' else 'repeat')
        self.repeat.set_label(REPEAT_LABELS[player.repeat])
        self.previous.setEnabled(player.can_previous())
        self.next.setEnabled(player.can_next())
        self.progress.setEnabled(bool(player.current))
        self.progress.set_playing(player.playing)
        muted = player.muted or not player.volume
        self.mute.set_symbol('volume_off' if muted else 'volume_down' if player.volume < 50 else 'volume_up')
        self.mute.set_label('Activar sonido' if muted else 'Silenciar')
        if not self.volume.dragging:
            self.volume.set_value(0 if player.muted else player.volume / 100)

    def set_panel(self, key):
        for name, button in self.panel_buttons.items():
            button.setChecked(name == key)

    def _position(self, seconds):
        duration = self.player.duration
        if not self.progress.dragging:
            self.progress.set_value(seconds / duration if duration else 0)
            self.elapsed.setText(stamp(seconds))
        self.total.setText(stamp(duration))

    def _preview_seek(self, value):
        self.elapsed.setText(stamp(value * self.player.duration))

    def _seek(self, value):
        self.player.seek(value * self.player.duration)

    def _favorite(self):
        if self.player.current:
            self.library.toggle_favorite(self.player.current)

    def _open_artist(self):
        names = artists(self.library.track(self.player.current)) if self.player.current else []
        if names:
            self.artist_requested.emit(names[0])

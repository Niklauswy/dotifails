"""Inicio: an editorial page built from the local library.

Date and greeting, a bento of hero tiles (keep listening, favourites, a
shuffle mix), then shelves in different shapes: plain covers, posters tinted
by their artwork, a ranked chart grid and artists in M3 cookies.
"""
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..library import FAVORITES, RECENT, Collection
from .cards import BentoTile, Card, ChartRow, PosterCard, Shelf
from .style import metric, songs, text_font

DAYS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
          'noviembre', 'diciembre')


def greeting():
    hour = time.localtime().tm_hour
    return 'Buenos días' if 5 <= hour < 12 else 'Buenas tardes' if 12 <= hour < 20 else 'Buenas noches'


def today():
    now = time.localtime()
    return f'{DAYS[now.tm_wday]} {now.tm_mday} de {MONTHS[now.tm_mon - 1]}'


class Bento(QWidget):
    """Hero row: one wide tile and two square-ish ones; stacks when narrow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(metric('space_m'))
        self.tiles = []
        self._wide = None

    def set_tiles(self, tiles):
        for tile in self.tiles:
            self.grid.removeWidget(tile)
            tile.hide()
            tile.deleteLater()
        self.tiles = tiles
        self._wide = None
        self._arrange()

    def _arrange(self):
        wide = self.width() >= 780
        if wide == self._wide or not self.tiles:
            return
        self._wide = wide
        for tile in self.tiles:
            self.grid.removeWidget(tile)
        for column in range(4):
            self.grid.setColumnStretch(column, 0)
        if wide:
            self.grid.addWidget(self.tiles[0], 0, 0, 1, 2)
            for index, tile in enumerate(self.tiles[1:3]):
                self.grid.addWidget(tile, 0, 2 + index)
            for column in range(4):
                self.grid.setColumnStretch(column, 1)
        else:
            self.grid.addWidget(self.tiles[0], 0, 0, 1, 2)
            for index, tile in enumerate(self.tiles[1:3]):
                self.grid.addWidget(tile, 1, index)
            for column in range(2):
                self.grid.setColumnStretch(column, 1)
        for tile in self.tiles:
            tile.setFixedHeight(200)
            tile.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange()


class HomePage(QScrollArea):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.actions = actions
        self.library, self.covers, self.player = actions.library, actions.covers, actions.player
        self.tiles = []
        self.dirty = True
        self.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        pad = metric('space_xl') + metric('space_s')
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(metric('space_xl') + metric('space_s'))
        header = QVBoxLayout()
        header.setSpacing(0)
        self.date = QLabel()
        font = text_font('small', 700)
        font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 1.2)
        self.date.setFont(font)
        self.date.setObjectName('muted')
        header.addWidget(self.date)
        self.title = QLabel()
        self.title.setFont(text_font('title', 800, 1.55))
        header.addWidget(self.title)
        layout.addLayout(header)
        layout.addSpacing(-metric('space_m'))
        self.bento = Bento()
        layout.addWidget(self.bento)
        self.recent = Shelf('Escuchado recientemente')
        self.recent.show_all.connect(lambda: actions.navigate.emit(('collection', RECENT)))
        self.playlists = Shelf('Tus playlists', item_width=PosterCard.WIDTH, extra_height=64,
                               subtitle='Listas que guardaste o creaste')
        self.chart = Shelf('Lo que más escuchas', item_width=290, item_height=ChartRow.HEIGHT, rows=3,
                           subtitle='Tus canciones más reproducidas')
        self.albums = Shelf('Álbumes')
        self.albums.show_all.connect(lambda: actions.navigate.emit(('albums',)))
        self.artists = Shelf('Tus artistas', item_width=150)
        self.artists.show_all.connect(lambda: actions.navigate.emit(('artists',)))
        self.shelves = (self.recent, self.playlists, self.chart, self.albums, self.artists)
        for shelf in self.shelves:
            layout.addWidget(shelf)
        layout.addStretch()
        self.setWidget(content)

        self._timer = QTimer(self, singleShot=True, interval=120)
        self._timer.timeout.connect(self.rebuild)
        for signal in (self.library.changed, self.library.history_changed, self.library.favorites_changed):
            signal.connect(self.invalidate)
        self.player.track_changed.connect(lambda _: self._refresh_bento())
        self.player.state_changed.connect(self._sync_playing)

    def invalidate(self):
        self.dirty = True
        if self.isVisible():
            self._timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        self._header()
        if self.dirty:
            self.rebuild()

    def _header(self):
        self.date.setText(today().upper())
        self.title.setText(greeting())

    # ----------------------------------------------------------------- build
    def _collection_card(self, collection, card_type=Card):
        round_cover = collection.kind == 'artist'
        subtitle = (songs(len(collection.keys)) if round_cover
                    else f'{collection.label} · {songs(len(collection.keys))}')
        tile = card_type(self.covers, collection.title, subtitle, collection=collection, round_cover=round_cover,
                         placeholder='person' if round_cover else 'queue_music')
        tile.opened.connect(lambda: self.actions.navigate.emit(('collection', collection.id)))
        tile.play_requested.connect(lambda: self.actions.toggle_collection(collection))
        return tile

    def _track_card(self, key, context):
        track = self.library.track(key)
        tile = Card(self.covers, track.get('title', ''), track.get('artist', ''), track=key, placeholder='music_note')
        tile.opened.connect(lambda: self._play_track(key, context))
        tile.play_requested.connect(lambda: self._play_track(key, context))
        return tile

    def _play_track(self, key, context):
        if key == self.player.current:
            self.player.toggle()
        else:
            self.player.play(key, context.keys, context.id)

    def _bento(self, favorites, recent):
        current = self.player.current or (recent.keys[0] if recent.keys else None)
        if current:
            track = self.library.track(current)
            eyebrow = 'Sonando ahora' if self.player.current else 'Sigue escuchando'
            resume = BentoTile(self.covers, track.get('title', ''), track.get('artist', ''), 'resume',
                               eyebrow=eyebrow, track=current, placeholder='music_note')
            resume.opened.connect(lambda: self._resume(current, recent, open_player=True))
            resume.play_requested.connect(lambda: self._resume(current, recent))
        else:
            resume = BentoTile(self.covers, 'Empieza por aquí', 'Toda tu biblioteca, al azar', 'resume',
                               eyebrow='Bienvenido')
            resume.opened.connect(self.actions.shuffle_library)
            resume.play_requested.connect(self.actions.shuffle_library)
        liked = BentoTile(self.covers, 'Tus me gusta', songs(len(favorites.keys)), 'accent', symbol='favorite',
                          eyebrow='Colección', collection=favorites)
        liked.opened.connect(lambda: self.actions.navigate.emit(('collection', FAVORITES)))
        mix = BentoTile(self.covers, 'Mezcla', 'Toda tu biblioteca, al azar', 'tonal', symbol='shuffle',
                        eyebrow='Para ti')
        mix.opened.connect(self.actions.shuffle_library)
        mix.setEnabled(bool(self.library.all_keys()))
        return [resume, liked, mix]

    def _resume(self, key, recent, open_player=False):
        if key == self.player.current:
            if not open_player:
                self.player.toggle()
        else:
            self.player.play(key, recent.keys or [key], recent.id)
        if open_player:
            self.actions.show_player.emit('now')

    def _refresh_bento(self):
        """A new song only changes the hero; shelves keep their widgets."""
        if not self.isVisible():
            self.dirty = True
            return
        old = self.bento.tiles
        self.bento.set_tiles(self._bento(self.library.collection(FAVORITES), self.library.collection(RECENT)))
        self.tiles = [tile for tile in self.tiles if tile not in old] + self.bento.tiles
        self._sync_playing()

    def rebuild(self):
        self.dirty = False
        self._header()
        collections = self.library.collections()
        favorites = next((c for c in collections if c.id == FAVORITES), self.library.collection(FAVORITES))
        others = [c for c in collections if c.id != FAVORITES and c.keys]
        recent = self.library.collection(RECENT)
        self.bento.set_tiles(self._bento(favorites, recent))
        self.recent.set_items([self._track_card(k, recent) for k in recent.keys[:12]], expandable=len(recent.keys) > 6)
        self.playlists.set_items([self._collection_card(c, PosterCard) for c in others if c.kind != 'album'])
        albums = [c for c in others if c.kind == 'album']
        self.albums.set_items([self._collection_card(c) for c in albums], expandable=len(albums) > 4)
        most = [k for k in self.library.store.most_played(9) if self.library.available(k)]
        top = Collection('top', 'Lo que más escuchas', 'recent', most)
        rows = []
        for rank, key in enumerate(most, 1):
            track = self.library.track(key)
            row = ChartRow(self.covers, rank, track.get('title', ''), track.get('artist', ''), key)
            row.play_requested.connect(lambda key=key: self._play_track(key, top))
            rows.append(row)
        self.chart.set_items(rows)
        ranked = sorted(self.library.artists().items(), key=lambda item: -len(item[1]))[:12]
        self.artists.set_items([self._collection_card(self.library.collection('artist:' + name)) for name, _ in ranked],
                               expandable=True)
        self.tiles = self.bento.tiles + [tile for shelf in self.shelves for tile in shelf.row.items]
        self._sync_playing()

    def _sync_playing(self):
        context, current, playing = self.player.queue.context, self.player.current, self.player.playing
        for tile in self.tiles:
            if isinstance(tile, BentoTile) and tile.style != 'resume':
                continue
            active = playing and (tile.collection.id == context if tile.collection else tile.track == current)
            if active != tile.playing:
                tile.playing = active
                tile.update()

"""Search: browse tiles when empty; top result, songs, artists and lists otherwise."""
from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from music_library import normalize
from theme_tokens import color, tokens
from .cards import Card, Shelf, Tile
from .shapes import filled
from .widgets import paint_favorites_cover
from .style import metric, songs, text_font
from .tracks import TrackView

class BrowseTile(Tile):
    """Full-bleed artwork tile with the title on a soft scrim (Explorar)."""

    def __init__(self, covers, collection, parent=None):
        super().__init__(covers, collection.title, collection=collection, parent=parent)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        radius = tokens()['radius_m']
        rect = QRectF(self.rect())
        shape = QPainterPath()
        shape.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(shape)
        key = self.art_key()
        path = self.covers.path(key) if key else None
        art = filled(path, self.width(), self.height(), self.devicePixelRatioF()) if path else None
        if self.collection.kind == 'favorites':
            paint_favorites_cover(painter, rect, 0)
        elif art is not None:
            # Slow zoom on hover: the artwork leans towards the pointer.
            scale = 1 + .04 * self.layer.amount
            painter.translate(rect.center())
            painter.scale(scale, scale)
            painter.translate(-rect.center())
            painter.drawPixmap(self.rect(), art)
            painter.resetTransform()
        else:
            painter.fillRect(rect, color('surface_raised'))
        gradient = QLinearGradient(0, self.height() * .35, 0, self.height())
        gradient.setColorAt(0, color('scrim', 0))
        gradient.setColorAt(1, color('scrim', 200))
        painter.fillRect(rect, gradient)
        painter.restore()
        pad = metric('space_m')
        eyebrow = text_font('caption', 700)
        eyebrow.setLetterSpacing(eyebrow.SpacingType.AbsoluteSpacing, 1.1)
        painter.setFont(eyebrow)
        painter.setPen(color('on_hud', 200))
        painter.drawText(QRect(pad, pad, self.width() - 2 * pad, 16), Qt.AlignLeft | Qt.AlignVCenter,
                         self.collection.label.upper())
        painter.setFont(text_font('heading', 800, 1.1))
        painter.setPen(color('on_hud'))
        painter.drawText(QRect(pad, self.height() // 2, self.width() - 2 * pad, self.height() // 2 - pad),
                         Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap, self.title)
        self.paint_focus(painter, self.rect(), radius)


class TopResult(Tile):
    """Large card for the best match (artist or song)."""

    def __init__(self, covers, title, kind_label, round_cover=False, **kwargs):
        super().__init__(covers, title, kind_label, round_cover=round_cover, **kwargs)
        self.setMinimumHeight(240)

    def play_rect(self):
        return QRect(self.width() - 56 - metric('space_l'), self.height() - 56 - metric('space_l'), 56, 56)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = tokens()['radius_m']
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('tint', round(8 + 10 * self.layer.amount)))
        painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
        pad = metric('space_l')
        side = 96
        self.draw_cover(painter, QRect(pad, pad, side, side), side / 2 if self.round_cover else 8)
        painter.setFont(text_font('title', 800, 1.2))
        painter.setPen(color('text_strong'))
        width = self.width() - 2 * pad
        painter.drawText(QRect(pad, pad + side + metric('space_m'), width, 40), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(self.title, Qt.ElideRight, width))
        painter.setFont(text_font('small', 600))
        label = self.subtitle
        chip = QRectF(pad, pad + side + metric('space_m') + 46, painter.fontMetrics().horizontalAdvance(label) + 20, 26)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('fill'))
        painter.drawRoundedRect(chip, 13, 13)
        painter.setPen(color('text'))
        painter.drawText(chip, Qt.AlignCenter, label)
        self.draw_play(painter, self.play_rect())
        self.paint_focus(painter, self.rect(), radius)


class SearchPage(QScrollArea):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.actions = actions
        self.library, self.covers, self.player = actions.library, actions.covers, actions.player
        self.query = ''
        self.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        pad = metric('space_xl')
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(metric('space_xl'))

        self.browse = Shelf('Explorar', item_width=230, item_height=150, rows=0,
                            subtitle='Tus listas, álbumes y artistas más escuchados')
        self.browse.title.setFont(text_font('title', 800, 1.4))
        layout.addWidget(self.browse)

        self.results = QWidget()
        results = QVBoxLayout(self.results)
        results.setContentsMargins(0, 0, 0, 0)
        results.setSpacing(metric('space_xl'))
        top_row = QHBoxLayout()
        top_row.setSpacing(metric('space_l'))
        top_column = QVBoxLayout()
        top_column.addWidget(self._heading('Resultado principal'))
        self.top_holder = QVBoxLayout()
        top_column.addLayout(self.top_holder)
        top_column.addStretch()
        top_row.addLayout(top_column, 2)
        songs_column = QVBoxLayout()
        songs_header = QHBoxLayout()
        songs_header.addWidget(self._heading('Canciones'), 1)
        self.all_songs = QPushButton('Ver todas')
        self.all_songs.clicked.connect(lambda: actions.navigate.emit(('collection', 'search:' + self.query)))
        songs_header.addWidget(self.all_songs)
        songs_column.addLayout(songs_header)
        self.songs = TrackView(self.library, self.covers, self.player, numbered=False)
        self.songs.play_requested.connect(self._play_song)
        self.songs.menu_requested.connect(lambda keys, pos: actions.track_menu(keys, pos))
        self.songs.artist_requested.connect(lambda name: actions.navigate.emit(('collection', 'artist:' + name)))
        songs_column.addWidget(self.songs)
        songs_column.addStretch()
        top_row.addLayout(songs_column, 3)
        results.addLayout(top_row)
        self.artists = Shelf('Artistas')
        self.lists = Shelf('Playlists y álbumes')
        results.addWidget(self.artists)
        results.addWidget(self.lists)
        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setObjectName('muted')
        results.addWidget(self.empty)
        layout.addWidget(self.results)
        layout.addStretch()
        self.setWidget(content)
        self.top = None
        self._pending = ''
        self._debounce = QTimer(self, singleShot=True, interval=140)
        self._debounce.timeout.connect(lambda: self.set_query(self._pending))
        self.library.changed.connect(lambda: self.set_query(self.query, force=True))

    def _heading(self, text):
        label = QLabel(text)
        label.setFont(text_font('heading', 700, 1.25))
        return label

    def type_query(self, query):
        """Live typing: render once the user pauses."""
        self._pending = query
        self._debounce.start()

    def set_query(self, query, force=False):
        query = query.strip()
        if query == self.query and not force and self.browse.row.items:
            return
        self.query = query
        searching = bool(normalize(query))
        self.browse.setVisible(not searching)
        self.results.setVisible(searching)
        if searching:
            self._render_results()
        elif not self.browse.row.items or force:
            self._render_browse()

    # ---------------------------------------------------------------- browse
    def _render_browse(self):
        collections = [c for c in self.library.collections() if c.keys]
        ranked = sorted(self.library.artists().items(), key=lambda item: -len(item[1]))[:8]
        collections += [self.library.collection('artist:' + name) for name, _ in ranked]
        tiles = []
        for collection in collections:
            tile = BrowseTile(self.covers, collection)
            tile.opened.connect(lambda c=collection: self.actions.navigate.emit(('collection', c.id)))
            tiles.append(tile)
        self.browse.set_items(tiles)

    # --------------------------------------------------------------- results
    def _render_results(self):
        query = normalize(self.query)
        keys = self.library.search(self.query)
        artist_names = [name for name in self.library.artists() if query in normalize(name)]
        artist_names.sort(key=lambda name: (not normalize(name).startswith(query), -len(self.library.artists()[name])))
        lists = [c for c in self.library.collections() if query in normalize(c.title) and c.keys]

        self.songs.set_keys(keys[:5])
        self.songs.fit_height(5)
        self.all_songs.setVisible(len(keys) > 5)
        self.all_songs.setText(f'Ver las {songs(len(keys))}')
        self._set_top(artist_names, keys)
        artist_cards = []
        for name in artist_names[:12]:
            collection = self.library.collection('artist:' + name)
            card = Card(self.covers, name, 'Artista', collection=collection, round_cover=True, placeholder='person')
            card.opened.connect(lambda c=collection: self.actions.navigate.emit(('collection', c.id)))
            card.play_requested.connect(lambda c=collection: self.actions.toggle_collection(c))
            artist_cards.append(card)
        self.artists.set_items(artist_cards)
        list_cards = []
        for collection in lists[:12]:
            card = Card(self.covers, collection.title, f'{collection.label} · {songs(len(collection.keys))}',
                        collection=collection)
            card.opened.connect(lambda c=collection: self.actions.navigate.emit(('collection', c.id)))
            card.play_requested.connect(lambda c=collection: self.actions.toggle_collection(c))
            list_cards.append(card)
        self.lists.set_items(list_cards)
        nothing = not (keys or artist_names or lists)
        self.empty.setVisible(nothing)
        self.empty.setText(f'No encontramos «{self.query}» en tu biblioteca.\n'
                           'Prueba otras palabras o búscalo en «Añadir música».')

    def _set_top(self, artist_names, keys):
        if self.top is not None:
            self.top.hide()
            self.top.deleteLater()
            self.top = None
        if artist_names:
            collection = self.library.collection('artist:' + artist_names[0])
            self.top = TopResult(self.covers, collection.title, 'Artista', round_cover=True,
                                 collection=collection, placeholder='person')
            self.top.opened.connect(lambda: self.actions.navigate.emit(('collection', collection.id)))
            self.top.play_requested.connect(lambda: self.actions.toggle_collection(collection))
        elif keys:
            key = keys[0]
            track = self.library.track(key)
            self.top = TopResult(self.covers, track.get('title', ''), 'Canción · ' + track.get('artist', ''),
                                 track=key, placeholder='music_note')
            self.top.opened.connect(lambda: self._play_song(key))
            self.top.play_requested.connect(lambda: self._play_song(key))
        if self.top is not None:
            self.top_holder.addWidget(self.top)

    def _play_song(self, key):
        self.player.play(key, self.library.search(self.query), 'search:' + self.query)

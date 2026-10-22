"""Library grids: every artist (in cookies) or every album, as a wall of artwork."""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from music_library import normalize
from .cards import Card, FlowRow
from .style import metric, songs, text_font

TITLES = {'artists': 'Artistas', 'albums': 'Álbumes'}


class GridPage(QScrollArea):
    def __init__(self, actions, kind, parent=None):
        super().__init__(parent)
        self.actions, self.kind = actions, kind
        self.library, self.covers = actions.library, actions.covers
        self.dirty = True
        self.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        pad = metric('space_xl') + metric('space_s')
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(metric('space_l'))
        title = QLabel(TITLES[kind])
        title.setFont(text_font('title', 800, 1.4))
        layout.addWidget(title)
        self.count = QLabel()
        self.count.setObjectName('muted')
        layout.addWidget(self.count)
        self.grid = FlowRow(150 if kind == 'artists' else Card.WIDTH, rows=0, extra_height=Card.CAPTION)
        layout.addWidget(self.grid)
        self.empty = QLabel('Todavía no hay nada aquí. Añade música desde «Añadir música».')
        self.empty.setObjectName('muted')
        layout.addWidget(self.empty)
        layout.addStretch()
        self.setWidget(content)
        self._timer = QTimer(self, singleShot=True, interval=150)
        self._timer.timeout.connect(self.rebuild)
        self.library.changed.connect(self.invalidate)

    def invalidate(self):
        self.dirty = True
        if self.isVisible():
            self._timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        if self.dirty:
            self.rebuild()

    def rebuild(self):
        self.dirty = False
        if self.kind == 'artists':
            ranked = sorted(self.library.artists().items(), key=lambda item: (-len(item[1]), normalize(item[0])))
            collections = [self.library.collection('artist:' + name) for name, _ in ranked]
            label = 'artista' if len(collections) == 1 else 'artistas'
        else:
            collections = sorted((c for c in self.library.collections() if c.kind == 'album' and c.keys),
                                 key=lambda c: normalize(c.title))
            label = 'álbum' if len(collections) == 1 else 'álbumes'
        cards = []
        for collection in collections:
            artist = collection.kind == 'artist'
            subtitle = songs(len(collection.keys)) if artist else self._album_artist(collection)
            card = Card(self.covers, collection.title, subtitle, collection=collection, round_cover=artist,
                        placeholder='person' if artist else 'album')
            card.opened.connect(lambda c=collection: self.actions.navigate.emit(('collection', c.id)))
            card.play_requested.connect(lambda c=collection: self.actions.toggle_collection(c))
            cards.append(card)
        self.grid.set_items(cards)
        self.count.setText(f'{len(collections)} {label}')
        self.empty.setVisible(not collections)

    def _album_artist(self, collection):
        names = {self.library.track(k).get('artist', '').split(',')[0].strip() for k in collection.keys[:6]}
        names.discard('')
        return names.pop() if len(names) == 1 else 'Varios artistas'

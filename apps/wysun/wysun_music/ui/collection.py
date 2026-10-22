"""Playlist / album / artist / favourites page.

Albums and playlists open with the artwork beside a large title, the artist
in the accent colour and text buttons (Apple Music's reading order); artists
get their portrait in an M3 cookie. A blurred wash of the artwork tints the top.
"""
from PySide6.QtCore import QEasingCurve, QRect, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QFontMetrics, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QMenu, QVBoxLayout, QWidget

from music_library import artists, normalize
from theme_tokens import color, tokens
from ui_motion import reduced_motion
from .shapes import artwork, blurred, clip_pixmap, cookie
from .style import long_duration, metric, songs, text_font
from .tracks import TrackHeader, TrackView
from .widgets import IconButton, PillButton, draw_art, paint_favorites_cover

SORTS = (('custom', 'Orden personalizado'), ('title', 'Título'), ('artist', 'Artista'),
         ('album', 'Álbum'), ('duration', 'Duración'))
FULL_HEIGHT, COMPACT_HEIGHT = 268, 76
WASH_HEIGHT = 420


def lead_artist(library, keys):
    """The album's artist when its songs agree, else «Varios artistas»."""
    names = {(artists(library.track(k)) or [''])[0] for k in keys[:8]}
    names.discard('')
    return names.pop() if len(names) == 1 else 'Varios artistas' if names else ''


class Hero(QWidget):
    """Cover, kind, big title and summary; collapses as the list scrolls."""

    def __init__(self, covers, parent=None):
        super().__init__(parent)
        self.covers = covers
        self.collection = None
        self.byline = ''
        self.meta = ''
        self.progress = 0.0  # 0 = full, 1 = compact
        self.animation = QVariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self._set_progress)
        self.setFixedHeight(FULL_HEIGHT)
        covers.updated.connect(self._cover_updated)

    def set_collection(self, collection, byline, meta):
        self.collection, self.byline, self.meta = collection, byline, meta
        self.setAccessibleName(collection.title)
        self.update()

    def _cover_updated(self, key):
        if self.collection and (key == self.collection.id or key in self.collection.keys[:12]):
            self.update()
            self.parentWidget().update()

    def set_compact(self, compact):
        target = 1.0 if compact else 0.0
        if self.animation.endValue() == target and self.animation.state() == QVariantAnimation.Running:
            return
        self.animation.stop()
        if reduced_motion(self.window()):
            self._set_progress(target)
            return
        self.animation.setDuration(metric('motion_enter'))
        self.animation.setStartValue(self.progress)
        self.animation.setEndValue(target)
        self.animation.start()

    def _set_progress(self, value):
        self.progress = float(value)
        self.setFixedHeight(round(FULL_HEIGHT + (COMPACT_HEIGHT - FULL_HEIGHT) * self.progress))

    def _title_font(self, width):
        """Largest display size whose title fits in two lines."""
        for scale in (2.4, 2.0, 1.65, 1.35):
            font = text_font('title', 850, scale)
            bounds = QFontMetrics(font).boundingRect(QRect(0, 0, width, 1000), Qt.TextWordWrap, self.collection.title)
            if bounds.height() <= QFontMetrics(font).height() * 2 + 2 and bounds.width() <= width:
                return font
        return text_font('title', 850, 1.2)

    def _paint_cover(self, painter, cover):
        kind = self.collection.kind
        if kind == 'artist':
            outline = cookie(QRectF(cover), 9)
            key = self.collection.id if self.covers.path(self.collection.id) else (self.collection.keys or [None])[0]
            path = self.covers.path(key) if key else None
            pixmap = artwork(path, cover.width(), self.devicePixelRatioF()) if path else None
            if pixmap is not None:
                clip_pixmap(pixmap, outline, painter, cover)
            else:
                painter.setBrush(color('surface_raised'))
                painter.drawPath(outline)
            return
        radius = min(tokens()['radius_m'], cover.width() / 8)
        if not self.progress:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('shadow'))
            painter.drawRoundedRect(QRectF(cover).adjusted(4, 10, -4, 6), radius, radius)
        if kind == 'favorites':
            paint_favorites_cover(painter, QRectF(cover), radius)
        else:
            draw_art(painter, cover, self.covers.collection_pixmap(self.collection, cover.width(), radius,
                                                                  self.devicePixelRatioF()), radius, 'queue_music')

    def paintEvent(self, _event):
        if self.collection is None:
            return
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        pad = metric('space_xl') + metric('space_s')
        if self.progress:
            side = max(0, self.height() - 2 * metric('space_m'))
            top = (self.height() - side) // 2
        else:
            side = self.height() - pad - metric('space_s')
            top = pad
        cover = QRect(pad, top, side, side)
        self._paint_cover(painter, cover)
        left = cover.right() + pad
        width = self.width() - left - pad
        fade = max(0.0, 1.0 - self.progress * 2)
        if self.progress:
            font = text_font('heading', 800, 1.4)
            painter.setFont(font)
            painter.setPen(color('text_strong'))
            painter.drawText(QRect(left, 0, width, self.height()), Qt.AlignLeft | Qt.AlignVCenter,
                             QFontMetrics(font).elidedText(self.collection.title, Qt.ElideRight, width))
            return
        # Bottom-aligned text block, like a record sleeve.
        title_font = self._title_font(width)
        title_metrics = QFontMetrics(title_font)
        title_box = title_metrics.boundingRect(QRect(0, 0, width, 1000), Qt.TextWordWrap, self.collection.title)
        y = cover.bottom() - 26 - 28 - title_box.height()
        painter.setOpacity(fade)
        eyebrow = text_font('caption', 700)
        eyebrow.setLetterSpacing(eyebrow.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(eyebrow)
        painter.setPen(color('muted'))
        painter.drawText(QRect(left, y - 24, width, 20), Qt.AlignLeft | Qt.AlignBottom, self.collection.label.upper())
        painter.setFont(title_font)
        painter.setPen(color('text_strong'))
        painter.drawText(QRect(left, y, width, title_box.height()), Qt.AlignLeft | Qt.TextWordWrap, self.collection.title)
        y += title_box.height() + 2
        if self.byline:
            painter.setFont(text_font('heading', 600, 1.05))
            painter.setPen(color('accent'))
            painter.drawText(QRect(left, y, width, 28), Qt.AlignLeft | Qt.AlignVCenter,
                             painter.fontMetrics().elidedText(self.byline, Qt.ElideRight, width))
        painter.setFont(text_font('small', 500))
        painter.setPen(color('muted'))
        painter.drawText(QRect(left, y + 28, width, 22), Qt.AlignLeft | Qt.AlignVCenter, self.meta)
        painter.setOpacity(1.0)


class CollectionPage(QWidget):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.actions = actions
        self.library, self.covers, self.player = actions.library, actions.covers, actions.player
        self.collection = None
        self.sort = 'custom'
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.hero = Hero(self.covers)
        layout.addWidget(self.hero)

        bar = QHBoxLayout()
        pad = metric('space_xl') + metric('space_s')
        bar.setContentsMargins(pad, metric('space_l'), pad, metric('space_m'))
        bar.setSpacing(metric('space_m'))
        self.play_button = PillButton('play_arrow', 'Reproducir', self._toggle, 'filled')
        self.shuffle_button = PillButton('shuffle', 'Aleatorio', self._shuffle, 'tonal')
        self.more_button = IconButton('more_horiz', 'Más opciones', self._more, 'tonal', 44)
        for widget in (self.play_button, self.shuffle_button, self.more_button):
            bar.addWidget(widget)
        bar.addStretch()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText('Buscar en la lista')
        self.filter.setClearButtonEnabled(True)
        self.filter.setFixedWidth(220)
        self.filter.textChanged.connect(self._render)
        bar.addWidget(self.filter)
        self.sort_button = IconButton('sort', 'Ordenar', self._sort_menu, size=40)
        bar.addWidget(self.sort_button)
        layout.addLayout(bar)

        body = QVBoxLayout()
        body.setContentsMargins(metric('space_l'), 0, metric('space_l'), 0)
        body.setSpacing(0)
        self.header = TrackHeader()
        body.addWidget(self.header)
        self.tracks = TrackView(self.library, self.covers, self.player)
        self.tracks.header = self.header
        self.tracks.play_requested.connect(self._play)
        self.tracks.menu_requested.connect(lambda keys, pos: actions.track_menu(keys, pos, self.collection))
        self.tracks.artist_requested.connect(lambda name: actions.navigate.emit(('collection', 'artist:' + name)))
        self.tracks.verticalScrollBar().valueChanged.connect(lambda value: self.hero.set_compact(value > 24))
        self.tracks.striped = True
        body.addWidget(self.tracks, 1)
        layout.addLayout(body, 1)

        self.player.state_changed.connect(self._sync_buttons)
        self.player.track_changed.connect(lambda _: self._sync_buttons())
        self.library.changed.connect(self.reload)
        self.library.favorites_changed.connect(self._favorites_changed)

    # ------------------------------------------------------------ navigation
    def open(self, key):
        collection = self.library.collection(key)
        if collection is None:
            return False
        reopened = self.collection is not None and self.collection.id == key
        self.collection = collection
        if not reopened:
            self.filter.blockSignals(True)
            self.filter.clear()
            self.filter.blockSignals(False)
            self.sort = 'custom'
            self.tracks.scrollToTop()
            self.hero.set_compact(False)
        self._render()
        return True

    def reload(self):
        if self.collection is not None and self.isVisible():
            self.open(self.collection.id)

    def _favorites_changed(self):
        if self.collection is not None and self.collection.kind == 'favorites':
            self.reload()

    # ---------------------------------------------------------------- render
    def _render(self):
        collection = self.collection
        keys = list(collection.keys)
        query = normalize(self.filter.text())
        if query:
            keys = [k for k in keys if query in normalize(self.library.track(k).get('title', '') + ' '
                                                          + self.library.track(k).get('artist', ''))]
        if self.sort != 'custom':
            sorters = {'title': lambda k: normalize(self.library.track(k).get('title', '')),
                       'artist': lambda k: normalize(self.library.track(k).get('artist', '')),
                       'album': lambda k: normalize(self.library.album(k)),
                       'duration': self.library.duration}
            keys.sort(key=sorters[self.sort])
        # Albums read like a sleeve: numbers, no repeated covers.
        self.tracks.show_covers = self.header.show_covers = collection.kind != 'album'
        self.tracks.album_column = collection.kind != 'album'
        self.tracks.set_keys(keys)
        total = sum(self.library.duration(k) for k in collection.keys)
        meta = [songs(len(collection.keys)), long_duration(total)]
        if collection.date:
            meta.insert(0, 'Actualizado ' + collection.date)
        byline = {'album': lead_artist(self.library, collection.keys), 'user': 'Tu playlist',
                  'favorites': 'Guardadas por ti', 'recent': 'Tus últimas canciones'}.get(collection.kind, '')
        if collection.kind == 'artist':
            albums = self.library.artist_albums(collection.title)
            byline = f'{len(albums)} álbum' + ('es' if len(albums) != 1 else '') if albums else ''
        self.hero.set_collection(collection, byline, ' · '.join(meta))
        self.play_button.setEnabled(bool(collection.keys))
        self.shuffle_button.setEnabled(bool(collection.keys))
        self.filter.setVisible(len(collection.keys) > 8)
        self._sync_buttons()
        self.update()

    def _sync_buttons(self):
        if self.collection is None:
            return
        playing = self.actions.is_playing(self.collection.id)
        self.play_button.set_content('pause' if playing else 'play_arrow', 'Pausar' if playing else 'Reproducir')

    def paintEvent(self, _event):
        """Blurred artwork wash at the top, dissolving into the surface."""
        if self.collection is None:
            return
        key = self.collection.id if self.covers.path(self.collection.id) else next(
            (k for k in self.collection.keys[:4] if self.covers.path(k)), None)
        path = self.covers.path(key) if key else None
        backdrop = blurred(path, self.width(), WASH_HEIGHT) if path else None
        if backdrop is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = tokens()['radius_l']
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter.setClipPath(clip)
        painter.setOpacity(.55)
        painter.drawPixmap(0, 0, backdrop)
        painter.setOpacity(1.0)
        gradient = QLinearGradient(0, 0, 0, WASH_HEIGHT)
        gradient.setColorAt(0, color('surface', 90))
        gradient.setColorAt(.6, color('surface', 200))
        gradient.setColorAt(1, color('surface'))
        painter.fillRect(QRect(0, 0, self.width(), WASH_HEIGHT), gradient)

    # --------------------------------------------------------------- actions
    def _toggle(self):
        self.actions.toggle_collection(self.collection)

    def _shuffle(self):
        self.actions.play_collection(self.collection, shuffle=True)

    def _play(self, key):
        self.player.play(key, self.tracks.keys, self.collection.id)

    def _more(self):
        self.actions.collection_menu(self.collection, self.more_button.mapToGlobal(self.more_button.rect().bottomLeft()))

    def _sort_menu(self):
        menu = QMenu(self)
        for key, label in SORTS:
            action = menu.addAction(label, lambda key=key: self._set_sort(key))
            action.setCheckable(True)
            action.setChecked(key == self.sort)
        menu.exec(self.sort_button.mapToGlobal(self.sort_button.rect().bottomLeft()))

    def _set_sort(self, key):
        self.sort = key
        self._render()

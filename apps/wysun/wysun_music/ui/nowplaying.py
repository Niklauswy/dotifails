"""«Ahora suena»: the immersive full player with karaoke lyrics and the queue.

It covers the whole window: a blurred wash of the artwork with M3 shapes
scattered over it, the cover in a slowly turning Cookie-12 on the left and,
on the right, big synced lyrics (or the queue). Esc or the chevron closes it.

Performance: the backdrop (artwork wash, scrim, shapes) is rendered once per
song, size and theme into a pixmap; painting only copies the damaged part of
it, so the spinning cover and the wavy progress stay cheap at full screen.
"""
import bisect
import math

from PySide6.QtCore import QEasingCurve, QElapsedTimer, QEvent, QPoint, QPointF, QRect, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPixmap, QRadialGradient
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QMenu, QSizePolicy, QStackedWidget,
                               QVBoxLayout, QWidget)

from music_library import artists, parse_lrc
from theme_tokens import color, tokens
from ui_motion import reduced_motion
from .playerbar import REPEAT_LABELS, TimeLabel
from .shapes import Drift, blurred, grain_tile
from .style import metric, paint_symbol, stamp, text_font
from .tracks import TrackView
from .widgets import Chip, CoverArt, ElidedLabel, IconButton, LinkLabel, Slider

TABS = (('lyrics', 'Letra'), ('queue', 'A continuación'))
USER_SCROLL_HOLD_MS = 3500


class LyricsView(QWidget):
    """Painted lyric lines, large and left aligned; the current one is lit and
    followed with a smooth scroll, the rest fade with their distance from it."""

    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []          # (seconds or None, text)
        self.synced = False
        self.message = 'Reproduce una canción para ver su letra.'
        self.current = -1
        self.offset = 0.0       # vertical scroll in px
        self.hover = -1
        self._heights = []
        self._width = -1
        self._user_scroll = QElapsedTimer()
        self.animation = QVariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.valueChanged.connect(self._scroll_to)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('Letra')

    def set_message(self, message):
        self.rows, self.synced, self.message, self.current, self.offset = [], False, message, -1, 0.0
        self._width = -1
        self.update()

    def set_lyrics(self, data):
        synced = parse_lrc(data.get('synced'))
        if synced:
            self.rows, self.synced = synced, True
        elif data.get('plain'):
            self.rows, self.synced = [(None, line or ' ') for line in data['plain'].splitlines()], False
        else:
            message = 'Instrumental · no hay letra' if data.get('instrumental') else 'La letra no está disponible para esta versión.'
            self.set_message(message)
            return
        self.message, self.current, self.offset, self._width = '', -1, 0.0, -1
        self.update()

    def set_position(self, seconds):
        if not self.synced:
            return
        index = bisect.bisect_right([row[0] for row in self.rows], seconds) - 1
        if index != self.current:
            self.current = index
            self._follow()
            self.update()

    # ---------------------------------------------------------------- layout
    def _font(self):
        return text_font('title', 750, 1.15 if self.synced else .9)

    def _layout(self):
        if self._width == self.width():
            return
        self._width = self.width()
        metrics = QFontMetrics(self._font())
        width = self.width() - 2 * metric('space_l')
        gap = metric('space_l') if self.synced else metric('space_s')
        self._heights = [metrics.boundingRect(QRect(0, 0, width, 10000), Qt.TextWordWrap, text).height() + gap
                         for _, text in self.rows]

    def _top_of(self, index):
        return self.height() * .3 + sum(self._heights[:index])

    def _content_height(self):
        return self.height() * .3 + sum(self._heights) + self.height() * .5

    def _follow(self):
        self._layout()
        if self.current < 0 or (self._user_scroll.isValid() and self._user_scroll.elapsed() < USER_SCROLL_HOLD_MS):
            return
        target = self._top_of(self.current) - self.height() * .3
        target = max(0.0, min(target, max(0.0, self._content_height() - self.height())))
        self.animation.stop()
        if reduced_motion(self.window()):
            self._scroll_to(target)
            return
        self.animation.setDuration(metric('motion_enter') * 3)
        self.animation.setStartValue(self.offset)
        self.animation.setEndValue(target)
        self.animation.start()

    def _scroll_to(self, value):
        self.offset = float(value)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._width = -1

    # ----------------------------------------------------------------- input
    def wheelEvent(self, event):
        self._layout()
        self.animation.stop()
        self._user_scroll.start()
        limit = max(0.0, self._content_height() - self.height())
        self._scroll_to(max(0.0, min(limit, self.offset - event.angleDelta().y() / 2)))

    def _row_at(self, y):
        self._layout()
        position = y + self.offset - self.height() * .3
        if position < 0:
            return -1
        for index, height in enumerate(self._heights):
            if position < height:
                return index
            position -= height
        return -1

    def mouseMoveEvent(self, event):
        row = self._row_at(event.position().y()) if self.synced else -1
        if row != self.hover:
            self.hover = row
            self.setCursor(Qt.PointingHandCursor if row >= 0 else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, event):
        self.hover = -1
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        row = self._row_at(event.position().y())
        if self.synced and row >= 0 and event.button() == Qt.LeftButton:
            self._user_scroll.invalidate()
            self.seek_requested.emit(self.rows[row][0])

    # ----------------------------------------------------------------- paint
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.rows:
            centre = self.rect().center()
            paint_symbol(painter, QRect(centre.x() - 40, centre.y() - 96, 80, 80), 'lyrics', 'subtle', 56)
            painter.setFont(text_font('heading', 600))
            painter.setPen(color('muted'))
            painter.drawText(self.rect().adjusted(24, 0, -24, 0), Qt.AlignCenter | Qt.TextWordWrap, self.message)
            return
        self._layout()
        painter.setFont(self._font())
        pad = metric('space_l')
        y = self.height() * .3 - self.offset
        for index, (_, text) in enumerate(self.rows):
            height = self._heights[index]
            if y + height >= 0 and y <= self.height():
                # Lines dissolve near the top and bottom edges instead of being cut.
                edge = min(y + height * .5, self.height() - y - height * .5)
                fade = max(0.0, min(1.0, edge / (self.height() * .14)))
                if not self.synced:
                    opacity = .85
                elif index == self.current:
                    opacity = 1.0
                elif index == self.hover:
                    opacity = .7
                else:
                    distance = abs(index - self.current)
                    opacity = max(.18, .42 - distance * .05) if index > self.current else .3
                painter.setOpacity(opacity * fade)
                painter.setPen(color('text_strong'))
                painter.drawText(QRect(pad, round(y), self.width() - 2 * pad, height), Qt.AlignLeft | Qt.TextWordWrap, text)
            y += height
        painter.setOpacity(1.0)


class QueueView(QWidget):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.actions = actions
        self.library, self.player = actions.library, actions.player
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(metric('space_s'))
        self.note = ElidedLabel('', 'small', 500, 'muted')
        self.note.setContentsMargins(metric('space_s'), 0, 0, 0)
        self.note.hide()
        layout.addWidget(self.note)
        layout.addWidget(self._heading('Sonando ahora'))
        self.now = TrackView(self.library, actions.covers, self.player, numbered=False)
        self.now.play_requested.connect(lambda _: self.player.toggle())
        layout.addWidget(self.now)
        header = QHBoxLayout()
        self.upcoming_label = self._heading('A continuación')
        header.addWidget(self.upcoming_label, 1)
        self.context = ElidedLabel('', 'small', 500, 'muted')
        self.context.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.context, 1)
        layout.addLayout(header)
        self.upcoming = TrackView(self.library, actions.covers, self.player, numbered=False)
        self.upcoming.album_column = self.now.album_column = False
        self.upcoming.play_requested.connect(self._jump)
        self.upcoming.menu_requested.connect(self._menu)
        self.upcoming.setDragEnabled(False)
        layout.addWidget(self.upcoming, 1)
        self.player.queue_changed.connect(self.refresh)
        self.player.track_changed.connect(lambda _: self.refresh())
        self.refresh()

    def set_note(self, text):
        """Why the queue is showing on its own (e.g. the song has no lyrics)."""
        self.note.setText(text)
        self.note.setVisible(bool(text))

    def _heading(self, text):
        label = QLabel(text)
        label.setFont(text_font('heading', 700))
        label.setContentsMargins(metric('space_s'), metric('space_s'), 0, 0)
        return label

    def refresh(self):
        self.now.set_keys([self.player.current] if self.player.current else [])
        self.now.fit_height(1)
        upcoming = self.player.queue.upcoming()
        self.upcoming.set_keys(upcoming)
        context = self.player.queue.context
        collection = self.library.collection(context) if context else None
        self.context.setText(('De ' + collection.title) if collection and upcoming else '')

    def _jump(self, key):
        index = self.upcoming.keys.index(key) if key in self.upcoming.keys else -1
        if index >= 0:
            self.player.jump_to_upcoming(index)

    def _menu(self, keys, position):
        index = self.upcoming.currentIndex().row()
        menu = QMenu(self)
        menu.addAction('Reproducir ahora', lambda: self.player.jump_to_upcoming(index))
        menu.addAction('Quitar de la cola', lambda: self.player.remove_upcoming(index))
        menu.addSeparator()
        menu.addAction('Más opciones…', lambda: self.actions.track_menu(keys, position))
        menu.exec(position)


class FullPlayer(QWidget):
    """Overlay over the whole window; ``show_tab`` picks lyrics or queue."""

    closed = Signal()

    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.actions = actions
        self.library, self.covers, self.player = actions.library, actions.covers, actions.player
        self.lyric_key = None
        self.drift = Drift()
        self._backdrop = None
        self._backdrop_key = None
        self._covered = None  # called once the entrance has covered the window
        self._halo, self._halo_key, self._breath = None, None, .5
        self._breath_clock = QElapsedTimer()
        self._breath_clock.start()
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.entrance = QVariantAnimation(self)
        self.entrance.setEasingCurve(QEasingCurve.OutCubic)
        self.entrance.valueChanged.connect(self._set_entrance)
        self.entrance.finished.connect(self._entered)
        self.setAttribute(Qt.WA_StyledBackground, False)

        outer = QVBoxLayout(self)
        pad = metric('space_xl')
        outer.setContentsMargins(pad, metric('space_m'), pad, pad)
        outer.setSpacing(metric('space_m'))
        top = QHBoxLayout()
        top.addWidget(IconButton('expand_more', 'Cerrar · Esc', self.closed.emit, 'tonal', 40))
        top.addStretch()
        self.tabs = QButtonGroup(self)
        for index, (_, label) in enumerate(TABS):
            chip = Chip(label)
            chip.setFocusPolicy(Qt.TabFocus)
            self.tabs.addButton(chip, index)
            top.addWidget(chip)
        top.addStretch()
        top.addSpacing(40)
        outer.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(metric('space_xl') * 2)
        self.body = QWidget()
        self.body.setLayout(body)
        self.body.setMaximumWidth(1440)
        centred = QHBoxLayout()  # very wide windows keep the record and lyrics together
        centred.addStretch(1)
        centred.addWidget(self.body, 100)
        centred.addStretch(1)
        outer.addLayout(centred, 1)

        # Left: the record.
        left = QVBoxLayout()
        left.setSpacing(metric('space_s'))
        left.addStretch(1)
        self.cover = CoverArt(self.covers, 320, shape='cookie')
        self.cover.turned.connect(self._breathe)
        left.addWidget(self.cover, 0, Qt.AlignHCenter)
        left.addSpacing(metric('space_l'))
        row = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = ElidedLabel('', 'title', 800, 'text_strong', scale=1.05)
        self.artist = LinkLabel('', 'heading', 500, 'accent')
        self.artist.activated.connect(self._open_artist)
        self.album = ElidedLabel('', 'small', 400, 'muted')
        titles.addWidget(self.title)
        titles.addWidget(self.artist)
        titles.addWidget(self.album)
        row.addLayout(titles, 1)
        self.favorite = IconButton('favorite', 'Guardar en Tus me gusta', self._favorite, 'tonal', 44, checkable=True)
        row.addWidget(self.favorite, 0, Qt.AlignVCenter)
        left.addLayout(row)
        self.progress = Slider('Posición de reproducción', wavy=True, step=5 / 300)
        self.progress.moved.connect(lambda value: self.elapsed.setText(stamp(value * self.player.duration)))
        self.progress.released.connect(lambda value: self.player.seek(value * self.player.duration))
        left.addWidget(self.progress)
        times = QHBoxLayout()
        self.elapsed = TimeLabel(Qt.AlignLeft)
        self.total = TimeLabel(Qt.AlignRight)
        times.addWidget(self.elapsed)
        times.addStretch()
        self.quality = ElidedLabel('', 'caption', 500, 'subtle')
        self.quality.setAlignment(Qt.AlignCenter)
        times.addWidget(self.quality, 1)
        times.addStretch()
        times.addWidget(self.total)
        left.addLayout(times)
        transport = QHBoxLayout()
        transport.setSpacing(metric('space_m'))
        transport.addStretch()
        player = self.player
        self.shuffle = IconButton('shuffle', 'Aleatorio', lambda: player.set_shuffle(not player.shuffle),
                                  size=44, checkable=True, dot=True)
        self.previous = IconButton('skip_previous', 'Anterior', player.previous, 'tonal', 56)
        self.play = IconButton('play_arrow', 'Reproducir', player.toggle, 'filled', 76)
        self.play.icon_scale = .5
        self.next = IconButton('skip_next', 'Siguiente', player.next, 'tonal', 56)
        self.repeat = IconButton('repeat', 'Repetir', player.cycle_repeat, size=44, checkable=True, dot=True)
        for button in (self.shuffle, self.previous, self.play, self.next, self.repeat):
            transport.addWidget(button)
        transport.addStretch()
        left.addLayout(transport)
        volume = QHBoxLayout()
        volume.addStretch()
        self.mute = IconButton('volume_up', 'Silenciar', player.toggle_mute, size=32)
        volume.addWidget(self.mute)
        self.volume = Slider('Volumen', step=.05)
        self.volume.setFixedWidth(180)
        self.volume.moved.connect(lambda value: player.set_volume(round(value * 100)))
        self.volume.released.connect(lambda value: player.set_volume(round(value * 100)))
        volume.addWidget(self.volume)
        volume.addStretch()
        left.addLayout(volume)
        left.addStretch(1)
        self.left = QWidget()
        self.left.setLayout(left)
        self.left.setMaximumWidth(460)
        self.left.installEventFilter(self)
        body.addWidget(self.left, 5)

        # Right: lyrics or queue.
        self.stack = QStackedWidget()
        self.lyrics = LyricsView()
        self.lyrics.seek_requested.connect(self._seek_lyric)
        lyrics_page = QWidget()
        lyrics_layout = QVBoxLayout(lyrics_page)
        lyrics_layout.setContentsMargins(0, 0, 0, 0)
        lyrics_layout.addWidget(self.lyrics, 1)
        offsets = QHBoxLayout()
        offsets.setContentsMargins(metric('space_l'), 0, 0, 0)
        self.lyric_source = ElidedLabel('', 'caption', 400, 'muted')
        offsets.addWidget(self.lyric_source, 1)
        offsets.addWidget(IconButton('remove', 'Adelantar la letra 0.5 s', lambda: self._offset(-.5), 'tonal', 28))
        self.offset_label = ElidedLabel('0.0 s', 'caption', 600, 'muted')
        self.offset_label.setFixedWidth(52)
        self.offset_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)  # Ignored overlaps the buttons
        self.offset_label.setAlignment(Qt.AlignCenter)
        offsets.addWidget(self.offset_label)
        offsets.addWidget(IconButton('add', 'Retrasar la letra 0.5 s', lambda: self._offset(.5), 'tonal', 28))
        lyrics_layout.addLayout(offsets)
        self.queue = QueueView(actions)
        for page in (lyrics_page, self.queue):
            self.stack.addWidget(page)
        body.addWidget(self.stack, 6)

        self._auto_queue = False   # switched to the queue because the song has no lyrics
        self._tab_chosen = False
        self.tabs.idClicked.connect(self.show_tab)
        self.covers.metadata.ready.connect(self._metadata_ready)
        self.covers.updated.connect(self._cover_updated)
        player.track_changed.connect(lambda _: self.refresh())
        player.track_changed.connect(lambda _: self._request_lyrics())
        player.state_changed.connect(self.refresh_state)
        player.queue_changed.connect(self.refresh_state)
        player.position_changed.connect(self._position)
        player.duration_changed.connect(lambda _: self._position(player.position))
        self.library.favorites_changed.connect(self.refresh)
        self.show_tab(0)
        self.refresh()
        self.refresh_state()

    # ------------------------------------------------------------------ tabs
    def current_tab(self):
        return TABS[self.stack.currentIndex()][0]

    def show_tab(self, index, chosen=True):
        """``chosen``: the user asked for this tab, so it is never switched for them."""
        if isinstance(index, str):
            chosen = index != 'now'  # «now» only opens the player: the tab may follow the lyrics
            index = 0 if index in ('now', 'lyrics') else 1
        self.tabs.button(index).setChecked(True)
        self.stack.setCurrentIndex(index)
        self._auto_queue = False
        self._tab_chosen = chosen
        self.queue.set_note('')
        self._request_lyrics()

    # ---------------------------------------------------------------- render
    def refresh(self):
        key = self.player.current
        track = self.library.track(key) if key else {}
        self.cover.set_track(key)
        self.title.setText(track.get('title', 'Nada sonando'))
        self.artist.setText(track.get('artist', 'Elige una canción de tu biblioteca'))
        self.album.setText(self.library.album(key) if key else '')
        audio = self.library.playable(key) if key else {}
        codec = audio.get('codec', '').upper()
        bitrate = round(audio.get('bitrate', 0) / 1000)
        self.quality.setText(f'{codec} · {bitrate} kb/s' if codec and bitrate else codec)
        self.favorite.setEnabled(bool(key))
        self.favorite.setChecked(bool(key) and key in self.library.favorites)
        self._position(self.player.position)
        self.update()

    def refresh_state(self):
        player = self.player
        self.play.set_symbol('play_arrow' if player.paused or player.ended else 'pause')
        self.play.set_label('Reproducir' if player.paused else 'Pausar')
        self.shuffle.setChecked(player.shuffle)
        self.repeat.setChecked(player.repeat != 'off')
        self.repeat.set_symbol('repeat_one' if player.repeat == 'one' else 'repeat')
        self.repeat.set_label(REPEAT_LABELS[player.repeat])
        self.previous.setEnabled(player.can_previous())
        self.next.setEnabled(player.can_next())
        self.progress.setEnabled(bool(player.current))
        self.progress.set_playing(player.playing)
        self.cover.set_spinning(player.playing)
        muted = player.muted or not player.volume
        self.mute.set_symbol('volume_off' if muted else 'volume_up')
        if not self.volume.dragging:
            self.volume.set_value(0 if player.muted else player.volume / 100)
        self._sync_halo()

    def _position(self, seconds):
        if not self.isVisible():
            return
        duration = self.player.duration
        if not self.progress.dragging:
            self.progress.set_value(seconds / duration if duration else 0)
            self.elapsed.setText(stamp(seconds))
        self.total.setText(stamp(duration))
        if self.lyrics.synced and self.current_tab() == 'lyrics':
            self.lyrics.set_position(seconds + self._offset_value())

    def _cover_updated(self, key):
        if key == self.player.current:
            self.invalidate()

    def eventFilter(self, watched, event):
        # Size the record from the left column once the layout has placed it.
        if watched is self.left and event.type() == QEvent.Resize:
            side = max(180, min(380, self.height() - 440, self.left.width() - 40))
            if side != self.cover.width():
                self.cover.setFixedSize(side, side)
        return super().eventFilter(watched, event)

    # ----------------------------------------------------------- background
    def invalidate(self):
        """Theme, song or artwork changed: render the backdrop again on next paint."""
        self._backdrop_key = None
        self.update()

    def _render_backdrop(self):
        path = self.covers.path(self.player.current) if self.player.current else None
        ratio = self.devicePixelRatioF()
        key = (path, self.width(), self.height(), ratio, tokens()['name'], tokens()['variant'])
        if key == self._backdrop_key and self._backdrop is not None:
            return self._backdrop
        pixmap = QPixmap(round(self.width() * ratio), round(self.height() * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        radius = tokens()['radius_l']
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), color('surface'))
        wash = blurred(path, self.width() // 2, self.height() // 2) if path else None
        if wash is not None:
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.setOpacity(.85)
            painter.drawPixmap(self.rect(), wash)
            painter.setOpacity(1.0)
        # Themed scrim keeps text legible whatever the artwork's colours are.
        painter.fillRect(self.rect(), color('surface', 150))
        self.drift.paint(painter, QRectF(self.rect()), color('accent'), .11)
        # Vignette: the edges sink, the centre glows; costs nothing once baked.
        vignette = QRadialGradient(QPointF(self.width() * .4, self.height() * .45), max(self.width(), self.height()) * .75)
        vignette.setColorAt(.55, color('shadow', 0))
        vignette.setColorAt(1, color('shadow', 150))
        painter.fillRect(self.rect(), vignette)
        painter.setOpacity(.6)
        painter.drawTiledPixmap(self.rect(), grain_tile())
        painter.end()
        self._backdrop, self._backdrop_key = pixmap, key
        return pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        # Source mode replaces pixels outright: the rounded corners stay truly transparent.
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        backdrop = self._render_backdrop()
        rect = event.rect()
        ratio = backdrop.devicePixelRatio()
        painter.drawPixmap(QRectF(rect), backdrop, QRectF(rect.x() * ratio, rect.y() * ratio,
                                                   rect.width() * ratio, rect.height() * ratio))
        halo = self._halo_rect()
        if halo.intersects(rect):
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setOpacity(.55 + .3 * self._breath)
            painter.drawPixmap(halo, self._halo_pixmap(halo.width()))

    # ----------------------------------------------------------------- halo
    # Ambient light: the artwork's own colour glows behind the record and
    # breathes slowly while it plays. Only this small square is repainted,
    # from a cached gradient, so the effect costs a pixmap copy per frame.
    def _halo_rect(self):
        if not self.player.current or not self.cover.isVisible():
            return QRect()
        cover = QRect(self.cover.mapTo(self, QPoint()), self.cover.size())
        grow = round(cover.width() * .3)
        return cover.adjusted(-grow, -grow, grow, grow)

    def _halo_pixmap(self, side):
        tone = self.covers.tone(self.player.current) if self.player.current else None
        key = (side, tone.name() if tone is not None else '', self.devicePixelRatioF())
        if key != self._halo_key:
            ratio = self.devicePixelRatioF()
            pixmap = QPixmap(round(side * ratio), round(side * ratio))
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            gradient = QRadialGradient(QPointF(side / 2, side / 2), side / 2)
            # theme-exception: the glow takes the user's artwork tone (accent when unknown).
            glow = QColor(tone) if tone is not None else color('accent')
            glow.setAlpha(170)
            gradient.setColorAt(.3, glow)
            glow.setAlpha(0)
            gradient.setColorAt(.82, glow)
            painter.fillRect(QRectF(0, 0, side, side), gradient)
            painter.end()
            self._halo, self._halo_key = pixmap, key
        return self._halo

    def _breathe(self):
        self._breath = (1 - math.cos(self._breath_clock.elapsed() / 1000 * 2 * math.pi / 5.5)) / 2
        self.update(self._halo_rect())

    def _sync_halo(self):
        # Driven by the record's own turn timer: Qt merges both updates into one paint.
        self._breath = self._breath if self.player.playing else .5
        self.update(self._halo_rect())

    # -------------------------------------------------------------- entrance
    def open(self, covered=None):
        """Slide in; ``covered`` runs once the window is fully covered."""
        self._covered = covered
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self.setFocus()
        if reduced_motion(self.window()):
            self._entered()
            return
        self.entrance.stop()
        self.entrance.setDuration(metric('motion_enter') * 2)
        self.entrance.setStartValue(1.0)
        self.entrance.setEndValue(0.0)
        self.entrance.start()

    def _set_entrance(self, value):
        self.move(0, round(float(value) * self.height() * .06))

    def _entered(self):
        if self._covered is not None:
            self._covered()
            self._covered = None

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        self.refresh_state()
        self._request_lyrics()

    def hideEvent(self, event):
        self.entrance.stop()
        self._covered = None
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.closed.emit()
        else:
            super().keyPressEvent(event)

    # --------------------------------------------------------------- actions
    def _favorite(self):
        if self.player.current:
            self.library.toggle_favorite(self.player.current)

    def _open_artist(self):
        names = artists(self.library.track(self.player.current)) if self.player.current else []
        if names:
            self.closed.emit()
            self.actions.navigate.emit(('collection', 'artist:' + names[0]))

    # ---------------------------------------------------------------- lyrics
    def _request_lyrics(self):
        # Also while the queue shows on its own: lyrics arriving bring the lyrics tab back.
        if not self.isVisible() or (self.current_tab() != 'lyrics' and not self._auto_queue):
            return
        key = self.player.current
        if not key:
            self.lyrics.set_message('Reproduce una canción para ver su letra.')
            return
        audio = self.library.playable(key)
        lyric_key = f"{key}:{round(audio.get('duration', 0), 2)}"
        if lyric_key == self.lyric_key:
            return
        self.lyric_key = lyric_key
        self.lyrics.set_message('Buscando letra…')
        self.lyric_source.setText('')
        self.offset_label.setText(f"{self.library.store.get('offset:' + key, 0):+.1f} s")
        track = self.library.track(key)
        self.covers.metadata.lyrics(lyric_key, dict(audio, title=track.get('title', ''), artist=track.get('artist', '')),
                                    self.library.store.reference(key))

    def _metadata_ready(self, kind, key, data):
        if kind == 'lyrics' and key == self.lyric_key:
            self.lyrics.set_lyrics(data)
            self.lyric_source.setText(('Sincronizada' if self.lyrics.synced else 'Sin sincronizar') + ' · LRCLIB'
                                      if self.lyrics.rows else '')
            self._follow_lyrics()
            self._position(self.player.position)

    def _follow_lyrics(self):
        """No lyrics: show what comes next instead of an empty column (unless the
        user picked «Letra»); lyrics again on a later song: back to them."""
        if self._tab_chosen:
            return
        has_lyrics = bool(self.lyrics.rows)
        if not has_lyrics and self.current_tab() == 'lyrics':
            self.tabs.button(1).setChecked(True)
            self.stack.setCurrentIndex(1)
            self._auto_queue = True
            self.queue.set_note(self.lyrics.message)
        elif has_lyrics and self._auto_queue:
            self.tabs.button(0).setChecked(True)
            self.stack.setCurrentIndex(0)
            self._auto_queue = False
            self.queue.set_note('')

    def _offset_value(self):
        return self.library.store.get('offset:' + str(self.player.current), 0)

    def _seek_lyric(self, seconds):
        self.player.seek(max(0.0, seconds - self._offset_value()))

    def _offset(self, amount):
        if not self.player.current or not self.lyrics.synced:
            return
        value = round(self._offset_value() + amount, 1)
        self.library.store.put('offset:' + self.player.current, value)
        self.offset_label.setText(f'{value:+.1f} s')

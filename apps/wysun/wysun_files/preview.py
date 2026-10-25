"""Inspector: a themed preview of the selection (image, media, Markdown, code, PDF) plus its details."""
import datetime
import itertools
import math
import os
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QThread, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from file_media import FilePreviewJob, duration_label, file_kind, human_size
from files_zoom import ZoomCanvas
from theme_tokens import color, tokens
from ui_motion import reduced_motion
from wysun_music.ui.shapes import squircle
from .highlight import language_for_path
from .kinds import describe, preview_kind
from .kit import Chip, ElidedLabel, IconButton, PillButton, metric, paint_symbol, text_font
from .textview import CodeView, MarkdownView

TEXT_LIMIT = 512 * 1024


class TextJob(QThread):
    ready = Signal(str, str, bool)      # path, text, truncated

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            with open(self.path, 'rb') as handle:
                raw = handle.read(TEXT_LIMIT + 1)
            if b'\0' in raw[:4096]:
                self.ready.emit(self.path, '', False)
                return
            self.ready.emit(self.path, raw[:TEXT_LIMIT].decode('utf-8', errors='replace'), len(raw) > TEXT_LIMIT)
        except OSError:
            self.ready.emit(self.path, '', False)


class FadeStack(QStackedWidget):
    """Stack whose content swaps under a veil of the panel colour that fades away.

    QGraphicsOpacityEffect cannot wrap scroll areas holding painted children, so the
    transition is a translucent overlay in the surface tone instead.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.alpha = 0.0
        self.veil = QVariantAnimation(self, duration=tokens()['motion_enter'])
        self.veil.setStartValue(1.0)
        self.veil.setEndValue(0.0)
        self.veil.setEasingCurve(QEasingCurve.OutCubic)
        self.veil.valueChanged.connect(self._fade)
        self.cover = QWidget(self)
        self.cover.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.cover.paintEvent = self._paint_cover
        self.cover.hide()

    def flash(self):
        if reduced_motion(self.window()):
            return
        self.cover.setGeometry(self.rect())
        self.cover.raise_()
        self.cover.show()
        self.veil.stop()
        self.veil.start()

    def _fade(self, value):
        self.alpha = float(value)
        self.cover.setVisible(self.alpha > .01)
        self.cover.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.cover.setGeometry(self.rect())

    def _paint_cover(self, _event):
        painter = QPainter(self.cover)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('surface', round(255 * self.alpha)))
        painter.drawRoundedRect(QRectF(self.cover.rect()), tokens()['radius_m'], tokens()['radius_m'])


class GlyphPage(QWidget):
    """Big tonal squircle with a kind symbol and a caption, for anything without a visual preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.symbol, self.tone, self.caption = 'draft', 'cat_slate', ''

    def show_kind(self, symbol, tone, caption=''):
        self.symbol, self.tone, self.caption = symbol, tone, caption
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = min(self.width() - 32, self.height() - 56, 200)
        box = QRectF(0, 0, side, side * .82)
        box.moveCenter(QPointF(self.width() / 2, self.height() / 2 - 14))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('tile'))
        outline = squircle(box, .6)
        painter.drawPath(outline)
        painter.setBrush(color(self.tone, 44))
        painter.drawPath(outline)
        paint_symbol(painter, box, self.symbol, self.tone, side * .42, filled=True)
        if self.caption:
            painter.setFont(text_font('small', 500))
            painter.setPen(color('muted'))
            painter.drawText(QRectF(8, box.bottom() + 10, self.width() - 16, 22), Qt.AlignHCenter | Qt.AlignVCenter, self.caption)


class ImageStage(ZoomCanvas):
    """Zoomable image in a rounded well with a zoom badge."""

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()), tokens()['radius_m'], tokens()['radius_m'])
        painter.fillPath(shape, color('well'))
        if self.image is None or self.image.isNull():
            painter.setFont(text_font('body', 500))
            painter.setPen(color('muted'))
            painter.drawText(self.rect(), Qt.AlignCenter, self.text())
            return
        painter.setClipPath(shape)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        scale = min(self.width() / self.image.width(), self.height() / self.image.height()) * self.zoom
        size = self.image.size() * scale
        center = QPointF(self.rect().center()) + self.offset
        painter.drawImage(QRectF(center.x() - size.width() / 2, center.y() - size.height() / 2, size.width(), size.height()), self.image)
        painter.setClipping(False)
        if abs(self.zoom - 1) > .02:
            label = f'{round(self.zoom * 100)} %'
            painter.setFont(text_font('caption', 700))
            width = painter.fontMetrics().horizontalAdvance(label) + 20
            badge = QRectF(self.width() - width - 10, 10, width, 24)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('tooltip'))
            painter.drawRoundedRect(badge, 12, 12)
            painter.setPen(color('on_tooltip'))
            painter.drawText(badge, Qt.AlignCenter, label)


class Tag(QWidget):
    """Small tonal pill: optional symbol and a value."""

    def __init__(self, symbol, text, parent=None):
        super().__init__(parent)
        self.symbol, self.text = symbol, text
        self.setFixedHeight(28)
        self.setToolTip(text)

    def sizeHint(self):
        from PySide6.QtGui import QFontMetrics
        return QSize(QFontMetrics(text_font('caption', 600)).horizontalAdvance(self.text) + (46 if self.symbol else 24), 28)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color('fill'))
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.setBrush(color('tint', 14))
        painter.drawRoundedRect(rect, 14, 14)
        left = 12
        if self.symbol:
            paint_symbol(painter, QRectF(8, 0, 20, 28), self.symbol, 'accent', 16)
            left = 30
        painter.setFont(text_font('caption', 600))
        painter.setPen(color('text'))
        painter.drawText(QRectF(left, 0, self.width() - left - 8, 28), Qt.AlignLeft | Qt.AlignVCenter, self.text)


class Details(QWidget):
    """Name, kind line, tags and the full location of the selection."""

    copy_path = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(metric('space_xs'))
        self.name = ElidedLabel('')
        self.name.setFont(text_font('heading', 650))
        self.name.setAccessibleName('Nombre')
        column.addWidget(self.name)
        self.line = ElidedLabel('')
        self.line.setObjectName('muted')
        self.line.setFont(text_font('small'))
        column.addWidget(self.line)
        self.tags = QHBoxLayout()
        self.tags.setContentsMargins(0, metric('space_xs'), 0, 0)
        self.tags.setSpacing(metric('space_xs'))
        column.addLayout(self.tags)
        self.location = ElidedLabel('')
        self.location.setObjectName('muted')
        self.location.setFont(text_font('caption'))
        self.location.setCursor(Qt.PointingHandCursor)
        self.location.setToolTip('Clic para copiar la ruta')
        self.location.mousePressEvent = lambda _e: self.copy_path.emit()
        column.addWidget(self.location)

    def set(self, name, line, tags, location=''):
        self.name.setText(name)
        self.line.setText(line)
        while self.tags.count():
            item = self.tags.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        for symbol, text in tags:
            self.tags.addWidget(Tag(symbol, text))
        self.tags.addStretch()
        self.location.setText(location)
        self.location.setVisible(bool(location))


def count_entries(path, limit=5000):
    try:
        with os.scandir(path) as entries:
            return sum(1 for _ in itertools.islice(entries, limit))
    except OSError:
        return 0


class SelectionPreview(QWidget):
    """Everything the inspector shows. ``set_selection`` is cheap; heavy work runs after a short debounce."""

    open_requested = Signal()
    link_requested = Signal(str)
    message = Signal(str)
    fullscreen_requested = Signal(bool)
    expand_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path, self.paths, self.folder = '', [], ''
        self.player, self.job, self.request = None, None, None
        self.page, self.pages = 1, 1
        self.kind = ''
        self.base_tags = []
        self.text_source = ''
        self.setObjectName('selectionPreview')
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(metric('space_m'))

        modes = QHBoxLayout()
        modes.setContentsMargins(0, 0, 0, 0)
        modes.setSpacing(metric('space_xs'))
        self.view_chip, self.source_chip = Chip('Vista'), Chip('Código')
        self.view_chip.setChecked(True)
        self.view_chip.clicked.connect(lambda: self._markdown_mode(True))
        self.source_chip.clicked.connect(lambda: self._markdown_mode(False))
        modes.addWidget(self.view_chip)
        modes.addWidget(self.source_chip)
        modes.addStretch()
        self.expand = IconButton('open_in_full', 'Ampliar · Espacio', self.expand_requested.emit, size=32)
        modes.addWidget(self.expand)
        self.modes = QWidget()
        self.modes.setLayout(modes)
        column.addWidget(self.modes)

        self.stack = FadeStack()
        self.glyph = GlyphPage()
        self.image = ImageStage()
        self.image.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.holder = QWidget()
        QVBoxLayout(self.holder).setContentsMargins(0, 0, 0, 0)
        self.media_page = QWidget()          # the one player lives here for the whole life of the panel
        QVBoxLayout(self.media_page).setContentsMargins(0, 0, 0, 0)
        for page in (self.glyph, self.image, self.holder, self.media_page):
            self.stack.addWidget(page)
        column.addWidget(self.stack, 1)

        pager = QHBoxLayout()
        pager.setContentsMargins(0, 0, 0, 0)
        self.previous = IconButton('chevron_left', 'Página anterior', lambda: self.turn(-1), variant='tonal', size=32)
        self.next = IconButton('chevron_right', 'Página siguiente', lambda: self.turn(1), variant='tonal', size=32)
        self.counter = QLabel()
        self.counter.setFont(text_font('small', 600))
        self.counter.setAlignment(Qt.AlignCenter)
        pager.addStretch()
        pager.addWidget(self.previous)
        pager.addWidget(self.counter)
        pager.addWidget(self.next)
        pager.addStretch()
        self.pager = QWidget()
        self.pager.setLayout(pager)
        column.addWidget(self.pager)

        self.details = Details()
        self.details.copy_path.connect(self.copy_path)
        column.addWidget(self.details)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(metric('space_s'))
        self.open_button = PillButton('arrow_outward', 'Abrir', self.open_requested.emit, height=40)
        actions.addWidget(self.open_button, 1)
        self.copy_button = IconButton('content_copy', 'Copiar ruta', self.copy_path, variant='tonal', size=40)
        actions.addWidget(self.copy_button)
        column.addLayout(actions)

        self.timer = QTimer(self, singleShot=True, interval=120)
        self.timer.timeout.connect(self._load)
        self.set_selection([], '')

    # ------------------------------------------------------------ capability
    @staticmethod
    def supported(path):
        return bool(path) and Path(path).is_file() and bool(preview_kind(path))

    # -------------------------------------------------------------- selection
    def set_selection(self, paths, folder):
        paths = list(paths)
        if paths == self.paths and folder == self.folder and self.kind:
            return
        self.paths, self.folder = paths, folder
        self._clear_dynamic()
        self.request = None
        self.timer.stop()
        self.path = paths[0] if len(paths) == 1 else ''
        self.page = self.pages = 1
        self.expand.setVisible(False)
        self.modes.setVisible(False)
        self.pager.setVisible(False)
        self.open_button.setEnabled(bool(paths))
        self.copy_button.setEnabled(bool(paths) or bool(folder))
        if not paths:
            self._folder_card()
        elif len(paths) > 1:
            self._multiple()
        else:
            self._single(paths[0])
        self.stack.flash()

    def _clear_dynamic(self):
        if self.player is not None:
            self.player.close_media()        # stops playback and decoding; the session is reused by the next file
        layout = self.holder.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.image.clear()

    def _show_glyph(self, symbol, tone, caption=''):
        self.glyph.show_kind(symbol, tone, caption)
        self.stack.setCurrentWidget(self.glyph)

    def _folder_card(self):
        self.kind = 'folder-card'
        name = Path(self.folder).name or 'Sistema'
        count = count_entries(self.folder) if self.folder else 0
        self._show_glyph('folder_open', 'accent', 'Selecciona un archivo para previsualizarlo')
        self.details.set(name, f'Carpeta · {count} elementos', [], self.folder)

    def _multiple(self):
        self.kind = 'multiple'
        total, kinds = 0, {}
        for path in self.paths:
            try:
                if Path(path).is_file():
                    total += Path(path).stat().st_size
            except OSError:
                pass
            label = describe(path)[2]
            kinds[label] = kinds.get(label, 0) + 1
        self._show_glyph('library_add_check', 'accent')
        tags = [(None, f'{count} {label.lower()}') for label, count in list(kinds.items())[:3]]
        self.details.set(f'{len(self.paths)} elementos', human_size(total) if total else 'Selección múltiple', tags)

    def _single(self, path):
        target = Path(path)
        symbol, tone, label = describe(path)
        try:
            stat = target.stat()
        except OSError:
            self.kind = 'missing'
            self._show_glyph('error', 'danger', 'El archivo ya no está disponible')
            self.details.set(target.name, 'No disponible', [])
            return
        modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%d %b %Y · %H:%M')
        tags = [('schedule', modified)]
        self.base_tags = tags
        location = str(target.parent)
        if target.is_dir():
            self.kind = 'folder'
            count = count_entries(path)
            self._show_glyph('folder', 'accent', f'{count} elementos')
            self.details.set(target.name, f'Carpeta · modificada {modified}', [('folder_open', f'{count} elementos')], location)
            return
        line = f'{label} · {human_size(stat.st_size)}' + (' · enlace simbólico' if target.is_symlink() else '')
        self.details.set(target.name, line, tags, location)
        kind = preview_kind(path)
        self.kind = kind or 'file'
        if not kind:
            self._show_glyph(symbol, tone, 'Sin vista previa · usa Abrir')
            return
        self.expand.setVisible(True)
        self.modes.setVisible(True)
        self.view_chip.setVisible(kind == 'markdown')
        self.source_chip.setVisible(kind == 'markdown')
        if kind == 'pdf':
            self.image.setText('Cargando vista previa…')
            self.stack.setCurrentWidget(self.image)
            self.request = (path, 1)
        else:
            self._show_glyph(symbol, tone, 'Cargando…')
        self.timer.start()

    # ---------------------------------------------------------------- loading
    def _load(self):
        if not self.path:
            return
        kind = preview_kind(self.path)
        if kind in ('video', 'audio', 'image'):
            self._show_media()
        elif kind == 'pdf':
            self._start_image()
        else:
            self._start_text()

    def _start_image(self):
        if self.job is not None or not self.request:
            return
        path, page = self.request
        self.request = None
        self.job = FilePreviewJob(path, page)
        self.job.ready.connect(lambda _p, data, p=path, n=page: self._image_loaded(p, n, data))
        self.job.finished.connect(self._job_finished)
        self.job.start()

    def _start_text(self):
        if self.job is not None:
            self.request = ('text', 0)
            return
        self.job = TextJob(self.path)
        self.job.ready.connect(self._text_loaded)
        self.job.finished.connect(self._job_finished)
        self.job.start()

    def _job_finished(self):
        self.job.deleteLater()
        self.job = None
        if self.request:
            if self.request[0] == 'text':
                self.request = None
                self._start_text()
            else:
                self._start_image()

    def _media_player(self):
        """The embedded player, created when the first picture, video or song is selected."""
        if self.player is None:
            import media_host
            media_host.install()
            from wysun_media.player import MediaPlayer
            self.player = MediaPlayer(mode='embedded', backdrop='surface')
            self.player.enable_integration()       # media keys and the shell widget see it once the user presses play
            self.player.fullscreenRequested.connect(self.fullscreen_requested)
            self.player.expandRequested.connect(self.open_in_player)
            self.player.infoChanged.connect(self._media_tags)
            self.player.errorOccurred.connect(lambda error: self.message.emit(error.message))
            self.player.reveal = lambda: None          # Files is already showing the folder
            self.media_page.layout().addWidget(self.player)
        return self.player

    def _show_media(self):
        player = self._media_player()
        if player.open(self.path, paused=True):         # no autoplay: video shows its first frame, audio waits for play
            self.stack.setCurrentWidget(self.media_page)
        else:
            self._show_glyph(*describe(self.path)[:2], 'Sin vista previa · usa Abrir')

    def _media_tags(self):
        """Duration, size and codec of the file on show, from what the player itself learned."""
        player = self.player
        if player is None or player.source is None or str(player.source.path) != self.path:
            return
        tags = list(self.base_tags)
        if player.kind == 'image':
            frame = player._images.frame if player._images else None
            if frame is not None:
                tags.append(('aspect_ratio', f'{frame.size.width()} × {frame.size.height()}'))
                tags.append(('image', frame.format.upper()))
        else:
            props = player.session.props
            if player.session.duration:
                tags.append(('schedule', duration_label(player.session.duration)))
            params = props.get('video-params') or {}
            if params.get('w'):
                tags.append(('aspect_ratio', f"{params['w']} × {params.get('h', 0)}"))
            codec = props.get('audio-codec-name') if player.kind == 'audio' else props.get('video-codec')
            if codec:
                tags.append(('graphic_eq', codec.split('/')[0].strip().upper()))
        self.details.set(self.details.name.text(), self.details.line.text(), tags[:3], self.details.location.text())

    def open_in_player(self):
        """Continue this file in Wysun Player, at the same place, and leave the panel quiet."""
        if not self.path:
            return
        from player_client import launch
        player = self.player
        timed = player is not None and player.kind in ('video', 'audio')
        position = player.session.position if timed else None
        paused = player.session.paused if timed else False
        if timed:
            player.session.set_paused(True)
        launch([self.path], start=position or None, paused=paused)

    def _image_loaded(self, path, page, data):
        if path != self.path or page != self.page:
            return
        meta = data.get('meta', {})
        self.pages = meta.get('pages', 1)
        image = data.get('image')
        tags = [('schedule', datetime.datetime.fromtimestamp(meta['modified']).strftime('%d %b %Y'))] if meta.get('modified') else []
        if meta.get('width'):
            tags.append(('aspect_ratio', f"{meta['width']} × {meta.get('height', 0)}"))
        if meta.get('pages'):
            tags.append(('description', f"{meta['pages']} páginas"))
        self.details.set(self.details.name.text(), self.details.line.text(), tags[:3], self.details.location.text())
        self.pager.setVisible(self.pages > 1)
        self._pager_state()
        if image is not None and not image.isNull():
            self.image.set_image(image)
        else:
            self.image.setText(data.get('error') or 'Vista previa no disponible')
            self.image.update()

    def turn(self, step):
        self.page = max(1, min(self.pages, self.page + step))
        self._pager_state()
        self.request = (self.path, self.page)
        self._start_image()

    def _pager_state(self):
        self.previous.setEnabled(self.page > 1)
        self.next.setEnabled(self.page < self.pages)
        self.counter.setText(f'{self.page} / {self.pages}')

    def _text_loaded(self, path, text, truncated):
        if path != self.path:
            return
        kind = preview_kind(path)
        if not text:
            self._show_glyph(*describe(path)[:2], 'Documento vacío o binario · usa Abrir')
            return
        self.text_source = text
        if kind == 'markdown':
            self._markdown_mode(self.view_chip.isChecked() or not self.source_chip.isChecked())
        else:
            self._show_code(text, language_for_path(path))
        lines = text.count('\n') + 1
        tags = [('format_list_numbered', f'{lines:,} líneas'.replace(',', ' '))]
        if truncated:
            tags.append(('content_cut', 'Primeros 512 KB'))
        self.details.set(self.details.name.text(), self.details.line.text(), tags, self.details.location.text())

    def _markdown_mode(self, rendered):
        self.view_chip.setChecked(rendered)
        self.source_chip.setChecked(not rendered)
        if self.kind != 'markdown' or not self.text_source:
            return
        layout = self.holder.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        if rendered:
            view = MarkdownView(self.text_source, str(Path(self.path).parent))
            view.link.connect(self.link_requested)
            view.message.connect(self.message)
            layout.addWidget(view)
            self.stack.setCurrentWidget(self.holder)
        else:
            self._show_code(self.text_source, 'plain')
        self.stack.flash()

    def _show_code(self, text, language):
        layout = self.holder.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        layout.addWidget(CodeView(text, language))
        self.stack.setCurrentWidget(self.holder)

    # ---------------------------------------------------------------- actions
    def copy_path(self):
        target = self.path or (self.paths[0] if self.paths else self.folder)
        if target:
            QGuiApplication.clipboard().setText(os.path.abspath(target))
            self.message.emit('Ruta copiada')

    def shutdown(self):
        """Stop playback and ask running jobs to finish before the window closes."""
        self.timer.stop()
        self.request = None
        if self.player is not None:
            self.player.shutdown()

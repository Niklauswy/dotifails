"""The continuous document: every page laid out, only the visible ones painted and rendered.

Geometry is pdf_layout's; rasters and text come from a PageSource. Page coordinates (points, rotated
like the displayed page) map to content pixels through each page rect; the scroll bars move the window.
"""
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QAbstractScrollArea, QFrame, QToolTip

from wysun_core.qt_theme import color, tokens
from wysun_core.ui.style import metric
from pdf_layout import Layout, anchor, clamp_zoom, fit_page, fit_width, locate

RENDER_DELAY = 120   # ms without zoom changes before asking for sharper rasters
DRAG = 4             # px before a press becomes a text selection
WHEEL_STEP = 1.1


class DocumentView(QAbstractScrollArea):
    pageChanged = Signal(int)
    zoomChanged = Signal(float)
    selectionChanged = Signal()
    selectionFinished = Signal()
    linkActivated = Signal(dict)
    noteRequested = Signal(int, QPointF)
    scrolled = Signal()          # the content moved under the viewport (overlays follow it)

    def __init__(self, source, parent=None):
        super().__init__(parent)
        self.source = source
        self.sizes = []
        self.zoom, self.zoom_mode, self.mode = 1.0, 'width', 'single'
        self.layout = Layout([], 1.0)
        self.hits, self.current_hit = {}, None
        self.selection = (None, [])
        self.note_mode = False
        self._press = None        # (viewport point, page, page point, link)
        self._anchor_word = None
        self._dragging = False
        self._page = -1
        self._keyboard_focus = False
        self.render_timer = QTimer(self, singleShot=True, interval=RENDER_DELAY)
        self.render_timer.timeout.connect(self.request)
        source.changed.connect(self._page_arrived)
        source.info_ready.connect(self._page_arrived)
        self.setFrameShape(QFrame.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)   # fit-to-width never fights the bar
        self.viewport().setMouseTracking(True)
        self.viewport().setAutoFillBackground(False)
        self.setAccessibleName('Documento')

    # ---------------------------------------------------------------- geometry
    def set_document(self, sizes):
        self.sizes = sizes
        self.hits, self.current_hit = {}, None
        self.selection = (None, [])
        self._page = -1
        self.relayout()
        self.horizontalScrollBar().setValue(0)
        self.verticalScrollBar().setValue(0)
        self.request()
        self._emit_page()

    def gap(self):
        return metric('space_l')

    def margin(self):
        return metric('space_xl')

    def _fit(self):
        width, height = self.viewport().width(), self.viewport().height()
        if self.zoom_mode == 'width':
            return fit_width(self.sizes, self.mode, width, self.gap(), self.margin())
        if self.zoom_mode == 'page':
            page = max(0, self.current_page())
            return fit_page(self.sizes, self.mode, page, width, height, self.gap(), self.margin())
        return self.zoom

    def relayout(self):
        if self.sizes and self.zoom_mode != 'custom':
            self.zoom = self._fit()
        self.layout = Layout(self.sizes, self.zoom, self.mode, self.viewport().width(), self.gap(), self.margin())
        for bar, extent, page in ((self.horizontalScrollBar(), self.layout.width, self.viewport().width()),
                                  (self.verticalScrollBar(), self.layout.height, self.viewport().height())):
            bar.setRange(0, max(0, round(extent - page)))
            bar.setPageStep(page)
            bar.setSingleStep(max(1, metric('space_xl') * 2))
        self.viewport().update()
        self.scrolled.emit()

    def _keep(self, change, point=None):
        """Apply ``change`` while the document point under ``point`` (default: the centre) stays put."""
        if not self.sizes:
            change()
            self.relayout()
            return
        if point is None:
            point = QPointF(self.viewport().width() / 2, self.viewport().height() / 2)
        hbar, vbar = self.horizontalScrollBar(), self.verticalScrollBar()
        mark = anchor(self.layout, hbar.value() + point.x(), vbar.value() + point.y())
        change()
        self.relayout()
        x, y = locate(self.layout, mark)
        hbar.setValue(round(x - point.x()))
        vbar.setValue(round(y - point.y()))
        self.render_timer.start()
        self._emit_page()

    def set_zoom(self, value, point=None):
        def change():
            self.zoom_mode = 'custom'
            self.zoom = clamp_zoom(value)
        self._keep(change, point)
        self.zoomChanged.emit(self.zoom)

    def zoom_by(self, factor, point=None):
        self.set_zoom(self.zoom * factor, point)

    def set_fit(self, kind):
        def change():
            self.zoom_mode = kind
        if kind == 'page':
            page = self.current_page()
            self.zoom_mode = kind
            self.relayout()
            self.go(page)
        else:
            self._keep(change)
        self.zoomChanged.emit(self.zoom)

    def set_mode(self, mode):
        def change():
            self.mode = mode
        self._keep(change)
        self.zoomChanged.emit(self.zoom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._keep(lambda: None, QPointF(self.viewport().width() / 2, 0))

    # -------------------------------------------------------------- navigation
    def go(self, page, y=None):
        """Scroll ``page`` to the top; ``y`` (points) is a target within it, as links carry."""
        if not 0 <= page < len(self.sizes):
            return
        x, top, w, h = self.layout.rects[page]
        # Half a gap above the page: the previous one is out of sight, the edge still reads as paper.
        lead = self.gap() / 2
        offset = y * w / self.sizes[page][0] - self.margin() if y else -lead
        self.verticalScrollBar().setValue(round(top + max(-lead, offset)))
        if self.layout.width > self.viewport().width():
            self.horizontalScrollBar().setValue(round(x + w / 2 - self.viewport().width() / 2))
        self.request()
        self._emit_page()

    def current_page(self):
        if not self.sizes:
            return -1
        x = self.horizontalScrollBar().value() + self.viewport().width() / 2
        y = self.verticalScrollBar().value() + self.viewport().height() * .35
        page = anchor(self.layout, x, y)[0]
        return self.layout.rows[self.layout.row_of(page)][0]

    def _emit_page(self):
        page = self.current_page()
        if page != self._page:
            self._page = page
            self.setAccessibleDescription(f'Página {page + 1} de {len(self.sizes)}')
            self.pageChanged.emit(page)

    def position(self):
        hbar, vbar = self.horizontalScrollBar(), self.verticalScrollBar()
        page, fx, fy = anchor(self.layout, hbar.value() + self.viewport().width() / 2, vbar.value())
        return {'page': page, 'fx': fx, 'fy': fy, 'zoom': self.zoom, 'zoom_mode': self.zoom_mode, 'view': self.mode}

    def restore(self, state):
        self.mode, self.zoom_mode, self.zoom = state['view'], state['zoom_mode'], state['zoom']
        self.relayout()
        x, y = locate(self.layout, (state['page'], state.get('fx', .5), state.get('fy', 0)))
        self.horizontalScrollBar().setValue(round(x - self.viewport().width() / 2))
        self.verticalScrollBar().setValue(round(y))
        self.request()
        self._emit_page()
        self.zoomChanged.emit(self.zoom)

    def scrollContentsBy(self, dx, dy):
        self.viewport().update()
        self.request()
        self._emit_page()
        self.scrolled.emit()

    # ---------------------------------------------------------------- rendering
    def request(self):
        """Ask for the visible pages first, then half a window above and below."""
        if not self.sizes:
            return
        top, height = self.verticalScrollBar().value(), self.viewport().height()
        visible = self.layout.visible(top, top + height)
        around = [p for p in self.layout.visible(top - height / 2, top + height * 1.5) if p not in visible]
        ratio = self.devicePixelRatioF()
        self.source.want([(page, self.pixel_width(page, ratio)) for page in visible + around])

    def pixel_width(self, page, ratio=None):
        width = self.layout.rects[page][2] * (ratio or self.devicePixelRatioF())
        return max(16, int(round(width / 8)) * 8)

    def _page_arrived(self, page):
        top = self.verticalScrollBar().value()
        if page in self.layout.visible(top, top + self.viewport().height()):
            self.viewport().update()

    def page_rect(self, page):
        x, y, w, h = self.layout.rects[page]
        return QRectF(x - self.horizontalScrollBar().value(), y - self.verticalScrollBar().value(), w, h)

    def to_viewport(self, page, x, y):
        rect = self.page_rect(page)
        scale = rect.width() / self.sizes[page][0]
        return QPointF(rect.x() + x * scale, rect.y() + y * scale)

    def _box(self, rect, page_rect, scale):
        return QRectF(page_rect.x() + rect[0] * scale, page_rect.y() + rect[1] * scale,
                      (rect[2] - rect[0]) * scale, (rect[3] - rect[1]) * scale)

    def paintEvent(self, _event):
        painter = QPainter(self.viewport())
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        top = self.verticalScrollBar().value()
        ratio = self.devicePixelRatioF()
        radius = tokens()['corner_xs']
        for page in self.layout.visible(top, top + self.viewport().height()):
            rect = self.page_rect(page)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color('shadow', 60))
            painter.drawRoundedRect(rect.translated(0, 2).adjusted(-1, -1, 1, 1), radius, radius)
            image, _ = self.source.image(page, self.pixel_width(page, ratio))
            if image is not None:
                painter.drawImage(rect, image)
            else:
                painter.setBrush(color('well'))
                painter.drawRect(rect)
            scale = rect.width() / self.sizes[page][0]
            for index, hit in enumerate(self.hits.get(page, ())):
                current = self.current_hit == (page, index)
                painter.setBrush(color('accent', 120 if current else 70))
                painter.setPen(QPen(color('focus'), 2) if current else Qt.NoPen)
                painter.drawRect(self._box(hit, rect, scale))
            if self.selection[0] == page:
                info = self.source.info(page)
                if info:
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(color('text_selection', 150))
                    for index in self.selection[1]:
                        painter.drawRect(self._box(info['words'][index], rect, scale))
        if self._keyboard_focus and self.hasFocus() and self.window().isActiveWindow():
            painter.setPen(QPen(color('focus'), tokens()['focus_width']))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(self.viewport().rect()).adjusted(1, 1, -1, -1))

    # ------------------------------------------------------------ hits & selection
    def set_hits(self, hits, current=None):
        self.hits, self.current_hit = hits, current
        if current is not None and current[0] in hits and current[1] < len(hits[current[0]]):
            self.show_rect(current[0], hits[current[0]][current[1]])
        self.viewport().update()

    def show_rect(self, page, rect):
        """Scroll so the page rectangle (points) is visible, with a margin."""
        box = self._box(rect, self.page_rect(page), self.page_rect(page).width() / self.sizes[page][0])
        view = QRectF(self.viewport().rect()).adjusted(0, self.margin() * 2, 0, -self.margin() * 2)
        if not view.contains(box):
            vbar, hbar = self.verticalScrollBar(), self.horizontalScrollBar()
            vbar.setValue(round(vbar.value() + box.center().y() - self.viewport().height() / 2))
            if box.left() < 0 or box.right() > self.viewport().width():
                hbar.setValue(round(hbar.value() + box.center().x() - self.viewport().width() / 2))
        self.request()

    def clear_selection(self):
        if self.selection[0] is not None:
            self.selection = (None, [])
            self.selectionChanged.emit()
            self.viewport().update()

    def selected_text(self):
        page, indices = self.selection
        info = self.source.info(page) if page is not None else None
        if not info:
            return ''
        text, last = '', None
        for index in indices:
            word = info['words'][index]
            line = (word[5], word[6])
            text += ('' if last is None else ' ' if line == last else '\n') + word[4]
            last = line
        return text

    def selected_rects(self):
        page, indices = self.selection
        info = self.source.info(page) if page is not None else None
        return [info['words'][i][:4] for i in indices] if info else []

    def selection_rect(self):
        page, indices = self.selection
        if page is None or not indices:
            return QRect()
        rect = self.page_rect(page)
        scale = rect.width() / self.sizes[page][0]
        result = QRectF()
        for word in self.selected_rects():
            result = result.united(self._box(word, rect, scale))
        return result.toAlignedRect()

    # ------------------------------------------------------------------- input
    def _hit(self, point):
        """(page, page point in points) under a viewport point, or (None, None)."""
        x = point.x() + self.horizontalScrollBar().value()
        y = point.y() + self.verticalScrollBar().value()
        page = self.layout.page_at(x, y)
        if page is None:
            return None, None
        px, py, w, _ = self.layout.rects[page]
        scale = w / self.sizes[page][0]
        return page, QPointF((x - px) / scale, (y - py) / scale)

    def _link(self, page, point):
        info = self.source.info(page)
        for link in (info or {}).get('links', ()):
            x0, y0, x1, y1 = link['rect']
            if x0 <= point.x() <= x1 and y0 <= point.y() <= y1:
                return link
        return None

    def _nearest(self, page, point):
        info = self.source.info(page)
        words = (info or {}).get('words') or []
        if not words:
            return None
        return min(range(len(words)), key=lambda i:
                   max(words[i][0] - point.x(), 0, point.x() - words[i][2]) ** 2 +
                   max(words[i][1] - point.y(), 0, point.y() - words[i][3]) ** 2)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self.setFocus(Qt.MouseFocusReason)
        page, point = self._hit(event.position())
        self._dragging = False
        if page is None:
            self._press = None
            self.clear_selection()
            return
        if self.note_mode:
            self._press = None
            self.noteRequested.emit(page, point)
            return
        self._press = (event.position(), page, point, self._link(page, point))
        self._anchor_word = self._nearest(page, point)

    def mouseMoveEvent(self, event):
        if self._press and event.buttons() & Qt.LeftButton:
            start, page, _, _ = self._press
            if not self._dragging and (event.position() - start).manhattanLength() < DRAG:
                return
            self._dragging = True
            if self._anchor_word is None:
                return
            rect = self.page_rect(page)
            scale = rect.width() / self.sizes[page][0]
            point = QPointF((event.position().x() - rect.x()) / scale, (event.position().y() - rect.y()) / scale)
            end = self._nearest(page, point)
            first, last = sorted((self._anchor_word, end))
            self.selection = (page, list(range(first, last + 1)))
            self.selectionChanged.emit()
            self.viewport().update()
            return
        page, point = self._hit(event.position())
        link = self._link(page, point) if page is not None else None
        if self.note_mode:
            self.viewport().setCursor(Qt.CrossCursor)
        elif link:
            self.viewport().setCursor(Qt.PointingHandCursor)
            target = link.get('uri') or f'Ir a la página {link["page"] + 1}'
            QToolTip.showText(event.globalPosition().toPoint(), target, self.viewport())
        else:
            self.viewport().setCursor(Qt.IBeamCursor if page is not None else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        press, self._press = self._press, None
        if event.button() != Qt.LeftButton or press is None:
            return
        if self._dragging:
            self._dragging = False
            if self.selection[1]:
                self.selectionFinished.emit()
            return
        self.clear_selection()
        if press[3] is not None:
            self.linkActivated.emit(press[3])

    def mouseDoubleClickEvent(self, event):
        page, point = self._hit(event.position())
        word = self._nearest(page, point) if page is not None and not self.note_mode else None
        if word is not None:
            self.selection = (page, [word])
            self.selectionChanged.emit()
            self.selectionFinished.emit()
            self.viewport().update()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            steps = event.angleDelta().y() / 120
            if steps:
                self.zoom_by(WHEEL_STEP ** steps, event.position())
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        key, bar = event.key(), self.verticalScrollBar()
        if key == Qt.Key_Home:
            bar.setValue(0)
        elif key == Qt.Key_End:
            bar.setValue(bar.maximum())
        elif key == Qt.Key_Space:
            step = bar.pageStep() - self.margin() * 2
            bar.setValue(bar.value() + (-step if event.modifiers() & Qt.ShiftModifier else step))
        elif key == Qt.Key_Escape and self.selection[0] is not None:
            self.clear_selection()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        # The ring marks keyboard arrival only; a click on the page already shows where focus is.
        self._keyboard_focus = event.reason() in (Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)
        super().focusInEvent(event)
        self.viewport().update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.viewport().update()

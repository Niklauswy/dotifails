"""Pages for the view: rasters and text asked from the engine only for what is on screen.

``want`` is called with the visible pages (first) and the prefetch margin. Queued renders and text
for anything else are cancelled; replies for an older document or an older revision of a page (one
that was edited since) are dropped.
"""
from collections import OrderedDict

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from wysun_pdf.cache import RenderCache
from wysun_pdf.layout import raster_width

INFO_LIMIT = 96


class PageSource(QObject):
    changed = Signal(int)      # a raster arrived for this page
    info_ready = Signal(int)   # words, links and annotations arrived

    def __init__(self, worker, parent=None):
        super().__init__(parent)
        self.worker = worker
        self.cache = RenderCache()
        self.infos = OrderedDict()
        self.sizes = []
        self.generation = 0
        self.revisions = {}
        self.pending = {}          # ('render'|'info', page) -> width or True
        self.requested = []        # (page, width) of every render asked for; tests read it

    def reset(self, sizes):
        self.generation += 1
        self.sizes = sizes
        self.cache.clear()
        self.infos.clear()
        self.revisions.clear()
        self.pending.clear()
        self.requested = []
        self.worker.cancel(lambda op, key: op in ('render', 'page_info'))

    def width_for(self, page, width):
        w, h = self.sizes[page]
        return raster_width(w, h, width)

    def _settle(self):
        """Forget pending requests the worker no longer holds (cancelled ones never answer)."""
        live = self.worker.queued_keys()
        active = getattr(self.worker, 'active', None)
        if active is not None and active[4] is not None:
            live.add(active[4])
        for key in [key for key in self.pending if key not in live]:
            del self.pending[key]

    def want(self, requests):
        if not self.sizes:
            return
        requests = [(page, self.width_for(page, width)) for page, width in requests if 0 <= page < len(self.sizes)]
        pages = {page for page, _ in requests}
        self.worker.cancel(lambda op, key: op in ('render', 'page_info') and key is not None and key[1] not in pages)
        self._settle()
        for page, width in requests:
            key = ('render', page)
            if self.cache.get(page, width) is None and self.pending.get(key) != width:
                self._render(page, width)
        for page, _ in requests:
            key = ('info', page)
            if page not in self.infos and key not in self.pending:
                self._info(page)

    def _render(self, page, width):
        generation, revision = self.generation, self.revisions.get(page, 0)
        self.pending[('render', page)] = width
        self.requested.append((page, width))

        def done(reply):
            if generation != self.generation or revision != self.revisions.get(page, 0):
                return
            if self.pending.get(('render', page)) == width:
                del self.pending[('render', page)]
            if 'result' not in reply:
                return
            result = reply['result']
            image = QImage(result['blob'], result['width'], result['height'], result['stride'],
                           QImage.Format_RGB888).copy()
            self.cache.put(page, width, image, image.sizeInBytes())
            self.changed.emit(page)
        self.worker.request('render', done, key=('render', page), page=page, width=width)

    def _info(self, page):
        generation, revision = self.generation, self.revisions.get(page, 0)
        self.pending[('info', page)] = True

        def done(reply):
            if generation != self.generation or revision != self.revisions.get(page, 0):
                return
            self.pending.pop(('info', page), None)
            if 'result' not in reply:
                return
            self.infos[page] = reply['result']
            while len(self.infos) > INFO_LIMIT:
                self.infos.popitem(last=False)
            self.info_ready.emit(page)
        self.worker.request('page_info', done, key=('info', page), page=page)

    def image(self, page, width):
        """(QImage or None, exact) for ``page`` at ``width`` pixels (capped like the engine)."""
        if not 0 <= page < len(self.sizes):
            return None, False
        return self.cache.best(page, self.width_for(page, width))

    def info(self, page):
        info = self.infos.get(page)
        if info is not None:
            self.infos.move_to_end(page)
        return info

    def invalidate(self, page):
        """The page changed (an annotation): forget its raster and text, drop answers already on the way."""
        self.revisions[page] = self.revisions.get(page, 0) + 1
        self.cache.drop(page)
        self.infos.pop(page, None)
        self.pending.pop(('render', page), None)
        self.pending.pop(('info', page), None)
        self.worker.cancel(lambda op, key: key in (('render', page), ('info', page)))

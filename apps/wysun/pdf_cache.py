"""Rasters kept in memory: least recently used first out, bounded in bytes and in widths per page."""
from collections import OrderedDict

BUDGET = 192 * 2 ** 20


class RenderCache:
    def __init__(self, budget=BUDGET, per_page=2):
        self.budget, self.per_page = budget, per_page
        self.entries = OrderedDict()   # (page, width) -> (image, nbytes)
        self.bytes = 0

    def put(self, page, width, image, nbytes):
        self._remove((page, width))
        if nbytes > self.budget:
            return
        self.entries[(page, width)] = (image, nbytes)
        self.bytes += nbytes
        widths = [key for key in self.entries if key[0] == page]
        for key in widths[:-self.per_page]:
            self._remove(key)
        while self.bytes > self.budget:
            self._remove(next(iter(self.entries)))

    def get(self, page, width):
        entry = self.entries.get((page, width))
        if entry is None:
            return None
        self.entries.move_to_end((page, width))
        return entry[0]

    def best(self, page, width):
        """(image, exact): the requested width, else the closest one this page has, else (None, False)."""
        exact = self.get(page, width)
        if exact is not None:
            return exact, True
        widths = [key[1] for key in self.entries if key[0] == page]
        if not widths:
            return None, False
        return self.get(page, min(widths, key=lambda w: abs(w - width))), False

    def drop(self, page):
        for key in [key for key in self.entries if key[0] == page]:
            self._remove(key)

    def clear(self):
        self.entries.clear()
        self.bytes = 0

    def _remove(self, key):
        entry = self.entries.pop(key, None)
        if entry is not None:
            self.bytes -= entry[1]

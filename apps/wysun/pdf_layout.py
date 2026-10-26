"""Reader geometry without Qt: page placement, visibility, fit zooms and raster limits."""
from bisect import bisect_left, bisect_right
import math

MAX_RASTER_WIDTH = 2800
MAX_RASTER_PIXELS = 8_000_000


def raster_width(page_width, page_height, want):
    """Pixel width the engine renders for ``want``: at most 2800 px wide and 8 MP, even for oversized pages."""
    limit = math.sqrt(MAX_RASTER_PIXELS / (page_width * page_height)) * page_width
    return max(1, int(min(want, MAX_RASTER_WIDTH, limit)))
PX_PER_PT = 4 / 3      # 100 %: a PDF point at 96 dpi
ZOOM_MIN = .1
ZOOM_MAX = 8.0


def clamp_zoom(zoom):
    return max(ZOOM_MIN, min(ZOOM_MAX, zoom))


def rows_for(count, mode):
    step = 2 if mode == 'spread' else 1
    return [list(range(start, min(count, start + step))) for start in range(0, count, step)]


class Layout:
    """Where every page sits, in content pixels, for one zoom, view mode and viewport width.

    ``rects[i]`` is ``(x, y, w, h)``. Rows are centred horizontally; pages in a row share its vertical centre.
    """

    def __init__(self, sizes, zoom, mode='single', viewport_width=0, gap=16, margin=24):
        self.sizes, self.zoom, self.mode, self.gap, self.margin = sizes, zoom, mode, gap, margin
        scale = zoom * PX_PER_PT
        self.rows = rows_for(len(sizes), mode)
        widths = [sum(sizes[p][0] * scale for p in row) + gap * (len(row) - 1) for row in self.rows]
        self.width = max(viewport_width, max(widths, default=0) + 2 * margin)
        self.rects = [None] * len(sizes)
        self.tops, self.bottoms = [], []
        y = margin
        for row, row_width in zip(self.rows, widths):
            height = max(sizes[p][1] * scale for p in row)
            x = (self.width - row_width) / 2
            for p in row:
                w, h = sizes[p][0] * scale, sizes[p][1] * scale
                self.rects[p] = (x, y + (height - h) / 2, w, h)
                x += w + gap
            self.tops.append(y)
            self.bottoms.append(y + height)
            y += height + gap
        self.height = (y - gap + margin) if self.rows else 2 * margin

    def row_of(self, page):
        return page // 2 if self.mode == 'spread' else page

    def visible(self, top, bottom):
        """Pages whose row intersects the band [top, bottom]."""
        first = bisect_left(self.bottoms, top)
        last = bisect_right(self.tops, bottom)
        return [p for row in self.rows[first:last] for p in row]

    def page_at(self, x, y):
        for page in self.visible(y, y):
            px, py, w, h = self.rects[page]
            if px <= x <= px + w and py <= y <= py + h:
                return page
        return None

    def nearest_row(self, y):
        index = min(max(bisect_left(self.tops, y) - 1, 0), len(self.rows) - 1)
        if index + 1 < len(self.rows) and y - self.bottoms[index] > self.tops[index + 1] - y:
            index += 1
        return index


def fit_width(sizes, mode, viewport_width, gap=16, margin=24):
    best = None
    for row in rows_for(len(sizes), mode):
        points = sum(sizes[p][0] for p in row)
        zoom = (viewport_width - 2 * margin - gap * (len(row) - 1)) / (points * PX_PER_PT)
        best = zoom if best is None else min(best, zoom)
    return clamp_zoom(best or 1.0)


def fit_page(sizes, mode, page, viewport_width, viewport_height, gap=16, margin=24):
    row = rows_for(len(sizes), mode)[page // 2 if mode == 'spread' else page]
    width = fit_width([sizes[p] for p in row], 'spread' if len(row) > 1 else 'single', viewport_width, gap, margin)
    height = (viewport_height - 2 * margin) / (max(sizes[p][1] for p in row) * PX_PER_PT)
    return clamp_zoom(min(width, height))


def anchor(layout, x, y):
    """(page, fx, fy): the point as a fraction of the page under it (or of the closest page)."""
    page = layout.page_at(x, y)
    if page is None:
        row = layout.rows[layout.nearest_row(y)]
        page = min(row, key=lambda p: abs(layout.rects[p][0] + layout.rects[p][2] / 2 - x))
    px, py, w, h = layout.rects[page]
    return page, (x - px) / w, (y - py) / h


def locate(layout, mark):
    page, fx, fy = mark
    px, py, w, h = layout.rects[page]
    return px + fx * w, py + fy * h

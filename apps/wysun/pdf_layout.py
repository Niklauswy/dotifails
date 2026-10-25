"""Reader geometry without Qt: page placement, visibility, fit zooms and raster limits."""
import math

MAX_RASTER_WIDTH = 2800
MAX_RASTER_PIXELS = 8_000_000


def raster_width(page_width, page_height, want):
    """Pixel width the engine renders for ``want``: at most 2800 px wide and 8 MP, even for oversized pages."""
    limit = math.sqrt(MAX_RASTER_PIXELS / (page_width * page_height)) * page_width
    return max(1, int(min(want, MAX_RASTER_WIDTH, limit)))

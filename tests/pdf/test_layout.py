"""Pure geometry of the continuous view: no Qt, no PyMuPDF."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
from pdf_layout import (Layout, PX_PER_PT, ZOOM_MAX, ZOOM_MIN, anchor, fit_page, fit_width, locate,  # noqa: E402
                        raster_width)

A4 = [595.0, 842.0]


def layout(pages=60, zoom=1.0, mode='single', viewport=1000, sizes=None):
    return Layout(sizes or [A4] * pages, zoom, mode, viewport, gap=16, margin=24)


class LayoutTests(unittest.TestCase):
    def test_single_column_stacks_pages_with_a_gap(self):
        result = layout(3)
        x, y, w, h = result.rects[0]
        self.assertAlmostEqual(w, 595 * PX_PER_PT)
        self.assertEqual(y, 24)
        self.assertAlmostEqual(result.rects[1][1], y + h + 16)
        self.assertAlmostEqual(x, (1000 - w) / 2)
        self.assertAlmostEqual(result.height, 24 * 2 + h * 3 + 16 * 2)

    def test_spread_pairs_pages_side_by_side(self):
        result = layout(5, mode='spread', viewport=2000)
        self.assertEqual(result.rows, [[0, 1], [2, 3], [4]])
        left, right = result.rects[0], result.rects[1]
        self.assertEqual(left[1], right[1])
        self.assertAlmostEqual(right[0], left[0] + left[2] + 16)
        self.assertEqual(result.row_of(3), 1)

    def test_rows_center_pages_of_different_heights(self):
        result = layout(sizes=[A4, [595.0, 421.0]], mode='spread', viewport=2000)
        tall, short = result.rects
        self.assertAlmostEqual(short[1] + short[3] / 2, tall[1] + tall[3] / 2)

    def test_wide_content_grows_past_the_viewport(self):
        result = layout(2, zoom=3.0, viewport=500)
        self.assertAlmostEqual(result.width, 595 * PX_PER_PT * 3 + 48)
        self.assertEqual(result.rects[0][0], 24)

    def test_visible_only_returns_intersecting_pages(self):
        result = layout(60)
        top = result.rects[30][1] + 10
        pages = result.visible(top, top + 1300)
        self.assertEqual(pages, [30, 31])
        self.assertEqual(result.visible(-100, -1), [])
        self.assertEqual(result.page_at(result.rects[30][0] + 5, top), 30)
        self.assertIsNone(result.page_at(1, top))

    def test_fit_width_fills_the_viewport_between_margins(self):
        zoom = fit_width([A4] * 4, 'single', 1000, gap=16, margin=24)
        self.assertAlmostEqual(layout(4, zoom=zoom).rects[0][2], 1000 - 48)
        spread = fit_width([A4] * 4, 'spread', 1000, gap=16, margin=24)
        rects = layout(4, zoom=spread, mode='spread').rects
        self.assertAlmostEqual(rects[1][0] + rects[1][2] - rects[0][0], 1000 - 48)

    def test_fit_page_keeps_the_whole_row_visible(self):
        zoom = fit_page([A4] * 4, 'single', 2, 1000, 700, gap=16, margin=24)
        self.assertAlmostEqual(layout(4, zoom=zoom).rects[2][3], 700 - 48)

    def test_zoom_is_clamped(self):
        self.assertEqual(fit_width([A4], 'single', 10, gap=16, margin=24), ZOOM_MIN)
        self.assertEqual(fit_width([[10.0, 10.0]], 'single', 100000, gap=16, margin=24), ZOOM_MAX)

    def test_anchor_survives_a_zoom_change(self):
        before = layout(20, zoom=1.0)
        x, y, w, h = before.rects[7]
        point = (x + w * .25, y + h * .6)
        mark = anchor(before, *point)
        self.assertEqual(mark[0], 7)
        after = layout(20, zoom=2.5)
        new = locate(after, mark)
        ax, ay, aw, ah = after.rects[7]
        self.assertAlmostEqual(new[0], ax + aw * .25, delta=1)
        self.assertAlmostEqual(new[1], ay + ah * .6, delta=1)

    def test_anchor_in_a_gap_uses_the_nearest_page(self):
        result = layout(5)
        between = result.rects[1][1] + result.rects[1][3] + 4
        self.assertIn(anchor(result, 500, between)[0], (1, 2))

    def test_raster_width_respects_both_limits(self):
        self.assertEqual(raster_width(595, 842, 1200), 1200)
        self.assertEqual(raster_width(400, 200, 9000), 2800)
        self.assertLess(raster_width(5000, 5000, 9000), 2800)
        self.assertLessEqual(raster_width(5000, 5000, 9000) ** 2, 8_000_000)


if __name__ == '__main__':
    unittest.main()

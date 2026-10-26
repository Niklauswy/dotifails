from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from wysun_pdf.cache import RenderCache  # noqa: E402


class RenderCacheTests(unittest.TestCase):
    def test_least_recently_used_is_evicted_over_budget(self):
        cache = RenderCache(budget=300, per_page=2)
        for page in range(3):
            cache.put(page, 100, f'image{page}', 100)
        cache.get(0, 100)
        cache.put(3, 100, 'image3', 100)
        self.assertIsNone(cache.get(1, 100))
        self.assertEqual(cache.get(0, 100), 'image0')
        self.assertEqual(cache.bytes, 300)

    def test_at_most_two_widths_per_page(self):
        cache = RenderCache(budget=10_000, per_page=2)
        for width in (100, 200, 300):
            cache.put(5, width, f'w{width}', 10)
        self.assertIsNone(cache.get(5, 100))
        self.assertEqual(cache.bytes, 20)

    def test_best_prefers_exact_then_nearest_width(self):
        cache = RenderCache()
        cache.put(1, 400, 'small', 10)
        cache.put(1, 900, 'large', 10)
        self.assertEqual(cache.best(1, 900), ('large', True))
        self.assertEqual(cache.best(1, 800), ('large', False))
        self.assertEqual(cache.best(1, 500), ('small', False))
        self.assertEqual(cache.best(2, 500), (None, False))

    def test_drop_and_clear(self):
        cache = RenderCache()
        cache.put(1, 100, 'a', 10); cache.put(2, 100, 'b', 10)
        cache.drop(1)
        self.assertIsNone(cache.get(1, 100))
        cache.clear()
        self.assertEqual(cache.bytes, 0)

    def test_an_image_larger_than_the_budget_is_not_kept(self):
        cache = RenderCache(budget=50)
        cache.put(1, 100, 'huge', 80)
        self.assertEqual(cache.bytes, 0)


if __name__ == '__main__':
    unittest.main()

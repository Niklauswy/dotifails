"""Image decoding and the canvas: orientation, scaled decoding, budgets, caching, stale results, zoom maths."""
import unittest
from pathlib import Path

import media_support as support

support.app()
from PySide6.QtCore import QPointF, QSize  # noqa: E402
from wysun_media import image  # noqa: E402
from wysun_media.errors import MediaError  # noqa: E402
from wysun_media.source import open_source  # noqa: E402


class DecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = support.fixtures()

    def decode(self, name, width=0, height=0, **options):
        source = open_source(self.files / name)
        return image.decode(source.path, source.fingerprint, QSize(width, height) if width else QSize(), **options)

    def test_exif_orientation_is_applied_once(self):
        flat = self.decode('exif1.jpg')
        self.assertEqual((flat.size.width(), flat.size.height()), (120, 80))
        for orientation in (5, 6, 7, 8):                       # the four that turn the picture a quarter
            frame = self.decode(f'exif{orientation}.jpg')
            self.assertEqual((frame.size.width(), frame.size.height()), (80, 120), orientation)
            self.assertEqual((frame.image.width(), frame.image.height()), (80, 120), orientation)
        for orientation in (2, 3, 4):
            self.assertEqual(self.decode(f'exif{orientation}.jpg').size, QSize(120, 80))

    def test_orientation_moves_the_marker(self):
        """Orientation 6 means "rotate 90° clockwise to display": the white corner marker ends at the top right."""
        frame = self.decode('exif6.jpg')
        self.assertGreater(frame.image.pixelColor(frame.image.width() - 3, 3).lightness(), 220)
        self.assertLess(frame.image.pixelColor(3, 3).lightness(), 220)

    def test_jpeg_decodes_scaled_and_never_the_full_image(self):
        frame = self.decode('big.jpg', 600, 400)
        self.assertEqual(frame.size, QSize(6000, 4000))
        self.assertLessEqual(frame.image.width(), 700)
        self.assertAlmostEqual(frame.scale, frame.image.width() / 6000, places=3)

    def test_png_decodes_in_full_and_keeps_a_display_copy(self):
        cache = image.Cache()
        frame = image.decode(self.files / 'plain.png', 'fp', QSize(30, 20), cache)
        self.assertLess(frame.image.width(), 120)
        self.assertEqual(frame.size, QSize(120, 80))
        full = cache.best('fp', 1.0)
        self.assertIsNotNone(full)
        self.assertEqual(full.image.width(), 120)

    def test_budget_refuses_instead_of_allocating(self):
        with self.assertRaises(MediaError) as caught:
            self.decode('plain.bmp', budget=100)                 # BMP cannot scale while decoding
        self.assertEqual(caught.exception.category, 'too_large')

    def test_damaged_files_report_clear_errors(self):
        expectations = {'corrupt.png': {'unreadable', 'decode', 'unsupported'}, 'truncated.jpg': {'decode', 'unreadable'},
                        'empty.jpg': {'unreadable', 'unsupported', 'decode'}}
        for name, allowed in expectations.items():
            with self.assertRaises(MediaError, msg=name) as caught:
                self.decode(name)
            self.assertIn(caught.exception.category, allowed, name)

    def test_alpha_is_preserved(self):
        self.assertTrue(self.decode('alpha.png').image.hasAlphaChannel())

    def test_animated_files_are_flagged(self):
        self.assertTrue(self.decode('anim.gif').animated)
        self.assertFalse(self.decode('plain.png').animated)


class CacheTests(unittest.TestCase):
    def frame(self, fingerprint, scale, side=100):
        from PySide6.QtGui import QImage
        return image.Frame(QImage(side, side, QImage.Format_RGB32), QSize(int(side / scale), int(side / scale)), scale, 'png', False, fingerprint)

    def test_best_returns_the_smallest_good_enough_decode(self):
        cache = image.Cache()
        cache.put(self.frame('a', .25))
        cache.put(self.frame('a', 1.0))
        self.assertEqual(cache.best('a', .2).scale, .25)
        self.assertEqual(cache.best('a', .5).scale, 1.0)
        self.assertIsNone(cache.best('b', .1))

    def test_budget_is_enforced_least_recently_used_first(self):
        one = self.frame('x', 1.0, 100).bytes
        cache = image.Cache(limit=one * 2 + 10)
        for name in ('a', 'b', 'c'):
            cache.put(self.frame(name, 1.0))
        self.assertLessEqual(cache.used, cache.limit)
        self.assertIsNone(cache.best('a', 1.0))
        self.assertIsNotNone(cache.best('c', 1.0))

    def test_an_image_larger_than_the_budget_is_not_retained(self):
        cache = image.Cache(limit=100)
        cache.put(self.frame('big', 1.0, 100))
        self.assertEqual(cache.used, 0)


class ViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = support.fixtures()

    def view(self, name='plain.png', size=(400, 300)):
        view = image.ImageView()
        view.resize(*size)
        view.show()
        self.addCleanup(view.deleteLater)
        loaded = []
        view.loaded.connect(loaded.append)
        view.show_source(open_source(self.files / name))
        self.assertTrue(support.pump(lambda: loaded), name)
        return view

    def test_fit_never_enlarges_a_small_image_and_actual_is_one_pixel_per_pixel(self):
        view = self.view('plain.png')
        self.assertEqual(view.mode, 'fit')
        self.assertAlmostEqual(view.scale, 1 / view.devicePixelRatioF())
        self.assertAlmostEqual(view.zoom_percent, 100.0)
        view.set_mode('actual')
        self.assertAlmostEqual(view.zoom_percent, 100.0)

    def test_fit_shrinks_a_large_image_to_the_window(self):
        view = self.view('big.jpg', size=(600, 400))
        self.assertAlmostEqual(view.scale, 600 / 6000)
        self.assertLess(view.zoom_percent, 11)

    def test_zoom_keeps_the_point_under_the_cursor(self):
        view = self.view('plain.png')
        view.zoom_to(5)                                          # 600 x 400: larger than the canvas, so it can pan
        anchor = QPointF(230, 140)
        before, _ = view._transform().inverted()
        picked = before.map(anchor)
        view.zoom_by(1.4, anchor)
        after = view._transform().map(picked)
        self.assertLess((after - anchor).manhattanLength(), 1.0)
        self.assertEqual(view.mode, 'zoom')

    def test_a_picture_smaller_than_the_canvas_stays_centred(self):
        view = self.view('plain.png')
        view.zoom_by(2.0, QPointF(10, 10))                       # 240 x 160 on 400 x 300
        self.assertEqual((view._offset.x(), view._offset.y()), (0.0, 0.0))

    def test_zoom_is_clamped(self):
        view = self.view('plain.png')
        view.zoom_to(1e9)
        self.assertEqual(view.scale, image.MAX_SCALE)
        view.zoom_to(0)
        self.assertEqual(view.scale, image.MIN_SCALE)

    def test_pan_cannot_leave_the_image(self):
        view = self.view('plain.png')
        view.zoom_to(10)                                         # 1200 x 800 on a 400 x 300 canvas
        view._offset = view._clamp(QPointF(1e6, 1e6), view.scale)
        self.assertLessEqual(abs(view._offset.x()), (1200 - 400) / 2 + 1e-6)
        self.assertLessEqual(abs(view._offset.y()), (800 - 300) / 2 + 1e-6)

    def test_rotation_is_presentational_and_swaps_the_extent(self):
        view = self.view('plain.png')
        view.rotate()
        self.assertEqual(view._extent(), (80, 120))
        view.rotate(-1)
        self.assertEqual(view._extent(), (120, 80))
        self.assertEqual(open_source(self.files / 'plain.png').size, (self.files / 'plain.png').stat().st_size)

    def test_a_replaced_request_never_shows_stale_output(self):
        image.jobs().cache.clear()                               # no synchronous hits: every request is a real decode
        view = image.ImageView()
        view.resize(400, 300)
        view.show()
        shown = []
        view.loaded.connect(lambda frame: shown.append(Path(view.source.path).name))
        for name in ('big.jpg', 'plain.png', 'plain.bmp', 'alpha.png'):
            view.show_source(open_source(self.files / name))
        self.assertTrue(support.pump(lambda: shown))
        support.settle(.4)
        self.assertEqual(shown, ['alpha.png'])
        self.assertEqual(view.frame.fingerprint, open_source(self.files / 'alpha.png').fingerprint)

    def test_errors_are_reported_without_a_frame(self):
        view = image.ImageView()
        view.resize(300, 200)
        view.show()
        errors = []
        view.failed.connect(errors.append)
        view.show_source(open_source(self.files / 'truncated.jpg'))
        self.assertTrue(support.pump(lambda: errors))
        self.assertIsNone(view.frame)

    def test_prefetched_neighbours_open_from_the_cache(self):
        view = self.view('plain.png')
        neighbour = open_source(self.files / 'alpha.png')
        view.prefetch([neighbour])
        self.assertTrue(support.pump(lambda: image.jobs().lookup(neighbour, view._want()) is not None))
        shown = []
        view.loaded.connect(shown.append)
        view.show_source(neighbour)
        self.assertTrue(shown, 'a cached image is adopted synchronously')

    def test_animation_starts_paused_with_reduced_motion_and_toggles(self):
        view = self.view('anim.gif')
        self.assertTrue(view.animated)
        self.assertFalse(view.animating)                         # tests run with reduced motion
        view.toggle_animation()
        self.assertTrue(view.animating)
        view.hide()
        self.assertFalse(view.animating)

    def test_clear_stops_everything(self):
        view = self.view('anim.gif')
        view.clear()
        self.assertFalse(view.animated)
        self.assertIsNone(view.frame)


if __name__ == '__main__':
    unittest.main()

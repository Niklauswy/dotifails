"""Shape: the corner scale comes from the tokens (each style may give its own numbers); morphing honours reduced motion."""
import unittest

import media_support as support

support.app()
from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from wysun_media import host, shape  # noqa: E402
from wysun_core import theme  # noqa: E402

VARIANTS = ['dark', 'light']


def with_tokens(values, reduced=False):
    base = host.get()
    host.install(host.Host(color=base.color, token=lambda name: values[name], font=base.font, symbol=base.symbol,
                           reduced_motion=lambda: reduced, on_theme_changed=base.on_theme_changed))
    return base


class ShapeTests(unittest.TestCase):
    def tearDown(self):
        host.install(self.base)

    def setUp(self):
        self.base = host.get()

    def test_every_variant_defines_the_whole_scale(self):
        for pair in VARIANTS:
            values = theme.resolve(pair)
            self.assertEqual(shape.CORNERS, ('none', 'extraSmall', 'small', 'medium', 'large', 'extraLarge', 'full'))
            for step in shape.CORNERS[1:]:
                self.assertIn('rounding.' + step, values, (pair, step))
            with_tokens(values)
            scale = [shape.radius(step) for step in shape.CORNERS]
            self.assertEqual(scale, sorted(scale), f'{pair}: the scale must grow')
            self.assertEqual(scale[0], 0)

    def test_radius_is_clamped_to_half_the_short_side(self):
        with_tokens(theme.resolve(VARIANTS[0]))
        rect = QRectF(0, 0, 100, 40)
        self.assertEqual(shape.radius('full', rect), 20)
        self.assertEqual(shape.radius('extraLarge'), theme.resolve(VARIANTS[0])['rounding.extraLarge'])
        self.assertEqual(shape.radius('large', QRectF(0, 0, 10, 10)), 5)

    def test_rounded_paths(self):
        with_tokens(theme.resolve(VARIANTS[0]))
        pill = shape.rounded(QRectF(0, 0, 100, 40), 'full')
        self.assertTrue(pill.contains(QPointF(50, 20)))
        self.assertFalse(pill.contains(QPointF(1, 1)))                 # rounded corner
        square = shape.rounded(QRectF(0, 0, 100, 40), 'none')
        self.assertTrue(square.contains(QPointF(1, 1)))
        flat = shape.rounded(QRectF(0, 0, 100, 40), 'extraLarge', top=False)
        self.assertTrue(flat.contains(QPointF(1, 1)))                  # top edge square
        self.assertFalse(flat.contains(QPointF(1, 39)))                # bottom edge rounded

    def test_frame_outside_covers_only_the_slivers(self):
        with_tokens(theme.resolve(VARIANTS[0]))
        slivers = shape.frame_outside(QRectF(0, 0, 100, 100), 'extraLarge')
        self.assertTrue(slivers.contains(QPointF(1, 1)))
        self.assertFalse(slivers.contains(QPointF(50, 50)))

    def test_morph_is_instant_with_reduced_motion_and_gradual_otherwise(self):
        with_tokens(theme.resolve(VARIANTS[-1]), reduced=True)
        morph = shape.Morph()
        morph.go(1.0)
        self.assertEqual(morph.value, 1.0)
        with_tokens(theme.resolve(VARIANTS[-1]), reduced=False)
        gradual = shape.Morph()
        gradual.go(1.0)
        self.assertLess(gradual.value, 1.0)
        self.assertTrue(support.pump(lambda: gradual.value == 1.0, 2))
        self.assertTrue(0 <= shape.lerp(4, 20, .5) - 12 < 1e-9)

    def test_cookie_is_a_closed_shape_around_its_centre(self):
        with_tokens(theme.resolve(VARIANTS[0]))
        path = shape.cookie(QRectF(0, 0, 100, 100), 12)
        self.assertTrue(path.contains(QPointF(50, 50)))
        self.assertFalse(path.contains(QPointF(1, 1)))


if __name__ == '__main__':
    unittest.main()

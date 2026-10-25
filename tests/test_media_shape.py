"""Shape: the corner scale comes from the tokens (each style may give its own numbers); morphing honours reduced motion."""
import unittest

import media_support as support

support.app()
from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from wysun_media import host, shape  # noqa: E402
import theme_core  # noqa: E402

VARIANTS = [(style, variant) for style, spec in theme_core.styles().items() for variant in spec['variants']]     # whatever the theme defines today


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
            values = theme_core.resolve(*pair)
            for step in shape.CORNERS:
                self.assertIn('corner_' + step, values, (pair, step))
            scale = [values['corner_' + step] for step in shape.CORNERS]
            self.assertEqual(scale, sorted(scale), f'{pair}: the scale must grow')
            self.assertEqual(scale[0], 0)

    @unittest.skipIf(len(theme_core.styles()) < 2, 'one style: nothing to compare')
    def test_styles_may_differ_in_numbers_but_not_in_structure(self):
        first, second = (theme_core.resolve(style, spec['default_variant']) for style, spec in list(theme_core.styles().items())[:2])
        self.assertEqual(first['corner_full'], second['corner_full'], '"fully round" means the same in every style')
        self.assertEqual({k for k in first if k.startswith('corner_')}, {k for k in second if k.startswith('corner_')})

    def test_radius_is_clamped_to_half_the_short_side(self):
        with_tokens(theme_core.resolve(*VARIANTS[0]))
        rect = QRectF(0, 0, 100, 40)
        self.assertEqual(shape.radius('full', rect), 20)
        self.assertEqual(shape.radius('xl'), theme_core.resolve(*VARIANTS[0])['corner_xl'])
        self.assertEqual(shape.radius('l', QRectF(0, 0, 10, 10)), 5)

    def test_rounded_paths(self):
        with_tokens(theme_core.resolve(*VARIANTS[0]))
        pill = shape.rounded(QRectF(0, 0, 100, 40), 'full')
        self.assertTrue(pill.contains(QPointF(50, 20)))
        self.assertFalse(pill.contains(QPointF(1, 1)))                 # rounded corner
        square = shape.rounded(QRectF(0, 0, 100, 40), 'none')
        self.assertTrue(square.contains(QPointF(1, 1)))
        flat = shape.rounded(QRectF(0, 0, 100, 40), 'xl', top=False)
        self.assertTrue(flat.contains(QPointF(1, 1)))                  # top edge square
        self.assertFalse(flat.contains(QPointF(1, 39)))                # bottom edge rounded

    def test_frame_outside_covers_only_the_slivers(self):
        with_tokens(theme_core.resolve(*VARIANTS[0]))
        slivers = shape.frame_outside(QRectF(0, 0, 100, 100), 'xl')
        self.assertTrue(slivers.contains(QPointF(1, 1)))
        self.assertFalse(slivers.contains(QPointF(50, 50)))

    def test_morph_is_instant_with_reduced_motion_and_gradual_otherwise(self):
        with_tokens(theme_core.resolve(*VARIANTS[-1]), reduced=True)
        morph = shape.Morph()
        morph.go(1.0)
        self.assertEqual(morph.value, 1.0)
        with_tokens(theme_core.resolve(*VARIANTS[-1]), reduced=False)
        gradual = shape.Morph()
        gradual.go(1.0)
        self.assertLess(gradual.value, 1.0)
        self.assertTrue(support.pump(lambda: gradual.value == 1.0, 2))
        self.assertTrue(0 <= shape.lerp(4, 20, .5) - 12 < 1e-9)

    def test_cookie_is_a_closed_shape_around_its_centre(self):
        with_tokens(theme_core.resolve(*VARIANTS[0]))
        path = shape.cookie(QRectF(0, 0, 100, 100), 12)
        self.assertTrue(path.contains(QPointF(50, 50)))
        self.assertFalse(path.contains(QPointF(1, 1)))


if __name__ == '__main__':
    unittest.main()

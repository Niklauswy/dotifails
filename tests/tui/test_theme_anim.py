"""wysun_core.tui.theme (palette from the wallpaper scheme) and wysun_core.tui.anim (tweens)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from wysun_core import theme  # noqa: E402
from wysun_core.tui import anim  # noqa: E402
from wysun_core.tui import theme as tui_theme  # noqa: E402

SCHEME = {'name': 'dynamic', 'flavour': 'tonalspot', 'mode': 'light', 'variant': 'tonalspot',
          'wallpaper_hash': 'a' * 64,
          'colours': {'surface': 'abcdef', 'onSurface': '111111', 'primary': '334455'}}


class PaletteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        patcher = patch.dict(os.environ, {})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('WYSUN_THEME', None)
        theme.invalidate()
        self.addCleanup(theme.invalidate)

    def base(self, mode):
        return theme.data()['palettes'][mode]['scheme']

    def test_palette_uses_scheme_when_mode_matches(self):
        theme.write_scheme(dict(SCHEME), self.home)
        palette = tui_theme.Palette.load(self.home)
        self.assertEqual(palette.mode, 'light')
        self.assertEqual(palette['primary'], (0x33, 0x44, 0x55))
        self.assertEqual(palette['surface'], (0xAB, 0xCD, 0xEF))
        self.assertEqual(palette['onSurface'], (0x11, 0x11, 0x11))
        # A role the scheme does not carry comes from the base palette of the same mode.
        self.assertEqual(palette['success'], tui_theme.parse_colour(self.base('light')['success']))
        self.assertEqual(palette['scrim'], tui_theme.parse_colour(self.base('light')['scrim']))
        self.assertIn('primary', palette)
        self.assertEqual(palette.get('notARole'), None)

    def test_palette_falls_back_to_base_palette(self):
        with patch.dict(os.environ, {'WYSUN_THEME': 'light'}):
            theme.invalidate()
            palette = tui_theme.Palette.load(self.home)
        self.assertEqual(palette.mode, 'light')
        for role in ('primary', 'surface', 'onSurface', 'outline', 'success'):
            self.assertEqual(palette[role], tui_theme.parse_colour(self.base('light')[role]), role)

    def test_palette_changed_after_scheme_write(self):
        palette = tui_theme.Palette.load(self.home)
        self.assertEqual(palette.mode, theme.DEFAULT_MODE)
        self.assertFalse(palette.changed(self.home))
        theme.write_scheme(dict(SCHEME), self.home)
        self.assertTrue(palette.changed(self.home))
        fresh = tui_theme.Palette.load(self.home)
        self.assertEqual(fresh.mode, 'light')
        self.assertEqual(fresh['primary'], (0x33, 0x44, 0x55))
        self.assertFalse(fresh.changed(self.home))


class AnimTests(unittest.TestCase):
    def test_bezier_endpoints_and_monotonic(self):
        ease = anim.bezier([0.2, 0.0, 0.0, 1.0])
        self.assertAlmostEqual(ease(0.0), 0.0)
        self.assertAlmostEqual(ease(1.0), 1.0)
        self.assertGreater(ease(0.5), 0.5)
        self.assertLess(ease(0.5), 1.0)
        values = [ease(index / 20) for index in range(21)]
        self.assertEqual(values, sorted(values))
        self.assertAlmostEqual(anim.curve('standard')(0.5), ease(0.5))
        self.assertAlmostEqual(anim.duration('normal'), 0.4)
        self.assertAlmostEqual(anim.duration('small'), 0.2)
        linear = anim.bezier([0, 0, 1, 1])
        self.assertAlmostEqual(linear(0.25), 0.25, places=3)

    def test_lerp_rect_rounds_to_cells(self):
        start = anim.Rect(x=0, y=0, w=10, h=4)
        end = anim.Rect(x=10, y=3, w=0, h=4)
        self.assertEqual(anim.lerp_rect(start, end, 0.0), start)
        self.assertEqual(anim.lerp_rect(start, end, 1.0), end)
        middle = anim.lerp_rect(start, end, 0.5)
        self.assertEqual(middle, anim.Rect(5, 2, 5, 4))
        self.assertIsInstance(middle.x, int)
        self.assertIsInstance(middle.y, int)
        self.assertEqual(anim.fade_steps(0.0), 0.0)
        self.assertEqual(anim.fade_steps(0.6), 0.625)
        self.assertEqual(anim.fade_steps(1.0), 1.0)

    def test_reduced_motion_finishes_instantly(self):
        steps, done = [], []
        animator = anim.Animator()
        with patch.dict(os.environ, {'WYSUN_REDUCED_MOTION': '1'}):
            animator.add(anim.Tween(1.0, anim.bezier([0, 0, 1, 1]), steps.append,
                                    lambda: done.append(True)))
        self.assertEqual(steps, [1.0])
        self.assertEqual(done, [True])
        self.assertFalse(animator.step(0.0))
        with patch.dict(os.environ, {'WYSUN_REDUCED_MOTION': '0'}):
            animator.add(anim.Tween(1.0, anim.bezier([0, 0, 1, 1]), steps.append))
        self.assertTrue(animator.step(0.0))

    def test_animator_runs_until_duration(self):
        values = []
        animator = anim.Animator()
        animator.add(anim.Tween(1.0, lambda t: t, values.append, lambda: values.append('done')))
        self.assertTrue(animator.step(0.0))
        self.assertEqual(values, [0.0])
        self.assertTrue(animator.step(0.5))
        self.assertAlmostEqual(values[-1], 0.5)
        self.assertFalse(animator.step(1.0))
        self.assertAlmostEqual(values[-2], 1.0)
        self.assertEqual(values[-1], 'done')
        self.assertFalse(animator.step(2.0))

        snapped = []
        animator.add(anim.Tween(10.0, lambda t: t, snapped.append, lambda: snapped.append('done')))
        animator.finish_all()
        self.assertEqual(snapped, [1.0, 'done'])
        self.assertFalse(animator.step(3.0))


if __name__ == '__main__':
    unittest.main()

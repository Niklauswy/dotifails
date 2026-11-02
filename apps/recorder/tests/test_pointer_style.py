"""The pretty pointer of a recording: its colour option, a ring that shows on dark and light desktops, and the shell's
start path turning the saved preferences into effects. Only synthetic frames and temporary preferences."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from wysun_recorder import headless
from wysun_recorder.cursor import effect_settings
from wysun_recorder.live_effects import TraceState, paint_frame


def frame_of(colour, w=160, h=120):
    from PySide6.QtGui import QColor, QGuiApplication, QImage
    QGuiApplication.instance() or QGuiApplication([])
    image = QImage(w, h, QImage.Format_ARGB32)
    image.fill(QColor(colour))
    return bytes(image.constBits()[:w * h * 4])


def pixel(frame, w, x, y):
    offset = (y * w + x) * 4
    b, g, r, a = frame[offset:offset + 4]
    return r, g, b


def snapshot(x=80, y=60, w=160, h=120):
    state = TraceState(w, h)
    state.accept(dict(version=1, width=w, height=h, origin=100., native_cursor_embedded=True))
    state.accept([.0, x, y, 0])
    state.accept([.1, x, y, 0])
    return state.snapshot()


def contrast(a, b):
    return max(abs(p - q) for p, q in zip(a, b))


class AccentOptionTests(unittest.TestCase):
    def test_the_accent_is_an_optional_hex_colour(self):
        self.assertEqual(effect_settings({'preset': 'presentation', 'accent': '#3366cc'})['accent'], '#3366cc')
        self.assertNotIn('accent', effect_settings({'preset': 'presentation'}))
        for bad in ('red', '#12345', '3366cc', '#33 66cc', '#3366ccdd', 5, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                effect_settings({'preset': 'presentation', 'accent': bad})

    def test_the_simple_preset_stays_a_native_cursor(self):
        self.assertEqual(effect_settings({'preset': 'simple', 'accent': '#3366cc'}), {})


class RingTests(unittest.TestCase):
    """A faint tint was invisible on dark desktops: the halo is a ring with its own contrast."""

    def band(self, background, accent=None):
        """(painted, plain) pixels along the ring's band, from just inside the line to just outside its white edge."""
        options = {'preset': 'presentation', 'clicks': False}
        if accent:
            options['accent'] = accent
        settings = effect_settings(options)
        plain = frame_of(background)
        out = paint_frame(plain, 160, 120, settings, snapshot(), now=100.1)
        radius = round(23 * settings['size'] / 32)
        return [(pixel(out, 160, 80 + dx, 60), pixel(plain, 160, 80 + dx, 60)) for dx in range(radius - 2, radius + 5)]

    def ring_pixel(self, background, accent=None):
        return max(self.band(background, accent), key=lambda pair: contrast(*pair))

    def test_the_ring_stands_out_on_dark_and_light_desktops(self):
        for background in ('#14161c', '#f4f6fa', '#2165d5'):      # the last one is the default accent itself
            with self.subTest(background=background):
                painted, plain = self.ring_pixel(background)
                self.assertGreaterEqual(contrast(painted, plain), 70, 'the ring must be easy to see')

    def test_a_pale_accent_still_shows_on_a_light_desktop_and_a_dark_one_on_a_dark_desktop(self):
        """The accent follows the wallpaper: a dark-mode scheme has a pale one, a light-mode scheme a deep one."""
        for background, accent in (('#f2f4f8', '#f8b89f'), ('#14161c', '#1b3a8a'), ('#ffffff', '#ffe08a')):
            with self.subTest(background=background, accent=accent):
                painted, plain = self.ring_pixel(background, accent)
                self.assertGreaterEqual(contrast(painted, plain), 110)

    def test_the_ring_takes_the_accent_colour(self):
        reddest = max((p for p, _ in self.band('#14161c', accent='#ff2d55')), key=lambda c: c[0] - c[1])
        self.assertGreater(reddest[0], reddest[1] + 100, reddest)
        self.assertGreater(reddest[0], reddest[2] + 60, reddest)

    def test_the_trail_is_visible_too(self):
        state = TraceState(160, 120)
        state.accept(dict(version=1, width=160, height=120, origin=100., native_cursor_embedded=True))
        for index in range(7):
            state.accept([index * .03, 40 + index * 10, 60, 0])
        settings = effect_settings({'preset': 'trail', 'clicks': False, 'halo': False})
        out = paint_frame(frame_of('#14161c'), 160, 120, settings, state.snapshot(), now=100.18)
        self.assertGreaterEqual(contrast(pixel(out, 160, 80, 60), pixel(frame_of('#14161c'), 160, 80, 60)), 40)


class StartPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wysun-pointer-')
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        patcher = patch.dict(os.environ, {'HOME': str(root / 'home'), 'XDG_CONFIG_HOME': str(root / 'config'),
                                          'XDG_STATE_HOME': str(root / 'state'), 'XDG_DATA_HOME': str(root / 'data')})
        patcher.start()
        self.addCleanup(patcher.stop)
        (root / 'config/wysun/recorder').mkdir(parents=True)
        (root / 'state/wysun').mkdir(parents=True)
        self.prefs = root / 'config/wysun/recorder/preferences.json'
        self.scheme = root / 'state/wysun/scheme.json'

    def test_the_pointer_is_highlighted_by_default_without_asking_for_root(self):
        effects = headless.cursor_effects({})
        self.assertEqual((effects['preset'], effects['halo'], effects['clicks'], effects['trail']), ('presentation', True, False, False))

    def test_the_saved_style_and_size_are_used(self):
        self.assertEqual(headless.cursor_effects({'cursor_preset': 'trail', 'cursor_size': 48})['trail'], True)
        self.assertEqual(headless.cursor_effects({'cursor_preset': 'trail', 'cursor_size': 48})['size'], 48)
        self.assertEqual(headless.cursor_effects({'cursor_preset': 'simple'}), {})

    def test_nonsense_falls_back_to_the_defaults(self):
        for prefs in ({'cursor_preset': 'disco'}, {'cursor_size': 5}, {'cursor_size': 'big'}, {'cursor_size': 99}):
            with self.subTest(prefs=prefs):
                effects = headless.cursor_effects(prefs)
                self.assertEqual((effects['preset'], effects['size']), ('presentation', 32))

    def test_the_accent_follows_the_wallpaper_scheme(self):
        self.scheme.write_text(json.dumps({'colours': {'primary': '2864D8'}}))
        self.assertEqual(headless.accent_color(), '#2864d8')
        self.assertEqual(headless.cursor_effects({}, headless.accent_color())['accent'], '#2864d8')

    def test_no_scheme_or_a_broken_one_means_no_accent(self):
        self.assertIsNone(headless.accent_color())
        for text in ('not json', '[]', json.dumps({'colours': {'primary': 'zzzzzz'}}), json.dumps({'colours': 5})):
            self.scheme.write_text(text)
            self.assertIsNone(headless.accent_color(), text)

    def test_the_shell_defaults_show_the_style_and_size(self):
        values = headless.shell_prefs()
        self.assertEqual((values['cursor_preset'], values['cursor_size']), ('presentation', 32))
        headless.set_shell_pref('cursor_preset', 'trail')
        headless.set_shell_pref('cursor_size', '40')
        values = headless.shell_prefs()
        self.assertEqual((values['cursor_preset'], values['cursor_size']), ('trail', 40))
        for key, value in (('cursor_preset', 'disco'), ('cursor_size', '5'), ('cursor_size', 'big')):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                headless.set_shell_pref(key, value)


if __name__ == '__main__':
    unittest.main()

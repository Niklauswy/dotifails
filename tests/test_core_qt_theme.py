"""wysun_core.qt_theme: stylesheet templates, live refresh and the theme watcher."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/python'))
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402
from wysun_core import qt_theme, theme  # noqa: E402
from wysun_core.jsonio import atomic_write_json  # noqa: E402

SCHEME = {'name': 'dynamic', 'flavour': 'tonalspot', 'mode': 'light', 'variant': 'tonalspot',
          'wallpaper_hash': 'b' * 64, 'colours': {'surface': 'abcdef', 'onSurface': '111111'}}


def wait(predicate, seconds=2.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end and not predicate():
        QApplication.processEvents()
        time.sleep(.01)
    return predicate()


class QtThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        patcher = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_STATE_HOME': str(root / 'state'),
                                          'XDG_RUNTIME_DIR': str(root / 'run')})
        patcher.start()
        self.addCleanup(patcher.stop)
        (root / 'run').mkdir(mode=0o700)
        os.environ.pop('WYSUN_THEME', None)
        qt_theme.invalidate()
        self.addCleanup(qt_theme.invalidate)

    def test_template_renders_tokens_alpha_and_pixels(self):
        values = qt_theme.tokens()
        text = qt_theme.qss('color: @text; background: @accent/40; border-radius: @rounding.medium; '
                            'font-family: @font.family.sans; font-size: @font.body.medium.size; padding: @spacing.small;')
        self.assertIn(values['text'][:7].lower(), text)
        self.assertIn(',40)', text)
        self.assertIn('border-radius: 12px;', text)
        self.assertIn('font-family: "Google Sans Flex";', text)
        self.assertIn('font-size: 14pt;', text)
        self.assertIn('padding: 8px;', text)
        self.assertNotIn('@', text)

    def test_fonts_use_the_shell_type_scale_in_points(self):
        body = qt_theme.font('body.medium')
        self.assertEqual(body.pointSizeF(), 14)
        self.assertEqual(body.weight(), 400)
        self.assertEqual(qt_theme.font('title.medium').weight(), 500)
        self.assertEqual(qt_theme.font('label.small', weight=600).weight(), 600)
        self.assertEqual(qt_theme.font('mono.small').family(), qt_theme.family(kind='mono'))

    def test_easing_is_the_shell_bezier_curve(self):
        from PySide6.QtCore import QEasingCurve
        curve = qt_theme.easing('anim.curves.standard')
        self.assertEqual(curve.type(), QEasingCurve.BezierSpline)
        self.assertAlmostEqual(curve.valueForProgress(1.0), 1.0)
        self.assertGreater(curve.valueForProgress(.5), .5)

    def test_theme_switch_refreshes_existing_widgets(self):
        label = QLabel('Tema')
        template = 'color: @text; background: @canvas; border-radius: @rounding.large;'
        with patch.dict(os.environ, {'WYSUN_THEME': 'dark'}):
            qt_theme.refresh_widgets()
            qt_theme.apply_style(label, template)
            dark = label.styleSheet()
            with patch.dict(os.environ, {'WYSUN_THEME': 'light'}):
                qt_theme.refresh_widgets()
                self.assertNotEqual(label.styleSheet(), dark)
                self.assertEqual(label.property('wysunThemeTemplate'), template)
            qt_theme.refresh_widgets()
            self.assertEqual(label.styleSheet(), dark)
        label.deleteLater()

    def test_a_failing_listener_does_not_stop_the_refresh(self):
        seen = []
        def broken():
            raise RuntimeError('closed window')
        qt_theme.on_theme_changed(broken)
        qt_theme.on_theme_changed(lambda: seen.append(True))
        qt_theme.refresh_widgets()
        self.assertEqual(seen, [True])

    def test_watcher_follows_atomic_replace_and_late_creation(self):
        seen = []
        qt_theme.on_theme_changed(lambda: seen.append(theme.active_mode()))
        previous = getattr(self.app, 'wysunThemeWatcher', None)
        if previous is not None:
            del self.app.wysunThemeWatcher
        qt_theme.watch_theme()
        watcher = self.app.wysunThemeWatcher

        def stop_watching():
            watcher.watcher.removePaths(watcher.watcher.files() + watcher.watcher.directories())
            watcher.timer.stop()
            watcher.deleteLater()
            del self.app.wysunThemeWatcher
            if previous is not None:
                self.app.wysunThemeWatcher = previous
            QApplication.processEvents()
        self.addCleanup(stop_watching)
        atomic_write_json(theme.scheme_path(), SCHEME, sort_keys=True)       # the state directory did not exist
        self.assertTrue(wait(lambda: 'light' in seen), 'late creation was not seen')
        atomic_write_json(theme.scheme_path(), dict(SCHEME, mode='dark'), sort_keys=True)   # atomic replace
        self.assertTrue(wait(lambda: seen[-1:] == ['dark']), 'atomic replace was not seen')

    def test_svg_asset_is_tinted_and_cached(self):
        path = Path(qt_theme.svg_asset('chevron-down', 'accent'))
        self.assertTrue(path.is_file())
        self.assertIn(qt_theme.tokens()['accent'][:7].lower(), path.read_text().lower())
        self.assertEqual(qt_theme.svg_asset('chevron-down', 'accent'), str(path))


if __name__ == '__main__':
    unittest.main()

"""The shell's camera-bubble geometry (apps/shell/utils/CameraBubble.js) equals the renderer's
(``wysun_recorder.render.camera_overlay``): the preview before recording and the marker during it must sit exactly where
the camera will cover the video. Venv Python: QJSEngine runs the same JavaScript file the shell imports."""
import itertools
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.append(str(ROOT / 'apps/recorder'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
JS = ROOT / 'apps/shell/utils/CameraBubble.js'


class ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtQml import QJSEngine
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.engine = QJSEngine()
        code = '\n'.join(line for line in JS.read_text().splitlines() if not line.startswith('.pragma'))
        result = cls.engine.evaluate(code)
        assert not result.isError(), result.toString()

    def call(self, name, *args):
        value = self.engine.globalObject().property(name).call([self.engine.toScriptValue(a) for a in args])
        self.assertFalse(value.isError(), value.toString())
        return value.toVariant()

    def test_the_bubble_is_where_the_renderer_puts_it(self):
        from wysun_recorder.render import camera_overlay
        from wysun_recorder.schema import CAMERA_CORNERS, CAMERA_SHAPES, CAMERA_SIZES
        for (w, h), size, shape, corner in itertools.product(
                ((1920, 1080), (2560, 1440), (800, 600), (333, 257), (1280, 720), (90, 64)), CAMERA_SIZES, CAMERA_SHAPES, CAMERA_CORNERS):
            with self.subTest(width=w, height=h, size=size, shape=shape, corner=corner):
                _, x, y = camera_overlay(SimpleNamespace(size=size, shape=shape, corner=corner), w, h)
                tall = max(2, int(h * CAMERA_SIZES[size]) // 2 * 2)
                wide = tall if shape == 'circle' else max(2, int(tall * 4 / 3) // 2 * 2)
                got = self.call('rect', w, h, {'size': size, 'shape': shape, 'corner': corner})
                self.assertEqual((got['x'], got['y'], got['width'], got['height']), (x, y, wide, tall))
                self.assertEqual(got['radius'], wide / 2 if shape == 'circle' else max(4, tall // 8))

    def test_an_unknown_style_falls_back_like_the_defaults(self):
        got = self.call('rect', 1920, 1080, {})
        self.assertEqual((got['width'], got['height']), (302, 302))        # medium circle: int(1080 * .28) // 2 * 2
        self.assertGreater(got['x'], 1920 / 2)                             # bottom-right

    def test_the_nearest_corner_is_the_quadrant_of_the_centre(self):
        for point, corner in (((10, 10), 'top-left'), ((1900, 10), 'top-right'), ((10, 1000), 'bottom-left'),
                              ((1900, 1000), 'bottom-right'), ((961, 541), 'bottom-right'), ((959, 539), 'top-left')):
            self.assertEqual(self.call('nearestCorner', point[0], point[1], 1920, 1080), corner, point)


if __name__ == '__main__':
    unittest.main()

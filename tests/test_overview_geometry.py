"""Source-output geometry contract for live overview thumbnails."""
import json
import unittest
import shutil
import subprocess
from pathlib import Path


@unittest.skipUnless(shutil.which("node"), "Node is needed to evaluate the shared QML geometry function")
class OverviewGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).resolve().parents[1] / 'apps/shell/modules/overview/OverviewGeometry.js').read_text().replace('.pragma library', '')

    def geometry(self, window, monitor, canvas=(400, 225)):
        args = [window, monitor, *canvas]
        script = self.source + '\nconsole.log(JSON.stringify(geometry(' + ','.join(map(json.dumps, args)) + ')));'
        return json.loads(subprocess.check_output(['node', '-e', script], text=True))

    def test_other_output_uses_its_origin(self):
        actual = self.geometry({'at': [2880, 0], 'size': [960, 1080]},
                               {'x': 1920, 'width': 1920, 'height': 1080})
        self.assertEqual(actual, dict(x=200, y=0, width=200, height=225))

    def test_scaled_negative_output(self):
        actual = self.geometry({'at': [-960, 0], 'size': [960, 1080]},
                               {'x': -1920, 'width': 3840, 'height': 2160, 'scale': 2})
        self.assertEqual(actual, dict(x=200, y=0, width=200, height=225))

    def test_rotated_scaled_fullscreen_fills_tile(self):
        actual = self.geometry({'at': [0, 0], 'size': [720, 1280]},
                               {'width': 2560, 'height': 1440, 'transform': 1, 'scale': 2})
        self.assertEqual(actual, dict(x=0, y=0, width=400, height=225))

    def test_offscreen_and_oversized_float_is_bounded(self):
        actual = self.geometry({'at': [-80, 1200], 'size': [3000, 400]},
                               {'width': 1920, 'height': 1080})
        self.assertEqual(actual['x'], 0)
        self.assertEqual(actual['width'], 400)
        self.assertAlmostEqual(actual['y'] + actual['height'], 225)

    def test_disappearing_monitor_has_finite_fallback(self):
        self.assertEqual(self.geometry({}, {}), dict(x=0, y=0, width=400, height=225))

    def test_reserved_edges_shrink_the_source_area(self):
        actual = self.geometry({'at': [60, 10], 'size': [1850, 1060]},
                               {'width': 1920, 'height': 1080, 'reserved': [60, 10, 10, 10]})
        self.assertEqual(actual, dict(x=0, y=0, width=400, height=225))

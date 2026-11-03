"""WysunM3 pieces added for Wysun Processes: RollingNumber (digits that roll), LiveChart (scrolling chart with a
scrub guide and markers) and StateShape (an M3 shape that morphs with a process state)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402


def tearDownModule():
    support.Harness.get().close_views()


class Base(unittest.TestCase):
    def setUp(self):
        from PySide6.QtCore import QObject
        self.QObject = QObject
        self.h = support.Harness.get()
        self.h.bridge.setPreview(None)
        self.h.bridge.setReducedMotion(True)
        self.warnings = []
        self.h.engine.warnings.connect(self._warn)
        self.h.pump()

    def _warn(self, errors):
        self.warnings.extend(e.toString() for e in errors)

    def tearDown(self):
        self.h.engine.warnings.disconnect(self._warn)
        self.h.bridge.setReducedMotion(None)
        self.h.close_views()

    def child(self, view, name):
        return view.rootObject().findChild(self.QObject, name)


class RollingNumberTests(Base):
    def test_shows_text_and_rolls_to_new_value(self):
        view = self.h.view('RollingNumber { objectName: "n"; text: "42%" }', 200, 60)
        n = self.child(view, 'n')
        self.assertEqual(self.h.call(n, 'shownText'), '42%')
        self.assertGreater(n.property('implicitWidth'), 0)
        n.setProperty('text', '57%')
        self.h.pump(30)
        self.assertEqual(self.h.call(n, 'shownText'), '57%')
        n.setProperty('text', '9.8 GB')
        self.h.pump(30)
        self.assertEqual(self.h.call(n, 'shownText'), '9.8 GB')
        self.assertEqual(self.warnings, [])

    def test_inactive_number_jumps_to_its_value(self):
        view = self.h.view('RollingNumber { objectName: "n"; active: false; text: "42%" }', 200, 60)
        n = self.child(view, 'n')
        n.setProperty('text', '57%')
        self.h.pump(1)
        self.assertEqual(self.h.call(n, 'shownText'), '57%')
        self.assertEqual(self.warnings, [])


class LiveChartTests(Base):
    def test_scrub_reports_index_and_label(self):
        view = self.h.view('LiveChart { objectName: "c"; anchors.fill: parent; scrub: true; capacity: 10;\n'
                           ' series: [[1,2,3,4,5,6,7,8,9,10]]; colors: [Theme.m3primary];\n'
                           ' formatValue: v => v + " %"; labelAt: i => "p" + i }', 300, 120)
        chart = self.child(view, 'c')
        self.assertEqual(chart.property('hoverIndex'), -1)
        self.h.move(view, 299, 60)
        self.assertEqual(chart.property('hoverIndex'), 9)
        self.assertIn('10 %', chart.property('hoverText'))
        self.assertIn('p9', chart.property('hoverText'))
        self.h.move(view, -5, -5)
        self.assertEqual(chart.property('hoverIndex'), -1)
        self.assertEqual(self.warnings, [])

    def test_auto_maximum(self):
        view = self.h.view('LiveChart { objectName: "c"; anchors.fill: parent; series: [[2, 40, 8]] }', 200, 80)
        self.assertGreaterEqual(self.child(view, 'c').property('effectiveMax'), 40)

    def test_inactive_chart_does_not_slide(self):
        view = self.h.view('LiveChart { objectName: "c"; anchors.fill: parent; active: false; interval: 1000 }',
                           200, 80)
        chart = self.child(view, 'c')
        self.h.bridge.setReducedMotion(False)
        chart.setProperty('series', [[1, 2, 3, 4]])
        self.h.pump(50)
        self.assertEqual(chart.property('progress'), 1)
        chart.setProperty('active', True)
        chart.setProperty('series', [[2, 3, 4, 5]])
        self.h.pump(50)
        self.assertLess(chart.property('progress'), 1)
        self.assertEqual(self.warnings, [])


class StateShapeTests(Base):
    def test_state_picks_shape(self):
        view = self.h.view('StateShape { objectName: "s"; state: "R" }', 80, 80)
        s = self.child(view, 's')
        self.assertEqual(s.property('shapeName'), 'cookie')
        self.assertTrue(s.property('spinning') in (True, False))
        for state, shape in (('S', 'circle'), ('T', 'squircle'), ('Z', 'burst'), ('G', 'sunny'), ('', 'circle')):
            s.setProperty('state', state)
            self.h.pump(10)
            self.assertEqual(s.property('shapeName'), shape, state)
        self.assertEqual(self.warnings, [])


if __name__ == '__main__':
    unittest.main()

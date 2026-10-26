"""Expressive springs (Anim/CAnim/Motion) and the M3 transition patterns (fade through, shared axis, container transform)."""
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402

TOKENS = json.loads((ROOT / 'apps/python/wysun_core/tokens.json').read_text())['anim']
SPACING = json.loads((ROOT / 'apps/python/wysun_core/tokens.json').read_text())['spacing']


def tearDownModule():
    support.Harness.get().close_views()


class Base(unittest.TestCase):
    def setUp(self):
        from PySide6.QtCore import QObject
        self.QObject = QObject
        self.h = support.Harness.get()
        self.h.bridge.setPreview(None)
        self.h.bridge.setReducedMotion(False)
        self.h.pump()

    def tearDown(self):
        self.h.bridge.setReducedMotion(None)
        self.h.close_views()

    def child(self, view, name):
        return view.rootObject().findChild(self.QObject, name)


class SpringTests(Base):
    def test_anim_uses_the_token_duration_and_bezier(self):
        view = self.h.view('Anim { id: a; objectName: "a"; kind: "fastSpatial" }\n'
                           'CAnim { id: c; objectName: "c"; kind: "slowEffects" }')
        anim, canim = self.child(view, 'a'), self.child(view, 'c')
        self.assertEqual(anim.property('duration'), TOKENS['durations']['expressiveFastSpatial'])
        points = [(p.x(), p.y()) for p in anim.property('easing').toCubicSpline()]
        curve = TOKENS['curves']['expressiveFastSpatial']
        self.assertEqual(points, [(curve[0], curve[1]), (curve[2], curve[3]), (curve[4], curve[5])])
        self.assertEqual(canim.property('duration'), TOKENS['durations']['expressiveSlowEffects'])

    def test_spatial_curves_overshoot_and_effects_do_not(self):
        for name, curve in TOKENS['curves'].items():
            ys = curve[1::2]
            if name.startswith('expressive') and name.endswith('Spatial'):
                self.assertGreater(max(ys), 1, name)
            if name.startswith('expressive') and name.endswith('Effects'):
                self.assertLessEqual(max(ys), 1, name)
        view = self.h.view('Anim { id: s; objectName: "s"; kind: "defaultSpatial" }\nAnim { id: e; objectName: "e"; kind: "defaultEffects" }')
        spatial = [p.y() for p in self.child(view, 's').property('easing').toCubicSpline()]
        effects = [p.y() for p in self.child(view, 'e').property('easing').toCubicSpline()]
        self.assertGreater(max(spatial), 1)
        self.assertLessEqual(max(effects), 1)

    def test_a_token_name_works_as_kind_too(self):
        view = self.h.view('Anim { id: a; objectName: "a"; kind: "emphasized" }')
        self.assertEqual(self.child(view, 'a').property('duration'), TOKENS['durations']['normal'])

    def test_reduced_motion_makes_the_duration_zero_and_back(self):
        view = self.h.view('Anim { id: a; objectName: "a"; kind: "slowSpatial" }')
        anim = self.child(view, 'a')
        self.h.bridge.setReducedMotion(True)
        self.h.pump()
        self.assertEqual(anim.property('duration'), 0)
        self.h.bridge.setReducedMotion(False)
        self.h.pump()
        self.assertEqual(anim.property('duration'), TOKENS['durations']['expressiveSlowSpatial'])

    def test_reduced_motion_mid_animation_completes_at_the_destination(self):
        view = self.h.view('Rectangle { id: r; objectName: "r"; width: 10; height: 10; x: 0\n'
                           '  SpringBehavior on x { kind: "slowSpatial" }\n'
                           '  SpringBehavior on opacity { kind: "slowEffects" } }\n'
                           'function go() { r.x = 100; r.opacity = 0.5 }')
        rect = self.child(view, 'r')
        self.h.call(view.rootObject(), 'go')
        self.h.pump(60)
        self.assertLess(rect.property('x'), 100, 'still travelling')
        self.h.bridge.setReducedMotion(True)
        self.h.pump(20)
        self.assertEqual(rect.property('x'), 100)
        self.assertEqual(rect.property('opacity'), 0.5)
        self.h.call(view.rootObject(), 'go')
        self.h.bridge.setReducedMotion(False)

    def test_spring_behavior_follows_the_token_and_does_not_animate_when_reduced(self):
        view = self.h.view('Rectangle { id: r; objectName: "r"; width: 10; height: 10; x: 0\n'
                           '  SpringBehavior on x { id: sb; objectName: "sb"; kind: "fastSpatial" } }\n'
                           'function go(v) { r.x = v }')
        self.h.bridge.setReducedMotion(True)
        self.h.pump()
        self.h.call(view.rootObject(), 'go', 50)
        self.assertEqual(self.child(view, 'r').property('x'), 50, 'no animation: the value is already there')

    def test_a_running_anim_completes_when_motion_becomes_reduced(self):
        view = self.h.view('Rectangle { id: r; objectName: "r"; width: 10; height: 10; x: 0 }\n'
                           'Anim { id: a; objectName: "a"; target: r; property: "x"; to: 100; kind: "slowSpatial" }\n'
                           'function go() { a.start() }')
        rect = self.child(view, 'r')
        self.h.call(view.rootObject(), 'go')
        self.h.pump(60)
        self.assertLess(rect.property('x'), 100)
        self.h.bridge.setReducedMotion(True)
        self.h.pump(20)
        self.assertEqual(rect.property('x'), 100)
        self.assertFalse(self.child(view, 'a').property('running'))


class FadeThroughTests(Base):
    BODY = ('FadeThrough { id: ft; objectName: "ft"; width: parent.width; height: parent.height }\n'
            'Component { id: pageA; Rectangle { objectName: "pageA"; color: Theme.m3primary } }\n'
            'Component { id: pageB; Rectangle { objectName: "pageB"; color: Theme.m3tertiary } }\n'
            'function a() { return ft.show(pageA) }\nfunction b() { return ft.show(pageB) }')

    def test_reduced_motion_mid_transition_finishes_it(self):
        view = self.h.view(self.BODY, 200, 100)
        ft = self.child(view, 'ft')
        self.h.call(view.rootObject(), 'a')
        self.h.call(view.rootObject(), 'b')
        self.h.pump(30)
        self.assertTrue(ft.property('running'))
        self.h.bridge.setReducedMotion(True)
        self.h.pump(20)
        self.assertFalse(ft.property('running'), 'the grouped sequence ends at once')
        self.assertIsNone(self.child(view, 'pageA'))
        self.assertEqual(self.child(view, 'pageB').property('opacity'), 1)

    def test_swaps_content_and_ends_clean(self):
        view = self.h.view(self.BODY, 200, 100)
        ft = self.child(view, 'ft')
        self.h.call(view.rootObject(), 'a')
        first = self.child(view, 'pageA')
        self.assertEqual((first.property('opacity'), first.property('scale')), (1, 1), 'the first page just appears')
        self.h.call(view.rootObject(), 'b')
        second = self.child(view, 'pageB')
        self.assertEqual(second.property('opacity'), 0, 'the incoming page waits for the outgoing one')
        self.assertTrue(self.h.wait_for(lambda: not ft.property('running'), 3000))
        self.assertIsNone(self.child(view, 'pageA'), 'the outgoing page is destroyed')
        self.assertEqual((second.property('opacity'), second.property('scale')), (1, 1))
        self.assertEqual((second.property('width'), second.property('height')), (200, 100))

    def test_timing_comes_from_the_tokens(self):
        view = self.h.view(self.BODY, 200, 100)
        ft = self.child(view, 'ft')
        d = TOKENS['durations']
        exit_ms = d['expressiveFastEffects']
        enter_ms = max(d['expressiveDefaultEffects'], d['expressiveDefaultSpatial'])
        self.assertEqual(ft.property('totalDuration'), exit_ms + enter_ms)
        self.h.call(view.rootObject(), 'a')
        started = time.monotonic()
        self.h.call(view.rootObject(), 'b')
        self.assertTrue(self.h.wait_for(lambda: not ft.property('running'), 3000))
        elapsed = (time.monotonic() - started) * 1000
        self.assertGreater(elapsed, exit_ms + enter_ms - 80)
        self.assertLess(elapsed, exit_ms + enter_ms + 600)

    def test_incoming_scales_up_from_the_pattern_scale(self):
        view = self.h.view(self.BODY, 200, 100)
        self.h.call(view.rootObject(), 'a')
        self.h.call(view.rootObject(), 'b')
        self.assertAlmostEqual(self.child(view, 'pageB').property('scale'), 0.92, places=2)

    def test_a_second_show_while_running_finishes_the_first(self):
        view = self.h.view(self.BODY, 200, 100)
        ft = self.child(view, 'ft')
        for _ in range(4):
            self.h.call(view.rootObject(), 'a')
            self.h.call(view.rootObject(), 'b')
            self.h.pump(30)
        self.assertTrue(self.h.wait_for(lambda: not ft.property('running'), 4000))
        survivors = [n for n in ('pageA', 'pageB') if self.child(view, n)]
        self.assertEqual(len(survivors), 1, survivors)

    def test_instant_when_motion_is_reduced(self):
        view = self.h.view(self.BODY, 200, 100)
        ft = self.child(view, 'ft')
        self.h.bridge.setReducedMotion(True)
        self.h.pump()
        self.h.call(view.rootObject(), 'a')
        self.h.call(view.rootObject(), 'b')
        self.assertFalse(ft.property('running'))
        self.h.pump()
        self.assertIsNone(self.child(view, 'pageA'))
        self.assertEqual(self.child(view, 'pageB').property('opacity'), 1)


class SharedAxisTests(Base):
    def body(self, axis):
        return (f'SharedAxis {{ id: sa; objectName: "sa"; axis: "{axis}"; width: parent.width; height: parent.height }}\n'
                'Component { id: pageA; Rectangle { objectName: "pageA"; color: Theme.m3primary } }\n'
                'Component { id: pageB; Rectangle { objectName: "pageB"; color: Theme.m3tertiary } }\n'
                'function a() { return sa.show(pageA, {}, true) }\n'
                'function forward() { return sa.show(pageB, {}, true) }\nfunction back() { return sa.show(pageB, {}, false) }')

    def test_x_axis_forward_enters_from_the_end_and_back_from_the_start(self):
        offset = SPACING['extraLargeIncreased']
        for method, expected in (('forward', offset), ('back', -offset)):
            view = self.h.view(self.body('x'), 200, 100)
            self.h.call(view.rootObject(), 'a')
            self.h.call(view.rootObject(), method)
            self.assertEqual(self.child(view, 'pageB').property('x'), expected, method)
            self.assertEqual(self.child(view, 'pageB').property('opacity'), 0)
            self.h.close_views()

    def test_y_axis_moves_vertically(self):
        offset = SPACING['extraLargeIncreased']
        view = self.h.view(self.body('y'), 200, 100)
        self.h.call(view.rootObject(), 'a')
        self.h.call(view.rootObject(), 'forward')
        page = self.child(view, 'pageB')
        self.assertEqual((page.property('x'), page.property('y')), (0, offset))

    def test_z_axis_scales(self):
        view = self.h.view(self.body('z'), 200, 100)
        self.h.call(view.rootObject(), 'a')
        self.h.call(view.rootObject(), 'forward')
        self.assertLess(self.child(view, 'pageB').property('scale'), 1)
        self.assertTrue(self.h.wait_for(lambda: not self.child(view, 'sa').property('running'), 3000))
        self.assertEqual(self.child(view, 'pageB').property('scale'), 1)

    def test_ends_in_place_and_removes_the_outgoing_page(self):
        view = self.h.view(self.body('x'), 200, 100)
        self.h.call(view.rootObject(), 'a')
        self.h.call(view.rootObject(), 'forward')
        self.assertTrue(self.h.wait_for(lambda: not self.child(view, 'sa').property('running'), 3000))
        page = self.child(view, 'pageB')
        self.assertEqual((page.property('x'), page.property('opacity')), (0, 1))
        self.assertIsNone(self.child(view, 'pageA'))


class ContainerTransformTests(Base):
    BODY = ('Rectangle { id: card; objectName: "card"; x: 20; y: 30; width: 60; height: 40; radius: 12; color: Theme.m3primaryContainer }\n'
            'ContainerTransform { id: ct; objectName: "ct"; width: parent.width; height: parent.height }\n'
            'Component { id: detail; Rectangle { objectName: "detail"; color: Theme.m3surface } }\n'
            'function open() { ct.open(card, detail) }\nfunction close() { ct.close() }')

    def test_open_close_roundtrip(self):
        view = self.h.view(self.BODY, 300, 200)
        ct = self.child(view, 'ct')
        container = self.child(view, 'container')
        self.assertFalse(ct.property('opened'))
        self.h.call(view.rootObject(), 'open')
        self.assertTrue(ct.property('opened'))
        self.assertEqual((container.property('x'), container.property('y'), container.property('width'), container.property('height')),
                         (20, 30, 60, 40), 'it starts exactly over the source')
        self.assertTrue(self.h.wait_for(lambda: not ct.property('running'), 3000))
        self.assertEqual((container.property('x'), container.property('y'), container.property('width'), container.property('height')),
                         (0, 0, 300, 200))
        self.assertEqual(self.child(view, 'detail').property('opacity'), 1)
        self.h.call(view.rootObject(), 'close')
        self.assertTrue(self.h.wait_for(lambda: not ct.property('running'), 3000))
        self.assertFalse(ct.property('opened'))
        self.assertFalse(container.property('visible'))
        self.assertIsNone(self.child(view, 'detail'), 'the detail page is destroyed on close')

    def test_reduced_motion_mid_open_finishes_it(self):
        view = self.h.view(self.BODY, 300, 200)
        ct = self.child(view, 'ct')
        self.h.call(view.rootObject(), 'open')
        self.h.pump(30)
        self.assertTrue(ct.property('running'))
        self.h.bridge.setReducedMotion(True)
        self.h.pump(20)
        self.assertFalse(ct.property('running'))
        container = self.child(view, 'container')
        self.assertEqual((container.property('width'), container.property('height')), (300, 200))

    def test_the_corner_morphs_from_the_source_radius(self):
        view = self.h.view(self.BODY, 300, 200)
        ct = self.child(view, 'ct')
        container = self.child(view, 'container')
        self.h.call(view.rootObject(), 'open')
        self.assertEqual(container.property('radius'), 12)
        self.assertTrue(self.h.wait_for(lambda: not ct.property('running'), 3000))
        self.assertEqual(container.property('radius'), 0)

    def test_instant_when_motion_is_reduced(self):
        view = self.h.view(self.BODY, 300, 200)
        ct = self.child(view, 'ct')
        self.h.bridge.setReducedMotion(True)
        self.h.pump()
        self.h.call(view.rootObject(), 'open')
        self.assertFalse(ct.property('running'))
        self.assertEqual(self.child(view, 'container').property('width'), 300)
        self.h.call(view.rootObject(), 'close')
        self.assertFalse(ct.property('opened'))
        self.assertFalse(self.child(view, 'container').property('visible'))


if __name__ == '__main__':
    unittest.main()

"""Wysun Music's QML window: loads clean, routes and history, hide-on-close, launch order."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support, music_fixture  # noqa: E402


class MusicWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()
        cls.warnings = []
        music_fixture.setup()
        cls.music = music_fixture.app()
        cls.window = cls.music.window.window
        cls.music.window.engine.warnings.connect(lambda errors: cls.warnings.extend(e.toString() for e in errors))
        cls.music.window.bridge.setReducedMotion(True)
        cls.music.window.present()
        cls.window.resize(1100, 800)          # standard drawer (the offscreen screen is small)
        cls.h.pump(100)

    def setUp(self):
        self.warnings.clear()
        self.h.call(self.window, 'navigate', 'home', False)
        self.window.setProperty('history', [])
        self.window.setProperty('future', [])
        self.h.pump(30)

    def nav(self):
        return self.h.find_in(self.window.contentItem(), 'musicNav')

    def test_loads_without_warnings(self):
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.warnings, [])
        self.assertEqual(self.window.property('title'), 'Wysun Music')

    def test_navigation_and_active_destination(self):
        for route, active in (('library:artists', 'library:artists'), ('collection:favorites', 'collection:favorites'),
                              ('search:tono', 'search'), ('downloads', 'downloads')):
            with self.subTest(route=route):
                self.h.call(self.window, 'navigate', route, True)
                self.h.pump(30)
                self.assertEqual(self.window.property('route'), route)
                self.assertEqual(self.nav().property('currentId'), active)
        self.assertEqual(self.warnings, [])

    def test_rail_groups_library_destinations(self):
        self.window.resize(700, 800)
        self.h.pump(30)
        try:
            for route, active in (('library:artists', 'library:albums'), ('collection:favorites', 'library:albums'),
                                  ('library:lists', 'library:lists'), ('search:x', 'search')):
                self.h.call(self.window, 'navigate', route, True)
                self.assertEqual(self.nav().property('currentId'), active, route)
        finally:
            self.window.resize(1100, 800)
            self.h.pump(30)

    def test_back_and_forward(self):
        for route in ('library:albums', 'collection:favorites', 'downloads'):
            self.h.call(self.window, 'navigate', route, True)
        self.h.call(self.window, 'goBack')
        self.h.call(self.window, 'goBack')
        self.assertEqual(self.window.property('route'), 'library:albums')
        self.h.call(self.window, 'goForward')
        self.assertEqual(self.window.property('route'), 'collection:favorites')

    def test_history_is_capped_at_fifty(self):
        for index in range(60):
            self.h.call(self.window, 'navigate', 'search:' + str(index), True)
            self.h.call(self.window, 'navigate', 'home', True)
        self.assertEqual(len(self.window.property('history').toVariant()), 50)

    def test_route_is_saved(self):
        self.h.call(self.window, 'navigate', 'library:songs', True)
        self.assertEqual(self.music.window.music.route, 'library:songs')

    def test_orphan_route(self):
        self.h.call(self.window, 'navigate', 'collection:user-does-not-exist', True)
        self.h.pump(30)
        state = self.h.find_in(self.window.contentItem(), 'orphanState')
        self.assertTrue(state.property('visible'))

    def test_closing_hides_and_keeps_playing(self):
        player = self.music.player
        with patch.object(player, 'save'):
            self.window.close()
            self.h.pump(30)
            self.assertFalse(self.window.isVisible())
        self.music.window.present()
        self.h.pump(30)
        self.assertTrue(self.window.isVisible())
        self.window.resize(1100, 800)


class LaunchOrderTests(unittest.TestCase):
    def test_second_launch_presents_without_reexec(self):
        from wysun_music import app
        with patch.object(app, 'send', return_value=True) as send, \
                patch('wysun_qml.bootstrap.ensure_runtime_python') as reexec, \
                patch.dict('os.environ', {'WYSUN_MUSIC_UI': 'qml'}):
            self.assertEqual(app.main(['wysun-music']), 0)
        send.assert_called_once()
        reexec.assert_not_called()

    def test_first_launch_reexecs_before_claiming(self):
        from wysun_music import app
        order = []
        with patch.object(app, 'send', return_value=False), \
                patch('wysun_qml.bootstrap.ensure_runtime_python', side_effect=lambda *a: order.append('reexec')), \
                patch('wysun_qml.bootstrap.require_qt', side_effect=SystemExit(9)), \
                patch.object(app.SingleInstance, 'claim', side_effect=lambda *a: order.append('claim')), \
                patch.dict('os.environ', {'WYSUN_MUSIC_UI': 'qml'}), self.assertRaises(SystemExit):
            app.main(['wysun-music'])
        self.assertEqual(order, ['reexec'])


if __name__ == '__main__':
    unittest.main()

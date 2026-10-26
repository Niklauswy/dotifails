"""Search and Explorar: typing routes and refines one history entry, results, Enter plays among all matches."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support, music_fixture  # noqa: E402


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import Qt
        cls.Qt = Qt
        cls.h = support.Harness.get()
        cls.warnings = []
        music_fixture.setup()
        cls.music = music_fixture.app()
        cls.window = cls.music.window.window
        cls.music.window.engine.warnings.connect(lambda errors: cls.warnings.extend(e.toString() for e in errors))
        cls.music.window.bridge.setReducedMotion(True)
        cls.music.window.present()
        cls.window.resize(1100, 800)
        cls.keys = music_fixture.keys_by_title()

    def setUp(self):
        self.warnings.clear()
        self.h.call(self.window, 'navigate', 'home', True)
        self.window.setProperty('history', [])
        self.search().setProperty('text', '')
        self.h.find_in(self.window.contentItem(), 'musicRoot').forceActiveFocus()

    def tearDown(self):
        self.music.player.set_paused(True)

    def search(self):
        return self.h.find_in(self.window.contentItem(), 'searchBar')

    def visible(self, name):
        from PySide6.QtQuick import QQuickItem
        stack, found = [self.window.contentItem()], []
        while stack:
            item = stack.pop()
            if item.objectName() == name and item.isVisible():
                found.append(item)
            stack.extend(item.childItems() if isinstance(item, QQuickItem) else [])
        return found

    def type(self, text):
        self.h.call(self.search(), 'forceFocus')
        self.h.type_text(self.window, text)
        self.h.pump(250)                       # past the debounce

    def test_typing_routes_to_search_and_refines_one_entry(self):
        self.type('sec')
        self.assertEqual(self.window.property('route'), 'search:sec')
        self.type('o')
        self.assertEqual(self.window.property('route'), 'search:seco')
        self.assertEqual(self.window.property('history').toVariant(), ['home'])

    def test_results_and_enter_plays_among_all_matches(self):
        self.type('synth')
        self.assertTrue(self.visible('topResult'))
        songs = self.visible('searchSongs')[0]
        self.assertEqual(songs.property('count'), 2)
        self.h.key(self.window, self.Qt.Key_Down)
        self.assertTrue(songs.property('activeFocus'))
        self.h.key(self.window, self.Qt.Key_Return, text='\r')
        self.assertTrue(self.h.wait_for(lambda: self.music.player.current in (self.keys['first'], self.keys['second']), 4000))
        self.assertEqual(self.music.player.queue.context, 'search:synth')

    def test_no_results(self):
        self.type('zzzz')
        self.assertTrue(self.visible('noResults'))

    def test_explore_when_empty(self):
        self.h.call(self.window, 'navigate', 'search:', True)
        self.h.pump(250)
        self.assertTrue(self.visible('explore'))
        self.assertTrue(self.visible('explore-artist:Synth'))
        self.assertEqual(self.warnings, [])

    def test_escape_clears_then_passes(self):
        self.type('third')
        self.h.key(self.window, self.Qt.Key_Escape)
        self.assertEqual(self.search().property('text'), '')
        self.assertTrue(self.window.isVisible())

    def test_ctrl_k_focuses_the_search(self):
        self.h.key(self.window, self.Qt.Key_K, self.Qt.ControlModifier, 'k')
        self.h.pump(50)
        self.assertTrue(self.search().property('focused'))
        self.assertTrue(self.window.property('route').startswith('search'))


if __name__ == '__main__':
    unittest.main()

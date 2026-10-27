"""Inicio and Biblioteca of the QML Music window against the synthetic library."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support, music_fixture  # noqa: E402


class PagesTests(unittest.TestCase):
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

    def tearDown(self):
        for key in list(self.music.library.favorites):
            self.music.library.toggle_favorite(key)
        self.music.player.set_paused(True)

    def go(self, route):
        self.h.call(self.window, 'navigate', route, True)
        self.h.pump(60)

    def find(self, name):
        return self.h.find_in(self.window.contentItem(), name)

    def visible(self, name):
        from PySide6.QtQuick import QQuickItem
        stack, found = [self.window.contentItem()], []
        while stack:
            item = stack.pop()
            if item.objectName() == name and item.isVisible():
                found.append(item)
            stack.extend(item.childItems() if isinstance(item, QQuickItem) else [])
        return found

    def test_home_sections(self):
        self.go('home')
        self.assertTrue(self.visible('greeting'))
        bento = self.find('bento')
        self.assertGreaterEqual(len([c for c in bento.childItems() if c.isVisible()]), 3)
        self.assertEqual(self.warnings, [])

    def test_library_tabs_and_counts(self):
        for tab, text in (('albums', 'álbum'), ('artists', '3 artistas'), ('songs', '3 canciones')):
            with self.subTest(tab=tab):
                self.go('library:' + tab)
                count = [c for c in self.visible('libraryCount')][0]
                self.assertIn(text, count.property('text'))
        self.assertEqual(self.warnings, [])

    def test_songs_filter_favorites(self):
        self.music.library.toggle_favorite(self.keys['third'])
        self.go('library:songs')
        page = self.h.find_in(self.window.contentItem(), 'songList').parentItem()
        page.setProperty('songFilter', 'favorites')
        self.h.pump(60)
        songs = self.visible('songList')[0]
        self.assertEqual(songs.property('count'), 1)
        page.setProperty('songFilter', 'all')

    def test_song_list_keyboard(self):
        self.go('library:songs')
        songs = self.visible('songList')[0]
        songs.forceActiveFocus(self.Qt.TabFocusReason)
        songs.setProperty('currentIndex', 1)
        self.h.key(self.window, self.Qt.Key_Return, text='\r')
        self.assertTrue(self.h.wait_for(lambda: self.music.player.current == self.keys['second'], 4000))
        self.h.key(self.window, self.Qt.Key_F, text='f')
        self.assertIn(self.keys['second'], self.music.library.favorites)

    def test_selection_survives_favourites_and_counted_plays(self):
        self.go('library:songs')
        songs = self.visible('songList')[0]
        songs.forceActiveFocus(self.Qt.TabFocusReason)
        self.h.key(self.window, self.Qt.Key_A, self.Qt.ControlModifier, 'a')
        self.music.library.toggle_favorite(self.keys['first'])
        self.music.library.record_play(self.keys['second'])
        self.h.pump(300)
        self.assertEqual(len(songs.property('selectedKeys').toVariant()), 3)
        self.h.key(self.window, self.Qt.Key_Escape)

    def test_f_on_an_empty_list_does_nothing(self):
        self.go('library:songs')
        page = self.visible('songList')[0].parentItem()
        page.setProperty('songFilter', 'favorites')
        self.h.pump(60)
        songs = self.visible('songList')[0]
        self.assertEqual(songs.property('count'), 0)
        songs.forceActiveFocus(self.Qt.TabFocusReason)
        self.h.key(self.window, self.Qt.Key_F, text='f')
        self.assertEqual(self.music.library.favorites, set())
        page.setProperty('songFilter', 'all')

    def test_artist_card_keyboard(self):
        self.go('library:artists')
        card = [c for c in self.visible('card-artist:Synth')][0]
        card.forceActiveFocus(self.Qt.TabFocusReason)
        self.h.key(self.window, self.Qt.Key_Return, text='\r')
        self.assertEqual(self.window.property('route'), 'collection:artist:Synth')

    def test_multiple_selection(self):
        self.go('library:songs')
        songs = self.visible('songList')[0]
        songs.forceActiveFocus(self.Qt.TabFocusReason)
        self.h.key(self.window, self.Qt.Key_A, self.Qt.ControlModifier, 'a')
        self.assertEqual(len(songs.property('selectedKeys').toVariant()), 3)
        self.assertTrue(self.visible('selectionBar'))
        self.h.key(self.window, self.Qt.Key_Escape)
        self.assertEqual(len(songs.property('selectedKeys').toVariant()), 0)
        self.assertTrue(self.window.isVisible(), 'Escape cleared the selection instead of hiding the window')


if __name__ == '__main__':
    unittest.main()

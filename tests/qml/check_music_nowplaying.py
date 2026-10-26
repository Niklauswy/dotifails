"""«Ahora suena»: opening and closing, synced lyrics following the position and the offset, line seeking,
the queue (with the automatic switch when a song has no lyrics)."""
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

LRC = '[00:00.00]uno\n[00:03.00]dos\n[00:06.00]tres\n[00:09.00]cuatro'


class NowPlayingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import Qt
        cls.Qt = Qt
        cls.h = support.Harness.get()
        cls.warnings = []
        music_fixture.setup()
        cls.music = music_fixture.app()
        cls.window = cls.music.window.window
        cls.lyrics = cls.music.window.lyrics
        cls.player = cls.music.player
        cls.music.window.engine.warnings.connect(lambda errors: cls.warnings.extend(e.toString() for e in errors))
        cls.music.window.bridge.setReducedMotion(True)
        cls.music.window.present()
        cls.window.resize(1100, 800)
        cls.keys = music_fixture.keys_by_title()
        cls.patcher = patch.object(cls.music.covers.metadata, 'lyrics')   # never ask LRCLIB from the tests
        cls.fetch = cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()
        cls.player.set_paused(True)

    def setUp(self):
        self.warnings.clear()
        self.player.play(self.keys['first'], [self.keys[t] for t in ('first', 'second', 'third')], 'all')
        self.assertTrue(self.h.wait_for(lambda: self.player.position > .1, 5000))
        self.player.set_paused(True)

    def tearDown(self):
        self.h.call(self.window, 'togglePanel', '')
        self.music.library.store.put('offset:' + self.keys['first'], 0)

    def find(self, name):
        return self.h.find_in(self.window.contentItem(), name)

    def deliver(self, data):
        self.music.covers.metadata.ready.emit('lyrics', self.lyrics._key, data)
        self.h.pump(30)

    def test_open_close_with_keys(self):
        panel = self.find('nowPlaying')
        self.h.key(self.window, self.Qt.Key_P, self.Qt.ControlModifier, 'p')
        self.assertTrue(panel.property('open'))
        self.assertTrue(self.lyrics.active)
        self.assertEqual(self.find('nowTitle').property('text'), 'first')
        self.h.key(self.window, self.Qt.Key_Escape)
        self.assertFalse(panel.property('open'))
        self.assertTrue(self.window.isVisible(), 'Escape closes the panel, not the window')
        self.h.key(self.window, self.Qt.Key_Q, self.Qt.ControlModifier, 'q')
        self.assertEqual(panel.property('shownTab'), 'queue')
        self.h.key(self.window, self.Qt.Key_Q, self.Qt.ControlModifier, 'q')
        self.assertFalse(panel.property('open'), 'the same key closes it')

    def test_synced_lyrics_follow_position_offset_and_seek(self):
        self.h.call(self.window, 'togglePanel', 'lyrics')
        self.assertEqual(self.lyrics.state, 'loading')
        self.fetch.assert_called()
        self.deliver({'synced': LRC, 'plain': 'uno'})
        self.assertEqual(self.lyrics.state, 'synced')
        self.assertEqual(self.lyrics.source, 'Sincronizada · LRCLIB')
        self.player.seek(4)
        self.h.pump(30)
        self.assertEqual(self.lyrics.currentIndex, 1)
        self.lyrics.nudge(0.5)
        self.lyrics.nudge(0.5)
        self.assertEqual(self.lyrics.offsetText, '+1.0 s')
        self.assertEqual(self.music.library.store.get('offset:' + self.keys['first']), 1.0)
        self.player.seek(5.2)
        self.h.pump(30)
        self.assertEqual(self.lyrics.currentIndex, 2, 'position + offset')
        self.lyrics.seekLine(3)
        self.assertTrue(self.h.wait_for(lambda: abs(self.player.position - 8) < .5, 3000), 'line 9 s − 1 s offset')

    def test_lyrics_keyboard(self):
        self.h.call(self.window, 'togglePanel', 'lyrics')
        self.deliver({'synced': LRC})
        self.player.seek(0)
        self.h.pump(30)
        lines = self.find('lyricLines')
        lines.forceActiveFocus()
        self.h.key(self.window, self.Qt.Key_Down)
        self.h.key(self.window, self.Qt.Key_Down)
        self.h.key(self.window, self.Qt.Key_Return, text='\r')
        self.assertTrue(self.h.wait_for(lambda: abs(self.player.position - 6) < .5, 3000))

    def test_no_lyrics_shows_the_queue_unless_lyrics_were_chosen(self):
        self.h.call(self.window, 'togglePanel', 'now')
        self.deliver({'unavailable': True})
        panel = self.find('nowPlaying')
        self.assertEqual(self.lyrics.state, 'missing')
        self.assertEqual(panel.property('shownTab'), 'queue')
        self.h.call(self.window, 'togglePanel', '')
        self.h.call(self.window, 'togglePanel', 'lyrics')
        self.assertEqual(panel.property('shownTab'), 'lyrics')

    def test_queue_lists_what_comes_next_and_jumps(self):
        self.h.call(self.window, 'togglePanel', 'queue')
        upcoming = self.find('upcomingList')
        self.assertEqual(upcoming.property('count'), 2)
        self.h.call(upcoming, 'play', 1)
        self.assertTrue(self.h.wait_for(lambda: self.player.current == self.keys['third'], 4000))
        self.assertEqual(self.warnings, [])


if __name__ == '__main__':
    unittest.main()

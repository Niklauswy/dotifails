"""Playback from the QML window with real mpv (--ao=null): capsule, keyboard, position slider, messages."""
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support, music_fixture  # noqa: E402


class PlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import Qt
        cls.Qt = Qt
        cls.h = support.Harness.get()
        music_fixture.setup()
        cls.music = music_fixture.app()
        cls.window = cls.music.window.window
        cls.player = cls.music.player
        cls.keys = music_fixture.keys_by_title()
        cls.music.window.bridge.setReducedMotion(True)
        cls.music.window.present()
        cls.window.resize(1100, 800)
        cls.h.pump(100)

    @classmethod
    def tearDownClass(cls):
        cls.player.set_paused(True)
        cls.player.engine.quit()

    def find(self, name):
        return self.h.find_in(self.window.contentItem(), name)

    def wait(self, predicate, what, seconds=8):
        self.assertTrue(self.h.wait_for(predicate, int(seconds * 1000)), 'timed out waiting for ' + what)

    def key(self, key, modifiers=None, text=''):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QGuiApplication, QKeyEvent
        mods = modifiers if modifiers is not None else self.Qt.NoModifier
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QGuiApplication.sendEvent(self.window, QKeyEvent(kind, key, mods, text))
        self.h.pump(30)

    def click(self, item):
        from PySide6.QtCore import QPointF
        point = item.mapToScene(QPointF(item.property('width') / 2, item.property('height') / 2))
        self.h.click(self.window, point.x(), point.y())

    def start(self):
        self.h.find_in(self.window.contentItem(), 'musicRoot').forceActiveFocus()
        self.player.play(self.keys['first'], [self.keys[t] for t in ('first', 'second', 'third')], 'all')
        self.wait(lambda: self.player.playing and self.player.position > .2, 'playback')

    def test_capsule_shows_the_song_and_toggles(self):
        self.start()
        self.assertEqual(self.find('capsuleTitle').property('text'), 'first')
        self.click(self.find('playButton'))
        self.wait(lambda: self.player.paused, 'pause from the capsule')
        self.click(self.find('playButton'))
        self.wait(lambda: self.player.playing, 'resume from the capsule')

    def test_space_and_m(self):
        self.start()
        self.key(self.Qt.Key_Space, text=' ')
        self.wait(lambda: self.player.paused, 'Space pauses')
        self.key(self.Qt.Key_Space, text=' ')
        self.wait(lambda: self.player.playing, 'Space resumes')
        muted = self.player.muted
        self.key(self.Qt.Key_M, text='m')
        self.wait(lambda: self.player.muted != muted, 'M toggles mute')
        self.key(self.Qt.Key_M, text='m')

    def test_space_types_in_text_fields(self):
        self.start()
        search = self.find('searchBar')
        self.h.call(search, 'forceFocus')
        self.key(self.Qt.Key_Space, text=' ')
        self.key(self.Qt.Key_M, text='m')
        self.assertTrue(self.player.playing, 'typing in the search bar does not pause')
        self.assertEqual(search.property('text'), ' m')
        search.setProperty('text', '')
        self.h.call(self.window, 'navigate', 'home', True)

    def test_ctrl_shortcuts(self):
        self.start()
        self.key(self.Qt.Key_Right, self.Qt.ControlModifier)
        self.wait(lambda: self.player.current == self.keys['second'], 'Ctrl+→ next')
        before = self.player.repeat
        self.key(self.Qt.Key_R, self.Qt.ControlModifier, 'r')
        self.assertNotEqual(self.player.repeat, before)
        while self.player.repeat != 'off':
            self.player.cycle_repeat()
        volume = self.player.volume
        self.key(self.Qt.Key_Down, self.Qt.ControlModifier)
        self.wait(lambda: self.player.volume == max(0, volume - 5), 'Ctrl+↓ volume')
        self.key(self.Qt.Key_Up, self.Qt.ControlModifier)

    def test_position_slider_keys(self):
        self.start()
        self.player.set_paused(True)
        self.player.seek(1)
        slider = self.find('positionSlider')
        slider.forceActiveFocus(self.Qt.TabFocusReason)
        self.key(self.Qt.Key_Right)
        self.wait(lambda: abs(self.player.position - 6) < .6, '→ seeks +5 s')
        self.key(self.Qt.Key_Home)
        self.wait(lambda: self.player.position < .6, 'Home seeks to the start')
        self.h.pump(50)
        self.assertLess(abs(slider.property('value') - self.player.position), 1, 'the slider follows the player again')

    def test_play_restarts_the_current_song_and_play_or_toggle_pauses(self):
        self.start()
        bridge = self.music.window.playback
        keys = [self.keys[t] for t in ('first', 'second', 'third')]
        bridge.play(self.keys['first'], keys, 'all')
        self.assertTrue(self.h.wait_for(lambda: self.player.playing and self.player.position < 1, 3000), 'restarted, not paused')
        bridge.playOrToggle(self.keys['first'], keys, 'all')
        self.assertTrue(self.h.wait_for(lambda: self.player.paused, 3000))

    def test_messages_are_snackbars(self):
        snackbars = self.find('snackbars')
        self.player.engine.failed.emit('No se pudo iniciar mpv.')
        self.h.pump(30)
        self.assertEqual(snackbars.property('currentText'), 'No se pudo iniciar mpv.')
        self.h.call(snackbars, 'dismiss')

    def test_favorite_from_the_capsule(self):
        self.start()
        heart = self.find('capsuleFavorite')
        self.click(heart)
        self.assertIn(self.keys['first'], self.music.library.favorites)
        self.key(self.Qt.Key_F, self.Qt.ControlModifier | self.Qt.ShiftModifier, 'F')
        self.assertNotIn(self.keys['first'], self.music.library.favorites)


if __name__ == '__main__':
    unittest.main()

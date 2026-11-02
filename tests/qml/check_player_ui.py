"""Wysun Player's QML window (venv Python, offscreen, software video, synthetic media): it loads without warnings
for each kind, the bar shows the controls of the kind and folds them when narrow, shortcuts reach the controller,
the bar hides itself on a picture, the «more» menu fits the kind, and closing releases the video first."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/python'))
sys.path.insert(0, str(ROOT / 'tests'))
os.environ['WYSUN_MPV_OPTIONS'] = 'ao=null,hwdec=no'
os.environ['WYSUN_PLAYER_RENDERER'] = 'software'
from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from qml import support  # noqa: E402
from qml.check_player_controller import build_media  # noqa: E402


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg needed for synthetic media')
class PlayerWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()
        from wysun_player.quick import video
        from wysun_player.quick.controller import CoverStore, cover_provider
        video.register()
        cls.covers = CoverStore()
        cls.h.engine.addImageProvider('cover', cover_provider(cls.covers))
        cls.warnings = []
        cls.h.engine.warnings.connect(lambda found: cls.warnings.extend(w.toString() for w in found))
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(prefix='player-ui-', dir=scratch)
        cls.media = build_media(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def open(self, *names, width=960, height=600):
        from wysun_player.quick.process import PlayerWindow
        del self.warnings[:]
        window = PlayerWindow(self.h.engine, self.covers)
        window.controller.positions = None
        window._fitted = True                     # keep the size the test asks for
        window.controller.toasts = []
        window.controller.toast.connect(lambda text, icon: window.controller.toasts.append(text))
        window.show_files([str(self.media / n) for n in names])
        window.present()
        window.window.resize(width, height)
        self.addCleanup(self.close, window)
        self.h.pump(100)
        return window

    def close(self, window):
        from shiboken6 import isValid
        if window.window is not None and isValid(window.window) and window.window.isVisible():
            window.window.close()
        self.h.pump(50)

    def find(self, window, name):
        from PySide6.QtCore import QObject
        found = window.window.findChild(QObject, name)
        self.assertIsNotNone(found, name)
        return found

    def visible(self, window, name):
        item = self.find(window, name)
        return bool(item.property('visible'))

    def key(self, window, key, text='', modifiers=None):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtGui import QGuiApplication
        mods = modifiers if modifiers is not None else Qt.NoModifier
        for kind in (QKeyEvent.KeyPress, QKeyEvent.KeyRelease):
            QGuiApplication.sendEvent(window.window, QKeyEvent(kind, key, mods, text))
        self.h.pump(20)

    def qml_warnings(self):
        return [w for w in self.warnings if '/apps/qml/player/' in w]

    def test_video_loads_without_warnings_and_shows_its_controls(self):
        window = self.open('clip.mp4')
        ctl = window.controller
        self.assertTrue(self.h.wait_for(lambda: ctl.property('state') == 'playing', 8000))
        self.assertTrue(self.h.wait_for(lambda: self.find(window, 'videoStage').property('item').property('frames') > 2, 8000))
        for name in ('playButton', 'seekSlider', 'muteButton', 'volumeSlider', 'speedPill', 'subtitlesButton',
                     'moreButton', 'fullscreenButton', 'backButton', 'aheadButton'):
            self.assertTrue(self.visible(window, name), name)
        for name in ('zoomPill', 'audioButton', 'animationButton'):
            self.assertFalse(self.visible(window, name), name)
        self.assertEqual(self.qml_warnings(), [])

    def test_narrow_bar_folds_volume_speed_and_tracks(self):
        window = self.open('clip.mp4', width=400, height=400)
        bar = self.find(window, 'controlBar')
        self.assertTrue(self.h.wait_for(lambda: bar.property('compact'), 2000), bar.property('width'))
        for name in ('volumeSlider', 'speedPill', 'subtitlesButton', 'backButton'):
            self.assertFalse(self.visible(window, name), name)
        self.assertTrue(self.visible(window, 'playButton'))

    def test_picture_controls_and_shortcuts(self):
        window = self.open('pictures/b.png')
        ctl = window.controller
        self.assertTrue(self.h.wait_for(lambda: ctl.property('count') == 3, 4000))
        for name in ('zoomPill', 'zoomInButton', 'zoomOutButton', 'rotateButton', 'previousButton', 'nextButton'):
            self.assertTrue(self.visible(window, name), name)
        for name in ('playButton', 'seekSlider', 'muteButton'):
            self.assertFalse(self.visible(window, name), name)
        from PySide6.QtCore import Qt
        stage = self.find(window, 'imageStage')
        self.assertTrue(self.h.wait_for(lambda: stage.property('ready'), 4000))
        self.key(window, Qt.Key_Plus, '+')
        self.assertEqual(stage.property('mode'), 'zoom')
        self.key(window, Qt.Key_0, '0')
        self.assertEqual(stage.property('mode'), 'fit')
        self.key(window, Qt.Key_R, 'r')
        self.assertEqual(stage.property('turns'), 1)
        self.key(window, Qt.Key_Right)
        self.assertEqual(ctl.property('title'), 'c.png')
        self.key(window, Qt.Key_Right)
        self.assertIn('No hay más archivos', ctl.toasts)
        info = {row['label']: row['value'] for row in ctl.property('info')}
        self.assertTrue(self.h.wait_for(lambda: 'Dimensiones' in {r['label'] for r in ctl.property('info')}, 4000), info)
        self.assertEqual(self.qml_warnings(), [])

    def test_bar_hides_on_a_picture_after_inactivity(self):
        window = self.open('pictures/a.png')
        bar = self.find(window, 'controlBar')
        self.assertTrue(bar.property('visible'))
        self.assertTrue(self.h.wait_for(lambda: not window.window.property('barShown'), 4000))

    def test_a_pointer_that_rests_over_a_playing_video_does_not_keep_the_bar_up(self):
        """Found live: Qt re-delivers the same hover position on every video frame, and each one counted as activity."""
        window = self.open('clip.mp4')
        self.assertTrue(self.h.wait_for(lambda: window.controller.session.state == 'playing', 8000))
        qwin = window.window
        self.assertTrue(self.h.wait_for(lambda: not qwin.property('barShown'), 5000), 'it hides on its own first')
        self.h.move(qwin, 200, 150)                     # one real movement, away from the bar
        self.assertTrue(qwin.property('barShown'), 'moving the pointer brings the bar back')
        self.assertTrue(self.h.wait_for(lambda: not qwin.property('barShown'), 6000), 'and the bar goes again when it rests')
        self.assertEqual(self.qml_warnings(), [])

    def test_media_shortcuts_reach_the_controller(self):
        from PySide6.QtCore import Qt
        window = self.open('tone.mka')
        ctl = window.controller
        self.assertTrue(self.h.wait_for(lambda: ctl.property('state') == 'playing', 8000))
        self.key(window, Qt.Key_Space, ' ')
        self.assertTrue(self.h.wait_for(lambda: ctl.property('state') == 'paused', 2000))
        self.key(window, Qt.Key_M, 'm')
        self.assertTrue(self.h.wait_for(lambda: ctl.property('muted'), 2000))
        self.key(window, Qt.Key_BracketRight, ']')
        self.assertTrue(self.h.wait_for(lambda: ctl.property('speed') == 1.25, 2000))
        self.key(window, Qt.Key_Backspace)
        self.assertTrue(self.h.wait_for(lambda: ctl.property('speed') == 1.0, 2000))
        self.key(window, Qt.Key_C, 'c')                 # subtitles: only for video
        self.assertNotIn('Sin subtítulos', ctl.toasts)
        self.assertFalse(self.visible(window, 'fullscreenButton'))
        self.assertEqual(self.find(window, 'audioTitle').property('text'), 'Tono')

    def test_more_menu_fits_the_kind(self):
        window = self.open('pictures/a.png')
        menus = None
        for child in window.window.findChildren(object):
            if child.metaObject().className().startswith('PlayerMenus'):
                menus = child
        self.assertIsNotNone(menus)
        ids = [entry.get('id') for entry in menus.model('more').toVariant()] if hasattr(menus.model('more'), 'toVariant') \
            else [entry.get('id') for entry in menus.model('more')]
        self.assertIn('rotr', ids)
        self.assertIn('copyimage', ids)
        self.assertNotIn('saveframe', ids)

    def test_closing_releases_the_video_and_closes_the_session(self):
        window = self.open('clip.mp4')
        ctl = window.controller
        self.assertTrue(self.h.wait_for(lambda: ctl.property('state') == 'playing', 8000))
        item = self.find(window, 'videoStage').property('item')
        window.window.close()
        self.h.pump(50)
        self.assertIsNone(item._thread)
        self.assertEqual(ctl.session.state, 'closing')


if __name__ == '__main__':
    unittest.main()

"""Wysun Player's desktop integration through the QML window (venv Python, private D-Bus): a window publishes MPRIS
while media plays and releases it after, pictures never publish, transport methods and properties drive the
controller, Raise and Quit reach the QML window, and the screen-awake hint follows a visible, playing video."""
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

ROOT_IFACE = 'org.mpris.MediaPlayer2'
PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player'
PROPS = 'org.freedesktop.DBus.Properties'


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('dbus-daemon'), 'ffmpeg and dbus-daemon needed')
class PlayerMprisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = support.Harness.get()          # starts the private session bus first
        from wysun_player.quick import video
        from wysun_player.quick.controller import CoverStore, cover_provider
        video.register()
        cls.covers = CoverStore()
        try:
            cls.h.engine.addImageProvider('cover', cover_provider(cls.covers))
        except Exception:
            pass                                # another check registered it already
        scratch = Path.home() / '.cache/wysun-fase1/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(prefix='player-mpris-', dir=scratch)
        cls.media = build_media(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        from wysun_media import integration
        integration._bus = None
        self.clients = []

    def tearDown(self):
        from wysun_media import integration
        for bus in self.clients:
            bus.close()
        integration._bus = None

    def client(self):
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        bus = dbus.SessionBus(mainloop=DBusGMainLoop(set_as_default=True), private=True)
        bus.set_exit_on_disconnect(False)
        self.clients.append(bus)
        return bus

    def window(self, name):
        from wysun_player.quick.process import PlayerWindow
        window = PlayerWindow(self.h.engine, self.covers)
        window.controller.positions = None
        window._fitted = True
        window.show_files([str(self.media / name)])
        window.present()
        self.addCleanup(self.close, window)
        return window

    def close(self, window):
        from shiboken6 import isValid
        if window.window is not None and isValid(window.window) and window.window.isVisible():
            window.window.close()
        self.h.pump(50)

    def names(self):
        return sorted(str(n) for n in self.client().list_names() if str(n).startswith(ROOT_IFACE + '.wysun_player'))

    def call(self, name, interface, method, *args):
        import dbus
        from wysun_media import mpris
        result = []
        proxy = self.client().get_object(name, mpris.OBJECT_PATH, introspect=False)
        getattr(dbus.Interface(proxy, interface), method)(*args, reply_handler=lambda *r: result.append(r or True),
                                                           error_handler=lambda e: result.append(e))
        self.assertTrue(self.h.wait_for(lambda: result, 5000), method)
        if isinstance(result[0], dbus.DBusException):
            raise result[0]
        return result[0][0] if isinstance(result[0], tuple) and len(result[0]) == 1 else result[0]

    def prop(self, name, interface, key):
        return self.call(name, PROPS, 'Get', interface, key)

    def playing(self, window):
        return self.h.wait_for(lambda: window.controller.session.state == 'playing', 8000)

    def test_audio_is_published_with_its_properties_and_released_on_close(self):
        window = self.window('tone.mka')
        self.assertTrue(self.playing(window))
        self.assertTrue(self.h.wait_for(lambda: len(self.names()) == 1, 3000))
        name = self.names()[0]
        self.assertEqual(self.prop(name, ROOT_IFACE, 'Identity'), 'Wysun Player')
        self.assertEqual(self.prop(name, ROOT_IFACE, 'DesktopEntry'), 'wysun-player')
        self.assertEqual(self.prop(name, PLAYER_IFACE, 'PlaybackStatus'), 'Playing')
        self.assertEqual(str(self.prop(name, PLAYER_IFACE, 'Metadata')['xesam:title']), 'Tono')
        window.window.close()
        self.h.pump(100)
        self.assertTrue(self.h.wait_for(lambda: self.names() == [], 3000))

    def test_pictures_never_publish(self):
        self.window('pictures/a.png')
        self.h.pump(300)
        self.assertEqual(self.names(), [])

    def test_transport_and_settable_properties_drive_the_controller(self):
        import dbus
        window = self.window('tone.mka')
        session = window.controller.session
        self.assertTrue(self.playing(window))
        self.assertTrue(self.h.wait_for(lambda: len(self.names()) == 1, 3000))
        name = self.names()[0]
        self.call(name, PLAYER_IFACE, 'Pause')
        self.assertTrue(self.h.wait_for(lambda: session.state == 'paused', 3000))
        self.call(name, PLAYER_IFACE, 'PlayPause')
        self.assertTrue(self.h.wait_for(lambda: session.state == 'playing', 3000))
        self.call(name, PROPS, 'Set', PLAYER_IFACE, 'Volume', dbus.Double(.5))
        self.call(name, PROPS, 'Set', PLAYER_IFACE, 'Rate', dbus.Double(2.0))
        self.assertTrue(self.h.wait_for(lambda: session.volume == 50 and session.speed == 2.0, 3000))

    def test_raise_and_quit_reach_the_qml_window(self):
        window = self.window('tone.mka')
        self.assertTrue(self.playing(window))
        self.assertTrue(self.h.wait_for(lambda: len(self.names()) == 1, 3000))
        name = self.names()[0]
        self.call(name, ROOT_IFACE, 'Raise')
        self.call(name, ROOT_IFACE, 'Quit')
        from shiboken6 import isValid
        self.assertTrue(self.h.wait_for(lambda: not isValid(window.window) or not window.window.isVisible(), 3000))

    def test_the_screen_awake_hint_follows_a_visible_playing_video(self):
        from wysun_media import mpris
        window = self.window('clip.mp4')
        self.assertTrue(self.playing(window))
        self.assertTrue(self.h.wait_for(lambda: len(self.names()) == 1, 3000))
        name = self.names()[0]

        def hint():
            return bool(self.prop(name, PLAYER_IFACE, 'Metadata')[mpris.VISIBLE_VIDEO])

        self.assertTrue(self.h.wait_for(hint, 3000))
        window.controller.session.set_paused(True)
        self.assertTrue(self.h.wait_for(lambda: not hint(), 3000), 'a paused video lets the screen sleep')


if __name__ == '__main__':
    unittest.main()

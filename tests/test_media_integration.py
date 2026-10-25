"""MPRIS, the screen-awake hint and pausing Music, on a private D-Bus session bus."""
import os
import time
import unittest
from unittest import mock

import media_support as support

support.app()
import dbus  # noqa: E402
import dbus.service  # noqa: E402
from dbus.mainloop.glib import DBusGMainLoop  # noqa: E402
from wysun_media import integration, mpris, mpv  # noqa: E402
from wysun_media.player import MediaPlayer  # noqa: E402

ROOT_IFACE, PLAYER_IFACE, PROPS = mpris.ROOT, mpris.PLAYER, mpris.PROPERTIES


class BusCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = support.fixtures()
        cls.environment = mock.patch.dict(os.environ, {'WYSUN_MPV_OPTIONS': 'ao=null'})
        cls.environment.start()

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()

    def setUp(self):
        integration._bus = None
        self.clients = []

    def tearDown(self):
        for bus in self.clients:
            bus.close()
        integration._bus = None

    def client(self):
        bus = dbus.SessionBus(mainloop=DBusGMainLoop(set_as_default=True), private=True)
        bus.set_exit_on_disconnect(False)
        self.clients.append(bus)
        return bus

    def player(self, mode='full', **kwargs):
        player = MediaPlayer(mode=mode, renderer='software', **kwargs)
        player.resize(600, 400)
        player.show()
        self.addCleanup(self.finish, player)
        return player

    def finish(self, player):
        player.shutdown()
        player.close()
        player.deleteLater()
        support.settle(.05)
        mpv.wait_closed()

    def names(self):
        bus = self.client()
        return sorted(str(n) for n in bus.list_names() if str(n).startswith(ROOT_IFACE + '.wysun_player'))

    def call(self, name, interface, method, *args, **kwargs):
        """A D-Bus call made from this very process: the event loop must keep running while we wait."""
        result = []
        proxy = self.client().get_object(name, mpris.OBJECT_PATH, introspect=False)
        getattr(dbus.Interface(proxy, interface), method)(*args, reply_handler=lambda *r: result.append(r or True),
                                                           error_handler=lambda e: result.append(e), **kwargs)
        self.assertTrue(support.pump(lambda: result, 5), method)
        if isinstance(result[0], dbus.DBusException):
            raise result[0]
        return result[0][0] if isinstance(result[0], tuple) and len(result[0]) == 1 else result[0]

    def prop(self, name, interface, key):
        return self.call(name, PROPS, 'Get', interface, key)

    def play(self, player, name, **options):
        player.open(self.files / name, **options)
        self.assertTrue(support.pump(lambda: player.session.state == 'playing', 8))


class PublishingTests(BusCase):
    def test_a_player_window_is_published_while_media_is_open_and_released_after(self):
        player = self.player()
        player.enable_integration()
        self.assertEqual(self.names(), [])
        self.play(player, 'tone.mp3')
        names = self.names()
        self.assertEqual(len(names), 1)
        self.assertRegex(names[0], r'^org\.mpris\.MediaPlayer2\.wysun_player\.instance\d+_\d+$')
        player.close_media()
        support.settle(.1)
        self.assertEqual(self.names(), [])

    def test_images_and_passive_previews_never_register(self):
        window = self.player('full')
        window.enable_integration()
        window.open(self.files / 'plain.png')
        support.settle(.2)
        self.assertEqual(self.names(), [])
        preview = self.player('embedded')
        preview.enable_integration()
        preview.open(self.files / 'tone.mp3', paused=True)
        self.assertTrue(support.pump(lambda: preview.session.state == 'paused'))
        support.settle(.2)
        self.assertEqual(self.names(), [], 'an embedded preview that nobody started is not a player')
        preview.session.set_paused(False)
        self.assertTrue(support.pump(lambda: self.names()))
        self.assertEqual(len(self.names()), 1, 'pressing play makes it one')

    def test_changing_file_keeps_the_same_service_and_gives_a_new_track_id(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.mp3')
        name = self.names()[0]
        first = str(self.prop(name, PLAYER_IFACE, 'Metadata')['mpris:trackid'])
        player.open(self.files / 'tone.flac')
        self.assertTrue(support.pump(lambda: player.session.state == 'playing'))
        self.assertEqual(self.names(), [name], 'the service must not flicker between files')
        metadata = self.prop(name, PLAYER_IFACE, 'Metadata')
        self.assertEqual(str(metadata['xesam:title']), 'tone.flac')
        self.assertNotEqual(str(metadata['mpris:trackid']), first)

    def test_every_player_gets_its_own_name_and_object(self):
        first, second = self.player(), self.player()
        for player in (first, second):
            player.enable_integration()
            self.play(player, 'tone.mp3')
        self.assertEqual(len(set(self.names())), 2)

    def test_root_and_player_properties(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.mp3')
        name = self.names()[0]
        self.assertEqual(self.prop(name, ROOT_IFACE, 'Identity'), 'Wysun Player')
        self.assertEqual(self.prop(name, ROOT_IFACE, 'DesktopEntry'), 'wysun-player')
        self.assertEqual(list(self.prop(name, ROOT_IFACE, 'SupportedUriSchemes')), ['file'])
        self.assertEqual(self.prop(name, PLAYER_IFACE, 'PlaybackStatus'), 'Playing')
        self.assertTrue(self.prop(name, PLAYER_IFACE, 'CanSeek'))
        self.assertEqual(float(self.prop(name, PLAYER_IFACE, 'Rate')), 1.0)
        metadata = self.prop(name, PLAYER_IFACE, 'Metadata')
        self.assertEqual(str(metadata['xesam:title']), 'tone.mp3')
        self.assertTrue(str(metadata['xesam:url']).startswith('file:///'))
        self.assertAlmostEqual(int(metadata['mpris:length']) / 1e6, 3.0, delta=.3)
        self.assertEqual(bool(metadata[mpris.VISIBLE_VIDEO]), False, 'audio never asks the screen to stay on')

    def test_transport_methods_drive_the_player(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.wav')
        name = self.names()[0]
        self.call(name, PLAYER_IFACE, 'Pause')
        self.assertTrue(support.pump(lambda: player.session.state == 'paused'))
        self.assertEqual(self.prop(name, PLAYER_IFACE, 'PlaybackStatus'), 'Paused')
        self.call(name, PLAYER_IFACE, 'PlayPause')
        self.assertTrue(support.pump(lambda: player.session.state == 'playing'))
        self.call(name, PLAYER_IFACE, 'Seek', dbus.Int64(1_000_000))
        self.assertTrue(support.pump(lambda: player.session.position > 1.0))
        track = self.prop(name, PLAYER_IFACE, 'Metadata')['mpris:trackid']
        self.call(name, PLAYER_IFACE, 'SetPosition', dbus.ObjectPath(track), dbus.Int64(500_000))
        self.assertTrue(support.pump(lambda: abs(player.session.position - .5) < .3))
        self.call(name, PLAYER_IFACE, 'SetPosition', dbus.ObjectPath('/not/this/track'), dbus.Int64(2_500_000))
        support.settle(.2)
        self.assertLess(player.session.position, 2.0, 'a position for another track is ignored')
        self.assertAlmostEqual(int(self.prop(name, PLAYER_IFACE, 'Position')) / 1e6, player.session.position, delta=.5)

    def test_settable_properties(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.wav')
        name = self.names()[0]
        self.call(name, PROPS, 'Set', PLAYER_IFACE, 'Rate', dbus.Double(2.0))
        self.call(name, PROPS, 'Set', PLAYER_IFACE, 'Volume', dbus.Double(.5))
        self.call(name, PROPS, 'Set', PLAYER_IFACE, 'LoopStatus', 'Track')
        self.assertTrue(support.pump(lambda: player.session.speed == 2.0 and player.session.volume == 50 and player.session.looping))

    def test_open_uri_accepts_local_media_only(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.wav')
        name = self.names()[0]
        self.call(name, PLAYER_IFACE, 'OpenUri', 'http://example.invalid/a.mp3')
        self.call(name, PLAYER_IFACE, 'OpenUri', 'file:///etc/passwd')
        support.settle(.2)
        self.assertEqual(player.source.name, 'tone.wav')
        self.call(name, PLAYER_IFACE, 'OpenUri', (self.files / 'tone.flac').as_uri())
        self.assertTrue(support.pump(lambda: player.source.name == 'tone.flac'))

    def test_next_and_previous_follow_the_collection(self):
        player = self.player()
        player.enable_integration()
        player.open(self.files / 'tone.flac', browse='folder')
        self.assertTrue(support.pump(lambda: len(player.collection) > 3 and player.session.state == 'playing'))
        name = self.names()[0]
        self.assertTrue(self.prop(name, PLAYER_IFACE, 'CanGoNext') or self.prop(name, PLAYER_IFACE, 'CanGoPrevious'))
        first = player.source.name
        direction = 'Next' if player.collection.neighbour(1) is not None else 'Previous'
        self.call(name, PLAYER_IFACE, direction)
        self.assertTrue(support.pump(lambda: player.source.name != first))

    def test_property_changes_are_signalled_with_only_what_changed(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.mp3')
        name = self.names()[0]
        seen = []
        bus = self.client()
        bus.add_signal_receiver(lambda interface, changed, invalidated: seen.append((str(interface), dict(changed))), 'PropertiesChanged', PROPS,
                                name, mpris.OBJECT_PATH)
        player.session.set_paused(True)
        self.assertTrue(support.pump(lambda: any('PlaybackStatus' in c for _, c in seen)))
        status = next(c for _, c in seen if 'PlaybackStatus' in c)
        self.assertEqual(str(status['PlaybackStatus']), 'Paused')
        self.assertNotIn('Position', status, 'Position is read on demand, never signalled')
        self.assertNotIn('Rate', status)

    def test_raise_and_quit_reach_the_window(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.mp3')
        name = self.names()[0]
        self.call(name, ROOT_IFACE, 'Raise')
        self.call(name, ROOT_IFACE, 'Quit')
        self.assertTrue(support.pump(lambda: not player.window().isVisible()))

    def test_shutdown_releases_the_name(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.mp3')
        self.assertEqual(len(self.names()), 1)
        player.shutdown()
        support.settle(.1)
        self.assertEqual(self.names(), [])

    def test_without_a_session_bus_the_player_still_plays(self):
        with mock.patch.object(mpris, '_dbus', side_effect=ImportError('sin dbus-python')):
            player = self.player()
            player.enable_integration()
            self.play(player, 'tone.mp3')
            self.assertIsNone(player.integrations[0].mpris.service)


class VisibleVideoTests(BusCase):
    def metadata(self, name):
        return self.prop(name, PLAYER_IFACE, 'Metadata')

    def test_the_hint_is_on_only_for_a_visible_playing_video(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'h264.mp4')
        name = self.names()[0]
        self.assertTrue(support.pump(lambda: bool(self.metadata(name)[mpris.VISIBLE_VIDEO])))
        player.session.set_paused(True)
        support.pump(lambda: player.session.state == 'paused')
        self.assertFalse(bool(self.metadata(name)[mpris.VISIBLE_VIDEO]), 'a paused video lets the screen sleep')
        player.session.set_paused(False)
        support.pump(lambda: player.session.state == 'playing')
        player.window().hide()
        support.settle(.1)
        self.assertFalse(bool(self.metadata(name)[mpris.VISIBLE_VIDEO]), 'a hidden window does not keep the screen on')
        player.window().show()
        self.assertTrue(support.pump(lambda: bool(self.metadata(name)[mpris.VISIBLE_VIDEO])))

    def test_the_hint_clears_when_the_video_ends_or_closes(self):
        player = self.player()
        player.enable_integration()
        self.play(player, 'h264.mp4')
        name = self.names()[0]
        player.session.seek(player.session.duration - .1)
        self.assertTrue(support.pump(lambda: player.session.state == 'ended', 6))
        self.assertFalse(bool(self.metadata(name)[mpris.VISIBLE_VIDEO]))
        player.close_media()
        support.settle(.1)
        self.assertEqual(self.names(), [])


class FakeMusic(dbus.service.Object):
    """Stands in for Wysun Music's MPRIS: a status and a Pause that records calls."""

    def __init__(self, bus, status='Playing', answer=True):
        self.name = dbus.service.BusName(integration.MUSIC, bus)
        super().__init__(bus, mpris.OBJECT_PATH)
        self.status, self.pauses, self.answer = status, 0, answer

    @dbus.service.method(PROPS, in_signature='ss', out_signature='v', async_callbacks=('ok', 'fail'))
    def Get(self, interface, key, ok, fail):
        if self.answer:
            ok(self.status)

    @dbus.service.method(PLAYER_IFACE)
    def Pause(self):
        self.pauses += 1
        self.status = 'Paused'


class MusicTests(BusCase):
    def music(self, **kwargs):
        bus = self.client()
        music = FakeMusic(bus, **kwargs)
        return music

    def test_sound_pauses_a_playing_music_once_per_start(self):
        music = self.music()
        player = self.player()
        player.enable_integration()
        self.play(player, 'h264.mp4')
        self.assertTrue(support.pump(lambda: music.pauses == 1, 5))
        player.session.set_muted(True)
        support.settle(.2)
        player.session.set_muted(False)
        support.settle(.4)
        self.assertEqual(music.pauses, 1, 'music was already paused, so it is left alone')
        music.status = 'Playing'
        player.session.set_muted(True)
        support.pump(lambda: not player.session.audible)
        player.session.set_muted(False)
        self.assertTrue(support.pump(lambda: music.pauses == 2, 5), 'a new start of sound pauses it again')

    def test_a_silent_video_or_a_muted_start_leaves_music_alone(self):
        music = self.music()
        player = self.player()
        player.enable_integration()
        self.play(player, 'silent.mp4')
        support.settle(.4)
        self.assertEqual(music.pauses, 0)

    def test_an_already_paused_music_is_not_touched_and_nothing_is_started(self):
        music = self.music(status='Paused')
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.mp3')
        support.settle(.4)
        self.assertEqual(music.pauses, 0)

    def test_no_music_means_no_delay_and_no_error(self):
        player = self.player()
        player.enable_integration()
        started = time.monotonic()
        self.play(player, 'tone.mp3')
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual(player.session.state, 'playing')

    def test_music_that_never_answers_cannot_stall_playback(self):
        music = self.music(answer=False)
        player = self.player()
        player.enable_integration()
        self.play(player, 'tone.mp3')
        position = player.session.position
        support.settle(.6)
        self.assertGreater(player.session.position, position, 'playback goes on while the request waits for its timeout')
        self.assertEqual(music.pauses, 0)

    def test_an_embedded_preview_pauses_music_only_when_the_user_plays(self):
        music = self.music()
        player = self.player('embedded')
        player.enable_integration()
        player.open(self.files / 'tone.mp3', paused=True)
        support.settle(.4)
        self.assertEqual(music.pauses, 0)
        player.session.set_paused(False)
        self.assertTrue(support.pump(lambda: music.pauses == 1, 5))


if __name__ == '__main__':
    unittest.main()

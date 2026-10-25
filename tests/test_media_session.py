"""Playback sessions on a real libmpv with a null audio output: states, seeking, stale events, errors, teardown."""
import os
import unittest
from unittest import mock

import media_support as support

support.app()
from wysun_media import mpv  # noqa: E402
from wysun_media.errors import MediaError  # noqa: E402
from wysun_media.session import MediaSession  # noqa: E402
from wysun_media.source import open_source  # noqa: E402
from wysun_media.video import SoftwareVideoView  # noqa: E402

OPTIONS = {'ao': 'null', 'hwdec': 'no'}


def descriptors():
    return len(os.listdir('/proc/self/fd'))


def threads():
    return len(os.listdir('/proc/self/task'))


class SessionCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = support.fixtures()

    def session(self):
        session = MediaSession(options=OPTIONS)
        self.addCleanup(self.release, session)
        session.states = []
        session.errors = []
        session.stateChanged.connect(session.states.append)
        session.errorOccurred.connect(session.errors.append)
        return session

    def release(self, session):
        session.close()
        mpv.wait_closed()

    def play(self, session, name, **options):
        session.open(open_source(self.files / name), **options)
        return support.pump(lambda: session.state == 'playing')

    def with_surface(self, session):
        view = SoftwareVideoView()
        view.resize(320, 180)
        view.ready.connect(lambda: session.set_surface_ready(True))
        view.attach(session)
        view.show()
        self.addCleanup(view.release)
        return view


class AudioTests(SessionCase):
    def test_states_progress_and_end(self):
        session = self.session()
        self.assertEqual(session.state, 'idle')
        self.assertTrue(self.play(session, 'tone.mp3'))
        self.assertEqual(session.states[:2], ['loading', 'playing'])
        self.assertTrue(support.pump(lambda: session.position > .5))
        self.assertAlmostEqual(session.duration, 3.0, delta=.2)
        self.assertTrue(session.has_audio)
        self.assertFalse(session.has_video)
        self.assertTrue(session.audible)
        self.assertTrue(support.pump(lambda: session.state == 'ended', 8))
        self.assertEqual(session.errors, [])

    def test_pause_resume_and_restart_after_the_end(self):
        session = self.session()
        self.play(session, 'tone.mp3')
        session.set_paused(True)
        self.assertTrue(support.pump(lambda: session.state == 'paused'))
        self.assertFalse(session.audible)
        session.set_paused(False)
        self.assertTrue(support.pump(lambda: session.state == 'playing'))
        session.seek(session.duration - .2)
        self.assertTrue(support.pump(lambda: session.state == 'ended', 5))
        session.toggle()
        self.assertTrue(support.pump(lambda: session.state == 'playing' and session.position < 1.5))

    def test_exact_seek_lands_on_the_target(self):
        session = self.session()
        self.play(session, 'tone.flac', paused=True)
        self.assertTrue(support.pump(lambda: session.duration > 0))
        session.seek(1.5)
        self.assertTrue(support.pump(lambda: abs(session.position - 1.5) < .05))
        session.seek_relative(-1.0)
        self.assertTrue(support.pump(lambda: abs(session.position - .5) < .05))
        session.seek(999)                                      # clamped to the end
        self.assertTrue(support.pump(lambda: session.position >= session.duration - .1))

    def test_start_position_and_start_paused(self):
        session = self.session()
        session.open(open_source(self.files / 'tone.wav'), start=1.0, paused=True)
        self.assertTrue(support.pump(lambda: session.state == 'paused' and session.duration > 0))
        self.assertAlmostEqual(session.position, 1.0, delta=.1)

    def test_volume_mute_and_speed(self):
        session = self.session()
        self.play(session, 'tone.opus')
        session.set_volume(40)
        self.assertTrue(support.pump(lambda: session.volume == 40))
        session.set_volume(500)
        self.assertTrue(support.pump(lambda: session.volume == 150))
        session.set_muted(True)
        self.assertTrue(support.pump(lambda: session.muted))
        self.assertFalse(session.audible)
        session.set_speed(9)
        self.assertTrue(support.pump(lambda: session.speed == 4.0))
        session.set_speed(.01)
        self.assertTrue(support.pump(lambda: session.speed == .25))

    def test_loop_keeps_playing_at_the_end(self):
        session = self.session()
        self.play(session, 'tone.mp3')
        session.set_loop(True)
        self.assertTrue(support.pump(lambda: session.looping))
        session.seek(session.duration - .3)
        support.settle(1.2)
        self.assertEqual(session.state, 'playing')
        self.assertLess(session.position, 2.0)

    def test_ab_loop_cycles_through_its_three_states(self):
        session = self.session()
        self.play(session, 'tone.mp3')
        session.mark_loop()
        self.assertTrue(support.pump(lambda: session.ab_loop[0] is not None))
        session.mark_loop()
        self.assertTrue(support.pump(lambda: session.ab_loop[1] is not None))
        session.mark_loop()
        self.assertTrue(support.pump(lambda: session.ab_loop == (None, None)))

    def test_metadata_and_track_list_arrive(self):
        session = self.session()
        self.play(session, 'cover.mp3')
        self.assertTrue(support.pump(lambda: session.tracks('audio')))
        self.assertEqual(session.tracks('video'), [])          # cover art is not a video to play

    def test_bad_track_change_does_not_stop_playback(self):
        session = self.session()
        failures = []
        session.commandFailed.connect(failures.append)
        self.play(session, 'tone.mp3')
        session.add_subtitle(self.files / 'missing.srt')
        self.assertTrue(support.pump(lambda: failures))
        self.assertTrue(failures[0].recoverable)
        self.assertEqual(session.state, 'playing')


class ReplacementTests(SessionCase):
    def test_rapid_a_b_c_ends_on_c_without_stale_errors(self):
        session = self.session()
        for _ in range(8):
            for name in ('fake.mp4', 'tone.mp3', 'tone.flac', 'tone.opus'):
                session.open(open_source(self.files / name))
        self.assertTrue(support.pump(lambda: session.state == 'playing'))
        support.settle(.5)
        self.assertEqual(session.source.name, 'tone.opus')
        self.assertEqual(session.state, 'playing')
        self.assertEqual(session.errors, [], 'the error of a replaced file must not surface')

    def test_an_undecodable_file_fails_clearly_and_the_next_one_recovers(self):
        session = self.session()
        view = self.with_surface(session)
        session.open(open_source(self.files / 'fake.mp4'))
        self.assertTrue(support.pump(lambda: session.state == 'error', 10), session.state)
        self.assertIn(session.errors[-1].category, ('unsupported', 'decode', 'unreadable'))
        self.assertTrue(session.errors[-1].message)
        self.assertTrue(self.play(session, 'tone.mp3'))
        self.assertIsNone(session.error)
        del view

    def test_seek_storm_is_coalesced_and_survives(self):
        session = self.session()
        self.play(session, 'tone.wav')
        for step in range(300):
            session.scrub((step % 30) / 10)
            if step % 25 == 0:
                support.settle(.01)
        session.seek(2.0)
        self.assertTrue(support.pump(lambda: abs(session.position - 2.0) < .3))
        self.assertIn(session.state, ('playing', 'ended'))

    def test_closing_during_load_is_safe(self):
        for _ in range(5):
            session = MediaSession(options=OPTIONS)
            session.open(open_source(self.files / 'tone.mp3'))
            session.close()
        mpv.wait_closed()
        session.close()                                          # idempotent
        session.seek(1)                                          # commands after close are ignored, not crashes
        session.set_paused(True)

    def test_no_descriptors_or_threads_survive_repeated_open_and_close(self):
        support.settle(.2)
        before = (descriptors(), threads())
        for _ in range(12):
            session = MediaSession(options=OPTIONS)
            session.open(open_source(self.files / 'tone.mp3'))
            support.pump(lambda: session.state == 'playing', 3)
            session.close()
            mpv.wait_closed()
        support.settle(.3)
        after = (descriptors(), threads())
        self.assertLessEqual(after[0], before[0] + 1, f'descriptors grew {before[0]} -> {after[0]}')
        self.assertLessEqual(after[1], before[1] + 1, f'threads grew {before[1]} -> {after[1]}')


class VideoTests(SessionCase):
    def test_video_waits_for_its_surface_then_plays(self):
        session = self.session()
        session.open(open_source(self.files / 'h264.mp4'))
        support.settle(.3)
        self.assertEqual(session.state, 'loading', 'video must not start before a render target exists')
        self.with_surface(session)
        self.assertTrue(support.pump(lambda: session.state == 'playing'))
        self.assertTrue(session.has_video and session.has_audio)
        self.assertTrue(support.pump(lambda: (session.props.get('video-params') or {}).get('w') == 640))

    def test_every_codec_fixture_plays_in_software(self):
        for name in ('h264.mp4', 'vp9.webm', 'hevc.mkv', 'av1.mkv', 'h264.mov', 'silent.mp4'):
            with self.subTest(name):
                session = self.session()
                self.with_surface(session)
                self.assertTrue(self.play(session, name), name)
                self.assertTrue(support.pump(lambda: session.position > .3), name)
                self.assertEqual(session.errors, [])
                if name == 'silent.mp4':
                    self.assertFalse(session.has_audio)
                    self.assertFalse(session.audible)

    def test_frame_is_saved_and_opaque(self):
        import tempfile
        from pathlib import Path
        from PySide6.QtGui import QImage
        session = self.session()
        self.with_surface(session)
        self.play(session, 'h264.mp4')
        support.pump(lambda: session.position > .3)
        saved = []
        session.frameSaved.connect(saved.append)
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'frame.png'
            session.save_frame(target)
            self.assertTrue(support.pump(lambda: saved))
            frame = QImage(str(target))
            self.assertEqual((frame.width(), frame.height()), (640, 360))

    def test_the_software_surface_is_opaque_for_the_compositor(self):
        """Whatever mpv writes in the alpha byte, what reaches the window must have no transparency."""
        from PySide6.QtGui import QImage
        session = self.session()
        view = self.with_surface(session)
        self.play(session, 'h264.mp4')
        self.assertTrue(support.pump(lambda: not view._image.isNull() and session.position > .3, 5))
        rendered = QImage(view.size(), QImage.Format_ARGB32_Premultiplied)
        rendered.fill(0)
        view.render(rendered)
        for x in range(0, rendered.width(), 37):
            for y in range(0, rendered.height(), 29):
                self.assertEqual(rendered.pixelColor(x, y).alpha(), 255, (x, y))
        self.assertGreater(rendered.pixelColor(rendered.width() // 2, rendered.height() // 2).lightness(), 20, 'the video is visible')

    def test_a_missing_libmpv_is_a_clear_error(self):
        session = MediaSession(options=OPTIONS)
        saved, mpv._lib = mpv._lib, None
        try:
            with mock.patch.dict(os.environ, {'WYSUN_LIBMPV': '/nonexistent/libmpv.so.2'}):
                with self.assertRaises(MediaError) as caught:
                    session.open(open_source(self.files / 'tone.mp3'))
        finally:
            mpv._lib = saved
        self.assertEqual(caught.exception.category, 'backend')


class BindingTests(unittest.TestCase):
    def test_numeric_locale_is_c_so_mpv_accepts_it(self):
        import locale
        mpv.normalize_numeric_locale()
        self.assertEqual(locale.setlocale(locale.LC_NUMERIC), 'C')

    def test_fixed_options_disable_user_config_scripts_and_foreign_protocols(self):
        for key, value in (('config', 'no'), ('load-scripts', 'no'), ('ytdl', 'no'), ('sub-auto', 'no'), ('audio-file-auto', 'no'),
                           ('load-unsafe-playlists', 'no'), ('osc', 'no'), ('vo', 'libmpv')):
            self.assertEqual(mpv.FIXED_OPTIONS[key], value, key)
        self.assertEqual(mpv.FIXED_OPTIONS['demuxer-lavf-o'], 'protocol_whitelist=file')


if __name__ == '__main__':
    unittest.main()

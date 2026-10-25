"""MediaPlayer as one reusable widget: both modes, every kind of file, keyboard, menus, themes, teardown."""
import unittest
from pathlib import Path

import media_support as support

support.app()
from PySide6.QtCore import QEvent, QMimeData, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent, QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402
from wysun_media import mpv  # noqa: E402
from wysun_media.player import MediaPlayer  # noqa: E402



class PlayerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = support.fixtures()

    def player(self, mode='full', size=(900, 540), **options):
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        player = MediaPlayer(mode=mode, renderer='software', options={'ao': 'null'}, **options)
        layout.addWidget(player)
        holder.resize(*size)
        holder.show()
        player.errors = []
        player.errorOccurred.connect(player.errors.append)
        self.addCleanup(self.finish, holder, player)
        return player

    def finish(self, holder, player):
        player.shutdown()
        holder.close()
        holder.deleteLater()
        mpv.wait_closed()

    def open(self, player, name, **options):
        self.assertTrue(player.open(self.files / name, **options), name)
        return player

    def key(self, player, key, modifiers=Qt.NoModifier):
        text = chr(key) if 32 <= key < 127 else ''
        text = text if modifiers & Qt.ShiftModifier else text.lower()
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QApplication.sendEvent(player, QKeyEvent(kind, key, modifiers, text))
        support.settle(.05)


class KindTests(PlayerCase):
    def test_audio_video_and_image_share_one_widget(self):
        player = self.player()
        self.open(player, 'tone.mp3')
        self.assertTrue(support.pump(lambda: player.session.state == 'playing'))
        self.assertEqual(player.kind, 'audio')
        self.assertTrue(player._audio.isVisible() and player._video is None)
        self.open(player, 'h264.mp4')
        self.assertTrue(support.pump(lambda: player.session.state == 'playing'))
        self.assertTrue(player._video.isVisible() and not player._audio.isVisible())
        self.open(player, 'plain.png')
        support.pump(lambda: player._images.frame is not None)
        self.assertTrue(player._images.isVisible() and not player._video.isVisible())
        self.assertEqual(player.session.state, 'idle', 'viewing an image stops the media session')
        self.assertEqual(player.errors, [])

    def test_titles_and_sources_are_reported(self):
        player, titles, sources = self.player(), [], []
        player.titleChanged.connect(titles.append)
        player.opened.connect(sources.append)
        self.open(player, 'tone.wav')
        self.assertEqual(titles, ['tone.wav'])
        self.assertEqual(sources[0].kind, 'audio')

    def test_unplayable_and_invalid_files_show_a_message_and_recover(self):
        player = self.player()
        self.assertFalse(player.open(self.files / 'list.m3u'))
        self.assertTrue(player.note.isVisible())
        self.assertEqual(player.errors[-1].category, 'unsupported')
        self.assertFalse(player.open('/no/such/file.mp4'))
        self.assertEqual(player.errors[-1].category, 'missing')
        self.assertFalse(player.open('http://example.invalid/a.mp4'))
        self.assertEqual(player.errors[-1].category, 'rejected')
        self.open(player, 'tone.mp3')
        self.assertFalse(player.note.isVisible())

    def test_damaged_image_reports_through_the_player(self):
        player = self.player()
        self.open(player, 'truncated.jpg')
        self.assertTrue(support.pump(lambda: player.errors))
        self.assertEqual(player.kind, 'image')

    def test_close_media_returns_to_an_empty_player(self):
        player = self.player()
        self.open(player, 'tone.mp3')
        player.close_media()
        self.assertEqual((player.source, player.kind, player.session.state), (None, '', 'idle'))
        self.assertFalse(player.bar.isVisible())


class ModeTests(PlayerCase):
    def test_embedded_image_has_no_bar_and_full_image_has_zoom_controls(self):
        embedded = self.player('embedded')
        self.open(embedded, 'plain.png')
        self.assertFalse(embedded.bar.isVisible())
        full = self.player('full')
        self.open(full, 'plain.png')
        support.settle(.1)
        self.assertTrue(full.bar.isVisible() and full.bar.zoom.isVisible() and full.bar.rotate.isVisible())
        self.assertFalse(full.bar.progress.isVisible())

    def test_embedded_media_offers_expand_and_full_offers_fullscreen(self):
        embedded = self.player('embedded')
        self.open(embedded, 'tone.mp3', paused=True)
        support.settle(.1)
        self.assertTrue(embedded.bar.expand.isVisible() and not embedded.bar.fullscreen.isVisible())
        expanded = []
        embedded.expandRequested.connect(lambda: expanded.append(True))
        embedded.bar.expand.click()
        self.assertEqual(expanded, [True])
        full = self.player('full')
        self.open(full, 'h264.mp4', paused=True)
        support.settle(.1)
        self.assertTrue(full.bar.fullscreen.isVisible() and not full.bar.expand.isVisible())

    def test_audio_has_no_fullscreen_and_embedded_corners_are_rounded(self):
        full = self.player('full')
        self.open(full, 'tone.mp3', paused=True)
        support.settle(.1)
        self.assertFalse(full.bar.fullscreen.isVisible())
        events = []
        full.fullscreenRequested.connect(events.append)
        full.set_fullscreen(True)
        self.assertEqual(events, [])
        self.assertEqual(self.player('embedded').rounding.corner, 'xl')
        self.assertEqual(full.rounding.corner, 'none')

    def test_fullscreen_requests_are_reported_and_reflected(self):
        player, events = self.player('full'), []
        player.fullscreenRequested.connect(events.append)
        self.open(player, 'h264.mp4', paused=True)
        self.key(player, Qt.Key_F)
        self.assertEqual(events, [True])
        self.assertEqual(player.bar.fullscreen.accessibleName(), 'Salir de pantalla completa · Esc')
        self.key(player, Qt.Key_Escape)
        self.assertEqual(events, [True, False])

    def test_bar_hides_while_video_plays_and_returns_on_activity(self):
        player = self.player('full')
        player._idle.setInterval(60)
        self.open(player, 'h264.mp4')
        self.assertTrue(support.pump(lambda: player.session.state == 'playing'))
        self.assertTrue(support.pump(lambda: not player.bar.isVisible(), 3))
        player.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(100, 100), QPointF(100, 100), Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        self.assertTrue(player.bar.isVisible())

    def test_bar_stays_visible_while_paused_and_for_audio(self):
        player = self.player('full')
        player._idle.setInterval(60)
        self.open(player, 'h264.mp4', paused=True)
        support.settle(.4)
        self.assertTrue(player.bar.isVisible())
        self.open(player, 'tone.mp3')
        support.settle(.4)
        self.assertTrue(player.bar.isVisible())

    def test_narrow_players_fold_secondary_controls_into_the_menu(self):
        player = self.player('full', size=(300, 300))
        self.open(player, 'h264.mp4', paused=True)
        support.settle(.1)
        self.assertTrue(player.bar.compact)
        self.assertFalse(player.bar.volume.isVisible() or player.bar.speed.isVisible() or player.bar.subtitles.isVisible())
        self.assertTrue(player.bar.more.isVisible())


class KeyboardTests(PlayerCase):
    def test_transport_keys(self):
        player = self.player()
        self.open(player, 'tone.wav')
        self.assertTrue(support.pump(lambda: player.session.state == 'playing'))
        self.key(player, Qt.Key_Space)
        self.assertTrue(support.pump(lambda: player.session.state == 'paused'))
        self.key(player, Qt.Key_Space)
        self.assertTrue(support.pump(lambda: player.session.state == 'playing'))
        self.key(player, Qt.Key_5)
        self.assertTrue(support.pump(lambda: abs(player.session.position - player.session.duration / 2) < .3))
        self.key(player, Qt.Key_Home)
        self.assertTrue(support.pump(lambda: player.session.position < .4))
        self.key(player, Qt.Key_Right, Qt.ShiftModifier)
        self.assertTrue(support.pump(lambda: player.session.position > .9))

    def test_volume_speed_and_mute_keys(self):
        player = self.player()
        self.open(player, 'tone.wav')
        support.pump(lambda: player.session.state == 'playing')
        self.key(player, Qt.Key_Down)
        self.assertTrue(support.pump(lambda: player.session.volume == 95))
        self.key(player, Qt.Key_Up)
        self.key(player, Qt.Key_Up)
        self.assertTrue(support.pump(lambda: player.session.volume == 105))
        self.key(player, Qt.Key_BracketRight)
        self.assertTrue(support.pump(lambda: player.session.speed == 1.25))
        self.key(player, Qt.Key_Backspace)
        self.assertTrue(support.pump(lambda: player.session.speed == 1.0))
        self.key(player, Qt.Key_M)
        self.assertTrue(support.pump(lambda: player.session.muted))
        self.assertEqual(player.bar.mute.accessibleName(), 'Activar sonido · M')

    def test_frame_stepping_only_while_paused(self):
        player = self.player()
        self.open(player, 'h264.mp4', paused=True)
        self.assertTrue(support.pump(lambda: player.session.state == 'paused' and (player.session.props.get('video-params') or {}).get('w'), 8))
        support.settle(.2)                                  # the first picture is up: stepping starts from a settled position
        before = player.session.position
        self.key(player, Qt.Key_Period)
        self.assertTrue(support.pump(lambda: player.session.position > before))

    def test_ab_loop_key_marks_and_clears(self):
        player = self.player()
        self.open(player, 'tone.wav')
        support.pump(lambda: player.session.state == 'playing')
        self.key(player, Qt.Key_L)
        self.assertTrue(support.pump(lambda: player.session.ab_loop[0] is not None))
        self.key(player, Qt.Key_L)
        self.key(player, Qt.Key_L)
        self.assertTrue(support.pump(lambda: player.session.ab_loop == (None, None)))

    def test_image_keys_zoom_rotate_and_navigate(self):
        player = self.player()
        player.open_many([self.files / 'plain.png', self.files / 'alpha.png', self.files / 'plain.bmp'])
        self.assertTrue(support.pump(lambda: player._images.frame is not None))
        self.key(player, Qt.Key_Plus)
        self.assertEqual(player._images.mode, 'zoom')
        self.key(player, Qt.Key_0)
        self.assertEqual(player._images.mode, 'fit')
        self.key(player, Qt.Key_R)
        self.assertEqual(player._images._turns, 1)
        self.key(player, Qt.Key_Right)
        self.assertEqual(Path(player.source.path).name, 'alpha.png')
        self.assertEqual(player._images._turns, 0, 'rotation is per picture')
        self.key(player, Qt.Key_Left)
        self.assertEqual(Path(player.source.path).name, 'plain.png')
        self.key(player, Qt.Key_Left)                                   # first picture: no wrap
        self.assertEqual(Path(player.source.path).name, 'plain.png')

    def test_info_key_opens_a_popup_with_real_values(self):
        player = self.player()
        self.open(player, 'h264.mp4')
        support.pump(lambda: (player.session.props.get('video-params') or {}).get('w'))
        self.key(player, Qt.Key_I)
        menu = player._menu
        self.assertIsNotNone(menu)
        values = {row.text: row.detail for row in menu.rows if row.kind == 'info'}
        self.assertEqual(values['Archivo'], 'h264.mp4')
        self.assertEqual(values['Resolución'], '640 × 360')
        self.assertEqual(values['Renderizador'], 'Software')
        menu.close()


class MenuTests(PlayerCase):
    def test_every_menu_builds_for_every_kind(self):
        player = self.player()
        for name in ('h264.mp4', 'tone.mp3', 'plain.png'):
            self.open(player, name, paused=True)
            support.settle(.2)
            for show in (player.show_more_menu, player.show_speed_menu, player.show_subtitle_menu, player.show_audio_menu, player.show_info):
                show(player.bar.more)
                self.assertIsNotNone(player._menu, (name, show.__name__))
                self.assertGreater(len(player._menu.rows), 0)
                player._menu.close()
                self.assertIsNone(player._menu)

    def test_speed_menu_marks_the_current_speed_and_applies_a_choice(self):
        player = self.player()
        self.open(player, 'tone.wav')
        support.pump(lambda: player.session.state == 'playing')
        player.show_speed_menu(player.bar.speed)
        rows = [r for r in player._menu.rows if r.kind == 'item']
        self.assertEqual([r.text for r in rows if r.checked], ['1× · Normal'])
        chosen = next(r for r in rows if r.text == '2×')
        player._menu._activate(player._menu.rows.index(chosen))
        self.assertTrue(support.pump(lambda: player.session.speed == 2.0))
        self.assertEqual(player.bar.speed.text(), '2×')
        self.assertTrue(player.bar.speed.highlight)

    def test_host_actions_appear_in_the_more_menu(self):
        player, called = self.player(), []
        player.extra_actions.append(('Mi acción', lambda: called.append(1)))
        self.open(player, 'tone.mp3', paused=True)
        player.show_more_menu(player.bar.more)
        row = next(r for r in player._menu.rows if r.text == 'Mi acción')
        player._menu._activate(player._menu.rows.index(row))
        self.assertTrue(support.pump(lambda: called))


class CollectionTests(PlayerCase):
    def test_next_and_previous_walk_the_folder(self):
        player = self.player()
        self.open(player, 'tone.flac', browse='folder')
        self.assertTrue(support.pump(lambda: len(player.collection) > 3))
        first = player.source.name
        self.assertTrue(player.step_collection(1))
        self.assertNotEqual(player.source.name, first)
        self.assertTrue(player.step_collection(-1))
        self.assertEqual(player.source.name, first)

    def test_drop_loads_media_and_subtitles_separately(self):
        player, dropped = self.player(), []
        player.filesDropped.connect(dropped.append)
        self.open(player, 'h264.mp4', paused=True)
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(self.files / 'tone.mp3'))])
        event = QDropEvent(QPointF(10, 10), Qt.CopyAction, data, Qt.LeftButton, Qt.NoModifier)
        player.dropEvent(event)
        self.assertEqual(dropped, [[str(self.files / 'tone.mp3')]])


class ThemeTests(PlayerCase):
    def test_every_variant_paints_a_complete_player_without_errors(self):
        import os
        import theme_core
        import theme_tokens
        variants = [variant for spec in theme_core.styles().values() for variant in spec['variants']]
        self.assertTrue(variants)
        for variant in variants:
            with self.subTest(variant):
                os.environ['WYSUN_THEME'] = variant
                theme_core.invalidate()
                theme_tokens.refresh_widgets()
                player = self.player('embedded', size=(520, 400))
                self.open(player, 'cover.mp3', paused=True)
                support.settle(.3)
                image = player.window().grab().toImage()
                self.assertGreater(image.size().width(), 100)
                painted = {image.pixelColor(x, y).rgb() for x in range(0, image.width(), 23) for y in range(0, image.height(), 19)}
                self.assertGreater(len(painted), 4, 'the player drew something')
        os.environ.pop('WYSUN_THEME', None)
        theme_core.invalidate()
        theme_tokens.refresh_widgets()

    def test_a_live_theme_change_remeasures_the_controls(self):
        """Sizes derive from tokens: when a token changes, the next theme refresh makes every control measure itself again."""
        from wysun_media import host
        player = self.player('full')
        self.open(player, 'tone.mp3', paused=True)
        support.settle(.1)
        before = player.bar.play.sizeHint()
        base = host.get()
        host.install(host.Host(color=base.color, token=lambda name: {'icon_size': 30}.get(name, base.token(name)), font=base.font,
                               symbol=base.symbol, reduced_motion=base.reduced_motion, on_theme_changed=base.on_theme_changed))
        self.addCleanup(host.install, base)
        player._theme_changed()
        support.settle(.1)
        self.assertGreater(player.bar.play.sizeHint().width(), before.width())
        self.assertGreater(player.bar.height(), 0)


class FreedWindowTests(PlayerCase):
    def test_a_player_whose_window_was_freed_never_breaks_a_later_theme_change(self):
        import theme_tokens
        holder = QWidget()
        layout = QVBoxLayout(holder)
        player = MediaPlayer(mode='embedded', renderer='software')
        layout.addWidget(player)
        holder.show()
        player.shutdown()
        holder.close()
        holder.deleteLater()
        support.settle(.1)                         # Qt frees the C++ widgets; the Python wrapper (and its theme listener) lives on
        theme_tokens.refresh_widgets()             # must not raise, or the other windows would miss the new theme
        self.assertIsNotNone(player)


class TeardownTests(PlayerCase):
    def test_shutdown_is_idempotent_and_releases_the_core(self):
        player = self.player()
        self.open(player, 'h264.mp4')
        support.pump(lambda: player.session.state == 'playing')
        player.shutdown()
        player.shutdown()
        self.assertIsNone(player.session.core)


if __name__ == '__main__':
    unittest.main()

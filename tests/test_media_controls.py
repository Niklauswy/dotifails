"""The painted controls: sliders, buttons, popup menu, toast. Behaviour first; looks are covered by the theme tests."""
import unittest

import media_support as support

support.app()
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent  # noqa: E402
from PySide6.QtGui import QRegion  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402
from wysun_media import controls, host  # noqa: E402


def mouse(widget, x, kind=QEvent.MouseButtonPress, buttons=Qt.LeftButton):
    point = QPointF(x, widget.height() / 2)
    QApplication.sendEvent(widget, QMouseEvent(kind, point, widget.mapToGlobal(point), Qt.LeftButton, buttons, Qt.NoModifier))


def key(widget, code):
    QApplication.sendEvent(widget, QKeyEvent(QEvent.KeyPress, code, Qt.NoModifier))


class HudInkTests(unittest.TestCase):
    def with_colours(self, table):
        base = host.get()
        host.install(host.Host(color=lambda name, alpha=None: table[name], token=base.token, font=base.font, symbol=base.symbol,
                               reduced_motion=base.reduced_motion, on_theme_changed=base.on_theme_changed))
        self.addCleanup(host.install, base)

    def test_an_accent_that_cannot_be_seen_on_the_hud_falls_back_to_its_text_colour(self):
        from PySide6.QtGui import QColor
        self.with_colours({'hud': QColor('#14161c'), 'on_hud': QColor('#e8eaf0'), 'accent': QColor('#4a4870')})     # dark accent, dark hud
        self.assertEqual(controls.hud_ink('accent').name(), '#e8eaf0')

    def test_a_readable_accent_is_kept(self):
        from PySide6.QtGui import QColor
        self.with_colours({'hud': QColor('#14161c'), 'on_hud': QColor('#e8eaf0'), 'accent': QColor('#c6c2ee')})
        self.assertEqual(controls.hud_ink('accent').name(), '#c6c2ee')

    def test_every_theme_variant_gives_visible_progress(self):
        import theme_core
        from PySide6.QtGui import QColor
        for style, spec in theme_core.styles().items():
            for variant in spec['variants']:
                tokens = theme_core.resolve(style, variant)
                self.with_colours({name: QColor(value[:7]) for name, value in tokens.items() if isinstance(value, str) and value.startswith('#')})
                ink, hud = controls.hud_ink('accent'), QColor(tokens['hud'][:7])
                light, dark = sorted((controls._luminance(ink), controls._luminance(hud)), reverse=True)
                self.assertGreaterEqual((light + .05) / (dark + .05), 3.0, (style, variant))


class SeekBarTests(unittest.TestCase):
    def bar(self, duration=100):
        bar = controls.SeekBar()
        bar.resize(216, 28)
        bar.show()
        bar.set_duration(duration)
        self.addCleanup(bar.deleteLater)
        bar.scrubbed_to, bar.sought = [], []
        bar.scrubbed.connect(bar.scrubbed_to.append)
        bar.seekRequested.connect(bar.sought.append)
        return bar

    def inset(self, bar):
        return float(host.get().token('space_s'))

    def x_at(self, bar, fraction):
        inset = self.inset(bar)
        return inset + (bar.width() - 2 * inset) * fraction

    def test_click_anywhere_scrubs_then_commits_in_seconds(self):
        bar = self.bar()
        mouse(bar, self.x_at(bar, .75))
        self.assertAlmostEqual(bar.scrubbed_to[-1], 75, delta=.7)
        self.assertTrue(bar.dragging)
        mouse(bar, self.x_at(bar, .75), QEvent.MouseButtonRelease, Qt.NoButton)
        self.assertAlmostEqual(bar.sought[-1], 75, delta=.7)
        self.assertFalse(bar.dragging)

    def test_playback_does_not_fight_a_drag_but_resumes_after_it(self):
        bar = self.bar()
        mouse(bar, self.x_at(bar, .75))
        bar.set_position(10)
        self.assertAlmostEqual(bar.ratio, .75, delta=.01)
        mouse(bar, self.x_at(bar, .25), QEvent.MouseMove)
        mouse(bar, self.x_at(bar, .25), QEvent.MouseButtonRelease, Qt.NoButton)
        bar.set_position(10)
        self.assertAlmostEqual(bar.ratio, .1, delta=.001)

    def test_keys_step_and_jump_to_the_ends(self):
        bar = self.bar(30)
        bar.set_position(10)
        key(bar, Qt.Key_Right)
        self.assertAlmostEqual(bar.sought[-1], 10.3, delta=.05)
        key(bar, Qt.Key_End)
        self.assertEqual(bar.sought[-1], 30)
        key(bar, Qt.Key_Home)
        self.assertEqual(bar.sought[-1], 0)

    def test_wheel_seeks_and_is_clamped(self):
        bar = self.bar()
        bar.set_position(50)
        point = QPointF(50, 10)
        QApplication.sendEvent(bar, QWheelEvent(point, bar.mapToGlobal(point), QPoint(), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                                                Qt.NoScrollPhase, False))
        self.assertAlmostEqual(bar.sought[-1], 51, delta=.01)
        bar.set_position(99.9)
        QApplication.sendEvent(bar, QWheelEvent(point, bar.mapToGlobal(point), QPoint(), QPoint(0, 1200), Qt.NoButton, Qt.NoModifier,
                                                Qt.NoScrollPhase, False))
        self.assertEqual(bar.sought[-1], 100)

    def test_no_duration_means_a_disabled_bar_that_never_seeks(self):
        bar = self.bar(0)
        self.assertFalse(bar.isEnabled())
        mouse(bar, 100)
        self.assertEqual(bar.sought, [])

    def test_chapters_cut_the_track_and_loop_ends_are_remembered(self):
        bar = self.bar(100)
        self.assertEqual(bar.segments(), [(0.0, 1.0)])
        bar.set_chapters([{'time': 0, 'title': 'Intro'}, {'time': 25, 'title': 'A'}, {'time': 75, 'title': 'B'}])
        self.assertEqual(bar.segments(), [(0.0, .25), (.25, .75), (.75, 1.0)])
        bar.set_chapters([{'time': 0}, {'time': 0}, {'time': 500}])                  # hostile or odd chapter lists never break painting
        self.assertEqual(bar.segments(), [(0.0, 1.0)])
        bar.set_loop(10, 40)
        self.assertEqual(bar.loop, (10, 40))
        bar.grab()

    def test_clock_formats(self):
        self.assertEqual((controls.clock(65), controls.clock(3725), controls.clock(-3), controls.clock(None)), ('1:05', '1:02:05', '0:00', '0:00'))


class VolumeTests(unittest.TestCase):
    def test_the_handle_crosses_full_scale_at_two_thirds(self):
        slider = controls.VolumeSlider()
        slider.resize(120, 28)
        slider.show()
        self.addCleanup(slider.deleteLater)
        seen = []
        slider.volumeChanged.connect(seen.append)
        slider.set_volume(100)
        self.assertAlmostEqual(slider.ratio, 2 / 3, places=3)
        slider.set_volume(500)
        self.assertEqual(slider.ratio, 1.0)
        key(slider, Qt.Key_Home)
        self.assertEqual(seen[-1], 0)
        key(slider, Qt.Key_End)
        self.assertEqual(seen[-1], 150)


class ButtonTests(unittest.TestCase):
    def test_buttons_name_themselves_for_assistive_technology(self):
        button = controls.ControlButton('play_arrow', 'Reproducir · Espacio')
        self.addCleanup(button.deleteLater)
        self.assertEqual(button.accessibleName(), 'Reproducir · Espacio')
        self.assertEqual(button.toolTip(), 'Reproducir · Espacio')
        button.set_label('Pausar')
        self.assertEqual(button.accessibleName(), 'Pausar')

    def test_size_follows_the_icon_size_token_and_play_is_bigger(self):
        small, play = controls.ControlButton('add', 'x', scale=1.8), controls.PlayButton('y')
        self.addCleanup(small.deleteLater)
        self.addCleanup(play.deleteLater)
        icon = float(host.get().token('icon_size'))
        self.assertEqual(small.sizeHint().width(), round(icon * 1.8))
        self.assertEqual(play.sizeHint().width(), round(icon * 3))

    def test_the_play_button_settles_from_a_circle_into_a_rounded_square(self):
        play = controls.PlayButton('y')
        play.resize(60, 60)
        self.addCleanup(play.deleteLater)
        corner = QPointF(6, 6)                              # inside a rounded square's corner, outside a circle
        self.assertFalse(play._outline(QRectF(play.rect())).contains(corner), 'paused: a circle')
        play.set_playing(True)
        self.assertTrue(support.pump(lambda: play.morph.value == 1.0, 2))
        self.assertTrue(play._outline(QRectF(play.rect())).contains(corner), 'playing: a rounded square')
        self.assertEqual(play.symbol, 'pause')
        play.set_playing(False)
        self.assertTrue(support.pump(lambda: play.morph.value == 0.0, 2))
        self.assertEqual(play.symbol, 'play_arrow')
        self.assertFalse(play._outline(QRectF(play.rect())).contains(corner))

    def test_pill_highlights_a_non_default_value(self):
        pill = controls.Pill('1×', 'Velocidad')
        self.addCleanup(pill.deleteLater)
        narrow = pill.sizeHint().width()
        pill.setText('0.25×')
        self.assertGreater(pill.sizeHint().width(), narrow)
        pill.highlight = True
        pill.grab()


class PopupTests(unittest.TestCase):
    def menu(self):
        parent = QWidget()
        parent.show()
        self.addCleanup(parent.deleteLater)
        self.called = []
        menu = controls.PopupMenu(parent)
        menu.add_header('Cabecera').add_item('Uno', lambda: self.called.append(1), checked=True).add_separator()
        menu.add_item('Dos', lambda: self.called.append(2), detail='x').add_item('Apagado', lambda: self.called.append(3), enabled=False)
        menu.add_info('Clave', 'valor')
        menu._measure()
        self.addCleanup(menu.deleteLater)
        return menu

    def test_arrow_keys_skip_headers_info_and_disabled_rows(self):
        menu = self.menu()
        key(menu, Qt.Key_Down)
        self.assertEqual(menu.rows[menu._current].text, 'Uno')
        key(menu, Qt.Key_Down)
        self.assertEqual(menu.rows[menu._current].text, 'Dos')
        key(menu, Qt.Key_Down)
        self.assertEqual(menu.rows[menu._current].text, 'Uno', 'wraps around, never landing on a disabled row')
        key(menu, Qt.Key_Up)
        self.assertEqual(menu.rows[menu._current].text, 'Dos')

    def test_activating_closes_and_runs_once_after_the_menu_is_gone(self):
        menu = self.menu()
        dismissed = []
        menu.dismissed.connect(lambda: dismissed.append(True))
        menu.show()
        menu._current = 1
        key(menu, Qt.Key_Return)
        self.assertFalse(menu.isVisible())
        self.assertEqual(dismissed, [True])
        self.assertTrue(support.pump(lambda: self.called == [1], 2))
        key(menu, Qt.Key_Return)                                           # a closed menu does nothing more
        support.settle(.05)
        self.assertEqual(self.called, [1])

    def test_disabled_rows_cannot_be_activated_with_the_mouse(self):
        menu = self.menu()
        menu.show()
        box = menu._layout()[menu.rows.index(next(r for r in menu.rows if r.text == 'Apagado'))]
        self.assertEqual(menu._row_at(box.center()), -1)
        self.assertGreaterEqual(menu._row_at(menu._layout()[1].center()), 0)

    def test_it_is_wide_enough_for_its_longest_row_and_escape_closes(self):
        menu = self.menu()
        self.assertGreaterEqual(menu.width(), int(controls.unit() * 11))
        menu.show()
        key(menu, Qt.Key_Escape)
        self.assertFalse(menu.isVisible())


class ToastTests(unittest.TestCase):
    def test_it_says_something_and_goes_away(self):
        parent = QWidget()
        parent.resize(400, 200)
        parent.show()
        self.addCleanup(parent.deleteLater)
        toast = controls.Toast(parent)
        toast.say('Volumen 80 %', 'volume_up')
        self.assertTrue(toast.isVisible())
        self.assertEqual(toast.text, 'Volumen 80 %')
        self.assertAlmostEqual(toast.x() + toast.width() / 2, parent.width() / 2, delta=2)
        toast._timer.setInterval(20)
        toast.say('Otro')
        toast._timer.setInterval(20)
        self.assertTrue(support.pump(lambda: not toast.isVisible(), 3))


class RoundingTests(unittest.TestCase):
    def test_square_corners_paint_nothing_and_rounded_ones_paint_only_the_slivers(self):
        from PySide6.QtGui import QImage
        widget = controls.Rounding()
        widget.resize(100, 100)
        self.addCleanup(widget.deleteLater)
        image = QImage(100, 100, QImage.Format_ARGB32_Premultiplied)
        widget.set_corner('none')
        image.fill(0)
        widget.render(image, QPoint(), QRegion(), QWidget.DrawChildren)     # no window background underneath
        self.assertEqual(image.pixelColor(1, 1).alpha(), 0)
        widget.set_corner('xl', 'surface')
        image.fill(0)
        widget.render(image, QPoint(), QRegion(), QWidget.DrawChildren)
        self.assertGreater(image.pixelColor(1, 1).alpha(), 0)
        self.assertEqual(image.pixelColor(50, 50).alpha(), 0)


if __name__ == '__main__':
    unittest.main()

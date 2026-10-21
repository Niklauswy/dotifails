"""The frozen selection overlays must always have a way out (offscreen, no real display)."""
import os
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QDialog
from wybieshot.ui.selection import SelectionGroup, SelectionGuard, SelectionOverlay


def overlay():
    image = QImage(200, 100, QImage.Format_ARGB32)
    image.fill(QColor('black'))
    return SelectionOverlay(image, QRect(0, 0, 200, 100))


class SelectionGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.overlays = [overlay(), overlay()]
        for item in self.overlays:
            item.show()
        self.cancelled = []
        self.guard = SelectionGuard(self.overlays, lambda: self.cancelled.append(True))
        self.guard.timer.stop()

    def tearDown(self):
        self.guard.stop()
        for item in self.overlays:
            item.close()
            item.deleteLater()
        self.app.processEvents()

    def ticks(self, count):
        for _ in range(count):
            self.guard.check()

    def test_focus_lost_on_every_overlay_cancels_exactly_once(self):
        with patch.object(QApplication, 'activeWindow', return_value=None):
            self.ticks(SelectionGuard.lost_limit - 1)
            self.assertEqual(self.cancelled, [])
            self.ticks(5)
        self.assertEqual(self.cancelled, [True])

    def test_focus_on_any_overlay_resets_the_counter(self):
        with patch.object(QApplication, 'activeWindow', return_value=None):
            self.ticks(SelectionGuard.lost_limit - 1)
        with patch.object(QApplication, 'activeWindow', return_value=self.overlays[1]):
            self.ticks(1)
        with patch.object(QApplication, 'activeWindow', return_value=None):
            self.ticks(SelectionGuard.lost_limit - 1)
        self.assertEqual(self.cancelled, [])

    def test_dialog_owned_by_the_overlay_pauses_the_guard(self):
        dialog = QDialog(self.overlays[0])
        dialog.show()
        with patch.object(QApplication, 'activeWindow', return_value=None):
            self.ticks(SelectionGuard.lost_limit * 2)
        dialog.close()
        self.assertEqual(self.cancelled, [])

    def test_annotation_in_progress_is_never_discarded(self):
        self.overlays[0].document = object()
        with patch.object(QApplication, 'activeWindow', return_value=None):
            self.ticks(SelectionGuard.lost_limit * 2)
        self.assertEqual(self.cancelled, [])

    def test_monitor_topology_change_cancels(self):
        self.guard.topology_changed()
        self.guard.topology_changed()
        self.assertEqual(self.cancelled, [True])

    def test_hidden_overlays_stop_the_guard_without_cancelling(self):
        for item in self.overlays:
            item.hide()
        with patch.object(QApplication, 'activeWindow', return_value=None):
            self.ticks(SelectionGuard.lost_limit * 2)
        self.assertEqual(self.cancelled, [])

    def test_stopped_guard_ignores_pending_ticks_and_topology_signals(self):
        self.guard.stop()
        self.guard.topology_changed()
        self.guard.fire()
        self.ticks(10)
        self.assertEqual(self.cancelled, [])

    def test_screen_geometry_signal_triggers_recovery(self):
        self.app.primaryScreen().geometryChanged.emit(QRect(0, 0, 400, 300))
        self.assertEqual(self.cancelled, [True])
        self.assertTrue(self.guard.stopped)

    def test_unrelated_active_library_does_not_keep_selection_alive(self):
        from PySide6.QtWidgets import QWidget
        library = QWidget()
        try:
            with patch.object(QApplication, 'activeWindow', return_value=library):
                self.ticks(SelectionGuard.lost_limit)
            self.assertEqual(self.cancelled, [True])
        finally:library.deleteLater()

    def test_group_hide_releases_guard_immediately(self):
        group = SelectionGroup(self.overlays)
        group.present()
        group.hide()
        self.assertTrue(group._guard.stopped)
        self.assertFalse(group._guard.timer.isActive())

    def test_keyboard_accept_translates_secondary_output_pixels(self):
        from PySide6.QtCore import QPoint, Qt, QEvent
        from PySide6.QtGui import QKeyEvent
        image = QImage(400, 200, QImage.Format_ARGB32)
        image.fill(QColor('black'))
        item = SelectionOverlay(image, QRect(-200, -100, 200, 100), image_origin=QPoint(800, 300))
        received = []
        item.selected.connect(received.append)
        item.selection = QRect(10, 20, 60, 30)
        self.app.sendEvent(item, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
        self.assertEqual(received, [QRect(820, 340, 120, 60)])
        item.deleteLater()

    def test_group_cancel_comes_from_a_single_guard(self):
        group = SelectionGroup(self.overlays)
        received = []
        self.overlays[0].recovery_requested.connect(lambda: received.append(True))
        group.present()
        self.assertIsNotNone(group._guard)
        self.assertFalse(any(getattr(item, '_guard', None) for item in self.overlays))
        group._guard.timer.stop()
        group._guard.topology_changed()
        self.assertEqual(received, [True])
        group._guard.stop()


if __name__ == '__main__':
    unittest.main()

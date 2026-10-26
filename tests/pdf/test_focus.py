"""A clock must never invent study time after suspension or duplicate the owner."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from PySide6.QtWidgets import QApplication
from wysun_pdf.focus import FocusClock, FocusController


class FocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pause_resume_excludes_paused_time(self):
        now = [0.]
        clock = FocusClock(lambda: now[0], lambda: now[0])
        clock.start(1)
        now[0] = 3
        clock.pause()
        self.assertEqual(clock.remaining, 57)
        now[0] = 90
        clock.resume()
        now[0] = 92
        clock.tick()
        self.assertEqual(clock.remaining, 55)

    def test_suspend_and_delayed_ticks_pause_without_credit(self):
        mono, wall = [0.], [0.]
        clock = FocusClock(lambda: mono[0], lambda: wall[0])
        clock.start(1)
        mono[0], wall[0] = 1., 3601.
        clock.tick()
        self.assertEqual((clock.state, clock.remaining), ('paused', 60))
        clock.resume()
        mono[0], wall[0] = 60., 3660.
        clock.tick()
        self.assertEqual((clock.state, clock.remaining), ('paused', 60))

    def test_completion_and_restore_are_explicit(self):
        now = [0.]
        clock = FocusClock(lambda: now[0], lambda: now[0])
        clock.start(1)
        snapshot = clock.snapshot()
        restored = FocusClock()
        restored.restore(snapshot)
        self.assertEqual(restored.state, 'paused')
        for second in range(1, 61):
            now[0] = second
            clock.tick()
        self.assertEqual((clock.state, clock.remaining), ('finished', 0))
        restored.restore({'remaining': float('nan'), 'duration': 60})
        self.assertEqual(restored.state, 'paused')

    def test_one_owner_and_last_window_pauses(self):
        with tempfile.TemporaryDirectory() as home:
            runtime = Path(home) / 'runtime'
            runtime.mkdir(mode=0o700)
            with mock.patch.dict(os.environ, XDG_RUNTIME_DIR=str(runtime), XDG_STATE_HOME=home):
                one, two = FocusController(), FocusController()
                try:
                    one.start(25, 'Comprender el argumento')
                    messages = []
                    two.message.connect(messages.append)
                    two.start()
                    self.assertEqual(two.clock.state, 'idle')
                    self.assertTrue(messages)
                    window = object()
                    one.windows.add(window)
                    one.detach(window)
                    self.assertEqual(one.clock.state, 'paused')
                    self.assertIsNone(one.owner)
                    restored = FocusController()
                    self.assertEqual(restored.clock.state, 'paused')
                    self.assertEqual(restored.goal, 'Comprender el argumento')
                    restored.deleteLater()
                    two.start()
                    self.assertEqual(two.clock.state, 'running')
                finally:
                    one.finish()
                    two.finish()
                    one.deleteLater()
                    two.deleteLater()

    def test_four_blocks_long_break_and_history_survive_restart(self):
        with tempfile.TemporaryDirectory() as home:
            runtime = Path(home) / 'runtime'
            runtime.mkdir(mode=0o700)
            with mock.patch.dict(os.environ, XDG_RUNTIME_DIR=str(runtime), XDG_STATE_HOME=home):
                controller = FocusController()
                controller.minutes, controller.break_minutes, controller.long_break_minutes = 2, 3, 12
                now = [0.]
                controller.clock = FocusClock(lambda: now[0], lambda: now[0])
                try:
                    for block in range(4):
                        controller.start(1, 'Synthetic goal')
                        for second in range(60):
                            now[0] += 1
                            controller.tick()
                    self.assertEqual(controller.next_break, 12)
                    self.assertEqual(len(controller.history), 4)
                    controller.finish()
                    restored = FocusController()
                    self.assertEqual(restored.completed_blocks, 4)
                    self.assertEqual(restored.long_break_minutes, 12)
                    self.assertEqual(restored.minutes, 2)
                    self.assertEqual(len(restored.history), 4)
                    restored.deleteLater()
                finally:
                    controller.finish()
                    controller.deleteLater()

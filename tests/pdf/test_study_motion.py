"""Transitions release their snapshots and obey reduced motion, even on interruption."""
import os
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/python'))
from PySide6.QtWidgets import QApplication, QWidget, QStackedLayout, QLabel
from PySide6.QtCore import QAbstractAnimation
from wysun_pdf.study_ui import navigate, ReadingArt


class StudyMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.host = QWidget()
        self.stack = QStackedLayout(self.host)
        self.pages = [QLabel('Library'), QLabel('Reader')]
        for page in self.pages:
            self.stack.addWidget(page)
        self.host.resize(720, 480)
        self.host.show()
        self.app.processEvents()
        self.addCleanup(self.host.close)

    def test_reduced_motion_does_not_allocate_snapshot(self):
        with mock.patch.dict(os.environ, WYSUN_REDUCED_MOTION='1'):
            navigate(self.stack, self.pages[1])
        self.assertIs(self.stack.currentWidget(), self.pages[1])
        self.assertIsNone(getattr(self.host, '_study_transition', None))

    def test_interrupted_navigation_releases_snapshot(self):
        with mock.patch('wysun_pdf.study_ui.reduced_motion', return_value=False):
            navigate(self.stack, self.pages[1])
            self.app.processEvents()
            group, overlay = self.host._study_transition
            self.assertEqual(overlay.pixmap().width(), self.pages[0].width())
            navigate(self.stack, self.pages[0])
            self.assertIsNot(self.host._study_transition[1], overlay)
            end = time.monotonic() + 2
            while self.host._study_transition and time.monotonic() < end:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(self.host._study_transition)
            self.assertIs(self.stack.currentWidget(), self.pages[0])

    def test_decorative_motion_has_no_idle_timer(self):
        art = ReadingArt()
        with mock.patch('wysun_pdf.study_ui.reduced_motion', return_value=True):
            art.animate(1.)
        self.assertEqual(art.phase, 1.)
        self.assertEqual(art.motion.state(), QAbstractAnimation.Stopped)

"""Presentation contracts independent of device discovery and media processes."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QAbstractAnimation,QEvent,QPointF,Qt
from PySide6.QtGui import QEnterEvent,QKeyEvent
from PySide6.QtWidgets import QApplication
from loomrec.ui.tokens import TOKENS,apply_theme
from loomrec.ui.motion import reduced_motion
from loomrec.ui.components import SoftButton


def luminance(color):
    values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))


class VisualContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def test_readable_text_and_focus_contrast(self):
        for foreground in ('text','muted'):
            for background in ('canvas','surface','well'):
                values=sorted([luminance(TOKENS[foreground]),luminance(TOKENS[background])])
                self.assertGreaterEqual((values[1]+.05)/(values[0]+.05),4.5,(foreground,background))
        for background in ('canvas','surface','well'):
            values=sorted([luminance(TOKENS['blue']),luminance(TOKENS[background])])
            self.assertGreaterEqual((values[1]+.05)/(values[0]+.05),3,background)

    def test_reduced_motion_environment_and_local_preference(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d,'LOOMREC_REDUCED_MOTION':'','ORBIT_REDUCED_MOTION':''}):
            for key in ('LOOMREC_REDUCED_MOTION','ORBIT_REDUCED_MOTION'):
                with patch.dict(os.environ,{key:'true'}):self.assertTrue(reduced_motion(),key)
            path=Path(d)/'loomrec/appearance.json';path.parent.mkdir();path.write_text(json.dumps({'reduced_motion':True}))
            self.assertTrue(reduced_motion())

    def test_reduced_motion_does_not_start_hover_animation(self):
        with patch.dict(os.environ,{'LOOMREC_REDUCED_MOTION':'1'}):
            button=SoftButton('Grabar')
            button.enterEvent(QEnterEvent(QPointF(2,2),QPointF(2,2),QPointF(2,2)))
            self.assertEqual(button.anim.state(),QAbstractAnimation.Stopped)
            button.leaveEvent(QEvent(QEvent.Leave))
            self.assertEqual(button.anim.state(),QAbstractAnimation.Stopped)
            button.deleteLater()

    def press_space(self,button):
        for event in (QEvent.KeyPress,QEvent.KeyRelease):
            self.app.sendEvent(button,QKeyEvent(event,Qt.Key_Space,Qt.NoModifier))

    def test_button_keyboard_activation_and_disabled_guard(self):
        button=SoftButton('Grabar');calls=[];button.clicked.connect(lambda:calls.append(True));button.show();button.setFocus();self.app.processEvents()
        self.assertTrue(button.focusPolicy() & Qt.TabFocus)
        self.assertTrue(button.accessibleName())
        self.press_space(button);self.assertEqual(len(calls),1)
        button.setEnabled(False);self.press_space(button);self.assertEqual(len(calls),1)
        button.close();button.deleteLater();self.app.processEvents()




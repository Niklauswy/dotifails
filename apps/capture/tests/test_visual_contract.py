"""Presentation contracts independent of device discovery and media processes."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from loomrec.ui.tokens import TOKENS,apply_theme
from loomrec.ui.motion import reduced_motion


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




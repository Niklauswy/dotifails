"""Recorder and Screenshot follow the shared theme selection live (synthetic data only)."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import tempfile
import time
import unittest
from pathlib import Path

CONFIG=tempfile.TemporaryDirectory()
os.environ['XDG_CONFIG_HOME']=CONFIG.name
for name in ('ORBIT_THEME','WYSUN_THEME'):os.environ.pop(name,None)

from PySide6.QtWidgets import QApplication
from loomrec.ui import theme_core
from loomrec.ui.tokens import apply_theme,color,tokens,refresh
from wybieshot.document import Document
from wybieshot.storage import Storage
from wybieshot.ui.main import Window
from PySide6.QtGui import QImage,QColor

VARIANTS=[('space-black','space-black'),('space-black','tokyo'),('space-black','severance'),('fluent','light'),('fluent','dark')]


def write(style,variant):
    path=Path(CONFIG.name)/'orbit/theme.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'style':style,'variant':variant}))


def settle(app,seconds=.4):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.01)


class CaptureTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        write('fluent','light');Path(os.environ['XDG_STATE_HOME'],'wysun').mkdir(parents=True,exist_ok=True);cls.app=QApplication.instance() or QApplication([]);apply_theme(cls.app)
    def test_selection_in_file_changes_palette_and_tokens_live(self):
        for style,variant in VARIANTS:
            write(style,variant);settle(self.app)
            expected=theme_core.resolve(style,variant)
            self.assertEqual(color('canvas').name().upper(),expected['canvas'][:7].upper(),(style,variant))
            self.assertEqual(self.app.palette().window().color().name().upper(),expected['canvas'][:7].upper(),(style,variant))
    def test_fluent_light_keeps_recorder_pearl_values(self):
        write('fluent','light');settle(self.app)
        self.assertEqual(color('accent').name().upper(),'#2165D5');self.assertEqual(tokens()['radius_m'],12);self.assertEqual(tokens()['motion_fast'],150)
    def test_dynamic_scheme_recolours_capture_tokens_live(self):
        from loomrec.ui import theme_core
        write('fluent','dark');settle(self.app)
        path=theme_core.scheme_path()
        first={'name':'dynamic','flavour':'default','mode':'dark','variant':'tonalspot','wallpaper_hash':'0'*64,
               'colours':{'primary':'2864D8','primaryDim':'2455B8','onPrimary':'FFFFFF','surface':'171A20','onSurface':'F3F4F8',
                          'surfaceContainerLowest':'101216','surfaceContainerHigh':'242830','outline':'788091','onSurfaceVariant':'B8BFCD',
                          'success':'96D0A3','error':'F27B82','tertiary':'E9AF67'}}
        second={**first,'wallpaper_hash':'1'*64,'colours':{**first['colours'],'primary':'A24670','primaryDim':'8D3B61'}}
        try:
            theme_core.write_scheme(first);settle(self.app)
            self.assertEqual(color('accent').name().upper(),'#2864D8')
            theme_core.write_scheme(second);settle(self.app)
            self.assertEqual(color('accent').name().upper(),'#A24670')
            self.assertEqual(color('blue').name().upper(),'#A24670')
        finally:
            path.unlink(missing_ok=True);theme_core.invalidate();settle(self.app)
    def test_invalid_variant_falls_back_to_style_default(self):
        write('fluent','tokyo');settle(self.app)
        self.assertEqual(theme_core.selection(),('fluent','light'))
        write('space-black','nope');settle(self.app)
        self.assertEqual(theme_core.selection(),('space-black','space-black'))
    def test_screenshot_window_restyles_in_every_variant(self):
        temp=tempfile.TemporaryDirectory();storage=Storage(Path(temp.name)/'library');storage.set_output(Path(temp.name)/'out')
        window=Window(storage);image=QImage(320,180,QImage.Format_ARGB32);image.fill(QColor('#F3F6FB'));window.set_document(Document(image,'Fixture'))
        window.show();seen=set()
        try:
            for style,variant in VARIANTS:
                write(style,variant);settle(self.app)
                grabbed=window.grab().toImage();seen.add(grabbed.pixelColor(2,grabbed.height()//2).name())
                window.notice('Error de prueba',True)
                self.assertIn(color('danger').name().lower(),window.statusBar().styleSheet().lower())
            self.assertGreaterEqual(len(seen),4,'window must look different across variants')
        finally:
            window._closing=True;window.thumbnail_timer.stop();window.quick.close();window.close();window.deleteLater();temp.cleanup()


if __name__=='__main__':unittest.main()

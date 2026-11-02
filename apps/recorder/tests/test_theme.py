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
os.environ.pop('WYSUN_THEME',None)

from PySide6.QtWidgets import QApplication
from wysun_core import theme
from wysun_core.qt_theme import apply_palette,apply_style,color,tokens,watch_theme
from PySide6.QtGui import QImage,QColor

MODES=('light','dark')


def write(mode):
    path=Path(CONFIG.name)/'wysun/theme.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'mode':mode}))


def settle(app,seconds=.4):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.processEvents();time.sleep(.01)


class CaptureTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        write('light');Path(os.environ['XDG_STATE_HOME'],'wysun').mkdir(parents=True,exist_ok=True);cls.app=QApplication.instance() or QApplication([]);cls.app.setStyle('Fusion');apply_palette(cls.app);apply_style(cls.app,'');watch_theme()
    def test_selection_in_file_changes_palette_and_tokens_live(self):
        for mode in MODES:
            write(mode);settle(self.app)
            expected=theme.resolve(mode)
            self.assertEqual(color('canvas').name().upper(),expected['canvas'][:7].upper(),mode)
            self.assertEqual(self.app.palette().window().color().name().upper(),expected['canvas'][:7].upper(),mode)
    def test_light_palette_is_the_opaque_pearl_one(self):
        write('light');settle(self.app)
        light=theme.resolve('light')
        self.assertEqual((tokens()['material'],tokens()['translucent']),('pearl',False))
        self.assertEqual(color('canvas').name().upper(),light['canvas'][:7].upper());self.assertEqual(tokens()['rounding.medium'],12);self.assertEqual(tokens()['anim.durations.expressiveFastEffects'],150)
    def test_dynamic_scheme_recolours_capture_tokens_live(self):
        write('dark');settle(self.app)
        path=theme.scheme_path()
        first={'name':'dynamic','flavour':'default','mode':'dark','variant':'tonalspot','wallpaper_hash':'0'*64,
               'colours':{'primary':'2864D8','primaryDim':'2455B8','onPrimary':'FFFFFF','surface':'171A20','onSurface':'F3F4F8',
                          'surfaceContainerLowest':'101216','surfaceContainerHigh':'242830','outline':'788091','onSurfaceVariant':'B8BFCD',
                          'success':'96D0A3','error':'F27B82','tertiary':'E9AF67'}}
        second={**first,'wallpaper_hash':'1'*64,'colours':{**first['colours'],'primary':'A24670','primaryDim':'8D3B61'}}
        try:
            theme.write_scheme(first);settle(self.app)
            self.assertEqual(color('accent').name().upper(),'#2864D8')
            theme.write_scheme(second);settle(self.app)
            self.assertEqual(color('accent').name().upper(),'#A24670')
        finally:
            path.unlink(missing_ok=True);theme.invalidate();settle(self.app)
    def test_auto_and_an_old_file_use_the_default_palette_without_a_scheme(self):
        path=Path(CONFIG.name)/'wysun/theme.json'
        for text in ('{"mode":"auto"}',json.dumps({'style':'fluent','variant':'tokyo'})):
            path.write_text(text);settle(self.app)
            self.assertEqual(theme.active_mode(),'dark','no scheme yet: the default palette')
        self.assertEqual(path.read_text(),json.dumps({'style':'fluent','variant':'tokyo'}),'reading never rewrites the file')
if __name__=='__main__':unittest.main()

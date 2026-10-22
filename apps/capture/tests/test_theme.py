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
    def test_material_resources_and_live_navigation_geometry(self):
        from loomrec.ui.material import load_fonts, SYMBOLS, symbol_pixmap, Navigation, Workspace, metric
        from PySide6.QtWidgets import QWidget
        self.assertTrue(all(identifier >= 0 for identifier in load_fonts()))
        for name in SYMBOLS:
            self.assertIsNotNone(symbol_pixmap(name, color('text'), 24), name)
        activated=[]
        nav=Navigation('Fixture', [('Biblioteca','library',lambda: activated.append('library'))])
        page=Workspace(nav,QWidget());page.resize(1100,650);page.show()
        try:
            for style,variant in VARIANTS:
                write(style,variant);settle(self.app)
                self.assertEqual(page.layout().contentsMargins().left(),metric('space_m'))
                nav.buttons[0][0].click()
                self.assertFalse(page.grab().isNull())
            self.assertEqual(activated,['library']*len(VARIANTS))
        finally:
            page.close();page.deleteLater()
    def test_invalid_variant_falls_back_to_style_default(self):
        write('fluent','tokyo');settle(self.app)
        self.assertEqual(theme_core.selection(),('fluent','light'))
        write('space-black','nope');settle(self.app)
        self.assertEqual(theme_core.selection(),('space-black','space-black'))
if __name__=='__main__':unittest.main()

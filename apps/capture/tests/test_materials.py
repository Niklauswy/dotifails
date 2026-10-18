"""Opt-in material and coherent native icon contracts; no display captures."""
import os,tempfile,json,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout
from PySide6.QtGui import QIcon
from loomrec.ui.materials import apply_material,backdrop_available
from loomrec.ui.components import SoftButton
from loomrec.ui.icons import icon

class MaterialTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_opaque_fallback_and_invalid_surface(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d}):
   w=QWidget();binding=apply_material(w,kind='popup');self.assertFalse(binding.layer.acrylic);self.assertEqual(w.property('materialMode'),'matte')
   self.assertIs(apply_material(w,kind='popup'),binding)
   with self.assertRaises(ValueError):apply_material(QWidget(),kind='selection')
   w.deleteLater();self.app.processEvents()
 def test_acrylic_requires_both_verification_and_live_compositor(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d}):
   p=Path(d)/'loomrec/materials.json';p.parent.mkdir();p.write_text(json.dumps({'backdrop_blur':True}))
   with patch('loomrec.ui.materials._x11_property',return_value=False):self.assertFalse(backdrop_available())
   with patch('loomrec.ui.materials._x11_property',return_value=True):
    self.assertTrue(backdrop_available());p.write_text(json.dumps({'backdrop_blur':True,'transparency':False}));self.assertFalse(backdrop_available())
 def test_layer_tracks_panel_and_does_not_intercept_input(self):
  from PySide6.QtCore import Qt
  w=QWidget();panel=QWidget(w);panel.resize(260,90);binding=apply_material(w,panel,kind='quick');w.show();self.app.processEvents()
  panel.resize(300,110);self.app.processEvents();self.assertEqual(binding.layer.size(),panel.size());self.assertTrue(binding.layer.testAttribute(Qt.WA_TransparentForMouseEvents));w.close();w.deleteLater()
 def test_icons_and_drawn_dropdown_preserve_callbacks(self):
  for name in ['record','play','pause','stop','close','screen','camera','mic','sound','rewind','refresh','settings','chevron']:
   glyph=icon(name);self.assertFalse(glyph.pixmap(20,20).isNull());self.assertFalse(glyph.pixmap(20,20,QIcon.Disabled).isNull())
  b=SoftButton('Pantalla ⌄','screen');self.assertEqual(b.text(),'Pantalla');self.assertTrue(b.property('dropdown'))
  calls=[];b.clicked.connect(lambda:calls.append(1));b.click();self.assertEqual(calls,[1]);b.setText('Región ⌄');self.assertTrue(b.property('dropdown'));b.deleteLater()

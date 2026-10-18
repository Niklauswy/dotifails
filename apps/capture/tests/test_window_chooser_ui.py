import os,tempfile,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from loomrec.ui.main import Window
from loomrec.ui.quick import WindowChooser
from loomrec.library import Library
class WindowChooserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'XDG_STATE_HOME':self.tmp.name,'XDG_CONFIG_HOME':self.tmp.name});self.env.start();self.owner=Window(Library(self.tmp.name),False);self.owner.timer.stop();self.pending=[];self.owner.task=lambda fn,cb:self.pending.append((fn,cb));self.chooser=WindowChooser(self.owner)
  self.entries=[dict(id=hex(900000+i),title='Título muy largo '+str(i)*80,app='Aplicación de prueba',desktop=i%3,hidden=False) for i in range(20)]
 def tearDown(self):self.chooser.selecting=False;self.chooser.reject();self.owner.close();self.owner.deleteLater();self.app.processEvents();self.env.stop();self.tmp.cleanup()
 def complete(self,entries=None):self.pending.pop(0)[1]((self.entries if entries is None else entries,None));self.app.processEvents()
 def test_visible_lifecycle_no_overlap_and_late_result_ignored(self):
  c=self.chooser;self.assertFalse(self.pending);c.show();self.assertEqual(len(self.pending),1);self.assertEqual(c.refresh_timer.interval(),5000)
  c.refresh();c.refresh_timer.timeout.emit();self.assertEqual(len(self.pending),1)
  c.reject();self.complete();self.assertFalse(c.refresh_timer.isActive());self.assertEqual(c.items.count(),0);c.refresh();self.assertFalse(self.pending)
 def test_refresh_preserves_xid_scroll_focus_and_reports_disappearance(self):
  c=self.chooser;c.show();self.complete();c.items.setCurrentRow(10);c.items.setFocus();c.items.verticalScrollBar().setValue(240);self.app.processEvents();scroll=c.items.verticalScrollBar().value()
  xid=c.items.currentItem().data(Qt.UserRole)['id'];c.refresh();self.complete(list(reversed(self.entries)))
  self.assertEqual(c.items.currentItem().data(Qt.UserRole)['id'],xid);self.assertEqual(c.items.verticalScrollBar().value(),scroll);self.assertTrue(c.items.hasFocus());self.assertEqual(c.items.horizontalScrollBar().maximum(),0)
  c.refresh();self.complete([e for e in self.entries if e['id']!=xid]);self.assertFalse(c.choose.isEnabled());self.assertIn('ya no está disponible',c.status.text())
 def test_empty_and_async_error_states(self):
  c=self.chooser;c.show();self.complete([]);self.assertTrue(c.empty.isVisible());self.assertFalse(c.choose.isEnabled())
  c.refresh();self.pending.pop(0)[1](([],'fixture failure'));self.assertIn('reintentará',c.status.text());self.assertFalse(c.refresh_busy)

 def test_enter_activates_selected_window_and_hides_before_validation(self):
  from PySide6.QtGui import QKeyEvent
  from PySide6.QtCore import QEvent
  c=self.chooser;c.show();self.complete();c.items.setCurrentRow(0);c.items.setFocus()
  self.app.sendEvent(c.items,QKeyEvent(QEvent.KeyPress,Qt.Key_Return,Qt.NoModifier))
  self.assertTrue(c.selecting);self.assertFalse(c.isVisible());self.assertEqual(len(self.pending),1)

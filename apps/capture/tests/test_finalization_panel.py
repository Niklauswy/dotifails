"""Publication UI states without devices, media jobs or desktop access."""
import os,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from loomrec.ui.finalization import FinalizationPanel

class FinalizationPanelTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_progress_cancel_retry_and_ready_are_distinct(self):
  events=[];panel=FinalizationPanel(lambda:events.append('cancel'),lambda:events.append('retry'))
  try:
   for state in ('pending','running'):
    panel.update_status(dict(state=state,progress=.42));self.assertEqual(panel.progress.value(),42)
    self.assertFalse(panel.cancel.isHidden());self.assertTrue(panel.retry.isHidden());panel.cancel.click()
   for state in ('error','cancelled'):
    panel.update_status(dict(state=state,error='Destino sin espacio' if state=='error' else None))
    self.assertTrue(panel.cancel.isHidden());self.assertFalse(panel.retry.isHidden());panel.retry.click()
    self.assertNotIn('listo',panel.title.text())
   panel.update_status(dict(state='ready',progress=1))
   self.assertEqual(panel.title.text(),'MP4 listo para enviar');self.assertTrue(panel.cancel.isHidden());self.assertTrue(panel.retry.isHidden())
   self.assertEqual(events,['cancel','cancel','retry','retry'])
  finally:panel.close();panel.deleteLater();self.app.processEvents()
 def test_error_text_is_actionable_and_progress_is_bounded(self):
  panel=FinalizationPanel(lambda:None,lambda:None)
  try:
   panel.update_status(dict(state='error',error='No hay espacio en Videos'))
   self.assertEqual(panel.detail.text(),'No hay espacio en Videos');self.assertEqual(panel.retry.text(),'Preparar MP4')
   panel.update_status(dict(state='running',progress=4));self.assertEqual(panel.progress.value(),100)
  finally:panel.close();panel.deleteLater();self.app.processEvents()

import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from loomrec.ui.main import Window
from loomrec.library import Library
from loomrec.videolibrary import save_preferences,preferences
class AudioSelectionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'XDG_STATE_HOME':self.temp.name,'XDG_CONFIG_HOME':self.temp.name});self.env.start()
  save_preferences(audio_sources={'mic':'usb-mic','system':'@DEFAULT_MONITOR@'},audio_source_names={'mic':'Micrófono USB'})
  self.w=Window(Library(Path(self.temp.name)/'library'),False);self.w.timer.stop();self.w.ensure_keys=lambda:None
  self.data={'monitors':[],'cameras':[],'audio':[{'kind':'mic','id':'usb-mic','name':'Micrófono USB'},{'kind':'mic','id':'other','name':'Otro micrófono'},{'kind':'system','id':'@DEFAULT_MONITOR@','name':'Salida actual · Bluetooth'},{'kind':'system','id':'alsa.monitor','name':'ALSA monitor'}]}
 def tearDown(self):self.w.close();self.w.deleteLater();self.app.processEvents();self.env.stop();self.temp.cleanup()
 def test_ids_restore_independently_through_reorder_and_explicit_off(self):
  w=self.w;w.devices_ready(self.data);self.assertEqual(w.mic.currentData(),'usb-mic');self.assertEqual(w.system.currentData(),'@DEFAULT_MONITOR@')
  w.mic.setCurrentIndex(0);self.data['audio'].reverse();w.devices_ready(self.data)
  self.assertIsNone(w.mic.currentData());self.assertEqual(w.system.currentData(),'@DEFAULT_MONITOR@');self.assertEqual(preferences()['audio_sources'],{'mic':None,'system':'@DEFAULT_MONITOR@'})
 def test_missing_stays_selected_unavailable_and_recovers_same_id(self):
  w=self.w;original=list(self.data['audio']);self.data['audio']=[e for e in original if e['id']!='usb-mic'];w.devices_ready(self.data)
  self.assertEqual(w.mic.currentData(),'usb-mic');self.assertTrue(w.mic.currentData(Qt.UserRole+1));self.assertIn('No disponible',w.mic.currentText())
  with self.assertRaisesRegex(ValueError,'no está disponible'):w.begin_countdown()
  self.assertEqual(preferences()['audio_sources']['mic'],'usb-mic');self.data['audio']=original;w.devices_ready(self.data);self.assertFalse(w.mic.currentData(Qt.UserRole+1))
 def test_quick_selection_state_names_source_without_claiming_signal(self):
  w=self.w;w.devices_ready(self.data);w.quick.sync();button=w.quick.source_buttons[2]
  self.assertTrue(button.property('sourceActive'));self.assertIn('Seleccionado',button.accessibleName());self.assertIn('Bluetooth',button.toolTip())
  w.system.setCurrentIndex(0);w.quick.sync();self.assertFalse(button.property('sourceActive'));self.assertIn('Desactivado',button.accessibleName())
 def test_restart_restores_explicit_off_and_manual_system_id(self):
  w=self.w;w.devices_ready(self.data);w.mic.setCurrentIndex(0);w.system.setCurrentIndex(w.system.findData('alsa.monitor'))
  other=Window(Library(Path(self.temp.name)/'second'),False);other.ensure_keys=lambda:None
  try:
   other.devices_ready(self.data);self.assertIsNone(other.mic.currentData());self.assertEqual(other.system.currentData(),'alsa.monitor')
  finally:other.close();other.deleteLater();self.app.processEvents()
 def test_system_meter_resolves_intent_and_ignores_late_completion(self):
  w=self.w;w.devices_ready(self.data);pending=[];w.task=lambda fn,cb:pending.append((fn,cb))
  with patch('loomrec.devices.resolve_system_audio',return_value='bluetooth.monitor') as resolve,patch.object(w.mic_meter,'start') as mic,patch.object(w.system_meter,'start') as system:
   w.start_meters();fn,done=pending.pop();result=fn();resolve.assert_called_once_with('@DEFAULT_MONITOR@');done(result)
   mic.assert_called_once_with('usb-mic',1.0);system.assert_called_once_with('bluetooth.monitor',1.0)
   w.start_meters();fn,done=pending.pop();w.stop_meters();done(fn());self.assertEqual(system.call_count,1)

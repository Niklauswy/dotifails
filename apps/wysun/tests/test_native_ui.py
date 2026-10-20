import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
APP=QApplication.instance() or QApplication([])

class NativeUITests(unittest.TestCase):
    def test_settings_opens_with_no_bspwm_config_and_uses_native_fragments(self):
        from settings_hub import SettingsHub
        with tempfile.TemporaryDirectory() as home,patch.dict(os.environ,{'WAYLAND_DISPLAY':'owned','HYPRLAND_INSTANCE_SIGNATURE':'owned'}),patch.object(SettingsHub,'start_job',return_value=Mock()):
            window=SettingsHub(test=True,home=home)
            self.assertTrue(window.shortcuts.native);self.assertEqual(window.backend.script.name,'hypr-settings.lua')
            self.assertGreaterEqual(window.output_scale.count(),5);self.assertFalse((Path(home)/'.config/bspwm').exists())
            window.close();window.deleteLater()
    def test_key_capture_on_wayland_does_not_open_an_x_display(self):
        from shortcut_capture import KeyField
        with patch.dict(os.environ,{'WAYLAND_DISPLAY':'owned'}):
            field=KeyField('old');values=[];field.captured.connect(values.append);field.record()
            field.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress,Qt.Key_J,Qt.ControlModifier|Qt.AltModifier))
            field.keyReleaseEvent(QKeyEvent(QKeyEvent.KeyRelease,Qt.Key_Control,Qt.NoModifier))
            self.assertEqual(values,['ctrl + alt + j']);self.assertIsNone(field.connection);field.close()
    def test_lock_and_suspend_use_managed_acquire_wrapper(self):
        import screen_lock
        with tempfile.TemporaryDirectory() as home,patch.dict(os.environ,{'HOME':home,'WAYLAND_DISPLAY':'owned'}):
            wrapper=Path(home)/'.local/bin/wysun-lock';wrapper.parent.mkdir(parents=True);wrapper.write_text('# synthetic no execution\n')
            self.assertEqual(screen_lock.lock_command(),[str(wrapper)])

if __name__=='__main__':unittest.main()

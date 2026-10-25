"""Motion, glass, battery and process regressions using isolated data and fake actions."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PySide6.QtCore import Qt,QPoint,QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QKeyEvent
from desktop_common import Surface,button
from ui_appearance import read_appearance,save_appearance
from energy_data import battery_snapshot,time_estimate
from process_data import matched,pressure,thread_snapshot


def wait(ms):
    until=time.monotonic()+ms/1000
    while time.monotonic()<until:QApplication.processEvents();time.sleep(.003)


def row(pid=20,start='10',ppid=1,**values):
    result=dict(pid=pid,start=start,ppid=ppid,uid=os.getuid(),user='demo',name='editor',cpu=26.,memory=400*1024**2,state='S',threads=3,nice=0,age=65,read_rate=32,write_rate=4)
    result.update(values);return result


class DataTests(unittest.TestCase):
    def test_battery_values_and_missing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);device=root/'BAT0';device.mkdir()
            for name,value in dict(type='Battery',scope='Device',capacity=98).items():(device/name).write_text(str(value))
            pack=root/'BAT1';pack.mkdir()
            values=dict(type='Battery',capacity=50,status='Discharging',energy_now=24000000,energy_full=48000000,energy_full_design=60000000,power_now=12000000,cycle_count=210)
            for name,value in values.items():(pack/name).write_text(str(value))
            data=battery_snapshot(root);self.assertEqual(data['capacity'],50);self.assertEqual(data['hours'],2);self.assertEqual(data['watts'],12);self.assertEqual(data['health'],80)
            (pack/'status').write_text('Charging');self.assertEqual(battery_snapshot(root)['hours'],2)
            (pack/'power_now').unlink();self.assertIsNone(battery_snapshot(root)['hours'])
            (pack/'capacity').write_text('broken');self.assertIsNone(battery_snapshot(root)['capacity'])
            self.assertIn('no disponible',time_estimate(None))
    def test_preferences_preserve_unknown_fields_and_clamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'.config/orbit/appearance.json';path.parent.mkdir(parents=True);path.write_text('{"custom":"keep"}')
            save_appearance(dict(opacity=2,reduced_motion=True),tmp)
            self.assertEqual(read_appearance(tmp)['opacity'],65);self.assertTrue(read_appearance(tmp)['reduced_motion']);self.assertIn('keep',path.read_text())
    def test_advanced_queries(self):
        r=row();self.assertTrue(matched(r,'cpu>20 mem>=256m state:s user:demo'))
        self.assertFalse(matched(r,'cpu>30'));self.assertFalse(matched(r,'mem<200m'));self.assertFalse(matched(r,'cpu>oops'))
        self.assertTrue(matched(r,'pid:20 ppid:1'))
    def test_pressure_missing_and_real_threads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'cpu').write_text('some avg10=12.34 avg60=1.0 avg300=0.1 total=40\n')
            data=pressure(root);self.assertEqual(data['cpu'],12.34);self.assertIsNone(data['io'])
        threads,total=thread_snapshot(os.getpid());self.assertGreater(total,0);self.assertTrue(any(t['tid']==os.getpid() for t in threads))


class MotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.motion=patch('ui_motion.reduced_motion',return_value=False);self.motion.start();self.w=Surface('Test');self.w.move(100,90)
    def tearDown(self):self.w.hide();self.w.deleteLater();wait(5);self.motion.stop()
    def test_rapid_close_reopen_restores_anchor(self):
        self.w.show();wait(70);self.w.dismiss();wait(35);self.w.show();wait(300)
        self.assertTrue(self.w.isVisible());self.assertEqual(self.w.pos(),QPoint(100,90));self.assertFalse(self.w._motion_exiting)
        self.w.dismiss();wait(190);self.assertFalse(self.w.isVisible());self.assertEqual(self.w.pos(),QPoint(100,90))
    def test_immediate_hide_cancels_animation_for_focus_handoff(self):
        self.w.show();wait(30);self.w.hide();self.assertFalse(self.w.isVisible());self.assertEqual(self.w.pos(),QPoint(100,90))
    def test_reduced_motion_and_press(self):
        with patch('ui_motion.reduced_motion',return_value=True):
            self.w.show();self.assertEqual(self.w.pos(),QPoint(100,90));self.w.dismiss();self.assertFalse(self.w.isVisible())
        b=button('Test',lambda:None);self.w.outer.addWidget(b);self.w.show();b.pressed.emit();wait(110);self.assertAlmostEqual(b.pressScale,.96,3);b.released.emit();wait(160);self.assertAlmostEqual(b.pressScale,1.,3)
    def test_glass_background_alpha(self):
        from theme_tokens import refresh_widgets
        # Glass belongs to dark mode; the user's current light palette is deliberately opaque.
        try:
            with patch.dict(os.environ,{'WYSUN_THEME':'dark'}):
                refresh_widgets()
                with patch('ui_theme.read_appearance',return_value=dict(opacity=80)):
                    self.w.show();wait(280);img=self.w.grab().toImage();alpha=img.pixelColor(80,self.w.height()-35).alpha();self.assertGreater(alpha,180);self.assertLess(alpha,245)
                with patch('ui_theme.read_appearance',return_value=dict(opacity=100)):
                    self.w.update();wait(10);self.assertEqual(self.w.grab().toImage().pixelColor(80,self.w.height()-35).alpha(),255)
            with patch.dict(os.environ,{'WYSUN_THEME':'light'}), patch('ui_theme.read_appearance',return_value=dict(opacity=80)):
                refresh_widgets();self.w.update();wait(10)
                self.assertEqual(self.w.grab().toImage().pixelColor(80,self.w.height()-35).alpha(),255)
        finally:
            refresh_widgets()


if __name__=='__main__':unittest.main(verbosity=2)

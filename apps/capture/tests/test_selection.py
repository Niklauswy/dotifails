"""Selection regression tests; no user display, devices, or media are captured."""
import os
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt,QPoint,QPointF,QRect,QEvent
from PySide6.QtGui import QMouseEvent,QKeyEvent
from PySide6.QtWidgets import QApplication
from loomrec.devices import list_windows,activate_window
from loomrec.ui.widgets import RegionPicker
from loomrec.ui.capture_feedback import RecordingIndicator


def mouse(widget,kind,point):
    event=QMouseEvent(kind,QPointF(point),QPointF(widget.mapToGlobal(point)),Qt.LeftButton,
                      Qt.LeftButton if kind==QEvent.MouseButtonPress else Qt.NoButton,Qt.NoModifier)
    QApplication.sendEvent(widget,event)


class WindowDiscoveryTests(unittest.TestCase):
    def test_other_desktops_and_hidden_clients_are_selectable_without_geometry(self):
        def run(args):
            if '-root' in args:return '_NET_CLIENT_LIST_STACKING(WINDOW): window id # 0x1, 0x2, 0x3'
            window=args[2]
            kind='DOCK' if window=='0x3' else 'NORMAL'
            return (f'_NET_WM_NAME(UTF8_STRING) = "Fixture {window}"\n'
                    'WM_CLASS(STRING) = "fixture", "Fixture"\n'
                    f'_NET_WM_WINDOW_TYPE(ATOM) = _NET_WM_WINDOW_TYPE_{kind}\n'
                    '_NET_WM_STATE(ATOM) = _NET_WM_STATE_HIDDEN\n'
                    '_NET_WM_DESKTOP(CARDINAL) = 3')
        with patch('loomrec.devices.run',side_effect=run),patch('loomrec.devices.visible_window_rect') as geometry:
            windows=list_windows()
        self.assertEqual([w['id'] for w in windows],['0x1','0x2'])
        self.assertTrue(all(w['desktop']==3 and w['hidden'] for w in windows))
        geometry.assert_not_called()

    def test_activation_restores_focus_and_uses_fresh_geometry(self):
        with patch('loomrec.devices.shutil.which',return_value='/bin/wmctrl'),patch('loomrec.devices.run',return_value='window id # 0x23') as run,patch('loomrec.devices.visible_window_rect',return_value=[40,60,200,100]) as geometry:
            self.assertEqual(activate_window('0x23'),[40,60,200,100])
        self.assertEqual(run.call_args_list[0].args[0],['wmctrl','-ia','0x23'])
        self.assertEqual(run.call_args_list[1].args[0][:2],['xprop','-root'])
        geometry.assert_called_once_with('0x23')
        self.assertFalse(any('-d' in call.args[0] for call in run.call_args_list))

    def test_wmctrl_activation_refusal(self):
        with patch('loomrec.devices.shutil.which',side_effect=lambda name:'/bin/wmctrl' if name=='wmctrl' else None),patch('loomrec.devices.run',return_value='window id # 0x99') as run,patch('loomrec.devices.time.monotonic',side_effect=[0,1,3]),patch('loomrec.devices.time.sleep'),patch('loomrec.devices.visible_window_rect') as geometry:
            with self.assertRaisesRegex(ValueError,'mostrar'):activate_window('0x23')
        self.assertEqual(run.call_args_list[0].args[0],['wmctrl','-ia','0x23'])
        geometry.assert_not_called()


class SelectionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_drag_reverse_coordinates_and_overlay_closed_before_result(self):
        picker=RegionPicker(QRect(-400,0,800,600));results=[]
        picker.selected.connect(lambda rect:results.append((rect,picker.isVisible())))
        picker.show();self.app.processEvents()
        self.assertTrue(picker.windowFlags() & Qt.X11BypassWindowManagerHint)
        self.assertEqual(picker.geometry(),QRect(-400,0,800,600))
        mouse(picker,QEvent.MouseButtonPress,QPoint(303,205))
        mouse(picker,QEvent.MouseButtonRelease,QPoint(100,100))
        self.assertEqual(results,[([-300,100,202,104],False)])

    def test_escape_and_small_drags_cancel_once(self):
        for small in (False,True):
            picker=RegionPicker(QRect(0,0,800,600));cancel=[];selected=[]
            picker.cancelled.connect(lambda:cancel.append(True));picker.selected.connect(selected.append)
            picker.show()
            if small:
                mouse(picker,QEvent.MouseButtonPress,QPoint(100,100));mouse(picker,QEvent.MouseButtonRelease,QPoint(104,104))
            else:QApplication.sendEvent(picker,QKeyEvent(QEvent.KeyPress,Qt.Key_Escape,Qt.NoModifier))
            picker.close()
            self.assertEqual(cancel,[True]);self.assertEqual(selected,[])

    def test_shade_has_clear_selected_interior(self):
        picker=RegionPicker(QRect(0,0,800,600));picker.selection=QRect(100,100,200,200)
        image=picker.grab().toImage()
        self.assertEqual(image.pixelColor(200,200).alpha(),0)
        self.assertEqual(image.pixelColor(500,400).alpha(),100)
        picker.close()

    def test_border_animation_pauses_and_releases_timer(self):
        indicator=RecordingIndicator();crop=QRect(100,100,400,300)
        indicator.present(list(crop.getRect()),[[0,0,800,600]])
        indicator.update('recording');self.assertTrue(indicator.timer.isActive())
        before=indicator.borders[0].grab().toImage();indicator.animate()
        self.assertNotEqual(before,indicator.borders[0].grab().toImage())
        for window in indicator.windows:
            self.assertFalse(window.geometry().intersects(crop))
            self.assertTrue(window.windowFlags() & Qt.WindowTransparentForInput)
        indicator.update('paused');self.assertFalse(indicator.timer.isActive())
        self.assertTrue(all(b.state=='paused' for b in indicator.borders))
        indicator.update('recording');self.assertTrue(indicator.timer.isActive())
        indicator.hide();self.assertFalse(indicator.timer.isActive());self.assertEqual(indicator.windows,[])

    def test_chooser_activation_success_failure_and_cancelled_refresh(self):
        from loomrec.ui.main import Window
        from loomrec.ui.quick import WindowChooser
        from loomrec.library import Library
        entry=dict(id='0xf00023',title='Synthetic',app='Fixture',desktop=2,hidden=True)
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'XDG_STATE_HOME':root,'XDG_CONFIG_HOME':root}):
            owner=Window(Library(root),False);owner.timer.stop();owner.quick.timer.stop()
            pending=[]
            with patch.object(owner,'task',side_effect=lambda fn,callback:pending.append((fn,callback))):
                chooser=WindowChooser(owner);chooser.show();pending.pop()[1]([entry]);chooser.items.setCurrentRow(0)
                self.assertIn('Escritorio 3',chooser.items.item(0).text())
                chooser.select();self.assertFalse(chooser.isVisible());self.assertTrue(chooser.selecting)
                fn,callback=pending.pop()
                with patch('loomrec.devices.activate_window',side_effect=ValueError('Closed fixture')):callback(fn())
                self.assertTrue(chooser.isVisible());self.assertEqual(chooser.status.text(),'Closed fixture');self.assertIsNone(owner.window_target)
                chooser.select();fn,callback=pending.pop()
                with patch('loomrec.devices.activate_window',return_value=[10,20,300,200]):callback(fn())
                self.assertEqual(owner.window_target,'0xf00023');self.assertEqual([w.value() for w in owner.rect],[10,20,300,200]);self.assertTrue(owner.quick_mode)
                chooser=WindowChooser(owner);chooser.show();chooser.reject();pending.pop()[1]([entry]);self.assertEqual(chooser.items.count(),0)
            owner.session=None;owner.quick.hide_all();owner.close();owner.deleteLater();self.app.processEvents()

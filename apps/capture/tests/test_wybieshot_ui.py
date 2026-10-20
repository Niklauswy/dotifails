"""Synthetic-only pointer/keyboard UI tests. No desktop or private image access."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QPoint,QPointF,QRect,QEvent
from PySide6.QtGui import QImage,QColor,QKeyEvent,QMouseEvent
class QTest:
    @staticmethod
    def keyClick(widget,key,modifiers=Qt.NoModifier):
        for kind in (QEvent.KeyPress,QEvent.KeyRelease):QApplication.sendEvent(widget,QKeyEvent(kind,key,modifiers))
    @staticmethod
    def mousePress(widget,button,pos):QApplication.sendEvent(widget,QMouseEvent(QEvent.MouseButtonPress,QPointF(pos),QPointF(widget.mapToGlobal(pos)),button,button,Qt.NoModifier))
    @staticmethod
    def mouseMove(widget,pos):QApplication.sendEvent(widget,QMouseEvent(QEvent.MouseMove,QPointF(pos),QPointF(widget.mapToGlobal(pos)),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
    @staticmethod
    def mouseRelease(widget,button,pos):QApplication.sendEvent(widget,QMouseEvent(QEvent.MouseButtonRelease,QPointF(pos),QPointF(widget.mapToGlobal(pos)),button,Qt.NoButton,Qt.NoModifier))
    @staticmethod
    def mouseClick(widget,button,pos):QTest.mousePress(widget,button,pos);QTest.mouseRelease(widget,button,pos)
from PySide6.QtWidgets import QApplication,QInputDialog,QDialog,QComboBox,QCheckBox,QSlider,QPushButton,QSpinBox
from wybieshot.document import Document
from wybieshot.schema import Layer
from wybieshot.storage import Storage
from wybieshot.ui.components import apply_theme
from wybieshot.ui.main import Window
from wybieshot.ui.selection import SelectionOverlay


def image(w=640,h=360):
    result=QImage(w,h,QImage.Format_ARGB32);result.fill(QColor('#F3F6FB'));return result

def control_drag(widget,start,end):
    start_global=widget.mapToGlobal(start);end_global=widget.mapToGlobal(end)
    with patch('wybieshot.ui.selection.QCursor.pos',return_value=start_global):
        QApplication.sendEvent(widget,QKeyEvent(QEvent.KeyPress,Qt.Key_Control,Qt.NoModifier))
    QApplication.sendEvent(widget,QMouseEvent(QEvent.MouseMove,QPointF(end),QPointF(end_global),Qt.NoButton,Qt.NoButton,Qt.ControlModifier))
    with patch('wybieshot.ui.selection.QCursor.pos',return_value=end_global):
        QApplication.sendEvent(widget,QKeyEvent(QEvent.KeyRelease,Qt.Key_Control,Qt.NoModifier))


class ScreenshotUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);apply_theme(cls.app)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.storage=Storage(Path(self.temp.name)/'library');self.storage.set_output(Path(self.temp.name)/'output')
        self.window=Window(self.storage);self.window.set_document(Document(image(),'Owned fixture'));self.app.processEvents()
    def tearDown(self):
        self.window._closing=True;self.window.thumbnail_timer.stop()
        for job in list(self.window.jobs):job.wait(5000)
        self.app.processEvents()
        self.window.quick.close();self.window.close();self.window.deleteLater();self.app.processEvents();self.temp.cleanup()
    def point(self,x,y):
        r=self.window.canvas.image_rect();return QPoint(round(r.x()+r.width()*x/640),round(r.y()+r.height()*y/360))
    def drag(self,start,end):
        canvas=self.window.canvas;QTest.mousePress(canvas,Qt.LeftButton,pos=start);QTest.mouseMove(canvas,end);QTest.mouseRelease(canvas,Qt.LeftButton,pos=end);self.app.processEvents()
    def test_pointer_draw_select_move_keyboard_undo_redo_and_reopen(self):
        canvas=self.window.canvas;self.window.choose_tool('rectangle');self.drag(self.point(60,60),self.point(200,150))
        self.assertEqual(len(self.window.document.layers),1);first=self.window.document.layers[0]
        self.assertEqual(first.tool,'rectangle');self.assertTrue(self.window.undo_button.isEnabled())
        self.window.choose_tool('select');self.drag(self.point(100,100),self.point(120,120));moved=self.window.document.layers[0]
        self.assertGreater(moved.points[0][0],first.points[0][0])
        QTest.keyClick(canvas,Qt.Key_Right);self.assertEqual(self.window.document.layers[0].points[0][0],moved.points[0][0]+1)
        self.window.undo();self.assertEqual(self.window.document.layers[0],moved)
        self.window.redo();self.assertEqual(self.window.document.layers[0].points[0][0],moved.points[0][0]+1)
        self.assertTrue(self.window.save_document());id=self.window.document.session_id
        loaded=self.storage.load(id);self.window.set_document(loaded)
        self.assertEqual(len(loaded.layers),1);self.window.choose_tool('select');QTest.mouseClick(canvas,Qt.LeftButton,pos=self.point(150,120));QTest.keyClick(canvas,Qt.Key_Delete)
        self.assertEqual(len(loaded.layers),0);self.window.undo();self.assertEqual(len(loaded.layers),1)
    def test_tools_create_real_layers_and_editable_step_auto_number(self):
        for tool in ('arrow','ellipse','pen','highlight','mask','blur'):
            self.window.choose_tool(tool);self.drag(self.point(50,50),self.point(120,100));self.assertEqual(self.window.document.layers[-1].tool,tool)
        self.window.choose_tool('number');QTest.mouseClick(self.window.canvas,Qt.LeftButton,pos=self.point(250,150))
        self.assertEqual(self.window.document.layers[-1].number,1)
        with patch.object(QInputDialog,'getInt',return_value=(7,True)):self.window.edit_selected()
        self.assertEqual(self.window.document.layers[-1].number,7)
        with patch.object(QInputDialog,'getInt',return_value=(8,True)):
            QTest.mouseClick(self.window.canvas,Qt.LeftButton,pos=self.point(300,150))
        self.assertEqual(self.window.document.layers[-1].number,8)
        with patch.object(QInputDialog,'getMultiLineText',return_value=('Editable text',True)):
            self.window.choose_tool('text');QTest.mouseClick(self.window.canvas,Qt.LeftButton,pos=self.point(300,200))
        self.assertEqual(self.window.document.layers[-1].text,'Editable text')
    def test_crop_cancel_tool_state_and_keyboard_tool_shortcuts(self):
        canvas=self.window.canvas;self.window.choose_tool('crop');self.drag(self.point(50,50),self.point(300,220));self.assertIsNotNone(self.window.document.crop)
        self.window.undo();self.assertIsNone(self.window.document.crop)
        self.window.choose_tool('arrow');QTest.mousePress(canvas,Qt.LeftButton,pos=self.point(50,50));QTest.mouseMove(canvas,self.point(200,100));QTest.keyClick(canvas,Qt.Key_Escape);QTest.mouseRelease(canvas,Qt.LeftButton,pos=self.point(200,100));self.assertEqual(len(self.window.document.layers),0)
        canvas.setFocus();QTest.keyClick(canvas,Qt.Key_R);self.app.processEvents();self.assertEqual(canvas.tool,'rectangle');self.assertTrue(self.window.tool_buttons['rectangle'].isChecked())
    def test_clipboard_export_and_library_actions(self):
        self.window.copy();self.assertEqual(self.app.clipboard().image(),self.window.document.render())
        path=self.window.export();self.assertTrue(path.exists());self.assertEqual(QImage(str(path)),self.window.document.render())
        self.window.save_document();self.window.show_library();self.window.items.setCurrentRow(0);self.assertTrue(self.window.open_button.isEnabled());self.assertFalse(self.window.compare_button.isEnabled())
        self.window.search.setText('no match');self.assertFalse(self.window.open_button.isEnabled());self.assertTrue(self.window.empty.isVisible())
    def test_responsive_and_accessible_controls(self):
        for size in ((1120,760),(720,600),(520,430)):
            self.window.resize(*size);self.app.processEvents();self.assertEqual((self.window.width(),self.window.height()),size)
            for b in (self.window.export_button,self.window.copy_button,self.window.tool_buttons['blur']):self.assertTrue(b.accessibleName());self.assertTrue(b.focusPolicy()&Qt.TabFocus)
            self.assertTrue(self.window.rect().contains(self.window.export_button.mapTo(self.window,self.window.export_button.rect().bottomRight())))
    def select_two(self):
        self.window.save_document();second=Document(image(),'After');second.add_layer(Layer('rectangle',((10,10),(100,80)),color='#FF0000'));self.storage.save(second)
        self.window.show_library();self.window.items.item(0).setSelected(True);self.window.items.item(1).setSelected(True)
    def test_ui_composition_titles_gap_and_comparison_slider_save(self):
        self.select_two()
        def configure(dialog):
            self.assertEqual(dialog.windowTitle(),'Componer capturas');dialog.findChild(QComboBox).setCurrentIndex(1);dialog.findChild(QSpinBox).setValue(24);dialog.findChild(QCheckBox).setChecked(True);return QDialog.Accepted
        with patch.object(QDialog,'exec',configure):self.window.compose()
        self.assertEqual(self.window.document.size.width(),640);self.assertEqual(self.window.document.size.height(),(360+48)*2+24)
        self.assertEqual(self.window.document.title,'Composición')
        self.select_two()
        # Select the equal-sized originals instead of the composition.
        self.window.items.clearSelection()
        for n in range(self.window.items.count()):
            item=self.window.items.item(n)
            if item.data(Qt.UserRole+1)['width']==640 and item.data(Qt.UserRole+1)['height']==360:item.setSelected(True)
        def compare(dialog):
            slider=dialog.findChild(QSlider);slider.setValue(25)
            view=dialog.findChild(__import__('wybieshot.ui.canvas',fromlist=['Canvas']).Canvas)
            self.assertEqual(view.document.title,'Antes y después')
            next(b for b in dialog.findChildren(QPushButton) if b.text()=='Guardar vista').click();return QDialog.Accepted
        # Keep exactly two entries when there are duplicate synthetic originals.
        selected=self.window.items.selectedItems()
        for item in selected[2:]:item.setSelected(False)
        with patch.object(QDialog,'exec',compare):self.window.compare()
        self.assertEqual(self.window.document.title,'Antes y después')
    def test_settings_persist_and_export_jpeg_and_context_properties(self):
        def settings(dialog):
            combos=dialog.findChildren(QComboBox);combos[0].setCurrentText('JPEG');combos[1].setCurrentIndex(1)
            for checkbox in dialog.findChildren(QCheckBox):checkbox.setChecked(True)
            return QDialog.Accepted
        with patch.object(QDialog,'exec',settings):self.window.show_settings()
        prefs=Storage(self.storage.root).settings;self.assertEqual(prefs['format'],'JPEG');self.assertEqual(prefs['delay'],3);self.assertTrue(prefs['reduced_motion']);self.assertTrue(prefs['include_cursor'])
        path=self.window.export();self.assertEqual(path.suffix,'.jpg');self.assertFalse(QImage(str(path)).isNull())
        self.window.choose_tool('blur');self.assertFalse(self.window.color_button.isEnabled());self.assertFalse(self.window.width_spin.isVisible())
        self.window.choose_tool('text');self.assertTrue(self.window.font_spin.isVisible());self.assertFalse(self.window.width_spin.isVisible())
        self.window.choose_tool('arrow');self.assertTrue(self.window.width_spin.isVisible());self.assertFalse(self.window.font_spin.isVisible())
        self.assertFalse(self.window.color_button.icon().isNull())
    def test_thumbnail_is_real_and_bounded_and_library_footer_context(self):
        self.window.save_document();self.window.show_library();self.app.processEvents();self.window.load_visible_thumbnail()
        for job in list(self.window.jobs):job.wait(5000)
        self.app.processEvents()
        self.assertTrue(self.window.thumbnail_cache);self.assertLessEqual(len(self.window.thumbnail_cache),32)
        self.assertNotIn('objeto',self.window.statusBar().currentMessage());self.assertIn('captura',self.window.statusBar().currentMessage())
    def test_selected_shape_resize_and_keyboard_object_cycle(self):
        self.window.choose_tool('rectangle');self.drag(self.point(50,50),self.point(200,140));self.window.choose_tool('select')
        self.drag(self.point(200,140),self.point(240,180));layer=self.window.document.layers[0];self.assertAlmostEqual(layer.points[-1][0],240,delta=2)
        self.window.canvas.selected_id=None;QTest.keyClick(self.window.canvas,Qt.Key_BracketRight);self.assertEqual(self.window.canvas.selected_id,layer.id)
    def test_autosave_error_keeps_document_on_navigation_replacement_and_close(self):
        original=self.window.document
        original.add_layer(Layer('rectangle',((10,10),(50,60))))
        original.add_layer(Layer('arrow',((80,80),(150,130))))
        original.undo()
        layers=original.layers;can_undo=original.can_undo;can_redo=original.can_redo
        with patch.object(self.storage,'save',side_effect=OSError('Fixture disk unavailable')):
            self.assertFalse(self.window.set_document(Document(image(),'Replacement')))
            self.assertIs(self.window.document,original)
            self.window.show_library();self.assertIs(self.window.stack.currentWidget(),self.window.editor_page)
            self.window.close();self.assertTrue(self.window.isVisible());self.assertIs(self.window.document,original)
            self.assertIn('No se pudo guardar',self.window.statusBar().currentMessage())
            self.assertIn('Fixture disk unavailable',self.window.statusBar().currentMessage())
            self.assertEqual(original.layers,layers);self.assertEqual(original.can_undo,can_undo);self.assertEqual(original.can_redo,can_redo)
        self.assertTrue(self.window.save_document())
        restored=self.storage.load(original.session_id);self.assertEqual(restored.layers,layers)
        self.assertEqual(original.can_undo,can_undo);self.assertEqual(original.can_redo,can_redo)
        self.window.show_library();self.assertIs(self.window.stack.currentWidget(),self.window.library_page)
    def test_selection_keyboard_resize_confirm_and_cancel(self):
        overlay=SelectionOverlay(image(),QRect(0,0,640,360));results=[];cancelled=[];overlay.selected.connect(results.append);overlay.cancelled.connect(lambda:cancelled.append(True));overlay.show();self.app.processEvents()
        QTest.keyClick(overlay,Qt.Key_Return);original=QRect(overlay.selection)
        QTest.keyClick(overlay,Qt.Key_Right);QTest.keyClick(overlay,Qt.Key_Down,Qt.ShiftModifier)
        self.assertEqual(overlay.selection.x(),original.x()+1);self.assertEqual(overlay.selection.height(),original.height()+1)
        QTest.keyClick(overlay,Qt.Key_Return);self.assertEqual(len(results),1)
        overlay.show();QTest.keyClick(overlay,Qt.Key_Escape);self.assertEqual(cancelled,[True]);overlay.deleteLater()
    def test_selection_pointer_adjust_and_cancel_capture_timer(self):
        overlay=SelectionOverlay(image(),QRect(0,0,640,360));overlay.show();self.app.processEvents()
        QTest.mousePress(overlay,Qt.LeftButton,pos=QPoint(20,30));QTest.mouseMove(overlay,QPoint(180,140));QTest.mouseRelease(overlay,Qt.LeftButton,pos=QPoint(180,140));self.assertEqual(overlay.selection,QRect(QPoint(20,30),QPoint(180,140)))
        QTest.mousePress(overlay,Qt.LeftButton,pos=QPoint(180,140));QTest.mouseMove(overlay,QPoint(200,160));QTest.mouseRelease(overlay,Qt.LeftButton,pos=QPoint(200,160));self.assertEqual(overlay.selection.bottomRight(),QPoint(200,160));overlay.close()
        overlay.show();self.app.processEvents();finished=[];overlay.control_drag_finished.connect(lambda:finished.append(True))
        control_drag(overlay,QPoint(250,180),QPoint(340,260))
        self.assertEqual(overlay.selection,QRect(QPoint(250,180),QPoint(340,260)));self.assertEqual(finished,[True]);overlay.close()
        self.window.busy=True;self.window.capture_timer.start(1000);self.window.cancel_capture();self.assertFalse(self.window.busy);self.assertFalse(self.window.capture_timer.isActive());self.window.quick.hide()

    def test_control_drag_finishes_on_the_output_where_it_started(self):
        left=SelectionOverlay(image(320,240),QRect(0,0,320,240));right=SelectionOverlay(image(320,240),QRect(320,0,320,240))
        left.show();right.show();self.app.processEvents();finished=[];left.control_drag_finished.connect(lambda:finished.append(True))
        start=QPoint(20,20);middle=QPoint(100,100);end=QPoint(340,100)
        with patch('wybieshot.ui.selection.QCursor.pos',return_value=start):
            QApplication.sendEvent(left,QKeyEvent(QEvent.KeyPress,Qt.Key_Control,Qt.NoModifier))
        QApplication.sendEvent(left,QMouseEvent(QEvent.MouseMove,QPointF(middle),QPointF(left.mapToGlobal(middle)),Qt.NoButton,Qt.NoButton,Qt.ControlModifier))
        QApplication.sendEvent(right,QMouseEvent(QEvent.MouseMove,QPointF(20,100),QPointF(end),Qt.NoButton,Qt.NoButton,Qt.ControlModifier))
        with patch('wybieshot.ui.selection.QCursor.pos',return_value=end):
            QApplication.sendEvent(right,QKeyEvent(QEvent.KeyRelease,Qt.Key_Control,Qt.NoModifier))
        self.assertEqual(finished,[True]);self.assertEqual(left.selection,QRect(QPoint(20,20),QPoint(319,100)))
        left.close();right.close()

if __name__=='__main__':unittest.main()

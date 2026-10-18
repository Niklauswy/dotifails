"""Frozen synthetic images only; no native desktop or user clipboard access."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QRect,QEvent,QPointF
from PySide6.QtGui import QImage,QColor,QMouseEvent
from PySide6.QtWidgets import QApplication,QPlainTextEdit,QColorDialog,QPushButton,QLabel
from wybieshot.ui.floating import FloatingSelection
from wybieshot.actions import ActionWindow,CaptureActions
from wybieshot.instance import CaptureLease
from wybieshot.storage import Storage
from wybieshot.__main__ import main
app=QApplication.instance() or QApplication([])

def drag(widget,a,b):
    for kind,p,button,buttons in ((QEvent.MouseButtonPress,a,Qt.LeftButton,Qt.LeftButton),(QEvent.MouseMove,b,Qt.NoButton,Qt.LeftButton),(QEvent.MouseButtonRelease,b,Qt.LeftButton,Qt.NoButton)):
        app.sendEvent(widget,QMouseEvent(kind,QPointF(*p),QPointF(*p),button,buttons,Qt.NoModifier))

def frozen():
    image=QImage(1280,720,QImage.Format_ARGB32);image.fill(QColor('#23a6bf'));return image

class FloatingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.overlay=FloatingSelection(frozen(),QRect(0,0,1280,720));self.overlay.show();app.processEvents();self.window=None
    def tearDown(self):
        if self.window:
            self.window.close();self.window.quick.close();self.window.quick.deleteLater();self.window.deleteLater()
        self.overlay.close();self.overlay.deleteLater();app.processEvents();app.sendPostedEvents(None,QEvent.DeferredDelete);self.temp.cleanup()
    def select(self):
        drag(self.overlay,(100,100),(599,399));app.processEvents()
        self.assertTrue(self.overlay.toolbar.isVisible());self.assertEqual(self.overlay.document.size.width(),500)
    def test_in_place_tools_pixels_history_and_editable_text(self):
        self.select();o=self.overlay;o.choose('arrow');drag(o.canvas,(30,40),(240,40))
        self.assertEqual(o.document.render().pixelColor(100,40).name(),'#2165d5')
        o.choose('mask');o.canvas.color='#000000';drag(o.canvas,(300,100),(350,150));self.assertEqual(o.document.render().pixelColor(320,120).name(),'#000000')
        o.undo();self.assertEqual(o.document.render().pixelColor(320,120).name(),'#23a6bf');o.redo()
        o.choose('text')
        drag(o.canvas,(100,150),(100,150))
        o._popover.findChild(QPlainTextEdit).setPlainText('Contexto')
        next(b for b in o._popover.findChildren(QPushButton) if b.text()=='Aplicar').click()
        self.assertEqual(o.document.layers[-1].text,'Contexto')
        o.font_spin.setValue(32);self.assertEqual(o.document.layers[-1].font_size,32)
        self.assertEqual(o.document.original.pixelColor(320,120).name(),'#23a6bf')
        self.assertFalse(o.area.isEnabled());self.assertTrue(o.rect().contains(o.toolbar.geometry()))
    def test_color_and_text_editors_are_embedded_nonmodal_and_escape_returns(self):
        self.select();o=self.overlay;o.choose('select');self.assertTrue(o.color.isEnabled())
        o.pick_color();picker=o._popover.findChild(QColorDialog)
        self.assertFalse(picker.isWindow());self.assertIsNone(app.activeModalWidget())
        sampler=picker.findChild(QPushButton,'wybieUnsupportedScreenPicker')
        self.assertIsNotNone(sampler);self.assertFalse(sampler.isEnabled());self.assertFalse(sampler.isVisible())
        labels=[w.text().replace('&','') for w in picker.findChildren(QLabel)]
        self.assertNotIn('Basic colors',labels);self.assertNotIn('Red:',labels)
        picker.setCurrentColor(QColor('#ff0055'))
        next(b for b in o._popover.findChildren(QPushButton) if b.text()=='Aplicar').click()
        self.assertIsNone(o._popover);self.assertEqual(o.canvas.color,'#ff0055')
        o.choose('text');drag(o.canvas,(40,40),(40,40));self.assertIsNotNone(o._popover)
        self.assertIsNone(app.activeModalWidget());self.assertIsNone(o.canvas.start)
        o.cancel();self.assertIsNone(o._popover);self.assertTrue(o.isVisible())
        results=[];o.finished.connect(lambda doc,action:results.append(action));o.copy_button.click();self.assertEqual(results,['copy'])
    def test_palette_hit_targets_remain_controls_over_large_canvas(self):
        o=self.overlay;o.selection=QRect(8,8,1264,704);o.prepare_selection();app.processEvents()
        for tool in ('arrow','pen','text','number','select','mask','blur'):
            o.choose(tool);app.processEvents()
            for b in (o.copy_button,o.color,o.tools['arrow']):
                self.assertIs(o.childAt(b.mapTo(o,b.rect().center())),b,tool)
        # Palette whitespace never bubbles up into a new region gesture.
        o.adjust_area();before=QRect(o.selection)
        drag(o.toolbar,(o.toolbar.width()-3,3),(o.toolbar.width()-3,7))
        self.assertEqual(o.selection,before);self.assertIsNone(o.anchor)

    def test_save_uses_only_annotated_bitmap_and_releases_lease(self):
        self.select();o=self.overlay;o.choose('rectangle');drag(o.canvas,(30,30),(120,120))
        store=Storage(Path(self.temp.name)/'private');self.window=ActionWindow(CaptureActions(),store);w=self.window
        w.overlay=o;w.busy=True;w._capture_lease=CaptureLease(Path(self.temp.name)/'runtime');self.assertTrue(w._capture_lease.claim())
        other=CaptureLease(Path(self.temp.name)/'runtime');self.assertFalse(other.claim())
        target=Path(self.temp.name)/'saved.png'
        with patch.object(o,'request_save_path',side_effect=lambda default,callback:callback(str(target))):w.complete_floating(o.document,'save')
        self.assertEqual(QImage(str(target)),o.document.render());self.assertTrue(other.claim());other.release();self.assertFalse(w.isVisible())
    def test_copy_owner_does_not_block_next_capture(self):
        self.select();o=self.overlay;store=Storage(Path(self.temp.name)/'private');self.window=ActionWindow(CaptureActions(),store);w=self.window
        w.overlay=o;w._capture_lease=CaptureLease(Path(self.temp.name)/'runtime');w._capture_lease.claim()
        w.complete_floating(o.document,'copy')
        self.assertEqual(app.clipboard().image(),o.document.render());self.assertTrue(w._clipboard_hidden)
        next_capture=CaptureLease(Path(self.temp.name)/'runtime');self.assertTrue(next_capture.claim());next_capture.release()
        self.assertFalse(w.isVisible())

    def test_failed_save_retains_floating_document_and_capture_lease(self):
        self.select();o=self.overlay;store=Storage(Path(self.temp.name)/'private');self.window=ActionWindow(CaptureActions(),store);w=self.window
        w.overlay=o;w._capture_lease=CaptureLease(Path(self.temp.name)/'runtime');w._capture_lease.claim()
        with patch.object(o,'request_save_path',side_effect=lambda default,callback:callback(str(Path(self.temp.name)/'bad.png'))),patch.object(store,'export',side_effect=OSError('disk unavailable')):w.complete_floating(o.document,'save')
        self.assertIs(w.overlay,o);self.assertTrue(o.isVisible());self.assertIn('disk unavailable',o.message.text())
        other=CaptureLease(Path(self.temp.name)/'runtime');self.assertFalse(other.claim());w.cancel_capture();self.assertTrue(other.claim());other.release()

class LeaseTests(unittest.TestCase):
    def test_repeat_direct_invocation_is_ignored_and_recovers_after_release(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'XDG_RUNTIME_DIR':directory}):
            first=CaptureLease();self.assertTrue(first.claim());second=CaptureLease();self.assertFalse(second.claim())
            with patch('wybieshot.actions.run') as run:
                self.assertEqual(main(['--region']),0);run.assert_not_called()
            first.release();self.assertTrue(second.claim());second.release()
    def test_process_death_releases_lock_and_displays_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            code='from wybieshot.instance import CaptureLease; import sys; x=CaptureLease(sys.argv[1]); assert x.claim(); print("ready",flush=True); sys.stdin.read()'
            child=subprocess.Popen([sys.executable,'-c',code,directory],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(),'ready');lease=CaptureLease(directory);self.assertFalse(lease.claim())
                with patch.dict(os.environ,{'DISPLAY':':other'}):
                    other=CaptureLease(directory);self.assertTrue(other.claim());other.release()
                child.terminate();child.wait(timeout=5);self.assertTrue(lease.claim());lease.release()
            finally:
                if child.poll() is None:child.kill();child.wait()
                child.stdin.close();child.stdout.close()
if __name__=='__main__':unittest.main()

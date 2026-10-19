"""Owned QImage/topology fixtures only: no portal, input, compositor or media."""
import copy
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PySide6.QtGui import QImage,QColor


def output(name,x,y=0,width=32,height=24,scale=1,transform=0):
    return dict(id=0 if name=='A' else 1,name=name,serial=name,make='fixture',model='owned',width=width,height=height,
                x=x,y=y,scale=scale,transform=transform,disabled=False,mirrorOf='none',dpmsStatus=True)


def frame(color='red',width=32,height=24):
    image=QImage(width,height,QImage.Format_ARGB32);image.fill(QColor(color));return image


class DesktopCursorTests(unittest.TestCase):
    def setUp(self):
        from loomrec import desktop_capture as desktop
        self.desktop=desktop
        self.rows=[output('A',-32),output('B',0)]
        self.opened=[];self.progress=[]
    def run_capture(self,selections=('A','B'),snapshots=None,read_error=None,on_wait=None):
        d=self.desktop;snapshot=d.topology_from_hypr(self.rows)
        selections=iter(selections);opened=self.opened
        class Capture:
            def __init__(self,config,on_wait=None):
                self.closed=False;opened.append(self)
                if on_wait:on_wait()
                selected=next(selections)
                if isinstance(selected,Exception):raise selected
                self.config=config;self.node=47
                self.metadata=dict(mapping_id=selected,source_type=1,size=[32,24],position=[0,0])
                self.portal=SimpleNamespace(streams=[(47,self.metadata)])
            def close(self):self.closed=True
        def read(capture,on_wait=None):
            if on_wait:on_wait()
            if read_error:raise read_error
            return frame('red' if capture.metadata['mapping_id']=='A' else 'blue')
        with patch.object(d,'read_topology',side_effect=snapshots if snapshots else None,return_value=snapshot),patch.object(d,'PipeWireCapture',Capture),patch.object(d,'read_frame',read):
            return d.desktop_cursor_image(progress=self.progress.append,on_wait=on_wait)
    def test_two_consents_exact_coverage_negative_coordinates(self):
        image=self.run_capture(('B','A'))
        self.assertEqual((image.width(),image.height()),(64,24))
        self.assertEqual(image.pixelColor(1,1),QColor('red'));self.assertEqual(image.pixelColor(50,1),QColor('blue'))
        self.assertEqual(len(self.opened),2);self.assertTrue(all(c.closed for c in self.opened))
        self.assertTrue(all(c.config.source_type=='monitor' and c.config.cursor for c in self.opened))
        self.assertEqual([p['stage'] for p in self.progress],['select','capture','select','capture','complete'])
        self.assertEqual(self.progress[0]['remaining'],['A','B']);self.assertEqual(self.progress[2]['remaining'],['A'])
    def test_duplicate_aborts_instead_of_reprompting_or_returning_partial(self):
        with self.assertRaisesRegex(RuntimeError,'repetida'):self.run_capture(('A','A'))
        self.assertEqual(len(self.opened),2);self.assertTrue(all(c.closed for c in self.opened))
        self.assertNotIn('complete',[p['stage'] for p in self.progress])
    def test_unknown_mapping_never_reads_unauthorized_extra_frame(self):
        with self.assertRaisesRegex(RuntimeError,'identidad'):self.run_capture(('UNKNOWN',))
        self.assertTrue(self.opened[0].closed)
        self.assertNotIn('capture',[p['stage'] for p in self.progress])
    def test_cancel_second_selection_discards_all(self):
        from loomrec.portal import PortalCancelled
        with self.assertRaises(PortalCancelled):self.run_capture(('A',PortalCancelled('own synthetic cancellation')))
        self.assertTrue(self.opened[0].closed);self.assertNotIn('complete',[p['stage'] for p in self.progress])
    def test_global_cancel_before_any_portal(self):
        from loomrec.portal import PortalCancelled
        def cancel():raise PortalCancelled('global')
        with self.assertRaises(PortalCancelled):self.run_capture(on_wait=cancel)
        self.assertEqual(self.opened,[])
    def test_read_failure_closes_and_never_completes(self):
        with self.assertRaisesRegex(RuntimeError,'fixture source'):self.run_capture(read_error=RuntimeError('fixture source'))
        self.assertTrue(self.opened[0].closed);self.assertNotIn('complete',[p['stage'] for p in self.progress])
    def test_hotplug_or_topology_change_at_every_checkpoint_aborts(self):
        baseline=self.desktop.topology_from_hypr(self.rows)
        changed_rows=copy.deepcopy(self.rows);changed_rows[1]['serial']='replacement'
        changed=self.desktop.topology_from_hypr(changed_rows)
        # initial, before each consent, after selection, after frame, final compose
        for index in range(1,9):
            with self.subTest(index=index):
                self.opened=[];self.progress=[]
                snapshots=[baseline]*index+[changed]*12
                with self.assertRaisesRegex(RuntimeError,'topología'):self.run_capture(snapshots=snapshots)
                self.assertTrue(all(c.closed for c in self.opened));self.assertNotIn('complete',[p['stage'] for p in self.progress])
    def test_snapshot_preserves_scale_rotation_identity_and_ignores_focus(self):
        rows=[output('A',-16,scale=2),output('B',20,width=48,height=32,scale=2,transform=1)]
        result=self.desktop.topology_from_hypr(rows)
        self.assertEqual(result[0].logical_size,(16,12));self.assertEqual(result[1].logical_size,(16,24))
        rows[0]['focused']=True;self.assertEqual(result,self.desktop.topology_from_hypr(rows))
        for field,value in [('scale',1.5),('x',-20),('transform',2),('serial','new'),('width',34)]:
            changed=copy.deepcopy(rows);changed[0][field]=value
            self.assertNotEqual(result,self.desktop.topology_from_hypr(changed))
    def test_invalid_ambiguous_or_unbounded_topology_rejected(self):
        for rows in ([],[output('A',0),output('A',32)],[output('A',0),output('B',0)],
                     [output('A',0,scale=0)],[output('A',0,scale=float('nan'))],[output('A',0,transform=9)],
                     [output('A',0,width=0)],[output(str(i),i*32) for i in range(17)],
                     [output('A',0,width=32000,height=32000)]):
            with self.subTest(rows=str(rows)[:100]):
                with self.assertRaises((ValueError,RuntimeError)):self.desktop.topology_from_hypr(rows)
    def test_rotation_and_mirrors_preserve_corner_pixels(self):
        image=frame(width=4,height=3)
        for x,y,color in [(0,0,'red'),(3,0,'green'),(0,2,'blue'),(3,2,'yellow')]:image.setPixelColor(x,y,QColor(color))
        # Expected top-left after the documented PipeWire→Gst orientations.
        corners=['red','blue','yellow','green','green','red','blue','yellow']
        for transform,color in enumerate(corners):
            oriented=self.desktop.orient_frame(image,transform)
            self.assertEqual(oriented.pixelColor(0,0),QColor(color),(transform,color))
            self.assertEqual((oriented.width(),oriented.height()),(3,4) if transform%2 else (4,3))
    def test_metadata_identity_and_raw_pixel_dimensions_required(self):
        outputs=self.desktop.topology_from_hypr(self.rows)
        valid=dict(mapping_id='A',source_type=1,size=[32,24],position=[0,0])
        self.assertEqual(self.desktop.match_output(valid,outputs,set()).name,'A')
        for delta in ({'mapping_id':''},{'mapping_id':'Z'},{'source_type':2},{'size':[16,12]}):
            with self.assertRaises(RuntimeError):self.desktop.match_output(dict(valid,**delta),outputs,set())
        with self.assertRaisesRegex(RuntimeError,'repetida'):self.desktop.match_output(valid,outputs,{'A'})
    def test_mixed_scale_composition_uses_authorized_mapping_not_portal_zero_position(self):
        from loomrec.portal_image import compose_frames
        rows=[output('A',-16,scale=2),output('B',0)]
        a,b=self.desktop.topology_from_hypr(rows)
        image=compose_frames([(frame(),a.composition_metadata()),(frame('blue'),b.composition_metadata())])
        self.assertEqual((image.width(),image.height()),(96,48))
        self.assertEqual(image.pixelColor(2,2),QColor('red'));self.assertEqual(image.pixelColor(90,2),QColor('blue'))



class CaptureFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        from PySide6.QtWidgets import QWidget
        from wybieshot.ui.capture_feedback import CaptureFeedback
        self.parent=QWidget();self.feedback=CaptureFeedback(self.parent)
    def tearDown(self):
        self.feedback.cancel();self.feedback.close();self.parent.deleteLater();self.app.processEvents()
    def test_cancel_button_and_escape_cancel_whole_sequence(self):
        import threading
        from PySide6.QtWidgets import QPushButton
        from loomrec.portal import PortalCancelled
        for escape in (False,True):
            self.feedback.cancelled.clear();ack=threading.Event()
            self.feedback.present((dict(stage='select',index=2,total=2,remaining=['B']),ack))
            self.assertTrue(self.feedback.dialog.isVisible())
            if escape:self.feedback.dialog.reject()
            else:next(b for b in self.feedback.dialog.findChildren(QPushButton) if b.text()=='Cancelar todo').click()
            self.assertTrue(ack.is_set());self.assertFalse(self.feedback.dialog.isVisible())
            with self.assertRaises(PortalCancelled):self.feedback.check()
    def test_continue_hides_before_worker_acknowledgement(self):
        import threading,time
        from PySide6.QtWidgets import QPushButton,QLabel
        ack=threading.Event();self.feedback.present((dict(stage='select',index=1,total=2,remaining=['A','B']),ack))
        text=self.feedback.dialog.findChild(QLabel).text()
        self.assertIn('1 de 2',text);self.assertIn('secuencia',text);self.assertIn('descarta toda',text)
        next(b for b in self.feedback.dialog.findChildren(QPushButton) if b.text()=='Continuar al portal').click()
        self.assertFalse(self.feedback.dialog.isVisible());self.assertFalse(ack.is_set())
        deadline=time.monotonic()+1
        while not ack.is_set() and time.monotonic()<deadline:self.app.processEvents();time.sleep(.005)
        self.assertTrue(ack.is_set());self.feedback.check()
    def test_worker_wait_is_cancelled_before_any_permission(self):
        import threading,time
        from loomrec.portal import PortalCancelled
        errors=[]
        def worker():
            try:self.feedback.report(dict(stage='select',index=1,total=2,remaining=['A','B']))
            except Exception as e:errors.append(e)
        thread=threading.Thread(target=worker);thread.start();deadline=time.monotonic()+1
        while self.feedback.dialog is None and time.monotonic()<deadline:self.app.processEvents();time.sleep(.005)
        self.assertIsNotNone(self.feedback.dialog);self.feedback.cancel();thread.join(timeout=1)
        self.assertFalse(thread.is_alive());self.assertIsInstance(errors[0],PortalCancelled)

    def test_window_cancellation_discards_result_without_autosave(self):
        import tempfile,time
        from pathlib import Path
        from wybieshot.ui.main import Window
        from wybieshot.storage import Storage
        from wybieshot.schema import CaptureRequest
        class Engine:
            def capture(self,request,**kwargs):
                kwargs['progress'](dict(stage='select',index=2,total=2,remaining=['B']))
                raise AssertionError('Cancellation must stop before producing a document')
        with tempfile.TemporaryDirectory() as folder,patch('loomrec.portal.is_wayland',return_value=True):
            window=Window(Storage(Path(folder)),Engine());window.busy=True
            window.pending_request=CaptureRequest(mode='desktop',include_cursor=True);window.capture_tick()
            deadline=time.monotonic()+2
            while (window._capture_feedback is None or window._capture_feedback.dialog is None) and time.monotonic()<deadline:self.app.processEvents();time.sleep(.005)
            self.assertIsNotNone(window._capture_feedback.dialog);window.cancel_capture()
            while window.jobs and time.monotonic()<deadline:self.app.processEvents();time.sleep(.005)
            self.assertEqual(window.jobs,[]);self.assertIsNone(window.document);self.assertFalse(window.busy)
            window.close();window.deleteLater();self.app.processEvents()

if __name__=='__main__':unittest.main()

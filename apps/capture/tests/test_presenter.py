"""Presentation layer: tools, numbering, undo and camera bubble geometry."""
import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from loomrec.ui.presenter import PresenterOverlay,BubbleCamera

APP=QApplication.instance() or QApplication([])


class PresenterTests(unittest.TestCase):
    def overlay(self,**kw):
        return PresenterOverlay([0,0,1280,720],place=lambda *a:True,**kw)

    def test_numbers_increment_and_undo_restores_counter(self):
        o=self.overlay();o.set_tool('number')
        for x in (100,200):o.shapes.append(('number',QPointF(x,100),o.color,o.next_number));o.next_number+=1
        self.assertEqual([s[3] for s in o.shapes],[1,2]);o.undo();self.assertEqual(o.next_number,2);o.clear();self.assertEqual((o.shapes,o.next_number),([],1))

    def test_bubble_stays_inside_and_shape_keeps_aspect(self):
        o=self.overlay(camera_device='/dev/video99',camera_style={'shape':'circle','corner':'top-left'})
        self.assertEqual(o.bubble.width(),o.bubble.height());o.toggle_shape()
        self.assertAlmostEqual(o.bubble.width()/o.bubble.height(),4/3,places=3)
        o.bubble.moveTopLeft(QPointF(5000,5000));o._clamp_bubble()
        self.assertLessEqual(o.bubble.right(),1280.01);self.assertLessEqual(o.bubble.bottom(),720.01)

    def test_bubble_camera_fills_frame_at_thirty_fps(self):
        _,args=BubbleCamera()._command('/dev/video0');vf=args[args.index('-vf')+1]
        self.assertIn('fps=30',vf);self.assertIn('crop=640:480',vf);self.assertNotIn('pad=',vf)



class RecorderIntegrationTests(unittest.TestCase):
    def test_countdown_opens_bubble_without_recording_camera_twice_and_cancel_closes(self):
        import tempfile,json,subprocess
        from unittest.mock import patch
        from loomrec.ui.main import Window
        from loomrec.library import Library
        monitors=json.dumps([{'name':'DP-1','x':1920,'y':0,'width':1920,'height':1080,'scale':1,'transform':0}])
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'XDG_CONFIG_HOME':root,'XDG_STATE_HOME':root,'HYPRLAND_INSTANCE_SIGNATURE':'fixture'}):
            w=Window(Library(root),False);w.timer.stop()
            w.pending_config=type('Config',(),{'camera':'/dev/video0'})()
            with patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,monitors,'')),patch('loomrec.ui.presenter.PresenterOverlay.present') as present:
                w.open_presenter([1920,0,1920,1080])
            present.assert_called_once()
            self.assertEqual(w.presenter.monitor,[1920,0,1920,1080]);self.assertEqual(w.presenter.camera_device,'/dev/video0')
            self.assertIsNone(w.pending_config.camera)
            presenter=w.presenter
            with patch.object(presenter,'shutdown') as shutdown:w.close_presenter()
            shutdown.assert_called_once();self.assertIsNone(w.presenter)
            w.close();w.deleteLater()


if __name__=='__main__':unittest.main()

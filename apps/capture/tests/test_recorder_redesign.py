"""Watch-only Wysun Recorder: camera bubble and no editing surface."""
import os,subprocess,tempfile,unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QPointF,Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from loomrec.render import camera_overlay
from loomrec.schema import Camera,camera_style

APP=QApplication.instance() or QApplication([])


def click(widget,x,kind=QMouseEvent.MouseButtonPress):
    event=QMouseEvent(kind,QPointF(x,widget.height()/2),QPointF(x,widget.height()/2),Qt.LeftButton,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(widget,event)


class CameraBubbleTests(unittest.TestCase):
    def test_style_validation_and_defaults(self):
        self.assertEqual(camera_style({}),{'shape':'circle','size':'medium','corner':'bottom-right'})
        with self.assertRaises(ValueError):camera_style({'shape':'hexagon'})
    def test_bubble_keeps_aspect_and_stays_inside_corner(self):
        chain,x,y=camera_overlay(Camera(),1920,1080)
        self.assertIn("crop='min(iw,ih)':'min(iw,ih)'",chain);self.assertIn('scale=302:302',chain)
        self.assertEqual((x+302<1920,y+302<1080,x>1500,y>700),(True,True,True,True))
        chain,x,y=camera_overlay(Camera(shape='rounded',size='small',corner='top-left'),1920,1080)
        self.assertIn('scale=288:216',chain);self.assertEqual((x,y),(37,37))
    def test_filters_run_in_ffmpeg_on_synthetic_frames(self):
        for camera in (Camera(),Camera(shape='rounded',corner='top-right')):
            chain,x,y=camera_overlay(camera,320,180)
            graph=f'[1:v]{chain}[cam];[0:v][cam]overlay=x={x}:y={y}[v]'
            result=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=s=320x180:d=0.2','-f','lavfi','-i','testsrc2=s=160x120:d=0.2',
                                   '-filter_complex',graph,'-map','[v]','-frames:v','1','-f','null','-'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()

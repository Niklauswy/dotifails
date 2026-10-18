"""Memory-only deterministic preview lifecycle tests. Never open a real camera."""
import os,sys,tempfile,time,unittest,shutil
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from loomrec.ui.camera_preview import CameraPreview


class SyntheticPreview(CameraPreview):
    def __init__(self):
        super().__init__();self.started=[];self.mode='live'
    def _command(self,device):
        self.started.append(device)
        if self.mode=='missing':return '/not/an/installed/program',[]
        if self.mode=='error':return shutil.which('python3'),['-c','import sys;sys.stderr.write("synthetic busy");sys.exit(1)']
        color='255,0,0' if device=='/dev/video0' else '0,255,0'
        # Deliberately split frame boundaries across pipe writes.
        code='import os,time,signal\n'
        if self.mode=='stubborn':code+='signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
        code+=f'frame=bytes([{color}])*320*180\n'
        code+='while True:\n for i in range(0,len(frame),1337): os.write(1,frame[i:i+1337])\n time.sleep(.08)\n'
        return shutil.which('python3'),['-u','-c',code]


class CameraPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):self.preview=SyntheticPreview();self.preview.show();self.app.processEvents()
    def wait(self,predicate,timeout=4):
        deadline=time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline:self.app.processEvents();time.sleep(.002)
        self.assertTrue(predicate(),'preview event timed out')
    def tearDown(self):
        done=[];self.preview.stop(lambda:done.append(True));self.wait(lambda:bool(done));self.preview.hide();self.preview.deleteLater();self.app.processEvents()
    def test_immediate_start_live_rgb_and_release_fence(self):
        p=self.preview;frames=[];p.frameReady.connect(frames.append);p.set_device('/dev/video0')
        self.assertEqual(p.state,'loading');self.wait(lambda:bool(frames));self.assertEqual(p.state,'live')
        self.assertEqual(frames[-1].pixelColor(100,50).getRgb()[:3],(255,0,0))
        self.assertLess(len(p._buffer),p.FRAME_BYTES)
        done=[];p.stop(lambda:done.append((p.is_running,p._process)))
        self.wait(lambda:bool(done));self.assertEqual(done,[(False,None)]);self.assertTrue(p.canvas.image.isNull())
    def test_switch_waits_for_prior_exit_and_off_releases(self):
        p=self.preview;p.set_device('/dev/video0');self.wait(lambda:p.state=='live');old=p._process
        p.set_device('/dev/video1');self.assertEqual(p.state,'stopping');self.assertEqual(len(p.started),1)
        self.wait(lambda:p.state=='live' and p.device=='/dev/video1')
        self.assertEqual(p.canvas.image.pixelColor(1,1).getRgb()[:3],(0,255,0));self.assertEqual(p.started,['/dev/video0','/dev/video1'])
        p.set_device(None);self.wait(lambda:p.state=='off');self.assertFalse(p.is_running)
    def test_switch_cancel_does_not_open_new_camera(self):
        p=self.preview;p.set_device('/dev/video0');self.wait(lambda:p.state=='live')
        p.set_device('/dev/video1');done=[];p.stop(lambda:done.append(True));self.wait(lambda:bool(done))
        self.assertEqual(p.started,['/dev/video0']);self.assertFalse(p.is_running)
    def test_errors_missing_executable_and_disconnect(self):
        p=self.preview;p.mode='missing';p.set_device('/dev/video0');self.wait(lambda:p.state=='error');self.assertIn('FFmpeg',p.status.text());self.assertFalse(p.is_running)
        p.mode='error';p.set_device('/dev/video0');self.wait(lambda:p.state=='error');self.assertIn('otra aplicación',p.status.text())
        p.mode='live';p.set_device('/dev/video0');self.wait(lambda:p.state=='live');p._process.kill();self.wait(lambda:p.state=='error');self.assertFalse(p.is_running);self.assertTrue(p.canvas.image.isNull())
    def test_stubborn_process_killed_async_before_callback(self):
        p=self.preview;p.mode='stubborn';p.set_device('/dev/video0');self.wait(lambda:p.state=='live')
        done=[];start=time.monotonic();p.stop(lambda:done.append(True));self.assertLess(time.monotonic()-start,.1);self.assertFalse(done)
        self.wait(lambda:bool(done));self.assertFalse(p.is_running)
    def test_hide_releases_and_reopen_restarts(self):
        p=self.preview;p.set_device('/dev/video0');self.wait(lambda:p.state=='live');p.hide();self.wait(lambda:not p.is_running);self.assertEqual(p.state,'off')
        p.show();p.set_device('/dev/video0');self.wait(lambda:p.state=='live')
    def test_invalid_device_never_starts_and_timeout_releases(self):
        p=self.preview;p.set_device('https://example.com/camera');self.assertEqual(p.state,'error');self.assertFalse(p.started)
        p.set_device('/dev/video0');self.wait(lambda:p.state=='live');p._timeout();self.wait(lambda:p.state=='error');self.assertFalse(p.is_running)
    def test_command_is_bounded_pipe_only(self):
        program,args=CameraPreview._command(self.preview,'/dev/video0')
        self.assertEqual(program,'ffmpeg');self.assertEqual(args[-1],'pipe:1');self.assertIn('rgb24',args);self.assertIn('fps=10',args[args.index('-vf')+1]);self.assertIn('/dev/video0',args);self.assertNotIn('-framerate',args[:args.index('-i')]);self.assertNotIn('-video_size',args[:args.index('-i')])

    def test_late_events_from_previous_process_are_ignored(self):
        p=self.preview;current=QProcess(p);stale=QProcess(p)
        p._process=current;p._desired='/dev/video1';p.device='/dev/video1';p.state='live'
        p._buffer.extend(b'current');p._stderr.extend(b'current diagnostic')
        p._drain(stale);p._read_error(stale);p._finished(stale,1);p._process_error(stale,QProcess.FailedToStart)
        self.assertIs(p._process,current);self.assertEqual(p.state,'live');self.assertEqual(p.device,'/dev/video1')
        self.assertEqual(bytes(p._buffer),b'current');self.assertEqual(bytes(p._stderr),b'current diagnostic')
        p._desired=None

    def test_narrow_popup_reserves_caption_space_without_media(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QWidget,QVBoxLayout
        popup=QWidget(None,Qt.Popup);popup.setFixedWidth(300);layout=QVBoxLayout(popup)
        p=self.preview;p.hide();p.setParent(popup);layout.addWidget(p);p.show()
        p._set_state('loading');popup.adjustSize();popup.show();self.app.processEvents()
        p._set_state('live');self.app.processEvents()
        self.assertGreater(p.status.geometry().top(),p.canvas.geometry().bottom())
        self.assertGreaterEqual(p.status.height(),p.status.heightForWidth(p.status.width()))
        self.assertGreaterEqual(p.height(),p.canvas.minimumHeight()+p.status.minimumHeight()+6)
        popup.hide();p.setParent(None);popup.deleteLater()

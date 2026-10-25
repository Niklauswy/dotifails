import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from loomrec.capture import CaptureConfig
from loomrec.worker import capture_command
from loomrec.pipewire_bridge import pixel_crop,packed_frame

class WaylandTests(unittest.TestCase):
    def test_no_xwayland_capture_fallback(self):
        with patch.dict(os.environ,{'WAYLAND_DISPLAY':'wayland-test','DISPLAY':':42'},clear=True):
            config=CaptureConfig('/tmp/own',':42',[0,0,320,180]);self.assertEqual(config.selected_backend(),'portal')
            with self.assertRaisesRegex(RuntimeError,'PipeWire'):capture_command(config,Path('/tmp'),'s')
            config.backend='x11'
            with self.assertRaisesRegex(ValueError,'XWayland'):config.validate()
    def test_pipewire_and_audio_share_one_wallclock_origin(self):
        config=CaptureConfig('/tmp/own','portal',[0,0,320,180],backend='portal',mic='synthetic-mic',camera='/dev/synthetic')
        cmd=capture_command(config,Path('/tmp'),'s',origin=123,pipewire=(19,640,360))
        self.assertNotIn('x11grab',cmd);self.assertIn('pipe:19',cmd);self.assertIn('640x360',cmd)
        self.assertEqual(cmd.count('setpts=PTS-123/TB,fps=fps=30'),2);self.assertIn('asetpts=PTS-123/TB,aresample=async=1',cmd)
    def test_region_maps_negative_fractional_monitor_coordinates_to_pixels(self):
        metadata=dict(position=[-1280,0],size=[1280,720])
        self.assertEqual(pixel_crop(1920,1080,metadata,[-1200,20,100,100]),[120,30,150,150])
        with self.assertRaisesRegex(ValueError,'monitor autorizado'):pixel_crop(1920,1080,metadata,[0,0,100,100])
        with self.assertRaisesRegex(ValueError,'coordenadas'):pixel_crop(1920,1080,{},[0,0,100,100])
    def test_frame_copy_honors_stride_and_crop_without_resampling(self):
        rows=[bytes([n])*80 for n in range(20)]
        result=packed_frame(b''.join(rows),80,18,20,[1,2,16,16])
        self.assertEqual(len(result),16*16*4);self.assertEqual(result[:64],bytes([2])*64);self.assertEqual(result[-64:],bytes([17])*64)
    def test_missing_dependencies_do_not_probe_an_x_display(self):
        from loomrec.wayland_capture import PipeWireCapture
        with patch('loomrec.wayland_capture.Portal',side_effect=RuntimeError('portal unavailable')):
            with self.assertRaisesRegex(RuntimeError,'portal unavailable'):PipeWireCapture(CaptureConfig('','portal',[0,0,32,32],backend='portal'))

    def test_end_segment_orders_eof_then_sigint_for_live_audio_and_keeps_heartbeat(self):
        from unittest.mock import Mock
        import signal
        from loomrec.worker import end_portal_segment
        events=[];producer=Mock();producer.finish.side_effect=lambda:events.append('eof')
        process=Mock();process.poll.side_effect=[None,None,None,255];process.send_signal.side_effect=lambda value:events.append(value)
        with patch('loomrec.worker.time.sleep'):
            intentional=end_portal_segment(process,producer,lambda:events.append('heartbeat'),live_inputs=True)
        self.assertTrue(intentional);self.assertEqual(events[:2],['eof',signal.SIGINT]);self.assertIn('heartbeat',events)
    def test_new_pipewire_client_reopens_remote_without_new_consent(self):
        from unittest.mock import Mock
        from loomrec.portal import Portal
        first,first_write=os.pipe();second,second_write=os.pipe()
        portal=Portal.__new__(Portal);portal.disposed=False;portal.closed=False;portal.session='/own/session';portal.object=object();portal.fd=first
        api=Mock();api.OpenPipeWireRemote.return_value.take.return_value=second
        portal.dbus=Mock();portal.dbus.Interface.return_value=api
        try:
            self.assertEqual(portal.open_remote(),second)
            with self.assertRaises(OSError):os.fstat(first)
            self.assertIsNotNone(os.fstat(second));api.OpenPipeWireRemote.assert_called_once()
            self.assertEqual(portal.session,'/own/session');self.assertFalse(portal.closed)
        finally:
            os.close(second);os.close(first_write);os.close(second_write)
    def test_three_remote_cycles_keep_fd_count_stable_and_close_is_idempotent(self):
        from unittest.mock import Mock
        from loomrec.portal import Portal
        read,write=os.pipe();portal=Portal.__new__(Portal)
        portal.disposed=False;portal.closed=False;portal.session='/own/session';portal.object=object();portal.fd=None;portal._match=None;portal.bus=Mock()
        portal.dbus=Mock();portal.dbus.DBusException=RuntimeError
        api=Mock();api.OpenPipeWireRemote.return_value.take.side_effect=lambda:os.dup(read);portal.dbus.Interface.return_value=api
        try:
            expected=None;previous=None
            for _ in range(3):
                current=portal.open_remote()
                if previous is not None:
                    with self.assertRaises(OSError):os.fstat(previous)
                count=len(list(Path('/proc/self/fd').iterdir()))
                if expected is None:expected=count
                self.assertEqual(count,expected);previous=current
            portal.close();portal.close();portal.bus.close.assert_called_once();api.Close.assert_called_once()
            with self.assertRaises(OSError):os.fstat(current)
        finally:
            if portal.fd is not None:os.close(portal.fd)
            os.close(read);os.close(write)
    def test_cancelled_request_removes_signal_and_timers_without_remote_fd(self):
        from unittest.mock import Mock
        from loomrec.portal import Portal,PortalCancelled
        portal=Portal.__new__(Portal);portal.dbus=Mock();portal.GLib=Mock();portal.bus=Mock();portal.object=object();portal.on_wait=None
        portal.dbus.Dictionary.side_effect=lambda values,**_:dict(values)
        portal.GLib.timeout_add_seconds.return_value=1;portal.GLib.timeout_add.return_value=2
        portal.bus.get_unique_name.return_value=':1.9';handlers=[]
        def receiver(fn,**kw):handlers.append((fn,kw['path']));return Mock()
        portal.bus.add_signal_receiver.side_effect=receiver
        api=Mock()
        def create(options):handlers[-1][0](1,{});return handlers[-1][1]
        api.CreateSession.side_effect=create;portal.dbus.Interface.return_value=api
        with self.assertRaises(PortalCancelled):portal.request('org.freedesktop.portal.ScreenCast','CreateSession')
        self.assertEqual(portal.GLib.source_remove.call_count,2);api.OpenPipeWireRemote.assert_not_called()
    def test_pipewire_start_failure_includes_anonymous_stderr(self):
        from loomrec.wayland_capture import diagnostic_tail
        with tempfile.TemporaryFile() as log:
            log.write(b'x'*5000+b'\nmissing own module fixture\n')
            message=diagnostic_tail(log);self.assertLessEqual(len(message),4096);self.assertIn('missing own module fixture',message)


class WaylandImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
    def test_desktop_uses_full_screenshot_portal_not_single_stream(self):
        from unittest.mock import Mock
        from PySide6.QtGui import QImage,QColor
        from loomrec.portal_image import capture_frame
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'authorized.png';image=QImage(128,32,QImage.Format_ARGB32);image.fill(QColor('blue'));image.save(str(path),'PNG')
            portal=Mock();portal.screenshot.return_value=path
            with patch('loomrec.portal.Portal',return_value=portal),patch('loomrec.portal_image.PipeWireCapture') as stream:
                result=capture_frame('desktop',False)
            self.assertEqual((result.width(),result.height()),(128,32));self.assertEqual(result.pixelColor(5,5),QColor('blue'))
            portal.screenshot.assert_called_once_with(interactive=False);portal.close.assert_called_once();stream.assert_not_called();self.assertTrue(path.exists())
    def test_mpv_numeric_locale_is_normalized_before_creating_handle(self):
        from wysun_media import mpv
        with patch('wysun_media.mpv.locale.setlocale') as normalize:
            mpv.normalize_numeric_locale()
        normalize.assert_called_once_with(mpv.locale.LC_NUMERIC,'C')
    def test_multimonitor_composition_uses_topology_and_max_scale(self):
        from PySide6.QtGui import QImage,QColor
        from loomrec.portal_image import compose_frames
        red=QImage(32,24,QImage.Format_ARGB32);red.fill(QColor('red'))
        blue=QImage(64,48,QImage.Format_ARGB32);blue.fill(QColor('blue'))
        result=compose_frames([(red,dict(position=[-32,0],size=[32,24])),(blue,dict(position=[0,0],size=[32,24]))])
        self.assertEqual((result.width(),result.height()),(128,48));self.assertEqual(result.pixelColor(10,10),QColor('red'));self.assertEqual(result.pixelColor(100,10),QColor('blue'))
        with self.assertRaisesRegex(ValueError,'topología'):compose_frames([(red,{}),(blue,{})])
    def test_software_renderer_buffer_alignment_and_image_ownership(self):
        import ctypes as C
        from wysun_media.video import SoftwareVideoView
        seen=[]
        class Library:
            def mpv_render_context_render(self,context,params):
                size=C.cast(params[0].data,C.POINTER(C.c_int));stride=C.cast(params[2].data,C.POINTER(C.c_size_t)).contents.value
                self.address=params[3].data;self.count=stride*size[1];seen.append((self.address%64,stride%64))
                C.memset(self.address,127,self.count)
                for offset in range(3,self.count,4):C.c_ubyte.from_address(self.address+offset).value=255      # bgra: opaque
                return 0
        library=Library();image=SoftwareVideoView._frame(library,None,21,19)
        self.assertEqual(seen,[(0,0)]);self.assertEqual(image.width(),21);self.assertEqual(image.pixelColor(0,0).red(),127)
        buffer_owner=bytes(image.constBits());self.assertEqual(buffer_owner[:4],bytes([127,127,127,255]),'the image owns its pixels after the render buffer is gone')

if __name__=='__main__':unittest.main()

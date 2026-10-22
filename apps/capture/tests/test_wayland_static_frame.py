"""Single owned frame in appsrc memory, no EOS, portal, FFmpeg or devices."""
import json
import time
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class StaticFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import gi
            gi.require_version('Gst','1.0');gi.require_version('GstVideo','1.0')
            from gi.repository import Gst
        except (ImportError,ValueError):raise unittest.SkipTest('GStreamer GI unavailable')
        Gst.init(None);cls.Gst=Gst
        if any(not Gst.ElementFactory.find(name) for name in ('appsrc','videoconvert','appsink')):raise unittest.SkipTest('GStreamer base plugins unavailable')
    def frame(self,pts):
        buffer=self.Gst.Buffer.new_allocate(None,32*24*4,None)
        buffer.fill(0,bytes([255,0,0,255])*32*24);buffer.pts=pts;buffer.duration=self.Gst.CLOCK_TIME_NONE
        return buffer
    def bridge_frames(self,pts,update_after=None):
        from loomrec.pipewire_bridge import stream
        Gst=self.Gst;factory=Gst.ElementFactory.make
        class FinishedFixture(Exception):pass
        class Output:
            def __init__(self):self.header=None;self.frames=[];self.times=[]
            def write(self,data):
                if self.header is None:self.header=json.loads(data)
                else:
                    self.frames.append(bytes(data));self.times.append(time.monotonic())
                    if len(self.frames)==8:raise FinishedFixture()
                return len(data)
            def flush(self):pass
        output=Output();sent=[];timers=[]
        def make(name,*args):
            return factory('appsrc' if name=='pipewiresrc' else name,*args)
        def configure(source,fd,node,metadata):
            # Only the remote source is replaced. Actual product convert/
            # caps/appsink/packing/repetition and shutdown run unchanged.
            source.set_property('is-live',True);source.set_property('format',Gst.Format.TIME)
            source.set_property('caps',Gst.Caps.from_string('video/x-raw,format=BGRA,width=32,height=24,framerate=0/1,max-framerate=120/1'))
            def update():
                buffer=self.frame(pts+int(update_after*Gst.SECOND));buffer.fill(0,bytes([0,0,255,255])*32*24)
                sent.append(buffer.pts);source.emit('push-buffer',buffer)
            def need_data(source,_length):
                if not sent:
                    sent.append(pts);source.emit('push-buffer',self.frame(pts))
                    if update_after is not None:
                        timer=threading.Timer(update_after,update);timers.append(timer);timer.start()
            source.connect('need-data',need_data)
        try:
            with patch.object(Gst.ElementFactory,'make',side_effect=make),patch('loomrec.pipewire_bridge.configure_pipewire_source',side_effect=configure),patch('loomrec.pipewire_bridge.sys.stdout',SimpleNamespace(buffer=output)):
                with self.assertRaises(FinishedFixture):stream(-1,42,{},15)
        finally:
            for timer in timers:timer.cancel();timer.join(timeout=1)
        self.assertEqual((output.header['width'],output.header['height']),(32,24));self.assertEqual(len(output.frames),8)
        self.assertGreaterEqual(output.times[-1]-output.times[0],.35)
        self.assertTrue(all(b>a for a,b in zip(output.times,output.times[1:])))
        return output,sent
    def test_product_bridge_emits_and_repeats_static_frame_without_second_input(self):
        for pts in (0,75846442223914):
            with self.subTest(pts=pts):
                output,sent=self.bridge_frames(pts)
                self.assertEqual(sent,[pts])
                self.assertTrue(all(frame==bytes([255,0,0,255])*32*24 for frame in output.frames))
                # Seven elapsed intervals and eight frames/15 fps, not one frame.
    def test_variable_fps_updates_replace_repeated_frame_after_idle(self):
        output,sent=self.bridge_frames(0,update_after=.2)
        self.assertEqual(len(sent),2);self.assertEqual(output.frames[0],bytes([255,0,0,255])*32*24)
        self.assertEqual(output.frames[-1],bytes([0,0,255,255])*32*24)
        self.assertGreater(sum(frame==output.frames[0] for frame in output.frames),1)
        self.assertGreater(sum(frame==output.frames[-1] for frame in output.frames),1)

if __name__=='__main__':unittest.main()

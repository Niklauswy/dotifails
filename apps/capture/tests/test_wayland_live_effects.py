"""Only owned QImage bytes and temporary telemetry; no media/input/root runtime."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from loomrec.cursor import effect_settings
from loomrec.live_effects import TraceState,TraceFollower,paint_frame
from loomrec.pipewire_bridge import packed_frame
from loomrec.wayland_pointer import native_point

SETTINGS=effect_settings(dict(preset='trail'))

class LiveEffectsTests(unittest.TestCase):
    def state(self,w=96,h=80):
        state=TraceState(w,h);state.accept(dict(version=1,width=w,height=h,origin=100.,native_cursor_embedded=True));return state
    def test_coordinates_negative_monitor_scale_and_region_after_stride_crop(self):
        # 1.5x monitor at negative logical coordinates, region starts inside it.
        crop=[30,12,96,80];point=native_point([-1240,20],dict(position=[-1280,0],size=[1280,720]),[1920,1080],crop)
        self.assertEqual(point,(30,18))
        stride=1920*4+16;data=bytes([255])*(stride*1080)
        frame=packed_frame(data,stride,1920,1080,crop);state=self.state();state.accept([0,*point,0])
        result=paint_frame(frame,96,80,SETTINGS,state.snapshot(),now=100.1)
        self.assertEqual(len(result),96*80*4);self.assertNotEqual(result,frame);self.assertEqual(data,bytes([255])*len(data))
        self.assertEqual(result[-4:],frame[-4:])
    def test_epoch_pause_exit_stale_and_no_double_arrow(self):
        frame=bytes([255])*96*80*4;state=self.state();state.accept([0,40,30,0])
        self.assertIs(paint_frame(frame,96,80,SETTINGS,state.snapshot(),now=99),frame)
        self.assertIs(paint_frame(frame,96,80,SETTINGS,state.snapshot(),now=100.6),frame)
        settings=effect_settings(dict(preset='presentation',halo=False,clicks=False,trail=False))
        self.assertEqual(paint_frame(frame,96,80,settings,state.snapshot(),now=100.1),frame) # no second arrow
        state.accept([.2,None,None,0])
        self.assertIs(paint_frame(frame,96,80,SETTINGS,state.snapshot(),now=100.21),frame)
        state.accept([.4,40,30,0]);self.assertNotEqual(paint_frame(frame,96,80,SETTINGS,state.snapshot(),now=100.41),frame)
    def test_click_pulse_fades_and_trail_does_not_bridge_exit(self):
        frame=bytes([255])*96*80*4;state=self.state();state.accept([0,40,30,0]);state.accept([0,40,30,1])
        settings=effect_settings(dict(preset='presentation',halo=False,clicks=True,trail=False))
        self.assertNotEqual(paint_frame(frame,96,80,settings,state.snapshot(),now=100.1),frame)
        self.assertEqual(paint_frame(frame,96,80,settings,state.snapshot(),now=100.41),frame)
        state.accept([.2,None,None,0]);state.accept([.3,70,60,0])
        settings=effect_settings(dict(preset='trail',halo=False,clicks=False,trail=True))
        self.assertEqual(paint_frame(frame,96,80,settings,state.snapshot(),now=100.301),frame)
    def test_strict_timestamp_dimensions_event_and_bounded_state(self):
        for header in [dict(version=1,width=95,height=80,origin=100,native_cursor_embedded=True),dict(version=1,width=96,height=80,origin=float('nan'),native_cursor_embedded=True)]:
            with self.assertRaises(ValueError):TraceState(96,80).accept(header)
        for event in [[0,96,0,0],[0,0,0,30],[float('nan'),0,0,0],[0,None,None,1]]:
            with self.assertRaises(ValueError):self.state().accept(event)
        state=self.state();state.accept([1,0,0,0])
        with self.assertRaises(ValueError):state.accept([.5,0,0,0])
        for n in range(1000):state.accept([1+n/100,0,0,0]);state.accept([1+n/100,0,0,1])
        self.assertEqual(len(state.points),512);self.assertEqual(len(state.clicks),128)
    def test_follower_incremental_json_nonblocking_snapshot_and_baked_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            trace=Path(folder)/'trace';marker=Path(folder)/'marker'
            follower=TraceFollower(trace,96,80,marker,SETTINGS)
            try:
                self.assertTrue(json.loads(marker.read_text())['baked'])
                with trace.open('wb',buffering=0) as stream:
                    stream.write((json.dumps(dict(version=1,width=96,height=80,origin=100,native_cursor_embedded=True))+'\n[0,40,').encode())
                    time.sleep(.03);self.assertIsNone(follower.error)
                    stream.write(b'30,0]\n')
                    deadline=time.monotonic()+1
                    while not follower.state.points and time.monotonic()<deadline:time.sleep(.01)
                    with patch('loomrec.live_effects.os.read',side_effect=AssertionError('render must not read files')):
                        frame=bytes([255])*96*80*4
                        self.assertNotEqual(paint_frame(frame,96,80,SETTINGS,follower.snapshot(),now=100.1),frame)
                    follower.lock.acquire()
                    try:self.assertIsNone(follower.snapshot())
                    finally:follower.lock.release()
                    stream.write(b'x'*8193)
                    deadline=time.monotonic()+1
                    while not follower.error and time.monotonic()<deadline:time.sleep(.01)
                    self.assertIsNotNone(follower.error)
            finally:follower.close()
            self.assertFalse(follower.thread.is_alive());self.assertTrue(json.loads(marker.read_text()).get('error'))
    def test_baked_segment_does_not_apply_trace_again_on_export(self):
        from loomrec.capture import CaptureConfig,append_segment
        from loomrec.schema import Project
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'s.cursor.jsonl').write_text('owned synthetic trace')
            (root/'s.cursor-live.json').write_text(json.dumps(dict(baked=True)))
            info=dict(streams=[dict(codec_type='video',width=96,height=80,avg_frame_rate='12/1')],format=dict(duration='1'))
            project=Project();config=CaptureConfig(folder,'portal',[0,0,96,80],backend='portal',cursor_effects=dict(preset='trail'))
            with patch('loomrec.capture.probe',return_value=info):append_segment(project,root,'s',config)
            self.assertTrue(project.sources[0].cursor_baked);self.assertIsNone(project.sources[0].cursor_path)
    def test_packed_odd_width_source_is_immutable(self):
        w,h=97,81;frame=bytes([32,64,128,255])*w*h;state=self.state(w,h);state.accept([0,30,30,0])
        result=paint_frame(frame,w,h,SETTINGS,state.snapshot(),now=100.1)
        self.assertEqual(len(result),len(frame));self.assertEqual(frame,bytes([32,64,128,255])*w*h)
        self.assertEqual(result[-4:],frame[-4:])

if __name__=='__main__':unittest.main()

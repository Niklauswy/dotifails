"""Mouse-only fixtures: pure broker policy, synthetic trace and fake IPC only."""
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock,patch
from loomrec.wayland_pointer import native_point,NativePointerReader
from loomrec.cursor import CursorRecorder,write_ass

SOURCE=Path(__file__).resolve().parents[1]/'privileged/wysun-pointer-helper'
loader=importlib.machinery.SourceFileLoader('wysun_pointer_fixture',str(SOURCE));spec=importlib.util.spec_from_loader(loader.name,loader);helper=importlib.util.module_from_spec(spec);loader.exec_module(helper)

class MouseOnlyTests(unittest.TestCase):
    def test_identity_session_lease_and_kernel_mouse_only(self):
        identity=helper.Identity(1000,123,9);session=dict(Active=True,LockedHint=False,Remote=False,State='active',Type='wayland',Class='user',User=[1000,'/user'],Seat=['seat0','/seat'])
        now=[0.];guard=helper.Guard(identity,(123,1000,1000),lambda _:identity,lambda _:session,clock=lambda:now[0]);self.assertEqual(guard.check(),'seat0')
        now[0]=4
        with self.assertRaises(PermissionError):guard.touch()
        now[0]=0
        with self.assertRaises(PermissionError):guard.check()
        mask=1<<272
        def bitmap(value):
            parts=[];bits=struct.calcsize('@L')*8
            while value:parts.insert(0,format(value&((1<<bits)-1),'x'));value>>=bits
            return ' '.join(parts)
        self.assertTrue(helper.pointer_capabilities(bitmap(mask)));self.assertFalse(helper.pointer_capabilities(bitmap(mask|(1<<30))))
        self.assertFalse(helper.allowed_device(dict(ID_INPUT_MOUSE='1',ID_INPUT_KEYBOARD='1'),'seat0'))
    def test_opened_fd_capabilities_reject_hotplug_keyboard_before_read(self):
        import stat
        from types import SimpleNamespace
        identity=SimpleNamespace(st_mode=stat.S_IFCHR|0o660,st_uid=0,st_rdev=7,st_dev=1,st_ino=9)
        def fake_ioctl(fd,request,data,mutate):
            self.assertEqual(fd,123);self.assertEqual(request&0xff,0x21);data[30//8]|=1<<(30%8)
            data[272//8]|=1<<(272%8)
        with patch.object(helper.Path,'lstat',return_value=identity),patch.object(helper.os,'open',return_value=123),patch.object(helper.os,'fstat',return_value=identity),patch.object(helper.os,'close') as close,patch.object(helper.fcntl,'ioctl',side_effect=fake_ioctl),patch.object(helper.os,'read') as read:
            with self.assertRaises(PermissionError):helper.open_device(Path('/dev/input/event42'),7)
            close.assert_called_once_with(123);read.assert_not_called()
        def mouse_ioctl(fd,request,data,mutate):data[272//8]|=1<<(272%8)
        with patch.object(helper.fcntl,'ioctl',side_effect=mouse_ioctl):self.assertTrue(helper.opened_pointer_capabilities(123))
    def test_decoder_discards_keyboard_msc_and_repeat_and_handles_truncated_event(self):
        def event(kind,code,value):return helper.EVENT.pack(100,500,kind,code,value)
        payload=event(1,30,1)+event(4,4,30)+event(1,272,2)+event(1,272,1)+event(1,273,0)
        events,tail=helper.decode_events(payload[:-1]);self.assertEqual(events,[dict(t=100.0005,button=1,value=1)]);self.assertEqual(len(tail),helper.EVENT.size-1)
        events,tail=helper.decode_events(tail+payload[-1:]);self.assertEqual(events,[dict(t=100.0005,button=3,value=0)]);self.assertFalse(tail)
        self.assertEqual(set(events[0]),{'t','button','value'})
    def test_native_coordinates_scale_negative_and_region_limits(self):
        metadata=dict(position=[-1280,0],size=[1280,720]);size=[1920,1080];crop=[120,30,150,150]
        self.assertEqual(native_point([-1190,30],metadata,size,crop),(15,15));self.assertIsNone(native_point([0,20],metadata,size,crop))
        with self.assertRaises(ValueError):native_point([0,0],{},size,crop)
    def test_native_trace_exports_halo_click_and_trail_without_second_arrow(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'cursor.jsonl';recorder=None
            reader=Mock()
            def position():recorder.stop_event.set();return (20,20)
            reader.position.side_effect=position;reader.clicks.return_value=[1]
            recorder=CursorRecorder(path,'',(0,0,64,48),dict(preset='trail'),reader=reader,native_cursor=True);recorder.origin=100
            with patch('loomrec.cursor.time.time',side_effect=[100.0,100.2]):recorder._run()
            header=json.loads(path.read_text().splitlines()[0]);self.assertTrue(header['native_cursor_embedded']);self.assertEqual(recorder.error,None);reader.close.assert_called_once()
            out=Path(folder)/'effects.ass';write_ass(path,out,0,.2,dict(preset='trail'));text=out.read_text()
            self.assertIn('Dialogue:',text);self.assertNotIn('0.00 27.00',text)
            events=[json.loads(line) for line in path.read_text().splitlines()[1:]];self.assertTrue(any(event[-1]==1 for event in events));self.assertTrue(all(len(event)==4 for event in events))
    def test_native_reader_uses_only_injected_position_and_mouse_broker(self):
        broker=Mock();broker.clicks.return_value=[1]
        reader=NativePointerReader(broker,dict(position=[0,0],size=[32,24]),[64,48],[0,0,64,48],position=lambda:(10,10))
        self.assertEqual(reader.position(),(20,20));self.assertEqual(reader.clicks(),[1]);reader.close();broker.pause.assert_called_once()
    def test_privileged_entry_refuses_user_source_without_any_device_access(self):
        with patch.object(helper.os,'geteuid',return_value=1000),patch.object(helper,'devices_for_seat') as devices:
            with self.assertRaises(PermissionError):helper.verify_entry()
            devices.assert_not_called()

if __name__=='__main__':unittest.main()

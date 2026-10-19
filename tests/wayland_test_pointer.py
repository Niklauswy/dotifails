"""Persistent virtual pointer for the guarded synthetic compositor, no devices.

Wire requests follow wlr-virtual-pointer-unstable-v1 version2. This test client
keeps the seat/pointer alive across move/down/up, unlike one-shot utilities.
"""
import os
from pathlib import Path
import socket
import struct
import time


class SyntheticPointer:
    def __init__(self,env):
        runtime=Path(env['XDG_RUNTIME_DIR']).resolve();display=env['WAYLAND_DISPLAY']
        if runtime.parent.parent!=Path('/tmp') or not runtime.parent.name.startswith('ws-') or runtime.name!='r' or '/' in display:
            raise RuntimeError('Synthetic pointer requires the private /tmp/ws-*/r display')
        self.socket=socket.socket(socket.AF_UNIX);self.socket.settimeout(3);self.socket.connect(str(runtime/display))
        pid,uid,_=struct.unpack('3i',self.socket.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        executable=Path(f'/proc/{pid}/exe').resolve()
        if uid!=os.getuid() or executable.name!='Hyprland' or not str(executable).startswith('/tmp/'):
            self.socket.close();raise RuntimeError('Unexpected synthetic compositor peer')
        self.pending=b'';self.sequence=2;self.globals={}
        self.send(1,1,struct.pack('I',2));self.roundtrip()
        manager=self.bind('zwlr_virtual_pointer_manager_v1',2)
        seat=self.bind('wl_seat',1);self.seat=seat;output=self.bind('wl_output',1)
        self.pointer=self.allocate();self.send(manager,2,struct.pack('III',seat,output,self.pointer));self.roundtrip()
    def allocate(self):self.sequence+=1;return self.sequence
    @staticmethod
    def string(value):
        data=value.encode()+b'\0';return struct.pack('I',len(data))+data+b'\0'*((-len(data))%4)
    def send(self,obj,opcode,body=b''):
        self.socket.sendall(struct.pack('II',obj,((len(body)+8)<<16)|opcode)+body)
    def bind(self,interface,version):
        name,available=self.globals[interface];obj=self.allocate()
        self.send(2,0,struct.pack('I',name)+self.string(interface)+struct.pack('II',min(version,available),obj));return obj
    def roundtrip(self):
        callback=self.allocate();self.send(1,0,struct.pack('I',callback))
        while True:
            while len(self.pending)<8:self.pending+=self.socket.recv(65536)
            obj,word=struct.unpack('II',self.pending[:8]);size=word>>16;opcode=word&65535
            if size<8:raise RuntimeError('Invalid Wayland message')
            while len(self.pending)<size:
                chunk=self.socket.recv(65536)
                if not chunk:raise RuntimeError('Synthetic compositor disconnected')
                self.pending+=chunk
            body=self.pending[8:size];self.pending=self.pending[size:]
            if obj==1 and opcode==0:raise RuntimeError('Wayland protocol error: '+repr(body))
            if obj==2 and opcode==0:
                name,length=struct.unpack('II',body[:8]);interface=body[8:8+length-1].decode();offset=8+((length+3)//4)*4
                version=struct.unpack('I',body[offset:offset+4])[0];self.globals[interface]=(name,version)
            if obj==callback and opcode==0:return
    def click(self,x,y,button=272):
        now=lambda:int(time.monotonic()*1000)&0xffffffff
        # Remapping/hiding another surface can clear pointerFocus without
        # changing cursorpos. Deliver actual movement before the next click.
        self.send(self.pointer,1,struct.pack('IIIII',now(),min(1279,x+120),min(799,y+100),1280,800));self.send(self.pointer,4);self.roundtrip()
        self.send(self.pointer,1,struct.pack('IIIII',now(),x,y,1280,800));self.send(self.pointer,4);self.roundtrip();time.sleep(.15)
        for state in (1,0):
            self.send(self.pointer,2,struct.pack('III',now(),button,state));self.send(self.pointer,4);self.roundtrip();time.sleep(.08)
    def move(self,x,y):
        if not 0<=x<1280 or not 0<=y<800:raise ValueError('Outside the owned synthetic output')
        self.send(self.pointer,1,struct.pack('IIIII',int(time.monotonic()*1000)&0xffffffff,x,y,1280,800))
        self.send(self.pointer,4);self.roundtrip()
    def close(self):
        try:self.send(self.pointer,8);self.roundtrip()
        finally:self.socket.close()

    def keyboard(self):
        """Use a standard XKB keymap and Linux keycodes, never physical evdev."""
        import array
        import ctypes
        manager=self.bind('zwp_virtual_keyboard_manager_v1',1)
        self.keyboard_id=self.allocate()
        # The already bound wl_seat is retained for the entire client lifetime.
        self.send(manager,0,struct.pack('II',self.seat,self.keyboard_id))
        xkb=ctypes.CDLL('libxkbcommon.so.0')
        xkb.xkb_context_new.argtypes=[ctypes.c_int];xkb.xkb_context_new.restype=ctypes.c_void_p
        xkb.xkb_keymap_new_from_names.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int];xkb.xkb_keymap_new_from_names.restype=ctypes.c_void_p
        xkb.xkb_keymap_get_as_string.argtypes=[ctypes.c_void_p,ctypes.c_int];xkb.xkb_keymap_get_as_string.restype=ctypes.c_void_p
        xkb.xkb_keymap_unref.argtypes=[ctypes.c_void_p];xkb.xkb_context_unref.argtypes=[ctypes.c_void_p]
        context=xkb.xkb_context_new(0);keymap=xkb.xkb_keymap_new_from_names(context,None,0)
        if not keymap:raise RuntimeError('Cannot compile test XKB keymap')
        address=xkb.xkb_keymap_get_as_string(keymap,1)
        try:data=ctypes.string_at(address)+b'\0'
        finally:
            libc=ctypes.CDLL(None);libc.free.argtypes=[ctypes.c_void_p];libc.free(address)
            xkb.xkb_keymap_unref(keymap);xkb.xkb_context_unref(context)
        fd=os.memfd_create('wysun-synthetic-keymap',os.MFD_CLOEXEC)
        try:
            os.write(fd,data);os.lseek(fd,0,os.SEEK_SET)
            body=struct.pack('II',1,len(data));message=struct.pack('II',self.keyboard_id,(16<<16))+body
            self.socket.sendmsg([message],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))])
        finally:os.close(fd)
        self.roundtrip();time.sleep(.2)

    def chord(self,shift=False):
        if not hasattr(self,'keyboard_id'):self.keyboard()
        now=lambda:int(time.monotonic()*1000)&0xffffffff
        def key(code,state):self.send(self.keyboard_id,1,struct.pack('III',now(),code,state))
        def mods(value):self.send(self.keyboard_id,2,struct.pack('IIII',value,0,0,0));self.roundtrip();time.sleep(.1)
        key(125,1)
        if shift:key(42,1)
        mods(65 if shift else 64)
        key(57,1);key(57,0);self.roundtrip();time.sleep(.1)
        if shift:key(42,0)
        key(125,0);mods(0)

    def press(self,code,modifiers=0):
        """A standard Linux keycode on our persistent virtual keyboard only."""
        if not hasattr(self,'keyboard_id'):self.keyboard()
        if code not in (1,28,30,38,46):raise ValueError('Key outside the fixture allowlist')
        if modifiers not in (0,4,8):raise ValueError('Modifier outside the fixture allowlist')
        self.send(self.keyboard_id,2,struct.pack('IIII',modifiers,0,0,0));self.roundtrip();time.sleep(.05)
        for state in (1,0):
            self.send(self.keyboard_id,1,struct.pack('III',int(time.monotonic()*1000)&0xffffffff,code,state));self.roundtrip();time.sleep(.05)
        self.send(self.keyboard_id,2,struct.pack('IIII',0,0,0,0));self.roundtrip()

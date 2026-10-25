"""Run the real Plymouth script interpreter with display-only test doubles."""
import ctypes as C
from pathlib import Path

PRELUDE='''
fun noop() {}
Window.GetWidth=fun () { return 1024; };
Window.GetHeight=fun () { return 768; };
Window.GetX=fun () { return 0; };
Window.GetY=fun () { return 0; };
Window.SetBackgroundTopColor=noop;
Window.SetBackgroundBottomColor=noop;
Math.Int=fun (value) { return value - value%1; };
fun make_image(name) {
    local.picture.name=name;
    picture.Scale=fun (w,h) { return this; };
    picture.GetWidth=fun () { return 640; };
    picture.GetHeight=fun () { return 300; };
    return picture;
}
Image.Text=fun (text,r,g,b) { return make_image(text); };
Image |= make_image;
fun Sprite(image) {
    local.sprite.image=image;
    sprite.SetImage=fun (image) { this.image=image; };
    sprite.SetPosition=fun (x,y,z) { this.x=x; this.y=y; this.z=z; };
    sprite.SetOpacity=fun (value) { this.opacity=value; };
    sprite.SetZ=noop;
    return sprite;
}
Plymouth.GetMode=fun () { return global.test_mode; };
Plymouth.SetRefreshFunction=noop;
Plymouth.SetDisplayPasswordFunction=noop;
Plymouth.SetDisplayQuestionFunction=noop;
Plymouth.SetDisplayNormalFunction=noop;
Plymouth.SetDisplayMessageFunction=noop;
Plymouth.SetHideMessageFunction=noop;
Plymouth.SetMessageFunction=noop;
Plymouth.SetQuitFunction=noop;
'''

class State(C.Structure):
    _fields_=[('user_data',C.c_void_p),('global_',C.c_void_p),('local',C.c_void_p),('this',C.c_void_p)]
class Return(C.Structure):
    _fields_=[('type',C.c_int),('object',C.c_void_p)]

class Engine:
    def __init__(self):
        candidates=list(Path('/usr/lib').glob('*/plymouth/script.so'))
        if not candidates:raise FileNotFoundError('Plymouth interpreter unavailable')
        self.lib=C.CDLL(str(candidates[0]))
        for name,args,result in (
            ('script_state_new',[C.c_void_p],C.POINTER(State)),
            ('script_state_destroy',[C.POINTER(State)],None),
            ('script_parse_string',[C.c_char_p,C.c_char_p],C.c_void_p),
            ('script_parse_op_free',[C.c_void_p],None),
            ('script_execute',[C.POINTER(State),C.c_void_p],Return),
            ('script_obj_hash_get_string',[C.c_void_p,C.c_char_p],C.c_void_p),
            ('script_obj_unref',[C.c_void_p],None),
            ('script_lib_math_setup',[C.POINTER(State)],C.c_void_p),
            ('script_lib_math_destroy',[C.c_void_p],None),
            ('script_lib_string_setup',[C.POINTER(State)],C.c_void_p)):
            f=getattr(self.lib,name);f.argtypes=args;f.restype=result
        self.free=C.CDLL(None).free;self.free.argtypes=[C.c_void_p]
        self.state=self.lib.script_state_new(None);self.programs=[]
        # Plymouth's own Math and String libraries; display objects stay test doubles.
        self.math=self.lib.script_lib_math_setup(self.state)
        self.strings=self.lib.script_lib_string_setup(self.state)
    def execute(self,source):
        op=self.lib.script_parse_string(source.encode(),b'boot-theme-test')
        if not op:raise AssertionError('Script parse failed')
        self.programs.append(op)
        result=self.lib.script_execute(self.state,op)
        if result.object:self.lib.script_obj_unref(result.object)
    def string(self,name):
        ptr=self.lib.script_obj_hash_get_string(self.state.contents.global_,name.encode())
        if not ptr:return None
        value=C.string_at(ptr).decode();self.free(ptr);return value
    def close(self):
        self.lib.script_lib_math_destroy(self.math)
        self.lib.script_state_destroy(self.state)
        for op in self.programs:self.lib.script_parse_op_free(op)

if __name__=='__main__':
    # Smoke run of every mode; tests/plymouth_preview.py paints full frames.
    import plymouth_preview
    for mode in ('boot','shutdown','reboot'):
        dump=plymouth_preview.run(mode,['for (j=0;j<60;j++) refresh();'])
        print(mode,len(dump.splitlines()),'sprites')

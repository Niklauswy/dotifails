"""Optional desktop integration; never writes Wysun files or changes panels."""
from pathlib import Path
import json
import os
import subprocess


def theme_id():
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))
    for name in ('orbit', 'dotifails'):
        try:
            data = json.loads((config/name/'theme.json').read_text())
            return data.get('id', data.get('name', 'space-black'))
        except (OSError, ValueError): pass
    return 'space-black'



def concentration_lock(method):
    def guarded(self,*args,**kwargs):
        import fcntl
        root=Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'loomrec'
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        with (root/'concentration.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            return method(self,*args,**kwargs)
    return guarded


def shell_command():
    """The shell's Do Not Disturb switch (the shell owns notifications; there is no separate daemon)."""
    import shutil
    return shutil.which('wysun-shell') or str(Path.home()/'.local/bin/wysun-shell')


def dnd_state():
    """'true' or 'false', the same strings the lease file has always stored."""
    answer=json.loads(subprocess.check_output([shell_command(),'dnd','status'],text=True,timeout=3))
    return 'true' if answer.get('dnd') else 'false'


def set_dnd(value):
    subprocess.run([shell_command(),'dnd','on' if value=='true' else 'off'],check=True,timeout=3,capture_output=True)


class Concentration:
    """Restore exactly the prior pause state, without desktop reloads."""
    def __init__(self): self.previous = None; self.lease = None; self.token = None
    @concentration_lock
    def begin(self, project_dir=None):
        if self.previous is not None: return
        try:
            value = dnd_state()
            if value not in ('true','false'): return
            if project_dir is not None:
                import uuid,time
                from .schema import atomic_json
                self.lease=Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'loomrec/concentration.json'
                if self.lease.exists():
                    existing=json.loads(self.lease.read_text())
                    if self.active(existing):raise RuntimeError('Otra grabación controla el modo concentración')
                    if existing.get('previous') not in ('true','false'):raise ValueError('Estado de No molestar inválido')
                    set_dnd(existing['previous'])
                    self.lease.unlink()
                    value=existing['previous']
                self.token=uuid.uuid4().hex
                self.lease.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                atomic_json(self.lease,{'previous':value,'project_dir':str(project_dir),'pid':os.getpid(),'created':time.time(),'token':self.token})
                self.lease.chmod(0o600)
            self.previous = value
            set_dnd('true')
        except (OSError, subprocess.SubprocessError): pass
    @concentration_lock
    def restore(self):
        if self.previous is None: return
        if self.lease:
            if not self.lease.exists() or json.loads(self.lease.read_text()).get('token')!=self.token:
                self.previous=None;return
        value = self.previous
        set_dnd(value)
        self.previous = None
        if self.lease and self.lease.exists():
            data=json.loads(self.lease.read_text())
            if data.get('token')==self.token:self.lease.unlink()

    @staticmethod
    def active(data):
        import fcntl,time
        root=Path(data['project_dir']);lock=root/'capture.lock'
        if lock.exists():
            with lock.open('r') as handle:
                try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:return True
            return False
        if time.time()-data.get('created',0)<30:
            try:os.kill(data.get('pid',0),0);return True
            except OSError:pass
        return False

    @concentration_lock
    def recover(self):
        path=self.lease or Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'loomrec/concentration.json'
        if not path.exists():return False
        data=json.loads(path.read_text())
        if self.active(data):return False
        if data.get('previous') not in ('true','false'):raise ValueError('Estado de No molestar inválido')
        set_dnd(data['previous'])
        path.unlink();return True

    def watch(self):
        if self.lease and self.token:
            import sys
            subprocess.Popen([sys.executable,'-m','loomrec.integration','--watch-concentration',str(self.lease),self.token],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)


def shortcut_conflicts(text, chord):
    """Conservative: reject exact chords and any potentially matching brace binding."""
    from itertools import product
    import re
    def normalize(s): return tuple(sorted(x.strip().lower() for x in s.split('+')))
    expected = normalize(chord)
    for line in text.splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith('#'): continue
        parts = re.split(r'(\{[^{}]+\})',line)
        variants = [p[1:-1].split(',') if p.startswith('{') else [p] for p in parts]
        for combination in product(*variants):
            if normalize(''.join(combination)) == expected: return True
    return False


def add_shortcut(path, chord, command):
    """Opt-in only. Back up user configuration and never reload the session."""
    path = Path(path)
    old = path.read_text() if path.exists() else ''
    if shortcut_conflicts(old,chord): raise ValueError('El atajo ya está asignado; elige otro')
    if '\n' in chord or '\n' in command: raise ValueError('Atajo inválido')
    import time
    if path.exists():
        backup = path.with_name(path.name+f'.loomrec-{time.time_ns()}.bak')
        with backup.open('x') as f: f.write(old)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w') as f: f.write(old+f'\n# Wysun Recorder (manual reload)\n{chord}\n    {command}\n')


class GlobalKeys:
    def __new__(cls,callbacks):
        from .portal import is_wayland
        if is_wayland():
            from .portal_shortcuts import PortalKeys
            return PortalKeys(callbacks)
        return super().__new__(cls)
    """Scoped X11 grabs; conflicts fail closed and all grabs disappear on exit."""
    def __init__(self, callbacks):
        import ctypes as C
        import ctypes.util
        self.C=C; self.lib=C.CDLL(ctypes.util.find_library('X11'))
        x=self.lib
        x.XOpenDisplay.argtypes=[C.c_char_p]; x.XOpenDisplay.restype=C.c_void_p
        x.XDefaultRootWindow.argtypes=[C.c_void_p]; x.XDefaultRootWindow.restype=C.c_ulong
        x.XStringToKeysym.argtypes=[C.c_char_p]; x.XStringToKeysym.restype=C.c_ulong
        x.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong]; x.XKeysymToKeycode.restype=C.c_uint
        for name,args in [('XGrabKey',[C.c_void_p,C.c_int,C.c_uint,C.c_ulong,C.c_int,C.c_int,C.c_int]),('XUngrabKey',[C.c_void_p,C.c_int,C.c_uint,C.c_ulong]),('XSync',[C.c_void_p,C.c_int]),('XPending',[C.c_void_p]),('XNextEvent',[C.c_void_p,C.c_void_p]),('XCloseDisplay',[C.c_void_p])]: getattr(x,name).argtypes=args
        self.display=x.XOpenDisplay(None)
        if not self.display: raise RuntimeError('No se pudo abrir X11 para los atajos globales')
        self.root=x.XDefaultRootWindow(self.display); self.callbacks={}; self.grabbed=[]; self.errors=[]
        handler_type=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p)
        self.handler=handler_type(lambda *_:self.errors.append(True) or 0)
        x.XSetErrorHandler.argtypes=[C.c_void_p]; x.XSetErrorHandler.restype=C.c_void_p
        previous=x.XSetErrorHandler(C.cast(self.handler,C.c_void_p))
        try:
            for chord,callback in callbacks.items():
                mask,key=parse_chord(chord) if '+' in chord else (64|4|1,chord)
                code=x.XKeysymToKeycode(self.display,x.XStringToKeysym(key.encode()))
                if not code:self.errors.append(True);continue
                self.callbacks[(code,mask)]=callback
                for locks in (0,2,16,18):
                    mods=mask|locks  # Super + Control + Shift, tolerate Caps/Num Lock
                    x.XGrabKey(self.display,code,mods,self.root,False,1,1); self.grabbed.append((code,mods))
            x.XSync(self.display,False)
        finally: x.XSetErrorHandler(previous)
        if self.errors:
            self.close(); raise RuntimeError('Atajos Super+Ctrl+Shift+r/p/s/c/z/i ocupados. Libéralos antes de grabar.')
    def poll(self):
        C=self.C
        class KeyEvent(C.Structure):
            _fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),('display',C.c_void_p),('window',C.c_ulong),('root',C.c_ulong),('subwindow',C.c_ulong),('time',C.c_ulong),('x',C.c_int),('y',C.c_int),('x_root',C.c_int),('y_root',C.c_int),('state',C.c_uint),('keycode',C.c_uint),('same_screen',C.c_int)]
        while self.display and self.lib.XPending(self.display):
            event=(C.c_long*24)(); self.lib.XNextEvent(self.display,C.byref(event)); key=C.cast(event,C.POINTER(KeyEvent)).contents
            binding=(key.keycode,key.state & ~(2|16))
            if key.type==2 and binding in self.callbacks:self.callbacks[binding]()
    def close(self):
        if self.display:
            for code,mods in self.grabbed:self.lib.XUngrabKey(self.display,code,mods,self.root)
            self.lib.XCloseDisplay(self.display); self.display=None


DEFAULT_SHORTCUTS = {'record':'Super+Ctrl+Shift+r','pause':'Super+Ctrl+Shift+p',
    'stop':'Super+Ctrl+Shift+s','cancel':'Super+Ctrl+Shift+c',
    'rewind':'Super+Ctrl+Shift+z','status':'Super+Ctrl+Shift+i'}


def shortcut_settings(path=None):
    path=Path(path) if path else Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'loomrec/shortcuts.json'
    values=dict(DEFAULT_SHORTCUTS)
    if path.exists():
        custom=json.loads(path.read_text())
        if not isinstance(custom,dict) or set(custom)-set(values):raise ValueError('Configuración de atajos inválida: '+str(path))
        values.update(custom)
    bindings=[parse_chord(chord) for chord in values.values()]
    if len(set(bindings))!=len(bindings):raise ValueError('Los atajos deben ser distintos')
    return values


def parse_chord(chord):
    if not isinstance(chord,str):raise ValueError('El atajo debe ser texto')
    parts=[p.strip() for p in chord.split('+')]
    modifiers={'super':64,'ctrl':4,'control':4,'shift':1,'alt':8}
    if len(parts)<2 or not parts[-1]:raise ValueError('El atajo necesita modificador y tecla')
    mask=0
    for modifier in parts[:-1]:
        if modifier.lower() not in modifiers:raise ValueError('Modificador no admitido: '+modifier)
        mask|=modifiers[modifier.lower()]
    if mask&4 and mask&8 and parts[-1].upper().startswith('F') and parts[-1][1:].isdigit():
        raise ValueError('Ctrl+Alt+Fn está reservado para terminales virtuales')
    return mask,parts[-1]


if __name__=='__main__':
    import sys,time
    if len(sys.argv)==4 and sys.argv[1]=='--watch-concentration':
        lease=Path(sys.argv[2]);token=sys.argv[3]
        while lease.exists():
            try:
                data=json.loads(lease.read_text())
                if data.get('token')!=token:break
                if not Concentration.active(data):
                    state=Concentration();state.lease=lease;state.recover();break
            except (OSError,ValueError,subprocess.SubprocessError):pass
            time.sleep(1)

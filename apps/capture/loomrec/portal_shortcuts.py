"""Portal global controls. Native compositor consent replaces all X11 key grabs."""
import json
import sys
import uuid
from .portal import Portal


def serve(chords):
    p=Portal();dbus=p.dbus;iface='org.freedesktop.portal.GlobalShortcuts'
    try:
        result=p.request(iface,'CreateSession',options={'session_handle_token':'wysun_'+uuid.uuid4().hex})
        p.session=str(result['session_handle'])
        def activated(session,ident,*_):
            if str(session)==p.session:print(json.dumps({'activated':str(ident)}),flush=True)
        match=p.bus.add_signal_receiver(activated,signal_name='Activated',dbus_interface=iface,bus_name='org.freedesktop.portal.Desktop')
        shortcuts=dbus.Array([dbus.Struct((str(i),dbus.Dictionary({'description':'Wysun Recorder · '+chord,'preferred_trigger':chord.replace('Ctrl','CTRL').replace('Super','LOGO').replace('Shift','SHIFT')},signature='sv'))) for i,chord in enumerate(chords)],signature='(sa{sv})')
        bound=p.request(iface,'BindShortcuts',dbus.ObjectPath(p.session),shortcuts,'')
        print(json.dumps({'bound':[(str(k),str(v.get('trigger_description',''))) for k,v in bound.get('shortcuts',[])]}),flush=True)
        p.GLib.MainLoop().run()
    finally:p.close()


class PortalKeys:
    def __init__(self,callbacks):
        from PySide6.QtCore import QProcess
        self.callbacks=list(callbacks.values());self.buffer=bytearray();self.bound=[];self.error=''
        self.process=QProcess()
        self.process.start(sys.executable,['-P','-m','loomrec.portal_shortcuts',json.dumps(list(callbacks))])
    def poll(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b'\n' in self.buffer:
            line,_,rest=self.buffer.partition(b'\n');self.buffer=bytearray(rest)
            try:
                data=json.loads(line)
                if 'activated' in data:self.callbacks[int(data['activated'])]()
                if 'bound' in data:self.bound=data['bound']
            except (KeyError,ValueError,IndexError):pass
        if self.process.state()==self.process.NotRunning:
            self.error='Atajos del portal no disponibles; usa controles de la bandeja o wysun recorder --pause/--stop.'
    def close(self):
        self.process.terminate()
        if not self.process.waitForFinished(500):self.process.kill();self.process.waitForFinished(500)

if __name__=='__main__':
    try:serve(json.loads(sys.argv[1]))
    except Exception as exc:print(str(exc),file=sys.stderr);raise SystemExit(1)

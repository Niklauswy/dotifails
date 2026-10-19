"""XDG Desktop Portal client; consent and PipeWire handles stay in the worker.

No X11 fallback on Wayland. Never persists an FD, restore token or desktop image.
See org.freedesktop.portal.ScreenCast, Screenshot and Request specifications.
"""
import os
import uuid

BUS='org.freedesktop.portal.Desktop'
PATH='/org/freedesktop/portal/desktop'


def is_wayland():
    return os.environ.get('XDG_SESSION_TYPE')=='wayland' or bool(os.environ.get('WAYLAND_DISPLAY'))


class PortalCancelled(RuntimeError):pass


class Portal:
    def __init__(self):
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
        self.dbus=dbus;self.GLib=GLib
        self.bus=dbus.SessionBus(private=True,mainloop=DBusGMainLoop());self.bus.set_exit_on_disconnect(False)
        self.object=self.bus.get_object(BUS,PATH)
        self.session=None;self.fd=None;self.closed=False;self._match=None;self.on_wait=None;self.disposed=False

    def request(self, interface, method, *args, options=None, timeout=120):
        dbus=self.dbus;token='wysun_'+uuid.uuid4().hex
        sender=self.bus.get_unique_name()[1:].replace('.','_')
        path='/org/freedesktop/portal/desktop/request/'+sender+'/'+token
        loop=self.GLib.MainLoop();answer=[]
        def response(code,results):answer.append((int(code),results));loop.quit()
        match=self.bus.add_signal_receiver(response,signal_name='Response',dbus_interface='org.freedesktop.portal.Request',path=path,bus_name=BUS)
        timer=self.GLib.timeout_add_seconds(timeout,lambda:(loop.quit(),False)[1])
        waiting_error=[]
        def tick():
            try:
                if self.on_wait:self.on_wait()
            except BaseException as exc:waiting_error.append(exc);loop.quit();return False
            return True
        heartbeat=self.GLib.timeout_add(250,tick)
        try:
            values=dbus.Dictionary(options or {},signature='sv');values['handle_token']=token
            handle=getattr(dbus.Interface(self.object,interface),method)(*args,values)
            # A compliant portal uses the pre-subscribed path; older portals may return another.
            if str(handle)!=path:
                match.remove();match=self.bus.add_signal_receiver(response,signal_name='Response',dbus_interface='org.freedesktop.portal.Request',path=str(handle),bus_name=BUS)
            if not answer:loop.run()
            if not answer:
                try:dbus.Interface(self.bus.get_object(BUS,handle),'org.freedesktop.portal.Request').Close()
                except dbus.DBusException:pass
                if waiting_error:raise waiting_error[0]
                raise TimeoutError('El portal no respondió. Vuelve a seleccionar la fuente.')
            code,results=answer[0]
            if code==1:raise PortalCancelled('Selección cancelada en el portal')
            if code:raise RuntimeError('El portal rechazó la solicitud ('+str(code)+')')
            return results
        finally:
            match.remove()
            if self.GLib.MainContext.default().find_source_by_id(timer):self.GLib.source_remove(timer)
            if self.GLib.MainContext.default().find_source_by_id(heartbeat):self.GLib.source_remove(heartbeat)

    def screencast(self, source='monitor', cursor=True, multiple=False):
        dbus=self.dbus;iface='org.freedesktop.portal.ScreenCast'
        props=dbus.Interface(self.object,'org.freedesktop.DBus.Properties')
        types=int(props.Get(iface,'AvailableSourceTypes'))
        requested=2 if source=='window' else 1
        if not types&requested:raise RuntimeError('El portal no ofrece captura independiente de ventanas' if requested==2 else 'El portal no ofrece monitores')
        modes=int(props.Get(iface,'AvailableCursorModes'))
        mode=2 if cursor else 1
        if not modes&mode:raise RuntimeError('El portal no ofrece el modo de cursor solicitado')
        created=self.request(iface,'CreateSession',options={'session_handle_token':'wysun_'+uuid.uuid4().hex})
        self.session=str(created['session_handle'])
        self._match=self.bus.add_signal_receiver(lambda details:setattr(self,'closed',True),signal_name='Closed',dbus_interface='org.freedesktop.portal.Session',path=self.session,bus_name=BUS)
        try:
            self.request(iface,'SelectSources',dbus.ObjectPath(self.session),options={
                'types':dbus.UInt32(requested),'multiple':bool(multiple),'cursor_mode':dbus.UInt32(mode)})
            started=self.request(iface,'Start',dbus.ObjectPath(self.session),'')
            streams=started.get('streams',[])
            if not streams or (not multiple and len(streams)!=1):raise RuntimeError('Selecciona una sola fuente en el portal')
            self.streams=[(int(node),dict(metadata)) for node,metadata in streams]
            node,metadata=self.streams[0]
            if any(int(props.get('source_type',requested))!=requested for _,props in self.streams):raise RuntimeError('El portal devolvió otro tipo de fuente')
            self.open_remote()
            return int(node),metadata
        except BaseException:self.close();raise

    def open_remote(self):
        """Each PipeWire client gets a fresh protocol connection under same consent."""
        if self.disposed or self.closed or not self.session:raise RuntimeError('La sesión del portal ya no está disponible')
        dbus=self.dbus
        remote=dbus.Interface(self.object,'org.freedesktop.portal.ScreenCast').OpenPipeWireRemote(dbus.ObjectPath(self.session),dbus.Dictionary({},signature='sv'))
        new_fd=remote.take();previous=self.fd;self.fd=new_fd
        if previous is not None:os.close(previous)
        return new_fd

    def dispatch(self):
        context=self.GLib.MainContext.default()
        for _ in range(16):
            if not context.pending():break
            context.iteration(False)
        if self.closed:raise RuntimeError('El portal cerró el permiso de captura')

    def release_remote(self):
        """Drop this client's socket without ending its consent session."""
        fd,self.fd=self.fd,None
        if fd is not None:os.close(fd)

    def screenshot(self, interactive=True):
        from pathlib import Path
        from urllib.parse import urlsplit,unquote
        result=self.request('org.freedesktop.portal.Screenshot','Screenshot','',options={'interactive':bool(interactive)})
        uri=urlsplit(str(result.get('uri','')))
        if uri.scheme!='file' or uri.netloc not in ('','localhost'):raise RuntimeError('El portal no devolvió una imagen local')
        return Path(unquote(uri.path))

    def pick_color(self):
        values=self.request('org.freedesktop.portal.Screenshot','PickColor','').get('color',())
        if len(values)!=3 or not all(0<=float(v)<=1 for v in values):raise RuntimeError('El portal devolvió un color inválido')
        return tuple(float(v) for v in values)

    def close(self):
        if self.disposed:return
        self.disposed=True
        self.release_remote()
        if self.session:
            try:self.dbus.Interface(self.bus.get_object(BUS,self.session),'org.freedesktop.portal.Session').Close()
            except self.dbus.DBusException:pass
            self.session=None
        if self._match:self._match.remove();self._match=None
        self.bus.close()


if __name__=='__main__':
    import json,sys
    portal=Portal()
    try:
        if sys.argv[1:] == ['pick-color']:print(json.dumps(portal.pick_color()))
        elif sys.argv[1:] == ['screenshot']:print(json.dumps({'path':str(portal.screenshot())}))
        else:raise SystemExit('Use screenshot or pick-color')
    finally:portal.close()

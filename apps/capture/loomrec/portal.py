"""XDG Desktop Portal client; consent and PipeWire handles stay in the worker.

No X11 fallback on Wayland. Never persists an FD or desktop image. When a caller
explicitly asks to remember a ScreenCast source, only the opaque portal restore
token is stored in the user's private state, scoped by source kind.
See org.freedesktop.portal.ScreenCast, Screenshot and Request specifications.
"""
import os
import uuid

BUS='org.freedesktop.portal.Desktop'
PATH='/org/freedesktop/portal/desktop'


def is_wayland():
    return os.environ.get('XDG_SESSION_TYPE')=='wayland' or bool(os.environ.get('WAYLAND_DISPLAY'))


class PortalCancelled(RuntimeError):pass


def share_request(output):
    """Write the short-lived picker request for one named output, or None."""
    import json,re,tempfile,time
    from pathlib import Path
    runtime=os.environ.get('XDG_RUNTIME_DIR')
    if not output or not runtime or not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):return None
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,64}',str(output)):return None
    path=Path(runtime)/'loomrec-share-request.json'
    try:
        descriptor,name=tempfile.mkstemp(prefix='.loomrec-share-',dir=runtime)
        with os.fdopen(descriptor,'w') as stream:json.dump({'output':str(output),'time':time.time()},stream)
        os.replace(name,path);return path
    except OSError:return None


class RestoredOtherOutput(RuntimeError):
    """A remembered ScreenCast consent restored a different output."""


class Portal:
    def __init__(self,*,strict_close=False):
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
        self.dbus=dbus;self.GLib=GLib
        self.bus=dbus.SessionBus(private=True,mainloop=DBusGMainLoop());self.bus.set_exit_on_disconnect(False)
        self.object=self.bus.get_object(BUS,PATH)
        self.session=None;self.fd=None;self.closed=False;self._match=None;self.on_wait=None;self.disposed=False
        self.strict_close=strict_close;self.cancel_requested=False;self.cancel_state='running'
        self._owner=None;self._owner_lost=False;self._owner_match=None;self._strict_loop=None;self._session_close_sent=False
        self.close_timeout=-1  # D-Bus default; private fixtures shorten the call deadline.

    def _pin_owner(self):
        if self._owner:return
        def changed(name,old,new):
            if str(old)==self._owner and str(new)!=self._owner:
                self._owner_lost=True;self._session_closed()
        self._owner_match=self.bus.add_signal_receiver(changed,signal_name='NameOwnerChanged',
            dbus_interface='org.freedesktop.DBus',bus_name='org.freedesktop.DBus',
            path='/org/freedesktop/DBus',arg0=BUS)
        self._owner=str(self.bus.get_name_owner(BUS))
        self.object=self.bus.get_object(self._owner,PATH,introspect=False)

    def _session_closed(self,details=None):
        self.closed=True
        if self.cancel_requested:self.cancel_state='terminal'
        if self._strict_loop:self._strict_loop.quit()

    def _check_strict_wait(self):
        if self.on_wait:
            try:self.on_wait()
            except BaseException:
                self.cancel_requested=True;raise

    def _close_session_once(self):
        if self.closed or self._owner_lost or not self.session:
            if self._strict_loop:self._strict_loop.quit()
            return
        if self._session_close_sent:return
        self._session_close_sent=True;self.cancel_state='session-close-pending'
        def failed(error):
            # UnknownObject alone is not proof that the selected source or
            # session closed. Keep the exact Closed/original-owner watchers.
            if not self.closed:self.cancel_state='session-close-unconfirmed'
        try:
            self.dbus.Interface(self.bus.get_object(self._owner,self.session,introspect=False),
                'org.freedesktop.portal.Session').Close(reply_handler=self._session_closed,error_handler=failed,timeout=self.close_timeout)
        except self.dbus.DBusException as error:failed(error)

    def _strict_request(self,interface,method,*args,options=None,timeout=120):
        """Cancel once, then wait for original request and session evidence.

        Transport errors do not imply teardown. No retries, successor owners,
        source re-selection, or external state polling are used here.
        """
        self._pin_owner()
        try:self._check_strict_wait()
        except BaseException:self.close();raise
        dbus=self.dbus;token='wysun_'+uuid.uuid4().hex
        sender=self.bus.get_unique_name()[1:].replace('.','_')
        path=PATH+'/request/'+sender+'/'+token
        loop=self.GLib.MainLoop();self._strict_loop=loop
        answer=[];cause=[];request_terminal=False;close_sent=False;handle=path
        def advance():
            if self.closed or self._owner_lost or not self.session:
                loop.quit()
            elif request_terminal:self._close_session_once()
        def close_ok():
            nonlocal request_terminal
            request_terminal=True;advance()
        def close_failed(error):
            # Preserve Response. Core1.20.3 leaves the Request exported on
            # backend Close failure; closing the picker can still resolve it.
            if not request_terminal and not self.closed:self.cancel_state='request-close-unconfirmed'
        def cancel(error):
            nonlocal close_sent
            if cause:return
            cause.append(error)
            self.cancel_requested=True;self.cancel_state='request-close-pending'
            if self.closed or self._owner_lost or request_terminal:advance();return
            if close_sent:return
            close_sent=True
            try:
                dbus.Interface(self.bus.get_object(self._owner,handle,introspect=False),
                    'org.freedesktop.portal.Request').Close(reply_handler=close_ok,error_handler=close_failed,timeout=self.close_timeout)
            except dbus.DBusException as failure:close_failed(failure)
        def response(code,results):
            nonlocal request_terminal
            if answer:return
            answer.append((int(code),results));request_terminal=True
            if cause:advance()
            elif int(code):cancel(PortalCancelled('Selección cancelada en el portal') if int(code)==1 else RuntimeError('El portal rechazó la solicitud ('+str(int(code))+')'))
            else:loop.quit()
        def tick():
            if not cause:
                try:
                    if self.on_wait:self.on_wait()
                except BaseException as error:cancel(error)
            return True
        def expired():cancel(TimeoutError('El portal no respondió. Cierra el selector del portal para terminar.'));return False
        match=self.bus.add_signal_receiver(response,signal_name='Response',dbus_interface='org.freedesktop.portal.Request',path=path,bus_name=self._owner)
        timer=self.GLib.timeout_add_seconds(timeout,expired);heartbeat=self.GLib.timeout_add(250,tick)
        try:
            values=dbus.Dictionary(options or {},signature='sv');values['handle_token']=token
            try:handle=getattr(dbus.Interface(self.object,interface),method)(*args,values)
            except dbus.DBusException as error:
                # A missing method reply does not prove the pre-subscribed
                # Request was never created. Close that exact path once and
                # retain Response/session evidence, without repeating the call.
                cancel(error)
            if str(handle)!=path:
                match.remove();match=self.bus.add_signal_receiver(response,signal_name='Response',dbus_interface='org.freedesktop.portal.Request',path=str(handle),bus_name=self._owner)
            if not answer and not self.closed:loop.run()
            elif cause and not self.closed and self.session:loop.run()
            if cause:raise cause[0]
            if self.closed or self._owner_lost:raise RuntimeError('El portal cerró el permiso de captura')
            return answer[0][1]
        finally:
            self._strict_loop=None;match.remove()
            for source in (timer,heartbeat):
                if self.GLib.MainContext.default().find_source_by_id(source):self.GLib.source_remove(source)

    def request(self, interface, method, *args, options=None, timeout=120):
        if getattr(self,'strict_close',False):return self._strict_request(interface,method,*args,options=options,timeout=timeout)
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

    def screencast(self, source='monitor', cursor=True, multiple=False, remember=False, output=None):
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
        self._match=self.bus.add_signal_receiver(self._session_closed if self.strict_close else lambda details:setattr(self,'closed',True),signal_name='Closed',dbus_interface='org.freedesktop.portal.Session',path=self.session,bus_name=self._owner if self.strict_close else BUS)
        from . import consent
        token_kind='desktop' if multiple else 'window' if source=='window' else consent.output_kind(output)
        try:
            options={'types':dbus.UInt32(requested),'multiple':bool(multiple),'cursor_mode':dbus.UInt32(mode)}
            stored=''
            if remember:
                stored=consent.load(token_kind)
                options['persist_mode']=dbus.UInt32(2)
                if stored:options['restore_token']=stored
            # The user already chose this screen in Wysun; the Wysun picker for
            # xdg-desktop-portal-hyprland answers this one-shot request.
            request=share_request(output) if requested==1 and not multiple else None
            try:
                self.request(iface,'SelectSources',dbus.ObjectPath(self.session),options=options)
                started=self.request(iface,'Start',dbus.ObjectPath(self.session),'')
            finally:
                if request:
                    try:request.unlink()
                    except OSError:pass
            streams=started.get('streams',[])
            if not streams or (not multiple and len(streams)!=1):raise RuntimeError('Selecciona una sola fuente en el portal')
            self.streams=[(int(node),dict(metadata)) for node,metadata in streams]
            node,metadata=self.streams[0]
            if any(int(props.get('source_type',requested))!=requested for _,props in self.streams):raise RuntimeError('El portal devolvió otro tipo de fuente')
            actual=str(metadata.get('mapping_id','')) if requested==1 and not multiple else ''
            if remember and stored and output and actual and actual!=output:
                # The restored consent named another screen: forget it and ask again.
                consent.clear(token_kind);raise RestoredOtherOutput(actual)
            self.open_remote()
            if remember:
                issued=started.get('restore_token')
                if issued is not None:consent.save(consent.output_kind(actual) if actual else token_kind,str(issued))
            return int(node),metadata
        except BaseException:self.close();raise

    def open_remote(self):
        """Each PipeWire client gets a fresh protocol connection under same consent."""
        if self.disposed or self.closed or not self.session:raise RuntimeError('La sesión del portal ya no está disponible')
        dbus=self.dbus
        if getattr(self,'strict_close',False):self._check_strict_wait()
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
        strict=getattr(self,'strict_close',False)
        if strict and self.cancel_requested and self.session and not self.closed:
            # A completed QThread/lease release must never stand in for an ACK.
            self._pin_owner();loop=self.GLib.MainLoop();self._strict_loop=loop
            try:
                self._close_session_once()
                if not self.closed and not self._owner_lost:loop.run()
            finally:self._strict_loop=None
        self.disposed=True
        self.release_remote()
        if self.session:
            if not (strict and (self.cancel_requested or self._owner_lost)):
                try:self.dbus.Interface(self.bus.get_object(self._owner if strict else BUS,self.session),'org.freedesktop.portal.Session').Close()
                except self.dbus.DBusException:pass
            self.session=None
        if self._match:self._match.remove();self._match=None
        if getattr(self,'_owner_match',None):self._owner_match.remove();self._owner_match=None
        self.bus.close()


if __name__=='__main__':
    import json,sys
    portal=Portal()
    try:
        if sys.argv[1:] == ['pick-color']:print(json.dumps(portal.pick_color()))
        elif sys.argv[1:] == ['screenshot']:print(json.dumps({'path':str(portal.screenshot())}))
        else:raise SystemExit('Use screenshot or pick-color')
    finally:portal.close()

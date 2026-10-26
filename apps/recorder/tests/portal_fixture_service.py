"""Private test-only portal service. No PipeWire/compositor/input/device access."""
import json
import os
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

SCREEN='org.freedesktop.portal.ScreenCast'
ROOT='/org/freedesktop/portal/desktop'
BUS='org.freedesktop.portal.Desktop'


class Request(dbus.service.Object):
    def __init__(self,owner,path,code,result):
        super().__init__(owner.bus,path);self.owner=owner;self.code=code;self.result=result
        if code is not None:GLib.idle_add(self.reply)
    def reply(self):self.Response(self.code,self.result);return False
    @dbus.service.signal('org.freedesktop.portal.Request',signature='ua{sv}')
    def Response(self,code,result):pass
    @dbus.service.method('org.freedesktop.portal.Request',async_callbacks=('reply','error'))
    def Close(self,reply,error):
        self.owner.stats['requests_closed']+=1
        if self.owner.mode=='hold-select-close':self.owner.close_reply=reply
        elif self.owner.mode in ('strict-response-closed','strict-response-success'):
            self.owner.close_reply=reply  # Let the *client's* short deadline expire.
        else:reply()


class Session(dbus.service.Object):
    def __init__(self,owner,path):super().__init__(owner.bus,path);self.owner=owner;self.closed=False
    @dbus.service.method('org.freedesktop.portal.Session',async_callbacks=('reply','error'))
    def Close(self,reply,error):
        self.owner.stats['session_close_calls']+=1
        if self.owner.mode=='strict-session-error':
            error(dbus.exceptions.DBusException('Owned unconfirmed session',name='org.freedesktop.DBus.Error.UnknownObject'));return
        if self.owner.mode=='strict-owner-loss':
            self.owner.session_reply=reply;return
        # Core Close is a client-requested teardown, not a Closed signal.
        self.owner.stats['sessions_closed']+=1;self.closed=True;reply();self.remove_from_connection()
    @dbus.service.signal('org.freedesktop.portal.Session',signature='a{sv}')
    def Closed(self,details):pass


class Desktop(dbus.service.Object):
    def __init__(self,bus,loop):
        super().__init__(bus,ROOT);self.bus=bus;self.loop=loop;self.objects=[];self.fds=[];self.mode='success';self.reset()
    def reset(self):self.stats=dict(created=0,selected=0,started=0,remotes=0,sessions_closed=0,requests_closed=0,session_close_calls=0,types=0,cursor=0)
    def request(self,options,sender,code,result):
        path=ROOT+'/request/'+sender[1:].replace('.','_')+'/'+str(options['handle_token'])
        request=Request(self,path,code,result);self.objects.append(request);self.pending_request=request
        return dbus.ObjectPath(path)
    @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
    def Get(self,interface,key):
        if interface!=SCREEN:raise dbus.exceptions.DBusException('Unknown interface')
        return dbus.UInt32({'version':5 if self.mode=='legacy' else 6,'AvailableSourceTypes':1 if self.mode=='no-window' else 3,'AvailableCursorModes':1 if self.mode=='no-cursor' else 3}[key])
    @dbus.service.method(SCREEN,in_signature='a{sv}',out_signature='o',sender_keyword='sender')
    def CreateSession(self,options,sender):
        if self.mode=='cancel-create':return self.request(options,sender,1,{})
        self.stats['created']+=1
        path=ROOT+'/session/'+sender[1:].replace('.','_')+'/'+str(options['session_handle_token'])
        self.objects.append(Session(self,path));self.session=path
        return self.request(options,sender,0,{'session_handle':dbus.String(path)})
    @dbus.service.method(SCREEN,in_signature='oa{sv}',out_signature='o',sender_keyword='sender')
    def SelectSources(self,session,options,sender):
        self.stats['selected']+=1;self.stats['types']=int(options['types']);self.stats['cursor']=int(options['cursor_mode'])
        if self.mode=='strict-initial-error':
            self.request(options,sender,None,{})
            raise dbus.exceptions.DBusException('Owned missing initial reply',name='org.freedesktop.DBus.Error.NoReply')
        if self.mode=='hold-select-close' or self.mode.startswith('strict-'):return self.request(options,sender,None,{})
        return self.request(options,sender,1 if self.mode=='cancel-select' else 0,{})
    @dbus.service.method(SCREEN,in_signature='osa{sv}',out_signature='o',sender_keyword='sender')
    def Start(self,session,parent,options,sender):
        self.stats['started']+=1
        if self.mode=='hold-start':return self.request(options,sender,None,{})
        if self.mode in ('cancel-start','fail-start'):return self.request(options,sender,1 if self.mode=='cancel-start' else 2,{})
        metadata={'position':dbus.Struct((dbus.Int32(-100),dbus.Int32(0)),signature='ii'),'size':dbus.Struct((dbus.Int32(100),dbus.Int32(80)),signature='ii'),'source_type':dbus.UInt32(self.stats['types'])}
        if self.mode!='legacy':metadata['pipewire-serial']=dbus.UInt64(987654321001)
        streams=dbus.Array([dbus.Struct((dbus.UInt32(47),dbus.Dictionary(metadata,signature='sv')),signature='ua{sv}')],signature='(ua{sv})')
        return self.request(options,sender,0,{'streams':streams})
    @dbus.service.method(SCREEN,in_signature='oa{sv}',out_signature='h')
    def OpenPipeWireRemote(self,session,options):
        # A transferred socket FD, deliberately unrelated to node ID 47. It is
        # only a lifecycle fixture, never a PipeWire server or usable media FD.
        import socket
        left,right=socket.socketpair();self.fds.extend((left,right));self.stats['remotes']+=1
        return dbus.types.UnixFd(left.fileno())
    @dbus.service.method('org.wysun.Test',in_signature='s')
    def Configure(self,mode):self.mode=mode;self.reset()
    @dbus.service.method('org.wysun.Test',out_signature='s')
    def Stats(self):return json.dumps(self.stats)
    @dbus.service.method('org.wysun.Test')
    def ReleaseClose(self):
        reply=self.close_reply;self.close_reply=None;reply()
    @dbus.service.method('org.wysun.Test',in_signature='ub')
    def CompleteSelection(self,code,closed):
        self.pending_request.Response(code,{})
        if closed:self.Revoke({})
    @dbus.service.method('org.wysun.Test')
    def ReplaceOwner(self):
        self.bus.release_name(BUS)
        self.successor=dbus.SessionBus(private=True);self.successor.set_exit_on_disconnect(False)
        self.successor.request_name(BUS,dbus.bus.NAME_FLAG_DO_NOT_QUEUE)
    @dbus.service.method('org.wysun.Test',in_signature='a{sv}')
    def Revoke(self,details):
        for obj in reversed(self.objects):
            if isinstance(obj,Session) and not obj.closed:
                obj.Closed(details);obj.closed=True;self.stats['sessions_closed']+=1;obj.remove_from_connection();break
    @dbus.service.method('org.wysun.Test')
    def Quit(self):GLib.idle_add(self.loop.quit)


def main():
    DBusGMainLoop(set_as_default=True);bus=dbus.SessionBus(private=True);bus.set_exit_on_disconnect(False)
    name=dbus.service.BusName(BUS,bus=bus,do_not_queue=True);loop=GLib.MainLoop();desktop=Desktop(bus,loop)
    print('READY',flush=True)
    try:loop.run()
    finally:
        for fd in desktop.fds:fd.close()
        if hasattr(desktop,'successor'):desktop.successor.close()
        bus.close()

if __name__=='__main__':main()

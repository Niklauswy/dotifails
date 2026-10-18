#!/usr/bin/env python3
"""D-Bus activation for Wysun FileManager1 and the file chooser portal."""
import signal
import sys
from pathlib import Path
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from PySide6.QtCore import QTimer,QItemSelectionModel,Qt
from PySide6.QtWidgets import QApplication,QMessageBox
from files_chooser import FileChooser,local_path
from files_window import FilesWindow

PORTAL='org.freedesktop.impl.portal.FileChooser'
REQUEST='org.freedesktop.impl.portal.Request'
MANAGER='org.freedesktop.FileManager1'

class Request(dbus.service.Object):
    def __init__(self,service,path,dialog,sender):
        super().__init__(service.bus,path);self.dialog=dialog;self.sender=sender
    @dbus.service.method(REQUEST,in_signature='',out_signature='',sender_keyword='sender')
    def Close(self,sender=None):
        if sender==self.sender:self.dialog.result_uris=[];self.dialog.close()

def typed_results(result):
    out=dbus.Dictionary(signature='sv')
    if 'uris' in result:out['uris']=dbus.Array(result['uris'],signature='s')
    if 'choices' in result:out['choices']=dbus.Array([dbus.Struct(pair,signature='ss') for pair in result['choices']],signature='(ss)')
    if 'current_filter' in result:
        name,rules=result['current_filter'];out['current_filter']=dbus.Struct((str(name),dbus.Array([dbus.Struct((dbus.UInt32(kind),str(pattern)),signature='us') for kind,pattern in rules],signature='(us)')),signature='sa(us)')
    return out

class Portal(dbus.service.Object):
    def __init__(self,bus):
        super().__init__(bus,'/org/freedesktop/portal/desktop');self.bus=bus;self.requests={}
    @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
    def Get(self,interface,name):
        if interface==PORTAL and name=='version':return dbus.UInt32(4)
        raise dbus.exceptions.DBusException('Unknown property',name='org.freedesktop.DBus.Error.UnknownProperty')
    @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='s',out_signature='a{sv}')
    def GetAll(self,interface):return {'version':dbus.UInt32(4)} if interface==PORTAL else {}
    def choose(self,mode,handle,parent,title,options,reply,error,sender):
        try:
            if sender!=self.bus.get_name_owner('org.freedesktop.portal.Desktop'):
                raise dbus.exceptions.DBusException('Use the public file chooser portal.',name='org.freedesktop.DBus.Error.AccessDenied')
            if str(handle) in self.requests:raise ValueError('Duplicate request handle')
            dialog=FileChooser(mode,str(title),options,str(parent));request=Request(self,str(handle),dialog,sender)
            self.requests[str(handle)]=(dialog,request)
            def complete(code,result):
                request.remove_from_connection();self.requests.pop(str(handle),None)
                reply(dbus.UInt32(code),typed_results(result));dialog.deleteLater()
            dialog.completed.connect(complete);dialog.show();dialog.raise_();dialog.activateWindow()
        except Exception as exc:error(exc)
    @dbus.service.method(PORTAL,in_signature='osssa{sv}',out_signature='ua{sv}',async_callbacks=('reply','error'),sender_keyword='sender')
    def OpenFile(self,handle,app_id,parent,title,options,reply,error,sender=None):self.choose('open',handle,parent,title,options,reply,error,sender)
    @dbus.service.method(PORTAL,in_signature='osssa{sv}',out_signature='ua{sv}',async_callbacks=('reply','error'),sender_keyword='sender')
    def SaveFile(self,handle,app_id,parent,title,options,reply,error,sender=None):self.choose('save',handle,parent,title,options,reply,error,sender)
    @dbus.service.method(PORTAL,in_signature='osssa{sv}',out_signature='ua{sv}',async_callbacks=('reply','error'),sender_keyword='sender')
    def SaveFiles(self,handle,app_id,parent,title,options,reply,error,sender=None):self.choose('savefiles',handle,parent,title,options,reply,error,sender)

class Manager(dbus.service.Object):
    def __init__(self,bus):
        super().__init__(bus,'/org/freedesktop/FileManager1');self.windows=[]
    def show(self,uris,items=False,properties=False):
        groups={}
        for uri in uris:
            try:
                path=local_path(uri)
                if not path.exists():continue
                folder=path.parent if items or path.is_file() else path
                groups.setdefault(str(folder),[]).append(str(path))
            except (ValueError,OSError):continue
        if not groups:groups={str(Path.home()):[]}
        for folder,paths in groups.items():
            window=FilesWindow([folder]);window.setAttribute(Qt.WA_DeleteOnClose);self.windows.append(window);window.show();window.raise_();window.activateWindow()
            tab=window.current();done=[False]
            def select(w=window,t=tab,values=paths,prop=properties,state=done):
                if state[0] or not all(t.model.index(p).isValid() for p in values):return
                state[0]=True;selection=t.view().selectionModel()
                for p in values:selection.select(t.model.index(p),QItemSelectionModel.Select|QItemSelectionModel.Rows)
                if values:t.view().scrollTo(t.model.index(values[0]))
                if prop:w.properties()
            tab.model.directoryLoaded.connect(lambda _,callback=select:callback());QTimer.singleShot(100,select)
            window.destroyed.connect(lambda *_args,w=window:self.windows.remove(w) if w in self.windows else None)
    @dbus.service.method(MANAGER,in_signature='ass',out_signature='')
    def ShowItems(self,uris,startup_id):self.show(uris,items=True)
    @dbus.service.method(MANAGER,in_signature='ass',out_signature='')
    def ShowFolders(self,uris,startup_id):self.show(uris)
    @dbus.service.method(MANAGER,in_signature='ass',out_signature='')
    def ShowItemProperties(self,uris,startup_id):self.show(uris,items=True,properties=True)

def main():
    DBusGMainLoop(set_as_default=True);bus=dbus.SessionBus()
    app=QApplication([sys.argv[0]]);app.setApplicationName('Wysun Files');app.setOrganizationName('Orbita');app.setDesktopFileName('orbit-files');app.setStyle('Fusion');app.setQuitOnLastWindowClosed(False)
    try:portal_name=dbus.service.BusName('org.freedesktop.impl.portal.desktop.orbit',bus,do_not_queue=True)
    except dbus.NameExistsException:return 0
    portal=Portal(bus);manager_name=None;manager=None
    try:
        manager_name=dbus.service.BusName(MANAGER,bus,allow_replacement=True,replace_existing=True,do_not_queue=True);manager=Manager(bus)
    except dbus.NameExistsException:print('FileManager1 already owned; Wysun chooser is available.',flush=True)
    context=GLib.MainContext.default();timer=QTimer();timer.setInterval(8)
    def dispatch():
        for _ in range(32):
            if not context.pending():break
            context.iteration(False)
    timer.timeout.connect(dispatch);timer.start()
    def stop(*_):
        for dialog,_request in list(portal.requests.values()):dialog.close()
        if manager:
            for window in list(manager.windows):window.close()
        pending=[dialog for dialog,_request in portal.requests.values()]
        if manager:pending+=manager.windows
        if any(window.isVisible() for window in pending):QTimer.singleShot(100,stop)
        else:app.quit()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    return app.exec()

if __name__=='__main__':sys.exit(main())

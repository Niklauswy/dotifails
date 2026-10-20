"""Exercise the real public portal and FileManager1 on a private session bus."""
import os,sys,tempfile,time,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if not (root/'apps/wysun').is_dir():root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'apps/wysun'))
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
import dbus,dbus.service
from gi.repository import GLib
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QItemSelectionModel,QTimer,QEvent,QCoreApplication
from files_service import Portal,Manager,PORTAL,MANAGER

tmp=tempfile.TemporaryDirectory();base=Path(tmp.name);(base/'data/xdg-desktop-portal/portals').mkdir(parents=True);(base/'config/xdg-desktop-portal').mkdir(parents=True)
(base/'data/xdg-desktop-portal/portals/orbit.portal').write_text('[portal]\nDBusName=org.freedesktop.impl.portal.desktop.orbit\nInterfaces=org.freedesktop.impl.portal.FileChooser;\n')
(base/'config/xdg-desktop-portal/portals.conf').write_text('[preferred]\ndefault=none\norg.freedesktop.impl.portal.FileChooser=orbit\n')
file=base/'sample ñ.txt';file.write_text('fixture')
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
bus=dbus.SessionBus();name=dbus.service.BusName('org.freedesktop.impl.portal.desktop.orbit',bus);portal=Portal(bus)
manager_name=dbus.service.BusName(MANAGER,bus);manager=Manager(bus)
env=dict(os.environ,XDG_DATA_HOME=str(base/'data'),XDG_CONFIG_HOME=str(base/'config'))
log=(base/'portal.log').open('w');frontend=subprocess.Popen(['/usr/libexec/xdg-desktop-portal','--verbose'],env=env,stdout=log,stderr=log)
context=GLib.MainContext.default()
def wait(fn,timeout=10):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  app.processEvents()
  for _ in range(32):
   if not context.pending():break
   context.iteration(False)
  time.sleep(.005)
  if fn():return
 raise AssertionError('Portal timeout: '+(base/'portal.log').read_text()[-2500:])
client=dbus.SessionBus(private=True)
try:
 wait(lambda:client.name_has_owner('org.freedesktop.portal.Desktop'))
 proxy=dbus.Interface(client.get_object('org.freedesktop.portal.Desktop','/org/freedesktop/portal/desktop'), 'org.freedesktop.portal.FileChooser')
 responses=[];errors=[]
 client.add_signal_receiver(lambda code,result:responses.append((int(code),result)),signal_name='Response',dbus_interface='org.freedesktop.portal.Request')
 def request(method,options):
  responses.clear();errors.clear();handles=[]
  getattr(proxy,method)('', 'Selector de prueba',dbus.Dictionary(options,signature='sv'),reply_handler=lambda value:handles.append(value),error_handler=errors.append)
  wait(lambda:bool(portal.requests) or bool(errors))
  assert not errors,errors
  return next(iter(portal.requests.values()))[0]
 dialog=request('OpenFile',{'multiple':dbus.Boolean(True),'current_folder':dbus.ByteArray(os.fsencode(base)+b'\0')})
 wait(lambda:dialog.current().model.index(str(file)).isValid())
 dialog.current().view().selectionModel().select(dialog.current().model.index(str(file)),QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)
 dialog.accept_selection();wait(lambda:bool(responses));assert responses[0][0]==0 and list(responses[0][1]['uris'])==[file.as_uri()],responses
 print('PASS real public OpenFile response and URI round trip',flush=True)
 dialog=request('SaveFile',{'current_folder':dbus.ByteArray(os.fsencode(base)+b'\0'),'current_name':'new.txt'})
 dialog.accept_selection();wait(lambda:bool(responses));assert responses[0][0]==0 and not (base/'new.txt').exists()
 print('PASS SaveFile response without modifying files',flush=True)
 dialog=request('OpenFile',{})
 # Public Request.Close must propagate through the frontend and cancel the backend.
 handle=next(iter(portal.requests))
 public_handle=handle
 client.get_object('org.freedesktop.portal.Desktop',public_handle).Close(dbus_interface='org.freedesktop.portal.Request',reply_handler=lambda:None,error_handler=errors.append)
 wait(lambda:not portal.requests);assert not errors,errors
 print('PASS cancellation propagates through public Request.Close',flush=True)
 fm=dbus.Interface(client.get_object(MANAGER,'/org/freedesktop/FileManager1'),MANAGER)
 result=[];fm.ShowItems(dbus.Array([file.as_uri()],signature='s'),'',reply_handler=lambda:result.append(True),error_handler=errors.append)
 wait(lambda:manager.windows and manager.windows[-1].current().selected_paths()==[str(file)])
 print('PASS FileManager1 ShowItems opens parent and selects file',flush=True)
finally:
 for dialog,_ in list(portal.requests.values()):dialog.close()
 for w in list(manager.windows):w.close();w.deleteLater()
 frontend.terminate();frontend.wait(timeout=5);app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
 portal.remove_from_connection();manager.remove_from_connection()
 bus.release_name(MANAGER);bus.release_name("org.freedesktop.impl.portal.desktop.orbit")
 log.close();tmp.cleanup();app.quit();client.close()
print("PORTAL_INTEGRATION_OK",flush=True)

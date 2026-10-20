"""Prepared native GTK FileChooser proof for the integrator's private runtime.

Call run_cases(run_dir, env, command, start, wait_for) from the existing guarded
portal runner. It creates only synthetic paths/window, uses the real public portal
and real GTK backend, and types only after identifying its own uniquely titled
native dialog in the private compositor. No host service/runtime is started here.
Needs GTK4 GI for exporting a synthetic parent, GTK portal and private wtype.
Preparation/AST checks do not count as a successful GTK runtime proof.
"""
import json
import os
from pathlib import Path
import re
import time


def run_cases(run_dir, env, command, start=None, wait_for=None):
    run_dir=Path(run_dir).resolve();runtime=Path(env['XDG_RUNTIME_DIR']).resolve()
    if not runtime.is_relative_to(run_dir) or not (run_dir/'private-portal.log').is_file():
        raise RuntimeError('Use only the guarded private portal runtime, never the host session')
    if not env.get('HYPRLAND_INSTANCE_SIGNATURE') or not env.get('DBUS_SESSION_BUS_ADDRESS'):
        raise RuntimeError('Missing private compositor or bus')
    import gi
    gi.require_version('Gtk','4.0');gi.require_version('GdkWayland','4.0')
    from gi.repository import Gtk,GdkWayland,GLib
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from loomrec.portal import Portal,PortalCancelled
    DBusGMainLoop(set_as_default=True)
    Gtk.init();parent=Gtk.Window();parent.set_title('Wysun GTK synthetic parent');parent.set_default_size(420,220)
    parent.set_child(Gtk.Label(label='Own synthetic FileChooser parent. No private files.'));parent.present()
    context=GLib.MainContext.default();end=time.monotonic()+5
    while parent.get_surface() is None and time.monotonic()<end:context.iteration(False);time.sleep(.01)
    surface=parent.get_surface();handles=[]
    if not isinstance(surface,GdkWayland.WaylandToplevel):parent.destroy();raise RuntimeError('Parent is not native Wayland')
    if not surface.export_handle(lambda *args:handles.extend('wayland:'+a for a in args if isinstance(a,str)),None):
        parent.destroy();raise RuntimeError('Could not export the synthetic native parent')
    while not handles and time.monotonic()<end:context.iteration(False);time.sleep(.01)
    if not handles:parent.destroy();raise TimeoutError('No exported Wayland parent handle')
    parent_handle=handles[0]
    fixture=run_dir/'gtk-chooser-fixtures';files=fixture/'files';folder=fixture/'directory';files.mkdir(parents=True,exist_ok=True);folder.mkdir(parents=True,exist_ok=True)
    one=files/'one.txt';two=files/'two.txt';one.write_text('own one');two.write_text('own two');(files/'ignore.png').write_bytes(b'not selected')
    def typed_filter(label,kind,pattern):
        entries=dbus.Array([dbus.Struct((dbus.UInt32(kind),pattern),signature='us')],signature='(us)')
        return dbus.Struct((label,entries),signature='sa(us)')
    text_filter=typed_filter('Fixture text',0,'*.txt');mime_filter=typed_filter('Fixture plain MIME',1,'text/plain')
    results={};portal=Portal()
    def persist():
        (run_dir/'gtk-filechooser-results.json').write_text(json.dumps(results,indent=2)+'\n')
    def one_case(name,method,options,expected=None,cancel=False,multiple=False):
        title='Wysun GTK portal fixture '+name;stage=[0];automation_error=[]
        def automate():
            try:
                clients=json.loads(command(['hyprctl','-j','clients']))
                owned=[w for w in clients if title in w.get('title','')]
                if not owned:return True
                if len(owned)!=1 or owned[0].get('xwayland'):raise RuntimeError('Expected one owned native GTK dialog')
                address=owned[0]['address']
                if not re.fullmatch('0x[0-9a-fA-F]+',address):raise ValueError('Invalid private dialog address')
                if stage[0]==0:
                    command(['hyprctl','dispatch','hl.dsp.focus({window="address:'+address+'"})'])
                    stage[0]=1;return True
                # In the private English GTK fixture Alt+C activates _Cancel.
                # Escape produces GTK_RESPONSE_DELETE_EVENT (portal code 2),
                # which must remain an error rather than PortalCancelled.
                if cancel:command(['wtype','-M','alt','-k','c','-m','alt']);return False
                if multiple and stage[0]==1:
                    command(['wtype','-M','ctrl','-k','a','-m','ctrl']);stage[0]=2;return True
                if name=='open' and stage[0]==1:
                    command(['wtype','-M','ctrl','-k','l','-m','ctrl']);stage[0]=2;return True
                if name=='open' and stage[0]==2:
                    command(['wtype','-M','ctrl','-k','a','-m','ctrl',str(one)]);stage[0]=3;return True
                if name=='open':command(['wtype','-k','Return'])
                else:command(['wtype','-M','alt','-k','a','-m','alt'])
                return False
            except Exception as error:automation_error.append(str(error));return False
        options=dict(options,accept_label='Fixture _Accept',modal=True)
        timer=GLib.timeout_add(250,automate)
        try:
            try:response=portal.request('org.freedesktop.portal.FileChooser',method,parent_handle,title,options=options,timeout=20)
            except PortalCancelled:
                if not cancel:raise
                results[name]=dict(cancelled=True,parent_exported=True,automation_errors=automation_error);persist();return
            if cancel:raise AssertionError('Cancel unexpectedly accepted')
            uris=sorted(str(u) for u in response.get('uris',[]))
            if uris!=sorted(p.as_uri() for p in expected):raise AssertionError((name,uris,expected,automation_error))
            results[name]=dict(uris=uris,parent_exported=True,native_dialog=True,current_filter=str(response.get('current_filter','')),automation_errors=automation_error)
            # Parent export alone is not evidence of backend import/transiency.
            results[name]['parent_import_verified']=False
            persist()
        finally:
            if context.find_source_by_id(timer):GLib.source_remove(timer)
    def byte_folder(path):return dbus.ByteArray(os.fsencode(path)+b'\0')
    try:
        one_case('cancel','OpenFile',dict(current_folder=byte_folder(files)),cancel=True)
        one_case('open','OpenFile',dict(current_folder=byte_folder(files),filters=dbus.Array([text_filter,mime_filter],signature='(sa(us))'),current_filter=dbus.Struct(text_filter,signature='sa(us)')),[one])
        one_case('multiple','OpenFile',dict(current_folder=byte_folder(files),multiple=True,filters=dbus.Array([text_filter],signature='(sa(us))')),[one,two],multiple=True)
        one_case('directory','OpenFile',dict(current_folder=byte_folder(folder),directory=True),[folder])
        one_case('save','SaveFile',dict(current_folder=byte_folder(files),current_name='new.txt',filters=dbus.Array([text_filter],signature='(sa(us))')),[files/'new.txt'])
        if (files/'new.txt').exists():raise AssertionError('Chooser must return save URI without creating the destination')
        return results
    finally:
        portal.close();surface.unexport_handle();parent.destroy()

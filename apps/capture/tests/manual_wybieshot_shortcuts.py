"""Actual SXHKD chords against installed Wybie, cancelled over an owned fixture.

No accepted capture, export or clipboard write. Requires exclusive native slot.
python3 tests/manual_wybieshot_shortcuts.py --owned-fixture
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import sys
import tempfile
from unittest.mock import patch


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--owned-fixture',action='store_true',required=True);parser.parse_args()
    from PySide6.QtWidgets import QApplication,QWidget
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor,QPainter
    from Xlib import display,X,XK
    from Xlib.ext import xtest
    def processes():
        result={}
        for path in Path('/proc').glob('[0-9]*'):
            try:
                args=[a.decode(errors='replace') for a in (path/'cmdline').read_bytes().split(b'\0') if a]
                if not args:continue
                if Path(args[0]).name=='ffmpeg' or 'loomrec.worker' in args:raise RuntimeError('Media capture/render active; no native test')
                if '-m' in args and args[args.index('-m')+1:args.index('-m')+2]==['wybieshot']:result[int(path.name)]=args
            except (OSError,IndexError):continue
        return result
    initial=processes();app=QApplication([]);c=display.Display();root=c.screen().root
    clip=c.intern_atom('CLIPBOARD');before_owner=c.get_selection_owner(clip)
    before_owner=getattr(before_owner,'id',0)
    base=Path.home()/'.local/share/wybie-screenshot';manifest=json.loads((base/'install-manifest.json').read_text())
    prefs=base/'preferences.json';pref_before=prefs.read_bytes() if prefs.exists() else None
    sessions=set((base/'sessions').iterdir()) if (base/'sessions').exists() else set()
    for name,digest in manifest['files'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
    class Fixture(QWidget):
        def paintEvent(self,event):
            painter=QPainter(self);painter.fillRect(self.rect(),QColor('#23a6bf'));painter.end()
    fixture=Fixture(None,Qt.Window|Qt.FramelessWindowHint|Qt.X11BypassWindowManagerHint|Qt.WindowStaysOnTopHint)
    fixture.setAttribute(Qt.WA_OpaquePaintEvent);geometry=root.get_geometry();fixture.setGeometry(0,0,geometry.width,geometry.height)
    owned_pids=set();outcomes=[];pointer_before=root.query_pointer()
    repeated_proof=False;save_proof=False
    def settle(duration=.3):
        deadline=time.monotonic()+duration
        while time.monotonic()<deadline:app.processEvents();time.sleep(.02)
    def keys(names):
        codes=[c.keysym_to_keycode(XK.string_to_keysym(name)) for name in names]
        assert all(codes)
        for code in codes:xtest.fake_input(c,X.KeyPress,code)
        for code in reversed(codes):xtest.fake_input(c,X.KeyRelease,code)
        c.sync()
    def overlay(pid):
        for window in root.query_tree().children:
            try:
                prop=window.get_full_property(c.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
                if prop and int(prop.value[0])==pid and window.get_attributes().map_state==X.IsViewable and 'Seleccionar región' in (window.get_wm_name() or ''):return window
            except Exception:pass
        return None
    try:
        fixture.show();fixture.raise_();settle()
        native=c.create_resource_object('window',int(fixture.winId()))
        for chord,names,path in [('Super+Shift+S',['Super_L','Shift_L','s'],str(Path.home()/'Screenshots')),('Super+Shift+Q',['Super_L','Shift_L','q'],str(Path.home()/'yurai/scshot')),('Super+Shift+A',['Super_L','Shift_L','a'],None),('Print',['Print'],None)]:
            fixture.raise_();settle();c.sync()
            attrs=native.get_attributes();g=native.get_geometry();point=root.translate_coords(native,0,0)
            assert attrs.map_state==X.IsViewable and attrs.override_redirect
            assert (point.x,point.y,g.width,g.height)==(0,0,geometry.width,geometry.height)
            visible=[w for w in root.query_tree().children if w.get_attributes().map_state==X.IsViewable and w.get_attributes().win_class==X.InputOutput]
            assert visible[-1].id==native.id,'Owned fixture must cover every root pixel before shortcut capture'
            native.set_input_focus(X.RevertToParent,X.CurrentTime);c.sync();old=set(processes());keys(names)
            deadline=time.monotonic()+8;pid=None;surface=None
            while time.monotonic()<deadline:
                settle(.05);new=set(processes())-old
                if new:
                    assert len(new)==1;pid=new.pop();owned_pids.add(pid);surface=overlay(pid)
                    if surface:break
            assert surface is not None,'No direct installed region overlay for '+chord
            argv=processes()[pid];assert '--region' in argv and argv[argv.index('--delay')+1]=='0'
            env=Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
            assert ('PYTHONPATH='+str(base/'releases'/manifest['release'])).encode() in env
            if path:
                assert '--accept-on-select' in argv and '--clipboard' in argv and argv[argv.index('--path')+1]==path
            else:assert '--accept-on-select' not in argv and '--clipboard' not in argv
            surface.set_input_focus(X.RevertToParent,X.CurrentTime);c.sync()
            if chord=='Super+Shift+A':
                keys(['Super_L','Shift_L','a']);settle(.4)
                assert set(processes())==old|{pid},'Repeated selection shortcut opened another process'
                def native_drag(a,b):
                    xtest.fake_input(c,X.MotionNotify,x=a[0],y=a[1]);xtest.fake_input(c,X.ButtonPress,1)
                    xtest.fake_input(c,X.MotionNotify,x=b[0],y=b[1]);xtest.fake_input(c,X.ButtonRelease,1);c.sync();settle(.15)
                native_drag((100,100),(899,539));keys(['a']);settle(.1)
                native_drag((180,200),(420,200))
                pixel=app.primaryScreen().grabWindow(0,300,200,1,1).toImage().pixelColor(0,0).name()
                assert pixel=='#2165d5',('Native arrow not rendered',pixel)
                keys(['Super_L','Shift_L','s']);settle(.4)
                assert set(processes())==old|{pid},'Repeated annotation shortcut opened another process'
                assert overlay(pid).id==surface.id
                assert app.primaryScreen().grabWindow(0,300,200,1,1).toImage().pixelColor(0,0).name()==pixel
                repeated_proof=True
            keys(['Escape'])
            deadline=time.monotonic()+5
            while pid in processes() and time.monotonic()<deadline:settle(.05)
            assert pid not in processes(),'Escape left direct screenshot process alive'
            keyboard=root.grab_keyboard(False,X.GrabModeAsync,X.GrabModeAsync,X.CurrentTime)
            if keyboard==X.GrabSuccess:c.ungrab_keyboard(X.CurrentTime)
            assert keyboard==X.GrabSuccess,'Keyboard grab retained'
            pointer=root.grab_pointer(False,0,X.GrabModeAsync,X.GrabModeAsync,X.NONE,X.NONE,X.CurrentTime)
            if pointer==X.GrabSuccess:c.ungrab_pointer(X.CurrentTime)
            assert pointer==X.GrabSuccess,'Pointer grab retained'
            c.sync();outcomes.append({'chord':chord,'direct_region':True,'installed_release':manifest['release'],'escape_terminated':True,'grabs_released':True})
        # Exercise installed in-place save with a controlled file-picker result;
        # export/storage/render remain real and no user clipboard is accessed.
        sys.path.insert(0,str(base/'releases'/manifest['release']))
        from wybieshot.actions import ActionWindow,CaptureActions
        from wybieshot.schema import CaptureRequest
        from wybieshot.instance import CaptureLease
        from wybieshot.storage import Storage
        from PySide6.QtCore import QEvent,QPointF
        from PySide6.QtGui import QMouseEvent,QImage
        fixture.raise_();settle();c.sync()
        visible=[w for w in root.query_tree().children if w.get_attributes().map_state==X.IsViewable and w.get_attributes().win_class==X.InputOutput]
        assert visible[-1].id==native.id,'Fixture must be topmost before installed save proof'
        with tempfile.TemporaryDirectory(prefix='wybie-floating-save-') as temporary:
            window=ActionWindow(CaptureActions(),Storage(Path(temporary)/'private'))
            try:
                window._capture_lease=CaptureLease();assert window._capture_lease.claim()
                window.pending_request=CaptureRequest();window.busy=True;window.capture_tick();settle();o=window.overlay
                def qt_drag(widget,a,b):
                    for kind,p,button,buttons in ((QEvent.MouseButtonPress,a,Qt.LeftButton,Qt.LeftButton),(QEvent.MouseMove,b,Qt.NoButton,Qt.LeftButton),(QEvent.MouseButtonRelease,b,Qt.LeftButton,Qt.NoButton)):
                        app.sendEvent(widget,QMouseEvent(kind,QPointF(*p),QPointF(*p),button,buttons,Qt.NoModifier))
                qt_drag(o,(100,100),(899,539));o.choose('mask');o.canvas.color='#000000';qt_drag(o.canvas,(30,40),(80,90))
                doc=o.document;target=Path(temporary)/'annotated.png'
                with patch.object(o,'request_save_path',side_effect=lambda default,callback:callback(str(target))):window.complete_floating(doc,'save')
                bitmap=QImage(str(target));assert bitmap==doc.render() and bitmap.width()==800 and bitmap.height()==440
                assert bitmap.pixelColor(40,50).name()=='#000000' and bitmap.pixelColor(0,0).name()=='#23a6bf'
                assert not window.isVisible() and window.overlay is None
                lease=CaptureLease();assert lease.claim();lease.release();save_proof=True
            finally:
                window.close();window.quick.close();window.quick.deleteLater();window.deleteLater();app.processEvents();app.sendPostedEvents(None,QEvent.DeferredDelete)
        assert getattr(c.get_selection_owner(clip),'id',0)==before_owner,'Clipboard owner unexpectedly changed'
        assert (prefs.read_bytes() if prefs.exists() else None)==pref_before
        assert (set((base/'sessions').iterdir()) if (base/'sessions').exists() else set())==sessions
        assert set(processes())==set(initial)
        print(json.dumps({'bindings':outcomes,'fixture':'opaque, root geometry/viewable/override_redirect/topmost verified each time','clipboard':'owner unchanged, no reads or writes','preferences':'unchanged','sessions':'unchanged','repeated_shortcuts_selection_and_annotation':repeated_proof,'installed_floating_save_png_and_lease_cleanup':save_proof,'capture_acceptance':'four hotkeys cancelled; installed in-process save accepted with controlled picker, no clipboard writes'},ensure_ascii=False))
    finally:
        # Only processes launched by this test are eligible for cleanup on failure.
        for pid in owned_pids & set(processes()):
            try:os.kill(pid,15)
            except ProcessLookupError:pass
        xtest.fake_input(c,X.MotionNotify,x=pointer_before.root_x,y=pointer_before.root_y);c.sync()
        fixture.close();app.processEvents();c.close()

if __name__=='__main__':main()

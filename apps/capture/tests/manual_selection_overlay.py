"""Explicit native BSPWM/X11 proof using owned synthetic windows; no media capture.

Run manually with graphical-session access. Temporarily selects another desktop,
then restores the original desktop/focus in finally. Never run during a media test.
"""
import ctypes as C
import ctypes.util
import os
import re
import subprocess
import time
from pathlib import Path
from PySide6.QtCore import Qt,QRect
from PySide6.QtWidgets import QApplication,QWidget
from loomrec.devices import activate_window,list_windows
from loomrec.ui.widgets import RegionPicker
from loomrec.ui.capture_feedback import RecordingIndicator


def run(*args):
    return subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=3).strip()


def settle(seconds=.2):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)


def native(widget):
    info=run('xwininfo','-id',str(int(widget.winId())))
    assert 'Map State: IsViewable' in info,info
    values=[int(re.search(re.escape(key)+r':\s*(-?\d+)',info)[1]) for key in
            ('Absolute upper-left X','Absolute upper-left Y','Width','Height')]
    return QRect(*values),info


# Do not change desktops underneath a user's live or paused recording. Check
# process identity rather than relying on a potentially stale status heartbeat.
for process in Path('/proc').glob('[0-9]*'):
    try:
        if process.stat().st_uid!=os.getuid():continue
        args=(process/'cmdline').read_bytes().split(b'\0')
    except (FileNotFoundError,ProcessLookupError):continue
    if b'loomrec.worker' in args or (args and Path(os.fsdecode(args[0])).name=='ffmpeg' and b'x11grab' in args):
        raise RuntimeError('A live recorder exists; native selection proof refused without changing focus.')

app=QApplication([]);app.setQuitOnLastWindowClosed(False)
original_desktop=run('bspc','query','-D','-d','focused')
try:original_focus=run('bspc','query','-N','-n','focused')
except subprocess.CalledProcessError:original_focus=None
desktops=run('bspc','query','-D').splitlines()
other=next((d for d in desktops if d!=original_desktop),None)
if not other:raise RuntimeError('This manual proof needs two existing desktops.')
fixture=QWidget();fixture.setWindowTitle('Loom selection synthetic fixture')
fixture.setStyleSheet('background:#466e8c');fixture.resize(640,360)
backdrop=None;picker=None;indicator=RecordingIndicator();connection=None
try:
    fixture.show();settle()
    target=hex(int(fixture.winId()))
    run('bspc','node',target,'-t','floating')
    run('bspc','node',target,'-d',other)
    run('bspc','desktop',original_desktop,'-f');settle()
    assert any(int(w['id'],16)==int(target,16) for w in list_windows())
    rect=activate_window(target);settle()
    assert run('bspc','query','-D','-d','focused')==other
    assert rect==list(native(fixture)[0].getRect())
    # A hidden client must also be discoverable, restored, and selected.
    run('bspc','node',target,'-g','hidden=on');settle()
    assert any(int(w['id'],16)==int(target,16) for w in list_windows())
    activate_window(target);settle();native(fixture)
    print('PASS: other-desktop and hidden fixture listed, activated, live geometry checked')

    geometry=app.primaryScreen().virtualGeometry()
    backdrop=QWidget(None,Qt.FramelessWindowHint|Qt.X11BypassWindowManagerHint|Qt.WindowStaysOnTopHint)
    backdrop.setStyleSheet('background:#466e8c');backdrop.setGeometry(geometry);backdrop.show();settle()
    assert native(backdrop)[0]==geometry
    picker=RegionPicker(geometry);selected=[];picker.selected.connect(selected.append);picker.show();settle()
    actual,info=native(picker)
    assert actual==geometry,(actual,geometry)
    assert 'Override Redirect State: yes' in info
    assert QWidget.mouseGrabber() is picker and QWidget.keyboardGrabber() is picker
    x=C.CDLL(ctypes.util.find_library('X11'));xt=C.CDLL(ctypes.util.find_library('Xtst'))
    x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
    x.XFlush.argtypes=[C.c_void_p];x.XCloseDisplay.argtypes=[C.c_void_p]
    connection=x.XOpenDisplay(None);assert connection
    xt.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
    xt.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    left=geometry.x()+100;top=geometry.y()+100
    xt.XTestFakeMotionEvent(connection,0,left,top,0)
    xt.XTestFakeButtonEvent(connection,1,True,0);x.XFlush(connection);settle(.1)
    xt.XTestFakeMotionEvent(connection,0,left+300,top+200,0);x.XFlush(connection);settle(.1)
    xt.XTestFakeButtonEvent(connection,1,False,0);x.XFlush(connection);settle()
    assert selected==[[left,top,300,200]],selected
    assert not picker.isVisible() and QWidget.mouseGrabber() is None and QWidget.keyboardGrabber() is None
    indicator.present(selected[0],[s.geometry().getRect() for s in app.screens()]);indicator.update('recording');settle()
    phase=indicator.phase;settle(.15);assert phase!=indicator.phase
    for widget in indicator.windows:
        actual,info=native(widget)
        assert not actual.intersects(QRect(*selected[0]))
        assert 'Override Redirect State: yes' in info
    indicator.update('paused');phase=indicator.phase;settle(.15);assert phase==indicator.phase
    print('PASS: native overlay bounds, override-redirect, real pointer drag, grab release, external animated/paused border')
finally:
    indicator.hide()
    if picker:picker.close()
    if backdrop:backdrop.close()
    fixture.close();settle()
    if connection:x.XCloseDisplay(connection)
    run('bspc','desktop',original_desktop,'-f')
    if original_focus:
        subprocess.run(['bspc','node',original_focus,'-f'],capture_output=True,timeout=3)

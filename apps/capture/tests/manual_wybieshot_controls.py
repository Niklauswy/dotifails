"""Native interactions on owned content; Copy backend isolated, user clipboard untouched."""
import os,sys,time,tempfile,json,argparse
from pathlib import Path
parser=argparse.ArgumentParser(description='Owned-fixture real pointer test for floating controls; reserve native slot first')
parser.add_argument('--owned-fixture',action='store_true',required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--bundle',type=Path)
parser.add_argument('--preview-only',action='store_true')
args=parser.parse_args()
sys.path.insert(0,str(args.bundle or Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QRect,QEvent
from PySide6.QtGui import QColor,QPainter,QImage
from PySide6.QtWidgets import QApplication,QWidget,QColorDialog,QLineEdit,QPushButton,QPlainTextEdit,QSpinBox,QDialogButtonBox
from Xlib import display,X,XK
from Xlib.ext import xtest
from wybieshot.actions import ActionWindow,CaptureActions
from wybieshot.schema import CaptureRequest
from wybieshot.storage import Storage
from wybieshot.instance import CaptureLease
from wybieshot.ui.floating import FloatingSelection
from loomrec.ui.tokens import apply_theme
app=QApplication([]);app.setQuitOnLastWindowClosed(False);apply_theme(app);c=display.Display();root=c.screen().root;g=root.get_geometry();pointer=root.query_pointer();clip=c.intern_atom('CLIPBOARD');owner=getattr(c.get_selection_owner(clip),'id',0)
for process in Path('/proc').glob('[0-9]*'):
 try:
  process_args=(process/'cmdline').read_bytes().split(b'\0');assert b'loomrec.worker' not in process_args and Path(process_args[0].decode(errors='replace')).name!='ffmpeg','Media active'
 except (OSError,IndexError):pass
class Fixture(QWidget):
 def paintEvent(self,event):
  p=QPainter(self);p.fillRect(self.rect(),QColor('#edf3fa'));p.setPen(QColor('#1c2a3b'));font=p.font();font.setPixelSize(28);p.setFont(font);p.drawText(100,160,'WYBIE / PRUEBA DE CONTROLES PROPIA');p.end()
f=Fixture(None,Qt.Window|Qt.FramelessWindowHint|Qt.X11BypassWindowManagerHint|Qt.WindowStaysOnTopHint);f.setGeometry(0,0,g.width,g.height);windows=[]
def settle(n=12):
 for _ in range(n):app.processEvents();time.sleep(.015)
def keys(names):
 codes=[c.keysym_to_keycode(XK.string_to_keysym(name)) for name in names];assert all(codes)
 for code in codes:xtest.fake_input(c,X.KeyPress,code)
 for code in reversed(codes):xtest.fake_input(c,X.KeyRelease,code)
 c.sync();settle(4)
def type_text(text):
 for char in text:
  sym=ord(char);code=c.keysym_to_keycode(sym);mapping=list(c.get_keyboard_mapping(code,1)[0]);level=mapping.index(sym)
  assert level<4,(char,level)
  mods=[]
  if level>=2:mods.append(c.keysym_to_keycode(XK.string_to_keysym('ISO_Level3_Shift')))
  if level%2:mods.append(c.keysym_to_keycode(XK.string_to_keysym('Shift_L')))
  for mod in mods:xtest.fake_input(c,X.KeyPress,mod)
  xtest.fake_input(c,X.KeyPress,code);xtest.fake_input(c,X.KeyRelease,code)
  for mod in reversed(mods):xtest.fake_input(c,X.KeyRelease,mod)
 c.sync();settle(5)
def click(widget):
 point=widget.mapToGlobal(widget.rect().center());assert app.widgetAt(point) is widget,(widget,app.widgetAt(point))
 xtest.fake_input(c,X.MotionNotify,x=point.x(),y=point.y());xtest.fake_input(c,X.ButtonPress,1);xtest.fake_input(c,X.ButtonRelease,1);c.sync();settle()
def drag(a,b):
 xtest.fake_input(c,X.MotionNotify,x=a[0],y=a[1]);xtest.fake_input(c,X.ButtonPress,1);xtest.fake_input(c,X.MotionNotify,x=b[0],y=b[1]);xtest.fake_input(c,X.ButtonRelease,1);c.sync();settle()
def top(widget):
 ids=[v.id for v in root.query_tree().children if v.get_attributes().map_state==X.IsViewable and v.get_attributes().win_class==X.InputOutput]
 assert ids[-1]==int(widget.winId()),('Not topmost',ids[-1],int(widget.winId()))
def apply(o):click(next(b for b in o._popover.findChildren(QPushButton) if b.text()=='Aplicar'))
try:
 f.show();f.raise_();settle();native=c.create_resource_object('window',int(f.winId()));a=native.get_attributes();pos=root.translate_coords(native,0,0);actual=native.get_geometry();assert a.map_state==X.IsViewable and a.override_redirect and (pos.x,pos.y,actual.width,actual.height)==(0,0,g.width,g.height);top(f)
 with tempfile.TemporaryDirectory(prefix='wybie-input-') as temporary:
  store=Storage(Path(temporary)/'private');output=Path(temporary)/'output';output.mkdir();store.set_output(output)
  w=ActionWindow(CaptureActions(),store);windows.append(w);w._capture_lease=CaptureLease();assert w._capture_lease.claim();w.pending_request=CaptureRequest();w.busy=True;w.capture_tick();settle();o=w.overlay;top(o)
  drag((8,8),(g.width-9,g.height-9));click(o.tools['arrow']);drag((120,240),(420,240));assert len(o.document.layers)==1
  click(o.color);assert o._popover.isVisible() and app.activeModalWidget() is None
  picker=o._popover.findChild(QColorDialog);assert not picker.isWindow()
  sampler=picker.findChild(QPushButton,'wybieUnsupportedScreenPicker');assert sampler and not sampler.isVisible() and not sampler.isEnabled()
  edit=picker.findChild(QLineEdit,'qt_colorname_lineedit');click(edit);keys(['Control_L','a']);type_text('#ff0055');assert edit.text()=='#ff0055';assert o._popover.isAncestorOf(app.focusWidget())
  evidence=args.output;evidence.mkdir(parents=True,exist_ok=True);top(o)
  app.primaryScreen().grabWindow(0,0,0,g.width,g.height).save(str(evidence/'color.png'))
  if args.preview_only:
   print('PASS localized embedded color preview: actual pointer focus, sampler unavailable, no modal');sys.exit(0)
  apply(o);assert o._popover is None and o.document.layers[0].color=='#ff0055'
  click(o.tools['text']);drag((500,300),(500,300));assert app.activeModalWidget() is None and o._popover
  text=o._popover.findChild(QPlainTextEdit);click(text.viewport());keys(['Control_L','a']);type_text('nota propia');apply(o);assert o.document.layers[-1].text=='nota propia'
  click(o.tools['number']);drag((700,300),(700,300));click(o.tools['select']);keys(['Return']);assert o._popover and o._popover.findChild(QSpinBox)
  keys(['Escape']);assert o._popover is None and o.isVisible() and QWidget.mouseGrabber() is None
  count=len(o.document.layers);before=QRect(o.selection);point=o.toolbar.mapToGlobal(o.toolbar.rect().topRight())
  xtest.fake_input(c,X.MotionNotify,x=point.x()-2,y=point.y()+2);xtest.fake_input(c,X.ButtonPress,1);xtest.fake_input(c,X.ButtonRelease,1);c.sync();settle()
  assert len(o.document.layers)==count and o.selection==before and o.canvas.start is None
  click(o.save_button);dialog=o._file_dialog;assert dialog and dialog.isVisible() and not dialog.isModal();top(dialog)
  click(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Cancel));assert o._file_dialog is None and o.isVisible() and len(o.document.layers)==count
  probe=CaptureLease();assert not probe.claim()
  click(o.save_button);dialog=o._file_dialog;top(dialog);filename=dialog.findChild(QLineEdit,'fileNameEdit');click(filename);keys(['Control_L','a']);type_text('actual.png')
  assert dialog.isAncestorOf(app.focusWidget());doc=o.document
  click(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save));assert w.overlay is None
  bitmap=QImage(str(output/'actual.png'));assert bitmap==doc.render();assert probe.claim();probe.release()
  # A second session tests the actual Copiar hit/dispatch with an isolated copy backend.
  image=f.grab().toImage();w2=ActionWindow(CaptureActions(),store);windows.append(w2);w2._capture_lease=CaptureLease();assert w2._capture_lease.claim()
  o2=FloatingSelection(image,QRect(0,0,g.width,g.height));w2.overlay=o2;o2.finished.connect(w2.complete_floating);o2.cancelled.connect(w2.cancel_capture);o2.present();settle();drag((8,8),(g.width-9,g.height-9))
  click(o2.tools['pen']);drag((120,240),(420,240));calls=[];store.copy=lambda doc:calls.append(doc.render())
  click(o2.color);keys(['Escape']);assert o2._popover is None and o2.isVisible()
  click(o2.copy_button);assert len(calls)==1 and w2.overlay is None and not w2.isVisible();assert probe.claim();probe.release()
  assert getattr(c.get_selection_owner(clip),'id',0)==owner
  assert QWidget.mouseGrabber() is None
  keyboard=root.grab_keyboard(False,X.GrabModeAsync,X.GrabModeAsync,X.CurrentTime);assert keyboard==X.GrabSuccess;c.ungrab_keyboard(X.CurrentTime)
  pointer_status=root.grab_pointer(False,0,X.GrabModeAsync,X.GrabModeAsync,X.NONE,X.NONE,X.CurrentTime);assert pointer_status==X.GrabSuccess;c.ungrab_pointer(X.CurrentTime);c.sync()
  print(json.dumps({'color':'real pointer open/hex/apply updated object; embedded/nonmodal','text':'real pointer/type/apply','number':'real pointer edit/Escape returns','large_crop_palette':'hit tests plus whitespace preserves canvas','save_dialog':'topmost visible, actual cancel and save; focus verified','PNG':'exact annotated bitmap','copy':'real click dispatched once with isolated backend, no system clipboard test','clipboard_owner':'unchanged, no read/write','grabs':'available'}))
finally:
 for w in windows:
  if w.overlay:w.overlay.close()
  w.close();w.quick.close();w.quick.deleteLater();w.deleteLater()
 f.close();app.processEvents();app.sendPostedEvents(None,QEvent.DeferredDelete);xtest.fake_input(c,X.MotionNotify,x=pointer.root_x,y=pointer.root_y);c.sync();c.close()

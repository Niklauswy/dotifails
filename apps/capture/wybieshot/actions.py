"""Direct region CLI actions, isolated from the normal launcher and preferences."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import uuid
from PySide6.QtCore import QEvent, QTimer, Qt, QRect
from .ui.selection import SelectionOverlay,SelectionGroup
from PySide6.QtWidgets import QApplication
from .ui.main import Window,selection_parts

@dataclass(frozen=True)
class CaptureActions:
    accept_on_select: bool = False
    clipboard: bool = False
    path: Path | None = None
    delay: int | None = None

class ActionWindow(Window):
    capture_settle_ms=16  # Direct capture never maps a window before the grab.
    def __init__(self,actions,storage=None,engine=None):
        self.actions=actions
        self._clipboard_pending=False
        super().__init__(storage,engine)

    def prefs(self):
        prefs=super().prefs()
        if self.actions.delay is not None:prefs['delay']=self.actions.delay
        return prefs

    def create_selection(self,frozen):
        if not self.actions.accept_on_select:return super().create_selection(frozen)
        overlays=[]
        for image,screen,origin,geometry in selection_parts(frozen):
            overlay=SelectionOverlay(image,geometry,screen=screen,image_origin=origin)
            overlay.selected.connect(self.selected_region);overlay.cancelled.connect(self.cancel_capture)
            overlay.control_drag_finished.connect(lambda o=overlay:QTimer.singleShot(0,lambda:self.accept_selection(o)))
            overlay.installEventFilter(self)
            overlays.append(overlay)
        if not overlays:raise RuntimeError('No hay una pantalla disponible para la selección')
        return overlays[0] if len(overlays)==1 else SelectionGroup(overlays)

    def eventFilter(self,obj,event):
        if event.type()==QEvent.MouseButtonRelease and event.button()==Qt.LeftButton:
            candidates=getattr(self.overlay,'overlays',[])
            if obj in candidates:
                # Run after the overlay has committed its adjusted rectangle.
                QTimer.singleShot(0,lambda overlay=obj:self.accept_selection(overlay))
        return super().eventFilter(obj,event)

    def accept_selection(self,overlay=None):
        overlay=overlay or self.overlay
        if overlay is None:return
        candidates=getattr(overlay,'overlays',None)
        if candidates and overlay is self.overlay:
            overlay=next((item for item in candidates if item.isVisible() and item.selection.width()>1 and item.selection.height()>1),candidates[0])
        if overlay and overlay.isVisible() and overlay.selection.width()>1 and overlay.selection.height()>1:
            rect=overlay.source_rect(overlay.selection.normalized().intersected(overlay.rect()))
            rect.translate(overlay.image_origin)
            if self.overlay:self.overlay.hide()
            overlay.selected.emit(rect)

    def cancel_capture(self):
        if self.defer_capture_cancel():return
        if self._capture_feedback:self._capture_feedback.cancel()
        self.release_capture()
        self.capture_timer.stop();self.busy=False;self.frozen=None
        if self.overlay:self.overlay.hide();self.overlay.deleteLater();self.overlay=None
        if hasattr(self,'countdown_window'):self.countdown_window.hide()
        # Direct invocation has no launcher behind it; Escape ends this process.
        self.close()

    def finish_capture(self,result):
        super().finish_capture(result)
        if not (self.actions.clipboard or self.actions.path):return
        if not self.save_document():return  # Keep the editable capture on save error.
        try:
            if self.actions.path:
                path=self.actions.path.expanduser().absolute()
                if path.is_dir() or path.suffix.lower() not in ('.png','.jpg','.jpeg'):
                    path=path/('Wysun-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.png')
                self.storage.export(self.document,path)
            if self.actions.clipboard:
                self.storage.copy(self.document)
                self._clipboard_pending=True
                QApplication.clipboard().dataChanged.connect(self.clipboard_changed)
        except Exception as exc:
            self.notice('No se pudo completar la captura: '+str(exc),True);return
        if self._clipboard_pending:
            # X11 has no clipboard persistence service on many desktops. Keep the
            # selection owner alive (like xclip) until another copy replaces it.
            # No window, keyboard/pointer grab or polling loop is retained.
            self.hide();self.quick.hide();self.save_timer.stop()
        else:self.close()

    def clipboard_changed(self):
        if self._clipboard_pending and not QApplication.clipboard().ownsClipboard():
            self._clipboard_pending=False;self.close()


def run(app,actions,lease=None):
    app.setQuitOnLastWindowClosed(False)
    window=ActionWindow(actions);window._capture_lease=lease;app._wybieshot_window=window
    QTimer.singleShot(0,window.begin_capture)
    result=app.exec()
    window.quick.close();window.close();window.quick.deleteLater();window.deleteLater()
    app.sendPostedEvents(None,QEvent.DeferredDelete);app._wybieshot_window=None
    return result

"""Frozen-frame selection. Never captures a desktop or saves a frame itself."""
from PySide6.QtCore import QObject, QPoint, QRect, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from loomrec.ui.tokens import color


class SelectionGuard(QObject):
    """Fullscreen overlays must never outlive their usefulness.

    A frozen overlay covers every output; if none of them holds the keyboard
    focus, Escape cannot reach the app and the desktop would stay covered. The
    guard cancels the selection when focus is lost for `lost_limit` checks in a
    row, or when the monitor topology changes (the frozen crops no longer map
    to real outputs). Dialogs opened by an overlay (save, colour) own the focus
    legitimately and pause the check.
    """
    interval_ms = 500
    lost_limit = 4

    def __init__(self, overlays, on_cancel):
        super().__init__(QApplication.instance())
        self.overlays = list(overlays)
        self.on_cancel = on_cancel
        self.lost = 0
        self.fired = False
        self.stopped = False
        self.timer = QTimer(self)
        self.timer.setInterval(self.interval_ms)
        self.timer.timeout.connect(self.check)
        app = QGuiApplication.instance()
        app.screenAdded.connect(self.topology_changed)
        app.screenRemoved.connect(self.topology_changed)
        self.screens = list(app.screens())
        for screen in self.screens:
            screen.geometryChanged.connect(self.topology_changed)
            screen.logicalDotsPerInchChanged.connect(self.topology_changed)
        self.timer.start()

    def stop(self):
        if self.stopped:return
        self.stopped = True
        self.timer.stop()
        app = QGuiApplication.instance()
        for signal in (app.screenAdded, app.screenRemoved):
            try:signal.disconnect(self.topology_changed)
            except (RuntimeError, TypeError):pass
        for screen in self.screens:
            try:
                screen.geometryChanged.disconnect(self.topology_changed)
                screen.logicalDotsPerInchChanged.disconnect(self.topology_changed)
            except (RuntimeError, TypeError):
                pass
        self.screens.clear()
        self.overlays.clear()
        self.on_cancel = None
        self.deleteLater()

    def has_dialog(self):
        return QApplication.activePopupWidget() is not None or any(
            isinstance(w, QDialog) and w.isVisible() for w in QApplication.topLevelWidgets())

    def visible(self):
        try:return any(o.isVisible() for o in self.overlays)
        except RuntimeError:return False  # overlay already destroyed

    def annotating(self):
        # Never discard an edit in progress: only the bare selection phase can
        # leave the user without a way to cancel.
        return any(getattr(o, 'document', None) is not None for o in self.overlays)

    def check(self):
        if self.fired or self.stopped:return
        if not self.visible():
            self.stop();return
        active = QApplication.activeWindow()
        owns_focus = active is not None and any(active is o or o.isAncestorOf(active) for o in self.overlays)
        if owns_focus or self.has_dialog() or self.annotating():
            self.lost = 0;return
        self.lost += 1
        if self.lost >= self.lost_limit:self.fire()

    def topology_changed(self, *_):
        if not self.stopped and self.visible():self.fire()

    def fire(self):
        if self.fired or self.stopped:return
        self.fired = True
        callback = self.on_cancel
        self.stop()
        callback()


class SelectionOverlay(QWidget):
    selected = Signal(QRect)
    cancelled = Signal()
    recovery_requested = Signal()
    control_drag_finished = Signal()
    _control_drag_owner = None

    def __init__(self, image, geometry, parent=None, *, screen=None, image_origin=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.image = image
        self.target_screen = screen
        self.image_origin = QPoint(image_origin) if image_origin is not None else QPoint(0, 0)
        self.selection = QRect()
        self.anchor = None
        self.drag_origin = None
        self.initial_rect = QRect()
        self.control_origin = None
        self.control_dragging = False
        self.setWindowTitle('Seleccionar región · Wysun Screenshot')
        self.setAccessibleName('Seleccionar región. Flechas para mover; Shift y flechas para ajustar; Enter para confirmar; Escape para cancelar.')
        self.setGeometry(geometry)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CrossCursor)

    @property
    def overlays(self):
        return [self]

    def source_rect(self,rect):
        # Widget coordinates may be logical/scaled; originals always keep pixel resolution.
        sx=self.image.width()/max(1,self.width());sy=self.image.height()/max(1,self.height())
        left=round(rect.x()*sx);top=round(rect.y()*sy)
        right=round((rect.x()+rect.width())*sx);bottom=round((rect.y()+rect.height())*sy)
        return QRect(left,top,right-left,bottom-top).intersected(self.image.rect())

    def present(self, guard=True):
        from loomrec.portal import is_wayland
        if guard:
            if getattr(self, '_guard', None) is not None:self._guard.stop()
            self._guard = SelectionGuard([self], self.recovery_requested.emit)
        if self.target_screen is not None:
            # One native, fullscreen overlay per output. The image is already the
            # crop for this output, so selection is never made on a miniature
            # copy of the whole desktop.
            self.setScreen(self.target_screen)
            self.setGeometry(self.target_screen.geometry())
            self.showFullScreen()
            handle=self.windowHandle()
            if handle is not None and handle.screen() is not self.target_screen:
                handle.setScreen(self.target_screen)
        elif is_wayland():
            from PySide6.QtWidgets import QApplication
            screen=QApplication.primaryScreen().availableGeometry()
            size=self.image.size();size.scale(screen.size(),Qt.KeepAspectRatio)
            self.resize(size);self.setWindowTitle('Recortar imagen autorizada · Wysun Screenshot')
            self.show()
        else:self.show()
        self.raise_(); self.activateWindow(); self.setFocus()

    def enterEvent(self,event):
        # Each display has its own fullscreen overlay. Keep keyboard modifiers
        # routed to the one currently under the pointer when crossing outputs.
        self.activateWindow();self.setFocus()
        super().enterEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawImage(self.rect(), self.image)
        p.fillRect(self.rect(), color('region_scrim'))
        r = self.selection.normalized().intersected(self.rect())
        if not r.isEmpty():
            p.save(); p.setClipRect(r); p.drawImage(self.rect(), self.image); p.restore()
            p.setPen(QPen(color('region_edge'), 1)); p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(r).adjusted(.5, .5, -.5, -.5))
            p.setPen(QPen(color('accent'), 2))
            for point in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
                p.fillRect(QRect(point-QPoint(4,4), point+QPoint(4,4)), color('region_edge'))
                p.drawRect(QRect(point-QPoint(4,4), point+QPoint(4,4)))
        hint = f'{r.width()} × {r.height()} · Enter capturar · Esc cancelar' if not r.isEmpty() else 'Arrastra o mantén Ctrl y mueve · Enter inicia selección con teclado · Esc cancelar'
        width = min(self.width()-24, p.fontMetrics().horizontalAdvance(hint)+32)
        box = QRect(12, max(12, self.height()-54), width, 38)
        p.setPen(Qt.NoPen); p.setBrush(color('surface')); p.drawRoundedRect(box, 19, 19)
        p.setPen(color('text')); p.drawText(box.adjusted(12,0,-12,0), Qt.AlignCenter, hint)
        p.end()

    def mousePressEvent(self, event):
        if event.button()!=Qt.LeftButton:return
        owner=SelectionOverlay._control_drag_owner
        if owner is not None:
            owner.control_origin=None;owner.control_dragging=False
        SelectionOverlay._control_drag_owner=None
        self.control_origin=None;self.control_dragging=False
        self._begin_drag(event.position().toPoint())

    def _bounded_point(self,point):
        point=QPoint(point)
        point.setX(max(0,min(self.width()-1,point.x())))
        point.setY(max(0,min(self.height()-1,point.y())))
        return point

    def _begin_drag(self,point):
        point=self._bounded_point(point)
        r=self.selection.normalized()
        self.initial_rect=QRect(r)
        corners=((r.topLeft(),r.bottomRight()),(r.topRight(),r.bottomLeft()),(r.bottomLeft(),r.topRight()),(r.bottomRight(),r.topLeft()))
        corner=next((opposite for handle,opposite in corners if (point-handle).manhattanLength()<=16),None) if not r.isEmpty() else None
        if corner is not None:
            self.anchor=corner;self.drag_origin=None
        elif r.contains(point):
            self.drag_origin=point;self.anchor=None
        else:
            self.anchor=point;self.drag_origin=None;self.selection=QRect(point,point)
        self.update()

    def _update_drag(self,point):
        point=self._bounded_point(point)
        if self.anchor is not None:self.selection=QRect(self.anchor,point).normalized()
        elif self.drag_origin is not None:
            r=self.initial_rect.translated(point-self.drag_origin)
            r.moveLeft(max(0,min(self.width()-r.width(),r.left())))
            r.moveTop(max(0,min(self.height()-r.height(),r.top())))
            self.selection=r
        self.update()

    def _pointer_position(self):
        return self._bounded_point(self.mapFromGlobal(QCursor.pos()))

    def mouseMoveEvent(self, event):
        point=event.position().toPoint()
        if self.control_origin is not None and not self.control_dragging and point!=self.control_origin:
            self.control_dragging=True
            self._begin_drag(self.control_origin)
        if self.control_dragging or self.anchor is not None or self.drag_origin is not None:
            self._update_drag(point)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton:
            self._update_drag(event.position().toPoint());self.anchor=None;self.drag_origin=None

    def keyPressEvent(self,event):
        key=event.key()
        if key==Qt.Key_Control:
            owner=SelectionOverlay._control_drag_owner
            if not event.isAutoRepeat() and (owner is None or not owner.isVisible()):
                if owner is not None:
                    owner.control_origin=None;owner.control_dragging=False
                self.control_origin=self._pointer_position();self.control_dragging=False
                SelectionOverlay._control_drag_owner=self
            event.accept();return
        if key==Qt.Key_Escape:self.hide();self.cancelled.emit();return
        if key in (Qt.Key_Return,Qt.Key_Enter):
            if self.selection.width()>1 and self.selection.height()>1:
                rect = self.source_rect(self.selection.normalized().intersected(self.rect()))
                rect.translate(self.image_origin)
                self.hide();self.selected.emit(rect)
            else:
                self.selection=QRect(self.width()//4,self.height()//4,max(2,self.width()//2),max(2,self.height()//2));self.update()
            return
        directions={Qt.Key_Left:(-1,0),Qt.Key_Right:(1,0),Qt.Key_Up:(0,-1),Qt.Key_Down:(0,1)}
        if key in directions:
            if self.selection.isEmpty():self.selection=QRect(0,0,min(200,self.width()),min(150,self.height()))
            dx,dy=directions[key];step=10 if event.modifiers()&Qt.ControlModifier else 1
            r=QRect(self.selection)
            if event.modifiers()&Qt.ShiftModifier:
                r.setWidth(max(2,min(self.width()-r.x(),r.width()+dx*step)))
                r.setHeight(max(2,min(self.height()-r.y(),r.height()+dy*step)))
            else:
                r.moveLeft(max(0,min(self.width()-r.width(),r.x()+dx*step)))
                r.moveTop(max(0,min(self.height()-r.height(),r.y()+dy*step)))
            self.selection=r;self.update();return
        super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key_Control:
            owner=SelectionOverlay._control_drag_owner
            if not event.isAutoRepeat() and owner is not None:
                if owner.control_origin is not None and owner.control_dragging:
                    owner._update_drag(owner._pointer_position())
                    owner.anchor=None;owner.drag_origin=None
                    owner.control_origin=None;owner.control_dragging=False
                    SelectionOverlay._control_drag_owner=None
                    owner.control_drag_finished.emit()
                else:
                    owner.control_origin=None;owner.control_dragging=False
                    SelectionOverlay._control_drag_owner=None
            event.accept();return
        super().keyReleaseEvent(event)

    def hideEvent(self,event):
        guard = getattr(self, '_guard', None)
        if guard is not None:guard.stop()
        if SelectionOverlay._control_drag_owner is self:
            SelectionOverlay._control_drag_owner=None
            self.control_origin=None;self.control_dragging=False
        super().hideEvent(event)


class SelectionGroup:
    """One native overlay per output; the group owns their shared lifecycle."""
    def __init__(self,overlays):
        self.overlays=list(overlays)
    def present(self):
        previous = getattr(self, '_guard', None)
        if previous is not None:previous.stop()
        for overlay in self.overlays:overlay.present(guard=False)
        self._guard = SelectionGuard(self.overlays, self.overlays[0].recovery_requested.emit) if self.overlays else None
        pointer=QCursor.pos()
        target=next((overlay for overlay in self.overlays if overlay.geometry().contains(pointer)),None)
        if target is not None:
            target.raise_();target.activateWindow();target.setFocus()
    def hide(self):
        guard = getattr(self, '_guard', None)
        if guard is not None:guard.stop()
        for overlay in self.overlays:overlay.hide()
    def deleteLater(self):
        guard = getattr(self, '_guard', None)
        if guard is not None:guard.stop()
        for overlay in self.overlays:overlay.deleteLater()
    def close(self):
        guard = getattr(self, '_guard', None)
        if guard is not None:guard.stop()
        for overlay in self.overlays:overlay.close()
    def __bool__(self):
        return bool(self.overlays)

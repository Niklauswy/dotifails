"""Qt/Wayland keyboard capture for Hyprland bindings."""
from PySide6.QtCore import Qt, QEvent, QTimer, Signal
from PySide6.QtWidgets import QLineEdit


class KeyField(QLineEdit):
    recordingChanged = Signal(bool)
    captureError = Signal(str)
    captured = Signal(str)

    def __init__(self, text=''):
        super().__init__(text)
        self.recording = False
        self.pending = ''
        self.previous = text
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.cancel)
        self.setPlaceholderText('super + alt + a')

    def record(self):
        if self.recording:
            self.cancel()
            return
        self.previous=self.text();self.pending='';self.recording=True
        self.setReadOnly(True);self.setText('Pulsa la combinación en este campo · Esc cancela')
        self.setFocus();self.timer.start(10000);self.recordingChanged.emit(True)

    def cancel(self):
        if self.recording:
            value = self.previous
            self.stop()
            self.setText(value)

    def stop(self):
        self.timer.stop()
        self.recording = False
        self.pending = ''
        self.setReadOnly(False)
        self.recordingChanged.emit(False)

    def keyPressEvent(self,event):
        if not self.recording:return super().keyPressEvent(event)
        event.accept()
        if event.key()==Qt.Key_Escape:self.cancel();return
        if event.key() in (Qt.Key_Shift,Qt.Key_Control,Qt.Key_Alt,Qt.Key_Meta):return
        from PySide6.QtGui import QKeySequence
        key=QKeySequence(event.key()).toString()
        if not key:return
        mods=[name for mask,name in ((Qt.MetaModifier,'super'),(Qt.ControlModifier,'ctrl'),(Qt.AltModifier,'alt'),(Qt.ShiftModifier,'shift')) if event.modifiers()&mask]
        self.pending=' + '.join(mods+[key.lower() if len(key)==1 else key]);self.setText(self.pending+' · suelta las teclas')

    def keyReleaseEvent(self,event):
        if not self.recording:return super().keyReleaseEvent(event)
        event.accept()
        released={Qt.Key_Control:Qt.ControlModifier,Qt.Key_Alt:Qt.AltModifier,Qt.Key_Shift:Qt.ShiftModifier,Qt.Key_Meta:Qt.MetaModifier}.get(event.key(),Qt.NoModifier)
        if self.pending and not (event.modifiers() & ~released):
            value=self.pending;self.stop();self.setText(value);self.captured.emit(value)

    def event(self, event):
        if self.recording and event.type() == QEvent.ShortcutOverride:
            event.accept()
            return True
        return super().event(event)

    def hideEvent(self, event):
        self.cancel()
        super().hideEvent(event)

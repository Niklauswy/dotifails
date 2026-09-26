"""Bounded X11 keyboard capture, separate from Qt and sxhkd shortcuts."""
import ctypes
import ctypes.util
from PySide6.QtCore import QEvent, QSocketNotifier, QTimer, Signal
from PySide6.QtWidgets import QLineEdit

_x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
_x11.XKeysymToString.argtypes = [ctypes.c_ulong]
_x11.XKeysymToString.restype = ctypes.c_char_p
MODIFIERS = {'Shift_L','Shift_R','Control_L','Control_R','Alt_L','Alt_R','Meta_L','Meta_R','Super_L','Super_R','Hyper_L','Hyper_R','ISO_Level3_Shift','Mode_switch','Caps_Lock','Num_Lock'}

def keysym_name(value):
    name = _x11.XKeysymToString(value)
    return name.decode() if name else ''

def chord_from_x11(keysym, state):
    name = keysym_name(keysym)
    if not name or name in MODIFIERS:
        return ''
    modifiers = [label for mask,label in ((64,'super'),(4,'ctrl'),(8,'alt'),(1,'shift'),(128,'mode_switch')) if state & mask]
    return ' + '.join(modifiers + [name.lower() if len(name) == 1 else name])

class KeyField(QLineEdit):
    recordingChanged = Signal(bool)
    captureError = Signal(str)
    captured = Signal(str)

    def __init__(self, text=''):
        super().__init__(text)
        self.recording = False
        self.connection = self.notifier = None
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
        connection = None
        try:
            from Xlib import X, display
            connection = display.Display()
            window = connection.create_resource_object('window', int(self.window().winId()))
            result = window.grab_keyboard(False, X.GrabModeAsync, X.GrabModeAsync, X.CurrentTime)
            connection.sync()
            if result != X.GrabSuccess:
                connection.close()
                connection = None
                raise RuntimeError('El teclado está ocupado. Suelta las teclas y vuelve a pulsar Grabar.')
            self.connection = connection
            self.previous = self.text()
            self.pending = ''
            self.recording = True
            self.setReadOnly(True)
            self.setText('Pulsa la combinación… · Esc cancela')
            self.setFocus()
            self.notifier = QSocketNotifier(connection.fileno(), QSocketNotifier.Read, self)
            self.notifier.activated.connect(self.read_events)
            self.timer.start(10000)
            self.recordingChanged.emit(True)
            QTimer.singleShot(0,self.read_events)
        except Exception as exc:
            if connection and connection is not self.connection:
                try:connection.close()
                except Exception:pass
            self.stop()
            self.captureError.emit(str(exc))

    def read_events(self, *_):
        from Xlib import X
        try:
            while self.connection and self.connection.pending_events():
                event = self.connection.next_event()
                if event.type == X.KeyPress:
                    group = (event.state >> 13) & 3
                    symbol = self.connection.keycode_to_keysym(event.detail, group * 2)
                    if keysym_name(symbol) == 'Escape':
                        self.cancel()
                        return
                    chord = chord_from_x11(symbol, event.state)
                    if chord and not self.pending:
                        self.pending = chord
                        self.setText(chord + '  ·  suelta las teclas')
                elif event.type == X.KeyRelease and self.pending:
                    # Keep the grab until modifiers are released: no release leaks
                    # into sxhkd or ksuperkey and no bound command is launched.
                    state = self.connection.screen().root.query_pointer().mask
                    if not state & (1|4|8|64|128):
                        value = self.pending
                        self.stop()
                        self.setText(value)
                        self.captured.emit(value)
                        return
        except Exception as exc:
            self.cancel()
            self.captureError.emit('No se pudo capturar el teclado: ' + str(exc))

    def cancel(self):
        if self.recording:
            value = self.previous
            self.stop()
            self.setText(value)

    def stop(self):
        self.timer.stop()
        if self.notifier:
            self.notifier.setEnabled(False)
            self.notifier.deleteLater()
            self.notifier = None
        if self.connection:
            try:
                self.connection.ungrab_keyboard(0)
                self.connection.sync()
                self.connection.close()
            finally:
                self.connection = None
        self.recording = False
        self.pending = ''
        self.setReadOnly(False)
        self.recordingChanged.emit(False)

    def event(self, event):
        if self.recording and event.type() == QEvent.ShortcutOverride:
            event.accept()
            return True
        return super().event(event)

    def hideEvent(self, event):
        self.cancel()
        super().hideEvent(event)

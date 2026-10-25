"""Embedded cover art of an audio file, extracted by a short-lived ffmpeg child without blocking the UI."""
from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtGui import QImage

from .source import argument

TIMEOUT_MS = 5000
MAX_BYTES = 16 * 1024 * 1024
_dying = set()           # killed processes kept alive until they exit: destroying a running QProcess aborts it noisily


class CoverJob(QObject):
    """Emits ``ready(QImage)`` (null when the file has no picture) exactly once unless cancelled."""

    ready = Signal(object)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._done = False
        self._data = bytearray()
        self._process = QProcess(self)
        self._process.setProgram('ffmpeg')
        self._process.setArguments(['-v', 'error', '-nostdin', '-protocol_whitelist', 'file', '-i', argument(path), '-an',
                                    '-map', '0:v:0', '-frames:v', '1', '-f', 'image2pipe', '-c:v', 'png', '-'])
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(lambda _: self._finish(QImage()))
        self._timer = QTimer(self, singleShot=True, interval=TIMEOUT_MS)
        self._timer.timeout.connect(lambda: self._finish(QImage()))

    def start(self):
        self._process.start()
        self._timer.start()

    def cancel(self):
        self._done = True
        self._kill()

    def _read(self):
        self._data += bytes(self._process.readAllStandardOutput())
        if len(self._data) > MAX_BYTES:
            self._finish(QImage())

    def _finished(self, code, _status):
        self._read()
        self._finish(QImage.fromData(bytes(self._data)) if code == 0 else QImage())

    def _finish(self, image):
        if self._done:
            return
        self._done = True
        self._timer.stop()
        self._kill()
        self.ready.emit(image)

    def _kill(self):
        """Stop ffmpeg; the QProcess outlives this job until the OS has reaped the child."""
        process = self._process
        if process.state() == QProcess.NotRunning:
            return
        process.finished.connect(lambda *_: _dying.discard(process))
        _dying.add(process)
        process.setParent(None)
        process.kill()

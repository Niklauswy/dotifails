"""Asynchronous, serialized transport. MuPDF never runs on the GUI thread."""
import json
from pathlib import Path
import sys
from PySide6.QtCore import QObject, QProcess, Signal


class PdfWorker(QObject):
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = []
        self.active = None
        self.buffer = bytearray()
        self.stopping = False
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(self.exited)
        self.process.errorOccurred.connect(lambda _: self.failed.emit('No se pudo iniciar el motor PDF.'))
        self.process.started.connect(self.pump)
        self.process.start(sys.executable, ['-u', str(Path(__file__).with_name('pdf_engine.py'))])

    def request(self, op, callback, **args):
        # Keep only the latest queued render; edits and saves keep their order.
        if op == 'render':
            self.queue = [item for item in self.queue if item[0] != 'render']
        self.queue.append((op, args, callback))
        self.pump()

    def pump(self):
        if self.active or not self.queue or self.process.state() != QProcess.Running:
            return
        self.active = self.queue.pop(0)
        op, args, _ = self.active
        self.process.write((json.dumps({'op': op, 'args': args}) + '\n').encode())

    def read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b'\n' in self.buffer:
            line, _, self.buffer = self.buffer.partition(b'\n')
            active, self.active = self.active, None
            if active:
                try:
                    reply = json.loads(line)
                except ValueError:
                    reply = {'error': 'Respuesta inválida del motor PDF.'}
                active[2](reply)
            self.pump()

    def exited(self, *_):
        if not self.stopping:
            self.queue.clear()
            self.active = None
            self.failed.emit('El motor PDF se cerró. Vuelve a abrir el lector; los cambios sin guardar no se han escrito.')

    def stop(self):
        self.stopping = True
        self.queue.clear()
        self.process.closeWriteChannel()
        if not self.process.waitForFinished(500):
            self.process.kill()
            self.process.waitForFinished(500)

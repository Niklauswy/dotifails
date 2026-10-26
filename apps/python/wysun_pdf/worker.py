"""Asynchronous, serialized transport. MuPDF never runs on the GUI thread.

Requests wait in a stable priority queue (0 interactive, 1 thumbnails, 2 search). A ``key`` keeps one
queued request per purpose and ``cancel`` drops queued work nobody wants any more. Replies are a JSON
line, followed by ``blob`` raw bytes when they carry pixels; the callback finds those in ``result['blob']``.
"""
import json
from pathlib import Path
import sys
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from wysun_core import launch


class PdfWorker(QObject):
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = []          # [priority, op, args, callback, key]
        self.active = None
        self.buffer = bytearray()
        self.header = None       # parsed reply waiting for its binary frame
        self.stopping = False
        self.failure_reported = False
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(self.exited)
        self.process.errorOccurred.connect(lambda _: self.fail('El motor PDF no está disponible. Vuelve a abrir el lector.'))
        self.process.started.connect(self.pump)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert('PYTHONPATH', str(launch.ROOT))
        self.process.setProcessEnvironment(environment)
        self.process.start(sys.executable, ['-u', '-P', '-m', 'wysun_pdf.engine'])

    def request(self, op, callback, *, priority=0, key=None, **args):
        if key is not None:
            self.queue = [item for item in self.queue if item[4] != key]
        at = next((i for i, item in enumerate(self.queue) if item[0] > priority), len(self.queue))
        self.queue.insert(at, [priority, op, args, callback, key])
        self.pump()

    def cancel(self, predicate):
        """Drop queued requests for which ``predicate(op, key)`` is true; the one in flight still answers."""
        kept = [item for item in self.queue if not predicate(item[1], item[4])]
        removed, self.queue = len(self.queue) - len(kept), kept
        return removed

    def queued_keys(self):
        return {item[4] for item in self.queue if item[4] is not None}

    def pump(self):
        if self.active or not self.queue or self.process.state() != QProcess.Running:
            return
        self.active = self.queue.pop(0)
        _, op, args, _, _ = self.active
        self.process.write((json.dumps({'op': op, 'args': args}) + '\n').encode())

    def read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while True:
            if self.header is None:
                if b'\n' not in self.buffer:
                    return
                line, _, rest = self.buffer.partition(b'\n')
                self.buffer = bytearray(rest)
                try:
                    self.header = json.loads(line)
                except ValueError:
                    self.header = {'error': 'Respuesta inválida del motor PDF.'}
            size = self.header.get('blob', 0) if isinstance(self.header, dict) else 0
            if len(self.buffer) < size:
                return
            reply, self.header = self.header, None
            if size:
                reply['result']['blob'] = bytes(self.buffer[:size])
                del self.buffer[:size]
            reply.pop('blob', None)
            active, self.active = self.active, None
            if active:
                active[3](reply)
            self.pump()

    def exited(self, *_):
        self.fail('El motor PDF se cerró. Vuelve a abrir el lector; los cambios sin guardar no se han escrito.')

    def fail(self, message):
        if self.stopping or self.failure_reported:
            return
        self.failure_reported = True
        self.queue.clear()
        self.active = None
        self.failed.emit(message)

    def stop(self):
        self.stopping = True
        self.queue.clear()
        self.process.closeWriteChannel()
        if not self.process.waitForFinished(500):
            self.process.kill()
            self.process.waitForFinished(500)

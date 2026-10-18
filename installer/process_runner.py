"""Non-blocking installer subprocess, private logs and durable cancellation requests."""
import codecs
import datetime
import json
import os
from pathlib import Path
import uuid

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from install_events import PREFIX


class InstallerProcess(QObject):
    line = Signal(str)
    event = Signal(dict)
    finished = Signal(int, dict)
    started = Signal()

    def __init__(self, home, parent=None):
        super().__init__(parent)
        self.home = Path(home)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self.process.started.connect(self.started)
        self.directory = None
        self.result = {}
        self.log = None
        self.cancel_requested = False
        self._ended = True

    @property
    def running(self):
        return not self._ended

    def start(self, program, arguments, source, plan=None):
        if self.running:
            raise RuntimeError('Ya hay una operación en curso.')
        self.result = {}
        self.cancel_requested = False
        self._buffer = ''
        self._decoder = codecs.getincrementaldecoder('utf-8')('replace')
        ident = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6]
        self.directory = self.home / '.local/state/dotifails/runs' / ident
        self.directory.mkdir(parents=True, mode=0o700)
        self.log = (self.directory / 'console.log').open('x', encoding='utf-8')
        os.chmod(self.log.name, 0o600)
        if plan is not None:
            target = self.directory / 'plan.json'
            target.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
            target.chmod(0o600)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONUNBUFFERED', '1')
        env.insert('DOTIFAILS_EVENTS', '1')
        env.insert('DOTIFAILS_CANCEL_FILE', str(self.directory / 'cancel'))
        env.insert('SUDO_ASKPASS', str(Path(__file__).with_name('askpass.py')))
        env.insert('PATH', str(self.home / '.local/bin') + ':' + os.environ.get('PATH', ''))
        self.process.setProcessEnvironment(env)
        self.process.setWorkingDirectory(str(source))
        self._ended = False
        self.process.start(str(program), list(map(str, arguments)))

    def cancel(self):
        if self.running and not self.cancel_requested:
            # Never terminate apt/dpkg, native compilation or initramfs mid-write.
            target = self.directory / 'cancel'
            target.touch(mode=0o600)
            self.cancel_requested = True
            self.line.emit('Detención solicitada. Se completará la operación en curso.')

    def _read(self):
        self._buffer += self._decoder.decode(bytes(self.process.readAllStandardOutput()))
        while '\n' in self._buffer:
            value, self._buffer = self._buffer.split('\n', 1)
            self._consume(value)

    def _consume(self, value):
        value = value.rstrip('\r')
        if self.log:
            self.log.write(value + '\n')
            self.log.flush()
        if value.startswith(PREFIX):
            try:
                payload = json.loads(value[len(PREFIX):])
                if not isinstance(payload, dict) or not isinstance(payload.get('event'), str):
                    raise ValueError('Invalid event')
                if payload['event'] == 'result':
                    self.result = payload
                self.event.emit(payload)
                return
            except (ValueError, TypeError):
                pass
        self.line.emit(value)

    def _error(self, error):
        if error == QProcess.FailedToStart:
            self.result = dict(status='failed', message=self.process.errorString())
            self._consume(self.process.errorString())
            self._finish(-1)

    def _finished(self, code, status):
        self._read()
        self._buffer += self._decoder.decode(b'', final=True)
        if self._buffer:
            self._consume(self._buffer)
            self._buffer = ''
        if status == QProcess.CrashExit:
            self.result = dict(status='failed', message='El proceso terminó de forma inesperada. Revisa el registro y los respaldos.')
        self._finish(code)

    def _finish(self, code):
        if self._ended:
            return
        self._ended = True
        if self.log:
            self.log.close()
            self.log = None
        if not self.result:
            self.result = dict(status='complete' if code == 0 else ('cancelled' if code == 130 else 'failed'))
        if code not in (0, 2) and self.result.get('status') == 'complete':
            self.result['status'] = 'failed'
        self.finished.emit(code, self.result)

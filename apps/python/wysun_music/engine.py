"""mpv audio engine over its JSON IPC socket.

Event driven: mpv pushes observed properties through a UNIX socket watched by
a QSocketNotifier, so no timer polls the player. One process lives for the
whole application; tracks are swapped with ``loadfile`` so playback starts
without process startup cost.
"""
import json
from pathlib import Path
import shutil
import socket
import tempfile

from PySide6.QtCore import QObject, QProcess, QSocketNotifier, QTimer, Signal

OBSERVED = ('time-pos', 'duration', 'pause', 'volume', 'mute')


class MpvEngine(QObject):
    position_changed = Signal(float)
    duration_changed = Signal(float)
    pause_changed = Signal(bool)
    volume_changed = Signal(int)
    mute_changed = Signal(bool)
    ended = Signal()
    failed = Signal(str)

    def __init__(self, volume=60, parent=None):
        super().__init__(parent)
        self.volume = volume
        self.paused = True
        self.stopping = False
        self.endpoint = None
        self._directory = None
        self._socket = None
        self._reader = None
        self._writer = None
        self._outbox = b''
        self._inbox = b''
        self._attempts = 0
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ForwardedErrorChannel)
        self.process.setStandardOutputFile(QProcess.nullDevice())
        self.process.errorOccurred.connect(self._process_error)
        self.process.finished.connect(self._process_finished)

    # ----------------------------------------------------------------- state
    @property
    def running(self):
        return self.process.state() != QProcess.NotRunning

    @property
    def ready(self):
        return self._socket is not None

    # -------------------------------------------------------------- commands
    def load(self, path, start=0.0, paused=False):
        self.command('loadfile', str(path), 'replace', -1, {'start': f'{max(0.0, start):.3f}'})
        self.command('set_property', 'pause', bool(paused))
        self.paused = bool(paused)
        self.pause_changed.emit(self.paused)

    def set_paused(self, paused):
        self.command('set_property', 'pause', bool(paused))

    def seek(self, seconds):
        self.command('seek', max(0.0, float(seconds)), 'absolute+exact')

    def set_volume(self, value):
        self.volume = max(0, min(100, int(value)))
        self.command('set_property', 'volume', self.volume)

    def set_mute(self, muted):
        self.command('set_property', 'mute', bool(muted))

    def command(self, *args):
        """Queue a command; the process starts lazily on the first one."""
        self._outbox += (json.dumps({'command': list(args)}) + '\n').encode()
        if self.ready:
            self._flush()
        elif not self.running:
            self._start()

    def quit(self, timeout=700):
        self.stopping = True
        if self.ready:
            self._outbox = b'{"command":["quit"]}\n'
            self._flush()
        if self.running and not self.process.waitForFinished(timeout):
            self.process.terminate()
            self.process.waitForFinished(timeout)
        self._close_socket()
        self._cleanup()

    # ------------------------------------------------------------- lifecycle
    def _start(self):
        binary = shutil.which('mpv')
        if not binary:
            self._outbox = b''
            self.failed.emit('Falta mpv para reproducir audio.')
            return
        self.stopping = False
        self._directory = tempfile.TemporaryDirectory(prefix='wysun-music-')
        self.endpoint = str(Path(self._directory.name) / 'mpv.sock')
        observe = b''.join((json.dumps({'command': ['observe_property', i, name]}) + '\n').encode()
                           for i, name in enumerate(OBSERVED))
        self._outbox = observe + self._outbox
        # mpv 0.40's Wayland clipboard backend can spin a core at 100 % depending on
        # what is copied; a headless audio engine has no use for the clipboard.
        self.process.start(binary, [
            '--no-config', '--no-video', '--audio-display=no', '--idle=yes', '--no-terminal',
            '--clipboard-backends-remove=wayland',
            '--gapless-audio=weak', '--replaygain=track', '--audio-client-name=wysun-music',
            '--input-ipc-server=' + self.endpoint, f'--volume={self.volume}'])
        self._attempts = 0
        QTimer.singleShot(25, self._connect)

    def _connect(self):
        if not self.running or self.ready:
            return
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(self.endpoint)
        except OSError:
            client.close()
            self._attempts += 1
            if self._attempts < 120:
                QTimer.singleShot(25, self._connect)
            else:
                self.failed.emit('No se pudo conectar con el reproductor de audio.')
            return
        client.setblocking(False)
        self._socket = client
        self._reader = QSocketNotifier(client.fileno(), QSocketNotifier.Read, self)
        self._reader.activated.connect(self._read)
        self._writer = QSocketNotifier(client.fileno(), QSocketNotifier.Write, self)
        self._writer.activated.connect(self._flush)
        self._flush()

    def _flush(self):
        if not self.ready:
            return
        try:
            while self._outbox:
                sent = self._socket.send(self._outbox)
                self._outbox = self._outbox[sent:]
        except BlockingIOError:
            pass
        except OSError:
            self._close_socket()
            return
        # Only wake up for writability while something is still waiting to go out.
        self._writer.setEnabled(bool(self._outbox))

    def _read(self):
        try:
            while True:
                chunk = self._socket.recv(65536)
                if not chunk:
                    self._close_socket()
                    break
                self._inbox += chunk
        except BlockingIOError:
            pass
        except OSError:
            self._close_socket()
        *lines, self._inbox = self._inbox.split(b'\n')
        for line in lines:
            try:
                self._event(json.loads(line))
            except ValueError:
                continue

    def _event(self, data):
        event = data.get('event')
        if event == 'property-change':
            name, value = data.get('name'), data.get('data')
            if value is None:
                return
            if name == 'time-pos':
                self.position_changed.emit(float(value))
            elif name == 'duration':
                self.duration_changed.emit(float(value))
            elif name == 'pause':
                self.paused = bool(value)
                self.pause_changed.emit(self.paused)
            elif name == 'volume':
                self.volume = round(value)
                self.volume_changed.emit(self.volume)
            elif name == 'mute':
                self.mute_changed.emit(bool(value))
        elif event == 'end-file':
            if data.get('reason') == 'eof':
                self.ended.emit()
            elif data.get('reason') == 'error':
                self.failed.emit('No se pudo reproducir este archivo de audio.')

    def _close_socket(self):
        for notifier in (self._reader, self._writer):
            if notifier is not None:
                notifier.setEnabled(False)
                notifier.deleteLater()
        if self._socket is not None:
            self._socket.close()
        self._socket = self._reader = self._writer = None
        self._inbox = b''

    def _process_error(self, error):
        if error == QProcess.FailedToStart:
            self.failed.emit('No se pudo iniciar mpv. Comprueba que esté instalado.')

    def _process_finished(self, *_):
        self._close_socket()
        self._cleanup()
        self._outbox = b''
        self.paused = True
        self.pause_changed.emit(True)
        if not self.stopping:
            self.failed.emit('El reproductor se detuvo. Pulsa reproducir para continuar.')

    def _cleanup(self):
        if self._directory:
            self._directory.cleanup()
            self._directory = None

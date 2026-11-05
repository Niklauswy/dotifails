"""Listening without downloading: a song becomes a YouTube video (the same match the downloader uses) and then a
direct audio URL that mpv plays over the network. Nothing is written to disk but the song → video choice; the audio
URL is signed and short-lived, so it stays in memory only."""
import json
import re
import subprocess
import time

from PySide6.QtCore import QObject, QProcess, QRunnable, QThreadPool, Signal

from wysun_music import data as music_data

AUDIO_TTL = 50 * 60          # seconds; YouTube signs audio URLs for a few hours
VIDEO = re.compile(r'(?:v=|youtu\.be/)([\w-]{11})')


def video_id(url):
    match = VIDEO.search(url or '')
    return match[1] if match else ''


def audio_url(video_url):
    """Direct audio stream of a YouTube video."""
    process = subprocess.run(music_data.ytdlp() + ['-f', 'bestaudio/best', '-g', '--no-playlist', '--', video_url],
                             text=True, capture_output=True, timeout=60)
    lines = [line for line in process.stdout.splitlines() if line.startswith('http')]
    if process.returncode or not lines:
        raise RuntimeError(process.stderr.strip()[-300:] or 'YouTube no entregó el audio.')
    return lines[0]


def entry_track(entry):
    """A YouTube result (``--flat-playlist``) as a track. «Artist - Title» videos are split into both fields."""
    title = entry.get('title') or 'Sin título'
    channel = entry.get('channel') or entry.get('uploader') or 'YouTube'
    artist = re.sub(r'\s*-\s*Topic$', '', channel)
    if ' - ' in title and not channel.endswith('- Topic'):
        artist, title = (part.strip() for part in title.split(' - ', 1))
    title = re.sub(r'\s*[\(\[](?:official|video|audio|lyric|letra|visuali[sz]er)[^\)\]]*[\)\]]', '', title,
                   flags=re.I).strip() or title
    title = title.split(' | ')[0].strip() or title          # «Song | Album» on artist channels
    return {'id': 'yt-' + entry['id'], 'title': title, 'artist': artist, 'duration': entry.get('duration') or 0,
            'youtube_url': 'https://www.youtube.com/watch?v=' + entry['id']}


class _Signals(QObject):
    done = Signal(str, int, object)


class _Job(QRunnable):
    def __init__(self, key, serial, track, signals):
        super().__init__()
        self.key, self.serial, self.track, self.signals = key, serial, track, signals

    def run(self):
        try:
            video = self.track.get('youtube_url') or music_data.find_video(self.track)
            result = {'video': video, 'audio': audio_url(video)} if video else {'error': 'No está en YouTube.'}
        except Exception as error:                      # network, yt-dlp, timeout: the caller skips the song
            result = {'error': str(error)[-300:] or 'No se pudo conectar.'}
        self.signals.done.emit(self.key, self.serial, result)


def helper_environment():
    """The app's environment with the private yt-dlp zipapp first on PYTHONPATH, so the helper imports it."""
    import os
    from pathlib import Path
    env = dict(os.environ)
    try:
        binary = music_data.ytdlp()[0]
    except RuntimeError:
        return env
    if Path(binary).is_file():
        env['PYTHONPATH'] = os.pathsep.join(p for p in (binary, env.get('PYTHONPATH', '')) if p)
    return env


def helper_command():
    """The warm yt-dlp helper, on this same Python (venv or system) with the app's module path."""
    import sys
    return [sys.executable, '-P', '-m', 'wysun_music.streamd']


class StreamResolver(QObject):
    """``request(key, track, urgent)`` ⇒ ``resolved(key, audio_url)`` or ``failed(key, message)``; ``call(op, payload,
    callback)`` for searches and mixes. Work goes to the warm helper (``streamd``); if it cannot start, each song
    runs its own yt-dlp as before. Repeated requests share one lookup; a fresh audio URL is reused for ``AUDIO_TTL``."""
    resolved = Signal(str, str)
    failed = Signal(str, str)
    video_found = Signal(str, str)      # key, YouTube watch URL: kept so a later download skips the search

    def __init__(self, parent=None, command=None):
        super().__init__(parent)
        self.command = command or helper_command()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.pool.setExpiryTimeout(20000)
        self.signals = _Signals(self)
        self.signals.done.connect(self._done)
        self._audio = {}
        self._pending = set()
        self._serial = 0
        self._calls = {}                # request id -> callback(answer)
        self._buffer = b''
        self._broken = False
        self.helper = None

    def cached(self, key):
        found = self._audio.get(key)
        return found[0] if found and time.monotonic() - found[1] < AUDIO_TTL else None

    def request(self, key, track, urgent=True):
        url = self.cached(key)
        if url:
            self.resolved.emit(key, url)
            return
        if key in self._pending:        # already on its way (perhaps as a prefetch)
            return
        self._pending.add(key)
        self._serial += 1
        if not self._ensure():
            self.pool.start(_Job(key, self._serial, dict(track), self.signals))
            return
        payload = {'op': 'resolve', 'track': {k: v for k, v in track.items() if isinstance(v, (str, int, float))},
                   'urgent': urgent}
        self.call(payload, lambda answer, key=key: self._done(key, 0, answer))

    # ---------------------------------------------------------------- helper
    def warm(self):
        """Start the helper ahead of the first song, so loading yt-dlp is not part of pressing play."""
        self._ensure()

    def call(self, payload, callback):
        """Send one request to the helper; ``callback(answer)`` runs on the UI thread."""
        if not self._ensure():
            callback({'ok': False, 'error': 'No se pudo iniciar yt-dlp.'})
            return
        self._serial += 1
        self._calls[self._serial] = callback
        self.helper.write(json.dumps(dict(payload, id=self._serial), ensure_ascii=False).encode() + b'\n')

    def _ensure(self):
        if self.helper is not None and self.helper.state() != QProcess.NotRunning:
            return True
        if self._broken:
            return False
        self.helper = QProcess(self)
        self.helper.setProcessChannelMode(QProcess.ForwardedErrorChannel)
        self.helper.readyReadStandardOutput.connect(self._read)
        self.helper.finished.connect(self._helper_finished)
        from PySide6.QtCore import QProcessEnvironment
        env = QProcessEnvironment()
        for name, value in helper_environment().items():
            env.insert(name, value)
        self.helper.setProcessEnvironment(env)
        self.helper.start(self.command[0], self.command[1:])
        if not self.helper.waitForStarted(3000):
            self._broken = True
            self.helper = None
            return False
        return True

    def _read(self):
        self._buffer += bytes(self.helper.readAllStandardOutput())
        *lines, self._buffer = self._buffer.split(b'\n')
        for line in lines:
            try:
                answer = json.loads(line)
            except ValueError:
                continue
            callback = self._calls.pop(answer.get('id'), None)
            if callback is not None:
                callback(answer)

    def _helper_finished(self, *_):
        """Idle exit or crash: whatever was waiting fails now; the next request starts a new helper."""
        calls, self._calls = self._calls, {}
        self._buffer = b''
        for callback in calls.values():
            callback({'ok': False, 'error': 'yt-dlp se detuvo.'})

    def _done(self, key, _serial, result):
        self._pending.discard(key)
        if result.get('audio'):
            self._audio[key] = (result['audio'], time.monotonic())
            self.video_found.emit(key, result['video'])
            self.resolved.emit(key, result['audio'])
        else:
            self.failed.emit(key, result.get('error', ''))

    def wait(self, ms=-1):
        end = time.monotonic() + (ms / 1000 if ms >= 0 else 3600)
        from PySide6.QtCore import QCoreApplication
        while (self._calls or self.pool.activeThreadCount()) and time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.01)
        return self.pool.waitForDone(max(0, int((end - time.monotonic()) * 1000)))

    def shutdown(self):
        if self.helper is not None:
            self.helper.closeWriteChannel()
            if not self.helper.waitForFinished(1500):
                self.helper.kill()

"""Listening without downloading: a song becomes a YouTube video (the same match the downloader uses) and then a
direct audio URL that mpv plays over the network. Nothing is written to disk but the song → video choice; the audio
URL is signed and short-lived, so it stays in memory only."""
import re
import subprocess
import time

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

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


class StreamResolver(QObject):
    """``request(key, track)`` ⇒ ``resolved(key, audio_url)`` or ``failed(key, message)``. Repeated requests for a
    key share one lookup; a fresh audio URL is reused for ``AUDIO_TTL``."""
    resolved = Signal(str, str)
    failed = Signal(str, str)
    video_found = Signal(str, str)      # key, YouTube watch URL: kept so a later download skips the search

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.pool.setExpiryTimeout(20000)
        self.signals = _Signals(self)
        self.signals.done.connect(self._done)
        self._audio = {}
        self._pending = set()
        self._serial = 0

    def cached(self, key):
        found = self._audio.get(key)
        return found[0] if found and time.monotonic() - found[1] < AUDIO_TTL else None

    def request(self, key, track):
        url = self.cached(key)
        if url:
            self.resolved.emit(key, url)
            return
        if key in self._pending:
            return
        self._pending.add(key)
        self._serial += 1
        self.pool.start(_Job(key, self._serial, dict(track), self.signals))

    def _done(self, key, _serial, result):
        self._pending.discard(key)
        if result.get('audio'):
            self._audio[key] = (result['audio'], time.monotonic())
            self.video_found.emit(key, result['video'])
            self.resolved.emit(key, result['audio'])
        else:
            self.failed.emit(key, result.get('error', ''))

    def wait(self, ms=-1):
        return self.pool.waitForDone(ms)

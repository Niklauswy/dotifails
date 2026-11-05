"""Warm yt-dlp for Wysun Music: one helper process that imports yt-dlp once and answers JSON lines on stdin.

Starting yt-dlp costs seconds on its own (≈3.5 s on a busy machine), and a streamed Spotify song needs two calls
(find the video, then its audio URL). Kept loaded, the same song resolves in about 3 s. Urgent requests (the song
you asked for) go before prefetches. The helper exits after ``IDLE`` seconds without work; the app starts it again
when needed.

Requests: ``{"id", "op": "resolve", "track", "urgent"}``, ``{"id", "op": "search", "query", "limit"}``,
``{"id", "op": "mix", "url", "limit"}``. Answers: ``{"id", "ok": true, ...}`` or ``{"id", "ok": false, "error"}``.
"""
import json
import queue
import shutil
import sys
import threading
import time

IDLE = 600
WORKERS = 3


def load_ytdlp():
    """yt-dlp as a module. The app puts Wysun's private zipapp first on PYTHONPATH (a zipapp is importable as it is),
    see ``stream.helper_environment``."""
    import yt_dlp
    options = dict(quiet=True, no_warnings=True, socket_timeout=20, retries=1, noplaylist=True)
    if shutil.which('node'):
        options['js_runtimes'] = {'node': {}}

    def factory(flat):
        return yt_dlp.YoutubeDL(dict(options, extract_flat='in_playlist') if flat
                                else dict(options, format='bestaudio/best'))
    return factory


class Service:
    """The requests, with one pair of YoutubeDL objects per thread (they are not thread-safe)."""

    def __init__(self, factory):
        self.factory = factory
        self.local = threading.local()

    def _ydl(self, flat):
        name = 'flat' if flat else 'full'
        if not hasattr(self.local, name):
            setattr(self.local, name, self.factory(flat))
        return getattr(self.local, name)

    def handle(self, request):
        try:
            answer = getattr(self, 'op_' + request['op'])(request)
        except Exception as error:                       # network, extractor: the app skips or hides it
            answer = {'ok': False, 'error': str(error)[-300:] or type(error).__name__}
        return dict(answer, id=request.get('id'))

    def op_search(self, request):
        found = self._ydl(True).extract_info(f"ytsearch{int(request.get('limit', 10))}:{request['query']}",
                                             download=False)
        return {'ok': True, 'entries': [_entry(e) for e in found.get('entries') or [] if e and e.get('id')]}

    def op_mix(self, request):
        from wysun_music.stream import video_id
        vid = video_id(request['url'])
        found = self._ydl(True).extract_info(f'https://www.youtube.com/watch?v={vid}&list=RD{vid}', download=False)
        entries = [_entry(e) for e in found.get('entries') or [] if e and e.get('id') and e['id'] != vid]
        return {'ok': True, 'entries': entries[:int(request.get('limit', 25))]}

    def op_resolve(self, request):
        from wysun_music import data as music_data
        track = request['track']
        video = track.get('youtube_url')
        if not video:
            query = f"{track['artist'].split(',')[0]} {music_data.song_title(track['title'])} official audio"
            entries = self.op_search({'query': query, 'limit': 10})['entries']
            entries.sort(key=lambda e: music_data.candidate_score(track, e), reverse=True)
            if not entries or music_data.candidate_score(track, entries[0]) < 10:
                return {'ok': False, 'error': 'No está en YouTube.'}
            video = 'https://www.youtube.com/watch?v=' + entries[0]['id']
        info = self._ydl(False).extract_info(video, download=False)
        audio = info.get('url') or next((f.get('url') for f in info.get('requested_formats') or [] if f.get('url')), '')
        if not audio:
            return {'ok': False, 'error': 'YouTube no entregó el audio.'}
        return {'ok': True, 'video': video, 'audio': audio}


def _entry(entry):
    return {k: entry.get(k) for k in ('id', 'title', 'channel', 'uploader', 'duration', 'channel_is_verified')}


def serve(service, stdin=sys.stdin, stdout=sys.stdout):
    jobs = queue.PriorityQueue()
    lock = threading.Lock()
    last = [time.monotonic()]

    def work():
        while True:
            _, _, request = jobs.get()
            answer = service.handle(request)
            with lock:
                stdout.write(json.dumps(answer, ensure_ascii=False) + '\n')
                stdout.flush()
            last[0] = time.monotonic()

    for _ in range(WORKERS):
        threading.Thread(target=work, daemon=True).start()

    def reader():
        for number, line in enumerate(stdin):
            try:
                request = json.loads(line)
            except ValueError:
                continue
            last[0] = time.monotonic()
            jobs.put((0 if request.get('urgent') else 1, number, request))
        last[0] = 0                          # stdin closed: the app is gone
    threading.Thread(target=reader, daemon=True).start()
    while time.monotonic() - last[0] < IDLE or not jobs.empty() and last[0]:
        time.sleep(1)


def main():
    serve(Service(load_ytdlp()))


if __name__ == '__main__':
    main()

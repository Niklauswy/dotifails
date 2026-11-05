"""What the connection adds: Spotify's public editorial lists (read from their embed pages), YouTube mixes seeded by
what you play in Wysun, and «Para ti», ranked here from both. No account, token or cookie is involved.

Whether we are online is learnt from the requests themselves (and from QNetworkInformation when its backend knows):
when every list fails, the app behaves as offline and tries again a little later."""
from PySide6.QtCore import QObject, QTimer, Signal

from wysun_music import stream
from wysun_music.store import artists, normalize

# Spotify playlist ids, checked against the public embed on 2026-11-04. Spotify publishes no «Viral» list there.
CHARTS = (
    ('novedades', 'Novedades', '37i9dQZF1DX4JAvHpjipBk'),
    ('top-mexico', 'Top 50 · México', '37i9dQZEVXbO3qyFxbkOE1'),
    ('top-global', 'Top 50 · Global', '37i9dQZEVXbMDoHDwVN2tF'),
    ('exitos', 'Éxitos del momento', '37i9dQZF1DXcBWIGoYBM5M'),
    ('pop', 'Pop en ascenso', '37i9dQZF1DWUa8ZRTfalHk'),
    ('latino', 'Viva Latino', '37i9dQZF1DX10zKzsJ2jva'),
    ('reggaeton', 'Baila Reggaeton', '37i9dQZF1DWY7IeIP1cdjF'),
    ('rap', 'RapCaviar', '37i9dQZF1DX0XUsuxWHRQd'),
    ('rock', 'Rock clásico', '37i9dQZF1DWXRqgorJj26U'),
    ('lofi', 'Lo-fi para concentrarte', '37i9dQZF1DWWQRwui0ExPn'),
)
MIX_SEEDS = 3
MIX_LENGTH = 25
RETRY_MS = 120_000


def recommend(charts, weights, local, recent, artist_of, limit=30, per_artist=2):
    """«Para ti»: songs found in several lists, or by artists you play, rank first; what you already have or just
    heard is left out, and no artist takes more than ``per_artist`` places.

    ``charts``: lists of keys (best first); ``weights``: normalized artist → how much you play them (0–1)."""
    scores = {}
    for keys in charts:
        for position, key in enumerate(keys):
            if key in local or key in recent:
                continue
            scores[key] = scores.get(key, 0) + 2 + (1 - position / max(1, len(keys)))
    for key in scores:
        scores[key] += 4 * weights.get(artist_of(key), 0)
    taken, result = {}, []
    for key in sorted(scores, key=lambda k: -scores[k]):
        artist = artist_of(key)
        if taken.get(artist, 0) >= per_artist:
            continue
        taken[artist] = taken.get(artist, 0) + 1
        result.append(key)
        if len(result) == limit:
            break
    return result


def mix(video_url):
    """The YouTube mix («Radio») of a video, without the video itself."""
    import json
    import subprocess
    from wysun_music import data as music_data
    vid = stream.video_id(video_url)
    process = subprocess.run(music_data.ytdlp() + ['--flat-playlist', '--dump-single-json', '--playlist-end',
                                                   str(MIX_LENGTH + 1), '--',
                                                   f'https://www.youtube.com/watch?v={vid}&list=RD{vid}'],
                             text=True, capture_output=True, timeout=90)
    if process.returncode:
        raise RuntimeError(process.stderr.strip()[-300:] or 'YouTube no respondió.')
    entries = [e for e in json.loads(process.stdout).get('entries') or [] if e and e.get('id') and e['id'] != vid]
    return {'tracks': [stream.entry_track(e) for e in entries[:MIX_LENGTH]],
            'cover_url': f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'}


class Online(QObject):
    """Keeps the library's online lists and «Para ti» fresh while there is a connection."""
    changed = Signal()

    def __init__(self, library, metadata, resolver=None, parent=None):
        super().__init__(parent)
        self.library, self.metadata, self.resolver = library, metadata, resolver
        self.for_you = []
        self.mixes = []
        self._charts = {}
        self._mixes = {}
        self._seeds = []
        self._waiting = set()
        self._rebuild = QTimer(self, singleShot=True, interval=250)
        self._rebuild.timeout.connect(self._publish)
        self._retry = QTimer(self, singleShot=True, interval=RETRY_MS)
        self._retry.timeout.connect(self.refresh)
        metadata.ready.connect(self._ready)
        library.history_changed.connect(self._history)
        self._network = None
        self._watch_network()
        library.set_online(True)

    def _watch_network(self):
        try:
            from PySide6.QtNetwork import QNetworkInformation
        except ImportError:
            return
        if not QNetworkInformation.loadDefaultBackend() or QNetworkInformation.instance() is None:
            return
        self._network = QNetworkInformation.instance()
        self._network.reachabilityChanged.connect(self._reachability)

    def _reachability(self, value):
        from PySide6.QtNetwork import QNetworkInformation
        if value == QNetworkInformation.Reachability.Disconnected:
            self.library.set_online(False)
        elif not self.library.online:
            self.refresh()

    # ----------------------------------------------------------------- fetch
    def refresh(self):
        from wysun_music.spotify import import_link
        self._waiting = {('online-chart', pid) for _, _, pid in CHARTS}
        for _, _, pid in CHARTS:
            url = 'https://open.spotify.com/playlist/' + pid
            self.metadata.request('online-chart', pid, lambda url=url: import_link(url))
        self._request_mixes()

    def _history(self):
        if self.library.online and self._seed_videos() != self._seeds:
            self._request_mixes()

    def _seed_videos(self):
        """YouTube videos of your most played songs, one per artist."""
        seen, seeds = set(), []
        for key in self.library.store.most_played(40):
            track = self.library.track(key)
            lead = normalize(track.get('artist', '').split(',')[0])
            if track.get('youtube_url') and lead and lead not in seen:
                seen.add(lead)
                seeds.append((key, track['youtube_url']))
            if len(seeds) == MIX_SEEDS:
                break
        return seeds

    def _request_mixes(self):
        """Mixes go to the warm yt-dlp helper (not the artwork threads, which they would hold for seconds)."""
        self._seeds = self._seed_videos()
        for key, url in self._seeds:
            vid = stream.video_id(url)
            if vid in self._mixes:
                continue
            if self.resolver is None:
                self.metadata.request('online-mix', vid, lambda url=url: mix(url))
                continue
            self.resolver.call({'op': 'mix', 'url': url, 'limit': MIX_LENGTH},
                               lambda answer, vid=vid: self._mix_answer(vid, answer))

    def _mix_answer(self, vid, answer):
        if answer.get('ok') and answer.get('entries'):
            self._ready('online-mix', vid, {'tracks': [stream.entry_track(e) for e in answer['entries']],
                                            'cover_url': f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'})

    def _ready(self, kind, key, result):
        if kind == 'online-chart':
            self._waiting.discard((kind, key))
            if result.get('collections'):
                self._charts[key] = result['collections'][0]
            if not self._waiting:
                found = any(pid in self._charts for _, _, pid in CHARTS)
                self.library.set_online(found)
                if not found:
                    self._retry.start()
            self._rebuild.start()
        elif kind == 'online-mix' and result.get('tracks'):
            self._mixes[key] = result
            self._rebuild.start()

    # --------------------------------------------------------------- publish
    def _publish(self):
        collections = []
        for cid, title, pid in CHARTS:
            raw = self._charts.get(pid)
            if raw:
                collections.append(dict(raw, id=cid, title=title))
        names = {}
        for key, url in self._seeds:
            names[stream.video_id(url)] = (self.library.track(key).get('artist', '').split(',')[0]).strip()
        mixes = []
        for vid, raw in self._mixes.items():
            if vid in names:
                mixes.append(dict(raw, id='mix-' + vid, title='Mix · ' + names[vid], source='YouTube'))
        self.library.set_online_collections(collections + mixes)
        self.mixes = ['online:' + m['id'] for m in mixes]
        self.for_you = self._for_you([c['id'] for c in collections])
        self.changed.emit()

    def _for_you(self, chart_ids):
        library = self.library
        plays = {}
        for rank, key in enumerate(library.store.most_played(60)):
            for name in artists(library.track(key))[:1]:
                plays[normalize(name)] = max(plays.get(normalize(name), 0), 1 - rank / 60)
        for name, keys in library.artists().items():
            plays[normalize(name)] = max(plays.get(normalize(name), 0), min(1, len(keys) / 10) * 0.6)
        local = {k for k in library.all_keys()}
        recent = set(library.store.recent(30))

        def artist_of(key):
            return normalize(library.track(key).get('artist', '').split(',')[0])
        charts = [library.collection('online:' + cid).keys for cid in chart_ids]
        return recommend(charts, plays, local, recent, artist_of)

    def collections(self):
        return [c for c in self.library.online_collections() if c.id not in self.mixes]

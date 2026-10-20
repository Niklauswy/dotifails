"""Small, bounded, on-demand metadata jobs. No network runs in the UI thread."""
import hashlib
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlencode, quote, urlparse
from urllib.request import Request, urlopen
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from music_library import normalize
import music_data

UA = 'WysunMusic/2.0 (local desktop music player; metadata cache)'
_mb_lock = threading.Lock()
_mb_last = 0


def fetch(url, limit=4*1024*1024):
    if urlparse(url).scheme != 'https':
        raise ValueError('Solo se permiten fuentes HTTPS')
    with urlopen(Request(url, headers={'User-Agent': UA}), timeout=10) as response:
        data = response.read(limit+1)
    if len(data) > limit:
        raise ValueError('Respuesta demasiado grande')
    return data


def get_json(url):
    return json.loads(fetch(url))


def musicbrainz(path):
    global _mb_last
    with _mb_lock:
        delay = 1.1-(time.monotonic()-_mb_last)
        if delay > 0:
            time.sleep(delay)
        _mb_last = time.monotonic()
        return get_json('https://musicbrainz.org/ws/2/'+path)


class JobSignals(QObject):
    done = Signal(str, str, object)


class Job(QRunnable):
    def __init__(self, kind, key, fn, signals):
        super().__init__()
        self.kind, self.key, self.fn, self.signals = kind, key, fn, signals

    def run(self):
        try:
            result = self.fn()
        except Exception as error:
            result = {'error': str(error), 'unavailable': True}
        self.signals.done.emit(self.kind, self.key, result)


class Metadata(QObject):
    ready = Signal(str, str, object)

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = Path(root)/'metadata'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.pool.setExpiryTimeout(5000)
        self.signals = JobSignals(self)
        self.signals.done.connect(self.finished)
        self.pending = set()
        self.results = {}

    def filename(self, kind, key):
        return self.root/(kind+'-'+hashlib.sha256(key.encode()).hexdigest()+'.json')

    def request(self, kind, key, fn):
        token = (kind, key)
        if token in self.pending:
            return
        path = self.filename(kind, key)
        try:
            cached = json.loads(path.read_text())
            ttl = 300 if kind=='spotify-import' else 3600 if cached.get('error') else (86400 if cached.get('unavailable') else 30*86400)
            if time.time()-path.stat().st_mtime < ttl:
                self.results[token] = cached
                self.ready.emit(kind, key, cached)
                return
        except (OSError, ValueError):
            pass
        self.pending.add(token)
        self.pool.start(Job(kind, key, fn, self.signals))

    def finished(self, kind, key, data):
        self.pending.discard((kind, key))
        self.results[kind, key] = data
        path = self.filename(kind, key)
        temp = path.with_suffix('.tmp')
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False));temp.chmod(0o600);temp.replace(path)
        except OSError:
            pass
        self.ready.emit(kind, key, data)

    def download_image(self, url):
        path = self.root/(hashlib.sha256(url.encode()).hexdigest()+'.image')
        if not path.exists():
            data = fetch(url)
            from PySide6.QtGui import QImage
            image = QImage.fromData(data)
            if image.isNull() or image.width()*image.height() > 25_000_000:
                raise ValueError('Imagen no válida')
            image = image.scaled(512, 512, aspectMode=__import__('PySide6.QtCore', fromlist=['Qt']).Qt.KeepAspectRatio,
                                 mode=__import__('PySide6.QtCore', fromlist=['Qt']).Qt.SmoothTransformation)
            temp = path.with_suffix('.tmp')
            image.save(str(temp), 'PNG');temp.chmod(0o600);temp.replace(path)
        return str(path)

    def cover(self, key, spotify_url):
        def work():
            data = get_json('https://open.spotify.com/oembed?'+urlencode({'url': spotify_url}))
            url = data.get('thumbnail_url')
            return {'path': self.download_image(url), 'source': spotify_url} if url else {'unavailable': True}
        self.request('cover', key, work)

    def lyrics(self, key, track, reference):
        def work():
            title = music_data.song_title(track['title'])
            artist = track['artist'].split(',')[0]
            duration = track.get('duration', 0)
            params = dict(track_name=title, artist_name=artist, duration=round(duration))
            if reference.get('album'):
                params['album_name'] = reference['album']
            try:
                candidates = [get_json('https://lrclib.net/api/get?'+urlencode(params))]
            except Exception:
                candidates = get_json('https://lrclib.net/api/search?'+urlencode(dict(track_name=title, artist_name=artist)))
            valid = [c for c in candidates if normalize(music_data.song_title(c.get('trackName', ''))) == normalize(title)
                     and normalize(artist) in [normalize(a) for a in c.get('artistName', '').split(',')]]
            valid.sort(key=lambda c: abs(c.get('duration', 0)-duration))
            if not valid:
                return {'unavailable': True}
            result = valid[0]
            compatible = abs(result.get('duration', 0)-duration) <= 2
            return dict(synced=result.get('syncedLyrics') if compatible else None,
                        plain=result.get('plainLyrics'), instrumental=result.get('instrumental', False),
                        source='https://lrclib.net', compatible=compatible)
        # Cache by audio duration too: a different recording must not inherit timing.
        self.request('lyrics', key, work)

    def artist(self, name):
        def work():
            escaped = name.replace('"', '').replace('\\', '')
            data = musicbrainz('artist/?'+urlencode({'query': f'artist:"{escaped}"', 'fmt': 'json', 'limit': 5}))
            matches = [a for a in data.get('artists', []) if normalize(a.get('name')) == normalize(name) and int(a.get('score', 0)) >= 95]
            if len(matches) != 1:
                return {'unavailable': True}
            entity = musicbrainz('artist/'+matches[0]['id']+'?inc=url-rels&fmt=json')
            wiki = next((r['url']['resource'] for r in entity.get('relations', []) if r.get('type') == 'wikidata'), '')
            if not wiki:
                return {'unavailable': True}
            qid = wiki.rstrip('/').split('/')[-1]
            claims = get_json('https://www.wikidata.org/wiki/Special:EntityData/'+qid+'.json')['entities'][qid].get('claims', {})
            photos = claims.get('P18', [])
            if not photos:
                return {'unavailable': True}
            filename = photos[0]['mainsnak']['datavalue']['value']
            details = get_json('https://commons.wikimedia.org/w/api.php?'+urlencode(dict(action='query', format='json',
                  prop='imageinfo', titles='File:'+filename, iiprop='url|extmetadata', iiurlwidth=512)))
            info = next(iter(details['query']['pages'].values())).get('imageinfo', [{}])[0]
            url = info.get('thumburl') or info.get('url')
            return {'path': self.download_image(url), 'source': info.get('descriptionurl', wiki),
                    'credit': info.get('extmetadata', {}).get('Artist', {}).get('value', ''),
                    'license': info.get('extmetadata', {}).get('LicenseShortName', {}).get('value', '')}
        self.request('artist', name, work)

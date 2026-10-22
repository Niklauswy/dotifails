"""Private local music library and resumable YouTube download queue."""
import argparse
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import unicodedata

DATA = Path(os.environ.get('ORBIT_MUSIC_HOME', str(Path.home()/'.local/share/orbit/music')))
LIBRARY = Path(os.environ.get('ORBIT_MUSIC_LIBRARY', str(Path.home()/'Music/Orbita')))
SUFFIXES = {'.m4a', '.opus', '.mp3', '.flac', '.ogg', '.wav', '.aac'}


def empty():
    return {'version': 1, 'tracks': {}, 'collections': {}, 'paused': False}


def read_state():
    try:
        return json.loads((DATA/'library.json').read_text())
    except FileNotFoundError:
        return empty()


@contextmanager
def edit_state():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (DATA/'library.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = read_state()
        yield state
        temp = DATA/'library.json.tmp'
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        temp.chmod(0o600)
        temp.replace(DATA/'library.json')


def update_track(key, **values):
    with edit_state() as state:
        state['tracks'][key].update(values)


def canonical(text):
    return ' '.join(re.findall(r'[a-z0-9]+',unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().casefold()))


def equivalent_track(state,source):
    key=source['id']
    if key in state['tracks']:return key
    for other,track in state['tracks'].items():
        if track.get('album_audio_of'):continue
        if key in track.get('spotify_ids',[]):return other
        if source.get('youtube_url') and track.get('youtube_url')==source['youtube_url']:return other
        # Different Spotify IDs often describe the same recording on two releases.
        if canonical(song_title(source['title']))!=canonical(song_title(track['title'])):continue
        if canonical(source['artist'].split(',')[0])!=canonical(track['artist'].split(',')[0]):continue
        expected=source.get('duration',0);actual=track.get('reference_duration') or track.get('duration',0)
        if expected and actual and abs(expected-actual)<=2:return other
    return key


def enqueue(manifest):
    with edit_state() as state:
        for collection in manifest['collections']:
            keys = list(state['collections'].get(collection['id'], {}).get('tracks', [])) if collection.get('append') else []
            for source in collection['tracks']:
                key = source['id'] if source.get('album_audio_of') else equivalent_track(state,source)
                keys.append(key)
                if key not in state['tracks']:
                    state['tracks'][key] = dict(source, status='pending', progress='', error='',reference_duration=source.get('duration',0))
                elif source.get('youtube_url') and state['tracks'][key].get('status')!='ready':
                    state['tracks'][key]['youtube_url'] = source['youtube_url']
                if len(source['id'])==22 and source['id'].isalnum():
                    track=state['tracks'][key]
                    track['spotify_ids']=list(dict.fromkeys(track.get('spotify_ids',[])+[source['id']]))
                    if source.get('duration'):track.setdefault('reference_duration',source['duration'])
            state['collections'][collection['id']] = {k: v for k, v in collection.items() if k != 'tracks'}
            state['collections'][collection['id']]['tracks'] = list(dict.fromkeys(keys))
        state['paused'] = False


def set_paused(paused):
    with edit_state() as state:
        state['paused'] = bool(paused)


def retry_failed():
    with edit_state() as state:
        for track in state['tracks'].values():
            if track['status'] in {'error', 'review'}:
                track.update(status='pending', error='', progress='')
        state['paused'] = False


def ytdlp():
    private = Path.home()/'.local/share/dotifails/tools/yt-dlp/yt-dlp'
    if not private.exists():private = Path.home()/'.local/share/musica-terminal/bin/yt-dlp'
    binary = str(private) if private.exists() else shutil.which('yt-dlp')
    if not binary:
        raise RuntimeError('Falta yt-dlp para descargar.')
    args = [binary, '--ignore-config', '--socket-timeout', '20', '--retries', '1', '--no-warnings']
    if private.exists() and shutil.which('node'):
        args += ['--js-runtimes', 'node']
    return args


def normal(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return set(re.findall(r'[a-z0-9]+', text))


def song_title(text):
    return re.sub(r'\s*[\(\[]\s*(?:feat\.?|ft\.?)\s+.*?[\)\]]', '', text, flags=re.I).strip()


def candidate_score(track, entry):
    title = normal(song_title(track['title']))
    found = normal(entry.get('title', ''))
    artist = normal(track['artist'].split(',')[0])
    channel = normal(entry.get('channel') or entry.get('uploader') or '')
    if not title or len(title & found)/len(title) < .75:
        return -100
    if artist and len(artist & (found | channel))/len(artist) < .6:
        return -100
    unwanted = {'cover', 'karaoke', 'sped', 'slowed', 'nightcore', 'reaction', 'tutorial', 'live', 'remix'}
    if (found & unwanted) - title:
        return -100
    score = 10*len(title & found)/len(title) + 4*len(artist & (found | channel))/max(1, len(artist))
    duration = entry.get('duration')
    expected = track.get('duration', 0)
    if expected and duration:
        difference = abs(duration-expected)
        if difference > (2 if (track.get('album_audio_of') or track.get('prefer_audio')) else max(10, expected*.05)):
            return -100
        score += max(0, 3-difference/10)
    if entry.get('channel_is_verified'):
        score += 2
    if 'topic' in channel:
        score += 2
    if {'audio', 'visualizer'} & found:score += 3
    if 'video' in found and not 'audio' in found:score -= 2
    return score


def find_video(track):
    if track.get('youtube_url'):
        return track['youtube_url']
    query = f"{track['artist'].split(',')[0]} {song_title(track['title'])} official audio"
    process = subprocess.run(ytdlp()+['--flat-playlist', '--dump-single-json', '--', 'ytsearch10:'+query],
                             text=True, capture_output=True, timeout=100)
    if process.returncode:
        raise RuntimeError(process.stderr.strip()[-1200:] or 'Falló la búsqueda en YouTube.')
    entries = [e for e in json.loads(process.stdout).get('entries', []) if e and e.get('id')]
    entries.sort(key=lambda e: candidate_score(track, e), reverse=True)
    if not entries or candidate_score(track, entries[0]) < 10:
        return None
    return 'https://www.youtube.com/watch?v='+entries[0]['id']


def probe(path):
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
            'format=duration,bit_rate:stream=codec_name,bit_rate,sample_rate', '-of', 'json', str(path)],
            capture_output=True, text=True, timeout=15, check=True)
        data = json.loads(result.stdout)
        audio = data['streams'][0]
        return {'duration': float(data.get('format', {}).get('duration', 0)),
                'codec': audio.get('codec_name', ''),
                'bitrate': int(audio.get('bit_rate') or data.get('format', {}).get('bit_rate') or 0)}
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return {}


def download_track(key, track):
    update_track(key, status='downloading', progress='Buscando audio oficial…', error='')
    url = find_video(track)
    if not url:
        update_track(key, status='review', progress='', error='No se encontró una versión que coincida con título y artista.')
        return
    update_track(key, youtube_url=url, progress='Preparando descarga…')
    LIBRARY.mkdir(parents=True, exist_ok=True)
    template = str(LIBRARY/(key+'.%(ext)s'))
    last_error = ''
    for format_spec in ('bestaudio', 'bestaudio[ext=m4a]/bestaudio'):
        args = ytdlp()+['--no-playlist', '-f', format_spec, '-x', '--audio-format', 'best',
            '--embed-metadata', '--write-info-json', '--no-overwrites', '--newline',
            '--progress-template', 'download:%(progress._percent_str)s · %(progress._speed_str)s',
            '-o', template, '--', url]
        lines = []
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as process:
            last_update = 0
            for line in process.stdout:
                line = line.strip()
                lines.append(line)
                if len(lines) > 30:
                    lines.pop(0)
                if time.monotonic()-last_update > .8:
                    update_track(key, progress=line[-180:])
                    last_update = time.monotonic()
            code = process.wait()
        if code == 0:
            paths = [p for p in LIBRARY.glob(key+'.*') if p.suffix.lower() in SUFFIXES]
            if paths:
                path = max(paths, key=lambda p: p.stat().st_size)
                metadata = probe(path)
                if not metadata.get('duration'):
                    raise RuntimeError('El archivo descargado no contiene audio válido.')
                if (track.get('album_audio_of') or track.get('prefer_audio')) and abs(metadata['duration']-(track.get('reference_duration') or track.get('duration',0)))>2:
                    update_track(key, status='review', path=str(path), progress='', error='La duración no coincide con la versión de álbum; se conserva el archivo para revisar.')
                    return
                update_track(key, status='ready', path=str(path), progress='', error='', **metadata)
                return
        last_error = '\n'.join(lines[-8:])
        if '403' not in last_error:
            break
    raise RuntimeError(last_error or 'No se pudo descargar el audio.')


def worker():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (DATA/'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        with edit_state() as state:
            for track in state['tracks'].values():
                if track['status'] == 'downloading':
                    track['status'] = 'pending'
        with ThreadPoolExecutor(max_workers=2) as executor:
            active = {}
            while True:
                state = read_state()
                pending = [(key, t) for key, t in state['tracks'].items() if t['status'] == 'pending']
                if not state.get('paused'):
                    for key, track in pending[:2-len(active)]:
                        update_track(key, status='downloading', progress='Preparando…')
                        active[executor.submit(download_track, key, track)] = (key, track)
                if not active:
                    return
                done, _ = wait(active, timeout=1, return_when=FIRST_COMPLETED)
                for future in done:
                    key, track = active.pop(future)
                    try:
                        future.result()
                        status = read_state()['tracks'][key]['status']
                        print(status.upper()+':', track['artist'], '—', track['title'], flush=True)
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                        update_track(key, status='error', progress='', error=str(error)[-1500:])
                        print('ERROR:', track['title'], str(error)[-300:], flush=True)


def start_worker():
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (DATA/'downloads.log').open('a') as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker'],
                         stdout=log, stderr=log, start_new_session=True)


def audio_files(paths):
    """Files and, recursively, the audio inside folders, in a stable order."""
    for path in paths:
        path = Path(path).expanduser().resolve()
        candidates = sorted(path.rglob('*')) if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() in SUFFIXES:
                yield candidate


def tags(path):
    """Embedded title/artist/album, when the file carries them."""
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format_tags:stream_tags',
                                 '-of', 'json', str(path)], capture_output=True, text=True, timeout=15, check=True)
        data = json.loads(result.stdout)
        # Ogg/Opus keep Vorbis comments on the stream, MP3/M4A on the container.
        sources = [s.get('tags', {}) for s in data.get('streams', [])] + [data.get('format', {}).get('tags', {})]
        found = {k.lower(): v.strip() for source in sources for k, v in source.items() if isinstance(v, str)}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}
    return {k: found[k] for k in ('title', 'artist', 'album') if found.get(k)}


def import_files(paths):
    import hashlib
    entries = {}
    for path in audio_files(paths):
        key = 'local-'+hashlib.sha256(str(path).encode()).hexdigest()[:22]
        entries[key] = dict(dict(id=key, title=path.stem, artist='Archivo local', path=str(path),
                                 status='ready', progress='', error='', **probe(path)), **tags(path))
    # Probe outside the lock: a large folder must not block the download worker.
    with edit_state() as state:
        state['tracks'].update(entries)
    return list(entries)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--enqueue', type=Path)
    parser.add_argument('--start', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.enqueue:
        enqueue(json.loads(args.enqueue.read_text()))
    if args.resume:
        set_paused(False)
    if args.worker:
        worker()
    elif args.start:
        start_worker()


if __name__ == '__main__':
    main()

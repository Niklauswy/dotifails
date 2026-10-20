"""Playback order and private UI storage, independent from the download queue."""
import json
from pathlib import Path
import random
import re
import sqlite3
import unicodedata


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text)).casefold() if not unicodedata.combining(c)).strip()


def artists(track):
    names = re.split(r',\s*|\s+&\s+', track.get('artist', ''))
    # Include featured artists even when the source puts credits in the title.
    featured = re.search(r'\((?:feat\.?|ft\.?)\s+([^)]*)\)', track.get('title', ''), re.I)
    if featured:
        names += re.split(r',\s*|\s+&\s+', featured[1])
    return list(dict.fromkeys(n.strip() for n in names if n.strip()))


class PlaybackOrder:
    """A stable shuffled sequence; moving backward never draws another random song."""
    def __init__(self):
        self.keys = []
        self.index = -1
        self.shuffle = False
        self.repeat = False
        self.source = []

    @property
    def current(self):
        return self.keys[self.index] if 0 <= self.index < len(self.keys) else None

    def start(self, keys, current, shuffle=False):
        self.source = list(dict.fromkeys(keys))
        self.keys = self.source.copy()
        self.shuffle = shuffle
        if current not in self.keys:
            self.keys.insert(0, current)
            self.source.insert(0, current)
        if shuffle:
            self.keys.remove(current)
            random.shuffle(self.keys)
            # Keep a reversible previous path for a selected song in the middle.
            pivot = min(self.source.index(current), len(self.keys))
            self.keys.insert(pivot, current)
        self.index = self.keys.index(current)

    def move(self, direction, available=lambda key: True):
        if not self.keys:
            return None
        cursor = self.index
        for _ in range(len(self.keys)):
            cursor += direction
            if not 0 <= cursor < len(self.keys):
                if not self.repeat:
                    return None
                cursor %= len(self.keys)
            if available(self.keys[cursor]):
                self.index = cursor
                return self.current
        return None

    def export(self):
        return dict(keys=self.keys, source=self.source, index=self.index, shuffle=self.shuffle, repeat=self.repeat)

    def restore(self, data):
        self.keys = list(dict.fromkeys(data.get('keys', [])))
        self.source = data.get('source', self.keys).copy()
        self.index = int(data.get('index', -1))
        self.shuffle = bool(data.get('shuffle'))
        self.repeat = bool(data.get('repeat'))


class MusicStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.root/'player.sqlite3')
        (self.root/'player.sqlite3').chmod(0o600)
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS favorites (track TEXT PRIMARY KEY, added REAL DEFAULT (unixepoch()));
        CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS references_meta (track TEXT PRIMARY KEY, duration REAL, album TEXT, spotify TEXT);
        CREATE TABLE IF NOT EXISTS variants (track TEXT PRIMARY KEY, preferred TEXT);
        PRAGMA user_version=1;
        ''')

    def favorites(self):
        return {row[0] for row in self.db.execute('SELECT track FROM favorites')}

    def toggle(self, key):
        if key in self.favorites():
            self.db.execute('DELETE FROM favorites WHERE track=?', (key,))
            value = False
        else:
            self.db.execute('INSERT INTO favorites(track) VALUES(?)', (key,))
            value = True
        self.db.commit()
        return value

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM preferences WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)', (key, json.dumps(value)))
        self.db.commit()

    def import_references(self, manifest):
        for collection in manifest.get('collections', []):
            album = collection['title'] if '/album/' in collection.get('source', '') else ''
            for track in collection.get('tracks', []):
                # An album reference takes priority over playlist descriptions.
                self.db.execute('''INSERT INTO references_meta VALUES(?,?,?,?)
                    ON CONFLICT(track) DO UPDATE SET
                    duration=COALESCE(references_meta.duration,excluded.duration),
                    album=CASE WHEN excluded.album!='' THEN excluded.album ELSE references_meta.album END''',
                    (track['id'], track.get('duration'), album, 'https://open.spotify.com/track/'+track['id']))
        self.db.commit()

    def reference(self, key):
        row = self.db.execute('SELECT duration,album,spotify FROM references_meta WHERE track=?', (key,)).fetchone()
        return dict(duration=row[0], album=row[1], spotify=row[2]) if row else {}

    def preferred(self, key):
        row = self.db.execute('SELECT preferred FROM variants WHERE track=?', (key,)).fetchone()
        return row[0] if row else key

    def set_preferred(self, key, preferred):
        self.db.execute('INSERT OR REPLACE INTO variants VALUES(?,?)', (key, preferred))
        self.db.commit()

    def close(self):
        self.db.close()


def parse_lrc(text):
    rows = []
    offset = 0
    for line in (text or '').splitlines():
        match = re.match(r'\[offset:([+-]?\d+)\]', line, re.I)
        if match:
            offset = int(match[1])/1000
        times = re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]', line)
        content = re.sub(r'\[[^]]*\]', '', line).strip()
        for minutes, seconds in times:
            rows.append((int(minutes)*60+float(seconds), content or '♪'))
    return sorted((max(0, t+offset), text) for t, text in rows)

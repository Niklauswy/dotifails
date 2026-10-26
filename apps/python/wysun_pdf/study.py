"""Private study library. PDF annotations remain owned by the PDF engine.

Short SQLite transactions and optimistic entry revisions prevent windows from
silently overwriting each other's reflections. No document text is indexed.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from wysun_core import paths


class StudyConflict(ValueError):
    pass


class StudyStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else paths.data('wysun', 'pdf-reader', 'study.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise ValueError('Esta biblioteca pertenece a una versión más reciente de Wysun PDF.')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
                    pages INTEGER NOT NULL, page INTEGER NOT NULL DEFAULT 0,
                    opened REAL NOT NULL, recent INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY, document TEXT NOT NULL REFERENCES documents(id),
                    page INTEGER NOT NULL, quote TEXT NOT NULL, anchor TEXT NOT NULL,
                    body TEXT NOT NULL, kind TEXT NOT NULL, revision INTEGER NOT NULL,
                    updated REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS entries_document ON entries(document, updated);
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=.15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def opened(self, path, pages, page=0, remember=True):
        path = str(Path(path).resolve())
        with self.connect() as db:
            db.execute('''INSERT INTO documents(id,path,title,pages,page,opened,recent) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET pages=excluded.pages, page=excluded.page,
                opened=excluded.opened, recent=excluded.recent''',
                       (uuid.uuid4().hex, path, Path(path).stem, pages, page, time.time(), int(remember)))
            return dict(db.execute('SELECT * FROM documents WHERE path=?', (path,)).fetchone())

    def position(self, document, page):
        with self.connect() as db:
            db.execute('UPDATE documents SET page=? WHERE id=?', (page, document))

    def recent(self, query=''):
        with self.connect() as db:
            rows = db.execute('''SELECT d.*, (SELECT COUNT(*) FROM entries e WHERE e.document=d.id)
                AS notes FROM documents d WHERE recent=1 ORDER BY opened DESC LIMIT 200''').fetchall()
        return [dict(row) for row in rows if query.casefold() in row['title'].casefold()]

    def forget(self, document):
        with self.connect() as db:
            db.execute('UPDATE documents SET recent=0 WHERE id=?', (document,))

    def clear_recent(self):
        with self.connect() as db:
            db.execute('UPDATE documents SET recent=0')

    def entries(self, document, limit=500):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM entries WHERE document=? ORDER BY updated DESC LIMIT ?', (document, limit))]

    def save_entry(self, document, page, quote, anchor, body, kind='note', entry=None):
        if kind not in ('note', 'question'):
            raise ValueError('Tipo de entrada desconocido')
        if not body.strip():
            raise ValueError('Escribe una idea antes de guardarla.')
        identifier = entry['id'] if entry else uuid.uuid4().hex
        revision = entry['revision'] + 1 if entry else 1
        with self.connect() as db:
            if entry:
                changed = db.execute('''UPDATE entries SET body=?, kind=?, revision=?, updated=?
                    WHERE id=? AND revision=? AND document=?''',
                    (body, kind, revision, time.time(), identifier, entry['revision'], document)).rowcount
                if not changed:
                    raise StudyConflict('Esta nota cambió en otra ventana. Tu texto sigue aquí; guárdalo como una nota nueva.')
            else:
                db.execute('INSERT INTO entries VALUES(?,?,?,?,?,?,?,?,?)',
                    (identifier, document, page, quote, json.dumps(anchor), body, kind, revision, time.time()))
            return dict(db.execute('SELECT * FROM entries WHERE id=?', (identifier,)).fetchone())

    def delete_entry(self, entry):
        with self.connect() as db:
            changed = db.execute('DELETE FROM entries WHERE id=? AND revision=?',
                                 (entry['id'], entry['revision'])).rowcount
            if not changed:
                raise StudyConflict('La nota cambió en otra ventana. Actualiza el cuaderno antes de eliminarla.')

    def export(self, document):
        with self.connect() as db:
            book = db.execute('SELECT * FROM documents WHERE id=?', (document,)).fetchone()
        lines = [f'# {book["title"]}', '', 'Cuaderno de estudio · Wysun PDF', '']
        for entry in reversed(self.entries(document, limit=-1)):
            label = 'Pregunta' if entry['kind'] == 'question' else 'Reflexión'
            lines += [f'## {label} · página PDF {entry["page"] + 1}', '']
            if entry['quote']:
                lines += ['> ' + entry['quote'].replace('\n', '\n> '), '']
            lines += [entry['body'], '']
        return '\n'.join(lines)

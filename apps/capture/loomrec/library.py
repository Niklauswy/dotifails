"""Private project library. Deletion is a reversible directory move."""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import os
import uuid
from .schema import load_project, save_project, atomic_json


def default_root():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share')))/'loomrec'/'recordings'


@dataclass
class Entry:
    path: Path
    title: str
    duration: float
    modified: float
    collection: str = ''
    error: str = ''


class Library:
    def __init__(self, root=None):
        self.root = Path(root) if root else default_root()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def new_directory(self):
        path = self.root/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
        path.mkdir(mode=0o700)
        return path

    def entries(self, query='', trash=False):
        import json
        base = self.root/'.trash' if trash else self.root
        result = []
        if not base.exists(): return result
        for directory in base.iterdir():
            if not directory.is_dir() or directory.name.startswith('.'): continue
            path = directory/'project.json'
            if not path.exists() and not (directory/'capture.json').exists(): continue
            try:
                p = load_project(path)
                metadata = directory/'library.json'
                collection = json.loads(metadata.read_text()).get('collection','') if metadata.exists() else ''
                entry = Entry(path,p.title,p.duration,path.stat().st_mtime,collection)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                entry = Entry(path,directory.name,0,directory.stat().st_mtime,error=str(exc))
            if query.casefold() in (entry.title+' '+entry.collection).casefold(): result.append(entry)
        return sorted(result,key=lambda e:e.modified,reverse=True)

    def _directory(self, path, trash=False):
        directory = Path(path).resolve().parent
        base = (self.root/'.trash' if trash else self.root).resolve()
        if directory.parent != base or directory.name.startswith('.'):
            raise ValueError('El proyecto no pertenece a esta biblioteca')
        return directory

    def rename(self, path, title):
        self._directory(path)
        if not title.strip(): raise ValueError('Escribe un título')
        p = load_project(path); p.title = title.strip(); save_project(p,path)

    def organize(self, path, collection):
        directory = self._directory(path)
        atomic_json(directory/'library.json', {'collection':collection.strip()})

    def delete(self, path):
        directory = self._directory(path)
        # Never move a running recorder's output directory.
        import fcntl
        with (directory/'capture.lock').open('a') as lock:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('Detén la grabación antes de moverla a la papelera')
            trash = self.root/'.trash'; trash.mkdir(exist_ok=True)
            destination = trash/directory.name
            if destination.exists(): destination = trash/(directory.name+'-'+uuid.uuid4().hex[:8])
            directory.rename(destination)
        return destination/'project.json'

    def restore(self, path):
        directory = self._directory(path,trash=True)
        destination = self.root/directory.name
        if destination.exists(): raise FileExistsError('Ya existe un proyecto con esta ruta')
        directory.rename(destination)
        return destination/'project.json'

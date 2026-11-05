"""What a LANShare shares, and the only way from a page path to a real one.

One folder is browsed as itself ('folder' mode). Files, or a mix of files and folders, become a
virtual list ('list' mode): each item is a root of its own under a virtual name (its name; equal
names get ' (2)', ' (3)'…), and every path stays confined to its root — no '..', no hidden parts,
no links that leave it.
"""
import os
import re

VIDEO = {'.mp4', '.m4v', '.mov', '.webm', '.mkv', '.avi', '.ts', '.flv', '.wmv'}
IMAGE = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.avif', '.heic'}
AUDIO = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg', '.opus'}
TEXT = {'.txt', '.md', '.log', '.json', '.csv', '.py', '.js', '.ts', '.html', '.css', '.sh', '.yml', '.yaml',
        '.toml', '.ini', '.xml', '.c', '.cpp', '.h', '.java', '.rs', '.go', '.srt', '.vtt'}
ARCHIVE = {'.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.xz', '.bz2'}


def kind_of(name, is_dir=False):
    if is_dir:
        return 'dir'
    ext = os.path.splitext(name)[1].lower()
    for kind, group in (('video', VIDEO), ('image', IMAGE), ('audio', AUDIO), ('text', TEXT), ('archive', ARCHIVE)):
        if ext in group:
            return kind
    return 'pdf' if ext == '.pdf' else 'file'


def clean_name(name):
    """A safe file name from what a browser sent: no folders, control characters or leading dots."""
    name = os.path.basename((name or '').replace('\\', '/')).strip()
    name = re.sub(r'[\x00-\x1f]', '', name).lstrip('.')
    return name[:240]


def unique_name(directory, name):
    base, ext = os.path.splitext(name)
    candidate, n = name, 1
    while os.path.lexists(os.path.join(directory, candidate)):
        n += 1
        candidate = f'{base} ({n}){ext}'
    return candidate


def _inside(real, root):
    return real == root or real.startswith(root.rstrip(os.sep) + os.sep)


def _parts(rel):
    """The parts of a page path, or None when one is hidden. In a list the first part is an item's own name,
    which may start with a dot when that file was shared on purpose."""
    if '\x00' in (rel or ''):
        return None
    parts = [p for p in (rel or '').replace('\\', '/').split('/') if p]
    if any(p.startswith('.') for p in parts[1:]) or parts[:1] == ['..']:
        return None
    return parts


class Share:
    def __init__(self, paths):
        paths = [os.path.realpath(p) for p in paths]
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self.mode = 'folder'
            self.root = paths[0]
            self.roots = {}
            self.title = os.path.basename(self.root) or self.root
            return
        self.mode = 'list'
        self.root = None
        self.roots = {}
        for path in paths:
            name = os.path.basename(path) or path
            if name in self.roots:
                base, ext = os.path.splitext(name) if os.path.isfile(path) else (name, '')
                n = 2
                while f'{base} ({n}){ext}' in self.roots:
                    n += 1
                name = f'{base} ({n}){ext}'
            self.roots[name] = path
        self.title = next(iter(self.roots)) if len(self.roots) == 1 else f'{len(self.roots)} elementos'

    @property
    def paths(self):
        return [self.root] if self.mode == 'folder' else list(self.roots.values())

    def _base(self, rel):
        """(root, real path) for a page path, or None when it leaves what is shared."""
        parts = _parts(rel)
        if parts is None:
            return None
        if self.mode == 'folder':
            if parts and parts[0].startswith('.'):
                return None
            root = self.root
        else:
            if not parts or parts[0] not in self.roots:
                return None
            root = self.roots[parts[0]]
            parts = parts[1:]
            if parts and not os.path.isdir(root):
                return None
        real = os.path.realpath(os.path.join(root, *parts))
        return (root, real) if _inside(real, root) else None

    def resolve(self, rel):
        found = self._base(rel)
        return found[1] if found else None

    def is_dir(self, rel):
        if self.mode == 'list' and not _parts(rel):
            return _parts(rel) is not None
        real = self.resolve(rel)
        return bool(real) and os.path.isdir(real)

    @staticmethod
    def _entry(name, path, is_dir, st):
        item = {'name': name, 'kind': kind_of(name, is_dir), 'mtime': int(st.st_mtime)}
        if is_dir:
            try:
                item['count'] = sum(1 for x in os.scandir(path) if not x.name.startswith('.'))
            except OSError:
                item['count'] = 0
        else:
            item['size'] = st.st_size
        return item

    def listing(self, rel):
        """Entries of a folder (or of the virtual list); LookupError when it is not a shared folder."""
        if self.mode == 'list' and _parts(rel) == []:
            entries = []
            for name, path in self.roots.items():
                try:
                    entries.append(self._entry(name, path, os.path.isdir(path), os.stat(path)))
                except OSError:
                    continue
            return entries
        found = self._base(rel)
        if not found or not os.path.isdir(found[1]):
            raise LookupError(rel)
        root, directory = found
        entries = []
        for item in os.scandir(directory):   # PermissionError reaches the caller
            if item.name.startswith('.'):
                continue
            try:
                if not _inside(os.path.realpath(item.path), root):
                    continue
                entries.append(self._entry(item.name, item.path, item.is_dir(), item.stat()))
            except OSError:
                continue
        return entries

    def zip_name(self, rel):
        parts = _parts(rel) or []
        if parts:
            return parts[-1]
        return self.title if self.mode == 'folder' else 'archivos'

    def _walk(self, root, start, prefix):
        if os.path.isfile(start):
            yield start, prefix
            return
        for base, dirs, files in os.walk(start):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and _inside(os.path.realpath(os.path.join(base, d)), root))
            for name in sorted(files):
                full = os.path.join(base, name)
                if name.startswith('.') or not _inside(os.path.realpath(full), root) or not os.path.isfile(full):
                    continue
                yield full, prefix + '/' + os.path.relpath(full, start).replace(os.sep, '/')

    def zip_members(self, rel):
        """(real path, name in the archive) for everything under a page path."""
        if self.mode == 'list' and _parts(rel) == []:
            for name, path in self.roots.items():
                yield from self._walk(path, path, name)
            return
        found = self._base(rel)
        if not found:
            raise LookupError(rel)
        root, real = found
        yield from self._walk(root, real, self.zip_name(rel))

    def display(self, rel):
        """Where something is, for people: 'Videos/Clases'."""
        parts = _parts(rel) or []
        if self.mode == 'folder':
            return '/'.join([self.title] + parts)
        return '/'.join(parts) or self.title

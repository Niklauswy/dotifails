#!/usr/bin/env python3
"""Data provider for the native Wysun launcher (apps/shell/modules/launcher).

Same sources as the Qt palette (orbit.py): clipboard history, files, emoji and
calculator history. Commands are argv arrays and results are
JSON; nothing is evaluated by a shell. Private data stays in ~/.local/share/orbit.
"""
import datetime as dt, json, os, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from core import Store, STATE, HOME, calculate, file_index  # noqa: E402

MODES = ('status', 'all', 'clip', 'files', 'emoji', 'calc')
LIMIT = 150
CLIP_KINDS = {'texto': 'text', 'text': 'text', 'imagen': 'image', 'image': 'image', 'color': 'color', 'enlace': 'url', 'url': 'url'}
CLIP_ICONS = {'image': 'image', 'color': 'palette', 'url': 'link', 'text': 'description'}
DEFAULT_EMOJI = [('😀', 'sonrisa feliz'), ('😂', 'risa lágrimas'), ('❤️', 'amor corazón'), ('✨', 'brillos magia'), ('👍', 'bien pulgar'), ('🙏', 'gracias manos'), ('🎉', 'fiesta celebración'), ('🔥', 'fuego'), ('🚀', 'cohete lanzar'), ('💡', 'idea luz'), ('✅', 'listo correcto'), ('👀', 'ojos mirar'), ('💻', 'computadora trabajo'), ('☕', 'café'), ('🌙', 'luna noche'), ('🫶', 'corazón manos'), ('🤔', 'pensar duda'), ('😎', 'genial gafas'), ('🥹', 'emoción'), ('💜', 'corazón morado')]
FILE_CACHE = STATE / 'launcher-files.json'
FILE_TTL = 300


def row(kind, title, subtitle='', icon='', **extra):
    return dict(kind=kind, title=title, subtitle=subtitle, icon=icon, **extra)


def clip_folder():
    folder = Path(os.environ.get('XDG_RUNTIME_DIR') or tempfile.gettempdir()) / 'wysun-launcher'
    folder.mkdir(mode=0o700, exist_ok=True)
    return folder


def clip_image(store, clip_id, folder):
    """Export an image clip once as clip-<id>-<w>x<h>.png and return (path, width, height)."""
    for found in folder.glob(f'clip-{clip_id}-*.png'):
        try:
            w, h = found.stem.split('-')[2].split('x')
            return str(found), int(w), int(h)
        except ValueError:
            pass
    blob = store.blob(clip_id)
    if not blob:
        return '', 0, 0
    w, h = (int.from_bytes(blob[16:20], 'big'), int.from_bytes(blob[20:24], 'big')) if blob[:8] == b'\x89PNG\r\n\x1a\n' else (0, 0)
    target = folder / f'clip-{clip_id}-{w}x{h}.png'
    target.write_bytes(blob)
    return str(target), w, h


def clip_rows(store, text):
    words = text.split()
    wanted = CLIP_KINDS.get(words[0].casefold()) if words else None
    needle = ' '.join(words[1:] if wanted else words).casefold()
    rows, folder, images = [], clip_folder(), 0
    for r in store.clips():
        if needle not in r['text'].casefold() or (wanted and r['kind'] != wanted):
            continue
        kind = r['kind']
        extra = {}
        title = 'Image' if kind == 'image' else (r['text'].split('\n')[0][:110] or '—')
        if kind == 'image' and images < 40:
            images += 1
            path, w, h = clip_image(store, r['id'], folder)
            if path:
                extra = dict(thumb=path, width=w, height=h)
                if w:
                    title = f'Image ({w} × {h})'
        rows.append(row('clip', title, dt.datetime.fromtimestamp(r['stamp']).strftime('%d %b · %H:%M') + f'  ·  {kind}',
                        CLIP_ICONS.get(kind, 'description'), id=r['id'], clip_kind=kind, value=r['text'], stamp=r['stamp'],
                        swatch=r['text'] if kind == 'color' else '', **extra))
    return rows[:LIMIT]


def load_files(rebuild=False):
    """Cached file index; a stale cache is served while a detached rebuild runs."""
    try:
        age = time.time() - FILE_CACHE.stat().st_mtime
        cached = json.loads(FILE_CACHE.read_text())
    except (OSError, ValueError):
        age, cached = None, None
    if cached is None or rebuild:
        return build_index()
    if age > FILE_TTL:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'reindex'], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    return cached


def build_index():
    files = file_index()
    STATE.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE, prefix='.launcher-files-')
    with os.fdopen(fd, 'w') as handle:
        json.dump(files, handle)
    os.chmod(tmp, 0o600)
    os.replace(tmp, FILE_CACHE)
    return files


def recent_files():
    """XDG recent documents, with a bounded local fallback for new sessions."""
    from urllib.parse import urlsplit, unquote
    import xml.etree.ElementTree as ET
    source = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share')) / 'recently-used.xbel'
    paths = []
    try:
        bookmarks = ET.fromstring(source.read_text()).findall('bookmark')
        bookmarks.sort(key=lambda b: b.get('visited', b.get('modified', '')), reverse=True)
        for bookmark in bookmarks:
            url = urlsplit(bookmark.get('href', ''))
            if url.scheme == 'file' and url.netloc in ('', 'localhost'):
                path = Path(unquote(url.path))
                if path.is_file() and str(path) not in paths:
                    paths.append(str(path))
            if len(paths) >= 40:
                break
    except (OSError, ValueError, ET.ParseError):
        pass
    if not paths:
        candidates = []
        for folder in ('Downloads', 'Documents', 'Screenshots'):
            try:
                for path in list((HOME / folder).iterdir())[:1000]:
                    if not path.name.startswith('.') and path.is_file():
                        candidates.append((path.stat().st_mtime, str(path)))
            except OSError:
                continue
        paths = [path for _, path in sorted(candidates, reverse=True)[:40]]
    return paths


def file_row(path):
    suffix = Path(path).suffix.lower()
    icon = 'image' if suffix in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.avif') else 'movie' if suffix in ('.mp4', '.mkv', '.webm', '.mov') else 'picture_as_pdf' if suffix == '.pdf' else 'draft'
    return row('file', Path(path).name, str(Path(path).parent).replace(str(HOME), '~'), icon, path=path)


def file_rows(text):
    terms = text.casefold().split()
    if not terms:
        return [file_row(path) for path in recent_files()]
    matches = [x for x in load_files() if all(t in x[2] for t in terms)]
    matches.sort(key=lambda x: (not x[0].startswith(terms[0]), len(x[2])))
    return [file_row(p) for _, p, _ in matches[:LIMIT]]


def discover_rows(store, text):
    rows = []
    def add(section, entries):
        rows.extend(dict(entry, section=section) for entry in entries)
    if text.strip():
        add('Calculator', calc_rows(store, text))
        add('Files', file_rows(text)[:8])
    else:
        add('Recent files', file_rows('')[:6])
    return rows


def preview(path):
    """Read-only bounded preview; invoked only for the selected file."""
    from file_media import preview_file
    from media import png_bytes
    import base64
    data = preview_file(path)
    image = data.pop('image', None)
    if image is not None and not image.isNull():
        data['image'] = 'data:image/png;base64,' + base64.b64encode(png_bytes(image)).decode()
    data['text'] = data.get('text', '')[:10000]
    return data


def emoji_category(emoji, name):
    code = ord(emoji[0])
    name = name.lower()
    if any(word in name for word in ('face', 'smile', 'heart', 'kiss', 'emotion')):
        return 'Smileys'
    if any(word in name for word in ('hand', 'finger', 'thumb', 'person', 'woman', 'man ', 'people', 'boy', 'girl', 'family', 'skin tone')):
        return 'People'
    if 0x1F330 <= code <= 0x1F37F or 0x1F950 <= code <= 0x1F96F or any(word in name for word in ('food', 'drink', 'coffee', 'fruit')):
        return 'Food'
    if 0x1F400 <= code <= 0x1F43F or any(word in name for word in ('animal', 'flower', 'tree', 'cat', 'dog', 'bird', 'sun', 'moon', 'plant')):
        return 'Nature'
    if 0x1F680 <= code <= 0x1F6FF or any(word in name for word in ('car ', 'train', 'plane', 'travel', 'building', 'city', 'flag')):
        return 'Travel'
    return 'Objects & symbols'


def emoji_rows(text):
    fold = text.casefold()
    entries = []
    source = ROOT / 'assets/emojis.txt'
    if source.exists():
        entries += [tuple(line.split(' ', 1)) for line in source.read_text().splitlines() if ' ' in line]
    aliases = dict(DEFAULT_EMOJI)
    seen, rows = set(), []
    for emoji, name in entries + list(DEFAULT_EMOJI):
        keywords = name + ' ' + aliases.get(emoji, '')
        if emoji in seen or fold not in (keywords + ' ' + emoji).casefold():
            continue
        seen.add(emoji)
        label = name.split(' | ')[0]
        rows.append(row('emoji', label, 'Copy emoji', 'emoji_emotions', value=emoji,
                        keywords=keywords, category=emoji_category(emoji, name)))
    rows.sort(key=lambda r: (r['value'] != text.strip(), not r['title'].casefold().startswith(fold)))
    return rows


def calc_rows(store, text):
    answer = calculate(text) if text.strip() else None
    if answer is not None:
        return [row('calc', answer, text + '  →  Copy result', 'function', query=text, value=answer)]
    if text.strip():
        return []
    return [row('calc', r['result'], r['query'], 'history', query=r['query'], value=r['result']) for r in store.calcs()[:50]]


def query(mode, text):
    if mode not in MODES:
        raise ValueError(f'modo desconocido: {mode}')
    store = Store()
    try:
        if mode == 'status':
            return [dict(paused=store.get('paused') == '1')]
        if mode == 'all':
            return discover_rows(store, text)
        if mode == 'clip':
            return clip_rows(store, text)
        if mode == 'calc':
            return calc_rows(store, text)
        return {'files': lambda: file_rows(text), 'emoji': lambda: emoji_rows(text)}[mode]()
    finally:
        store.db.close()


def act(action, args):
    store = Store()
    try:
        if action == 'record-calc':
            store.record_calc(args[0], args[1])
        elif action == 'delete-clip':
            store.delete_clip(int(args[0]))
        elif action == 'clear-clips':
            store.clear_clips()
        elif action == 'copy-image':
            blob = store.blob(int(args[0]))
            if blob:
                subprocess.run(['wl-copy', '--type', 'image/png'], input=blob, check=False, timeout=5)
        elif action == 'toggle-capture':
            store.set('paused', '0' if store.get('paused') == '1' else '1')
        elif action == 'paste':
            # The launcher is a layer surface: the previously focused window is still the active one.
            from desktop_backend import Desktop
            from wayland_clipboard import paste_to
            time.sleep(0.15)
            ok, message = paste_to(Desktop().focused())
            if not ok:
                raise RuntimeError(message)
        elif action == 'use':
            store.use(args[0])
        else:
            raise ValueError(f'acción desconocida: {action}')
    finally:
        store.db.close()


def main(argv):
    if len(argv) == 2 and argv[0] == 'preview-url':
        from launcher_web import cached_preview
        def emit(data):
            print(json.dumps(data, ensure_ascii=False), flush=True)
        emit(cached_preview(argv[1], emit))
        return 0
    if len(argv) >= 2 and argv[0] == 'query':
        try:
            print(json.dumps(query(argv[1], argv[2] if len(argv) > 2 else ''), ensure_ascii=False))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            print(json.dumps([row('error', 'Unable to load results', str(exc)[:200], 'error')], ensure_ascii=False))
        return 0
    if len(argv) == 2 and argv[0] == 'preview-clip':
        import base64
        store = Store()
        try:
            blob = store.blob(int(argv[1]))
            print(json.dumps({'image': 'data:image/png;base64,' + base64.b64encode(blob).decode()} if blob else {}))
        finally:
            store.db.close()
        return 0
    if len(argv) == 2 and argv[0] == 'clip-file':
        store = Store()
        try:
            path, _, _ = clip_image(store, int(argv[1]), clip_folder())
        finally:
            store.db.close()
        if path:
            print(path)
        return 0
    if len(argv) == 2 and argv[0] == 'preview':
        print(json.dumps(preview(argv[1]), ensure_ascii=False))
        return 0
    if argv and argv[0] == 'reindex':
        build_index()
        return 0
    if len(argv) >= 2 and argv[0] == 'act':
        try:
            act(argv[1], argv[2:])
        except (OSError, ValueError, IndexError, RuntimeError, subprocess.SubprocessError) as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0
    print('uso: launcher_data.py query <modo> [texto] | act <acción> [args] | reindex', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

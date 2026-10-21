#!/usr/bin/env python3
"""Data provider for the native Wysun launcher (apps/shell/modules/launcher).

Same sources as the Qt palette (orbit.py): clipboard history, snippets, files,
windows, emoji and calculator history. Commands are argv arrays and results are
JSON; nothing is evaluated by a shell. Private data stays in ~/.local/share/orbit.
"""
import datetime as dt, json, os, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from core import Store, STATE, HOME, calculate, expand_snippet, file_index  # noqa: E402

MODES = ('clip', 'files', 'snippets', 'windows', 'emoji', 'calc')
LIMIT = 150
CLIP_KINDS = {'texto': 'text', 'text': 'text', 'imagen': 'image', 'image': 'image', 'color': 'color', 'enlace': 'url', 'url': 'url'}
CLIP_ICONS = {'image': 'image', 'color': 'palette', 'url': 'link', 'text': 'description'}
DEFAULT_EMOJI = [('😀', 'sonrisa feliz'), ('😂', 'risa lágrimas'), ('❤️', 'amor corazón'), ('✨', 'brillos magia'), ('👍', 'bien pulgar'), ('🙏', 'gracias manos'), ('🎉', 'fiesta celebración'), ('🔥', 'fuego'), ('🚀', 'cohete lanzar'), ('💡', 'idea luz'), ('✅', 'listo correcto'), ('👀', 'ojos mirar'), ('💻', 'computadora trabajo'), ('☕', 'café'), ('🌙', 'luna noche'), ('🫶', 'corazón manos'), ('🤔', 'pensar duda'), ('😎', 'genial gafas'), ('🥹', 'emoción'), ('💜', 'corazón morado')]
FILE_CACHE = STATE / 'launcher-files.json'
FILE_TTL = 300


def row(kind, title, subtitle='', icon='', **extra):
    return dict(kind=kind, title=title, subtitle=subtitle, icon=icon, **extra)


def clip_rows(store, text):
    words = text.split()
    wanted = CLIP_KINDS.get(words[0].casefold()) if words else None
    needle = ' '.join(words[1:] if wanted else words).casefold()
    rows = []
    for r in store.clips():
        if needle not in r['text'].casefold() or (wanted and r['kind'] != wanted):
            continue
        kind = r['kind']
        title = r['text'] if kind == 'image' else (r['text'].split('\n')[0][:110] or '—')
        rows.append(row('clip', title, dt.datetime.fromtimestamp(r['stamp']).strftime('%d %b · %H:%M') + f'  ·  {kind}',
                        CLIP_ICONS.get(kind, 'description'), id=r['id'], clip_kind=kind, value=r['text'],
                        swatch=r['text'] if kind == 'color' else ''))
    return rows[:LIMIT]


def snippet_rows(store, text):
    if text.startswith('+'):
        parts = [x.strip() for x in text[1:].split('|', 2)] + ['', '']
        title, shortcut, body = parts[0], parts[1], parts[2]
        if title and body:
            return [row('snippet-new', f'Crear snippet «{title}»', f'Abreviatura: {shortcut or "—"} · {len(body)} caracteres', 'add',
                        args=[title, shortcut, body])]
        return [row('hint', 'Nuevo snippet', 'Escribe: +título | abreviatura | texto  (variables {date}, {time}, {datetime})', 'add')]
    fold = text.casefold()
    return [row('snippet', s['title'], s['shortcut'] or 'Fragmento de texto', 'code', id=s['id'], value=expand_snippet(s['body']))
            for s in store.snippets() if fold in (s['title'] + ' ' + s['shortcut'] + ' ' + s['body']).casefold()][:LIMIT]


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


def file_rows(text):
    files = load_files()
    terms = text.casefold().split()
    if terms:
        matches = [x for x in files if all(t in x[2] for t in terms)]
        matches.sort(key=lambda x: (not x[0].startswith(terms[0]), len(x[2])))
    else:
        downloads = str(HOME / 'Downloads')
        matches = sorted(files, key=lambda x: (not x[1].startswith(downloads), len(x[2])))[:80]
    return [row('file', Path(p).name, str(Path(p).parent).replace(str(HOME), '~'), 'draft', path=p) for _, p, _ in matches[:LIMIT]]


def window_rows(text):
    from desktop_backend import Desktop
    fold = text.casefold()
    return [row('window', w['title'], w['app'], 'web_asset', wid=w['id'])
            for w in Desktop().windows()
            if w.get('pid') != os.getpid() and fold in (w['title'] + ' ' + w['app']).casefold()][:LIMIT]


def emoji_rows(text):
    fold = text.casefold()
    entries = list(DEFAULT_EMOJI)
    source = ROOT / 'assets/emojis.txt'
    if source.exists():
        entries += [tuple(line.split(' ', 1)) for line in source.read_text().splitlines() if ' ' in line]
    seen, rows = set(), []
    for emoji, name in entries:
        if emoji in seen or fold not in name.casefold():
            continue
        seen.add(emoji)
        rows.append(row('emoji', f'{emoji}  {name}', 'Copiar emoji', 'emoji_emotions', value=emoji))
        if len(rows) >= LIMIT:
            break
    return rows


def calc_rows(store, text):
    answer = calculate(text) if text.strip() else None
    if answer is not None:
        return [row('calc', answer, text + '  →  Copiar resultado', 'function', query=text, value=answer)]
    if text.strip():
        return []
    return [row('calc', r['result'], r['query'], 'history', query=r['query'], value=r['result']) for r in store.calcs()[:50]]


def query(mode, text):
    if mode not in MODES:
        raise ValueError(f'modo desconocido: {mode}')
    store = Store()
    try:
        if mode == 'clip':
            return clip_rows(store, text)
        if mode == 'snippets':
            return snippet_rows(store, text)
        if mode == 'calc':
            return calc_rows(store, text)
        return {'files': lambda: file_rows(text), 'windows': lambda: window_rows(text), 'emoji': lambda: emoji_rows(text)}[mode]()
    finally:
        store.db.close()


def act(action, args):
    store = Store()
    try:
        if action == 'record-calc':
            store.record_calc(args[0], args[1])
        elif action == 'delete-clip':
            store.delete_clip(int(args[0]))
        elif action == 'delete-snippet':
            store.delete_snippet(int(args[0]))
        elif action == 'clear-clips':
            store.clear_clips()
        elif action == 'copy-image':
            blob = store.blob(int(args[0]))
            if blob:
                subprocess.run(['wl-copy', '--type', 'image/png'], input=blob, check=False, timeout=5)
        elif action == 'focus-window':
            from desktop_backend import Desktop
            Desktop().activate(args[0])
        elif action == 'toggle-capture':
            store.set('paused', '0' if store.get('paused') == '1' else '1')
        elif action == 'save-snippet':
            if not args[0].strip() or not args[2].strip():
                raise ValueError('el snippet necesita nombre y texto')
            store.save_snippet(args[0].strip(), args[1].strip(), args[2])
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
    if len(argv) >= 2 and argv[0] == 'query':
        try:
            print(json.dumps(query(argv[1], argv[2] if len(argv) > 2 else ''), ensure_ascii=False))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            print(json.dumps([row('error', 'No se pudo cargar', str(exc)[:200], 'error')], ensure_ascii=False))
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

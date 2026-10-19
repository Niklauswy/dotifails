#!/usr/bin/env python3
"""Journal only Wysun's two system files; never edit a display manager default."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import uuid

FILES = {'usr/local/bin/wysun-session': ('wysun-session-system', 0o755),
         'usr/share/wayland-sessions/wysun-hyprland.desktop': ('wysun-hyprland.desktop', 0o644)}


def digest(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('Destino inseguro: ' + str(path))
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes() + str(stat.S_IMODE(path.stat().st_mode)).encode()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def register(source, root, restore=False, dry_run=False, *, files=None,
             state_relative='var/lib/dotifails/wayland-session'):
    files = FILES if files is None else files
    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError('Raíz enlazada: ' + str(root))
    state = root / state_relative
    if dry_run:
        return _register(source, root, restore, True, files, state_relative)
    for parent in [state, *state.parents]:
        if parent == root:break
        if parent.is_symlink():raise ValueError('Directorio enlazado: ' + str(parent))
    state.mkdir(parents=True, exist_ok=True)
    lock = state / 'install.lock'
    if lock.is_symlink():raise ValueError('Lock enlazado')
    with lock.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _register(source, root, restore, False, files, state_relative)


def _register(source, root, restore=False, dry_run=False, files=FILES,
              state_relative='var/lib/dotifails/wayland-session'):
    source, root = Path(source), Path(root).absolute()
    state = root / state_relative
    receipt_path = state / 'installed.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {'files': {}}
    # Reject redirects even in an isolated root.
    for relative in [*files, state_relative + '/installed.json']:
        for parent in (root / relative).parents:
            if parent == root:
                break
            if parent.is_symlink():
                raise ValueError('Directorio enlazado: ' + str(parent))
    plans = []
    conflicts = []
    for relative, (name, mode) in files.items():
        target = root / relative
        current = digest(target)
        owned = receipt['files'].get(relative)
        if restore:
            if owned is None:
                continue
            if current != owned['after'] and not (current is None and owned['backup'] is None):
                conflicts.append(relative); continue
            before = state / owned['backup'] if owned['backup'] else None
            plans.append((relative, before, owned.get('mode', mode), current))
        else:
            expected = hashlib.sha256((source / name).read_bytes() + str(mode).encode()).hexdigest()
            if current == expected:
                continue
            if current is not None and (owned is None or current != owned['after']):
                conflicts.append(relative); continue
            plans.append((relative, source / name, mode, current))
    if dry_run:
        print(json.dumps({'action': 'restore' if restore else 'register',
                          'paths': [p[0] for p in plans], 'conflicts': conflicts}, indent=2))
        return 2 if conflicts else 0
    # A conflict means no partial registration. User can inspect proposals first.
    if conflicts:
        if not restore:
            for relative in conflicts:
                incoming = state / 'incoming' / relative
                incoming.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / files[relative][0], incoming)
        print('Conflictos de sesión conservados: ' + ', '.join(conflicts))
        return 2
    for relative, proposal, mode, expected_current in plans:
        target = root / relative
        before = digest(target)
        if before != expected_current:
            raise RuntimeError('Cambio concurrente: ' + relative)
        if not restore:
            # Keep the original pre-Wysun image across repeated updates.
            owned = receipt['files'].get(relative)
            if owned is None:
                backup = 'before/' + relative if before is not None else None
                if backup:
                    path = state / backup; path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, path)
                owned = {'backup': backup, 'mode': stat.S_IMODE(target.stat().st_mode) if before else mode}
            owned['after'] = hashlib.sha256(proposal.read_bytes() + str(mode).encode()).hexdigest()
            receipt['files'][relative] = owned
        # Persist intent before publishing, including expected image for recovery.
        save(receipt_path, receipt)
        if digest(target) != before:
            raise RuntimeError('Cambio concurrente: ' + relative)
        if proposal is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name('.' + target.name + uuid.uuid4().hex)
            shutil.copy2(proposal, temporary); temporary.chmod(mode); temporary.replace(target)
        if restore:
            receipt['files'].pop(relative)
            save(receipt_path, receipt)
    print('WYSUN_SESSION_REMOVED' if restore else 'WYSUN_SESSION_REGISTERED')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'remove'))
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--root', type=Path, default=Path('/'))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.root == Path('/') and not args.dry_run and os.geteuid() != 0:
        parser.error('Usa sudo para registrar o retirar la sesión del sistema.')
    return register(args.source, args.root, args.action == 'remove', args.dry_run)


if __name__ == '__main__':
    raise SystemExit(main())

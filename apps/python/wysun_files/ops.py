"""Filesystem operations for Wysun Files (run outside the GUI thread)."""
from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path
import shutil
import subprocess


def validate_name(name: str) -> str:
    """Validate a single filename, without silently rewriting it."""
    if not isinstance(name, str) or not name or name in {'.', '..'}:
        raise ValueError('Escribe un nombre de archivo válido.')
    if '/' in name or '\x00' in name:
        raise ValueError('El nombre no puede contener / ni caracteres nulos.')
    return name


def unique_destination(directory: str, name: str) -> str:
    """Suggest an unused name; execution still checks collisions atomically."""
    validate_name(name)
    parent = Path(directory)
    candidate = parent / name
    stem, suffix = os.path.splitext(name)
    index = 2
    while os.path.lexists(candidate):
        candidate = parent / f'{stem} ({index}){suffix}'
        index += 1
    return str(candidate)


def _check_target(source: Path, target: Path) -> None:
    if os.path.lexists(target):
        raise FileExistsError(f'Ya existe: {target}. Elige otro nombre.')
    if not target.parent.is_dir():
        raise NotADirectoryError(f'La carpeta de destino no existe: {target.parent}')
    if source.is_dir() and not source.is_symlink():
        origin = source.resolve()
        resolved_target = target.resolve()
        if resolved_target == origin or origin in resolved_target.parents:
            raise ValueError('No puedes copiar o mover una carpeta dentro de sí misma.')


def _copy(source: Path, target: Path) -> None:
    """Reserve targets exclusively; clean up only the entry we created."""
    identity = None
    try:
        if source.is_symlink():
            os.symlink(os.readlink(source), target)
            return
        if source.is_dir():
            target.mkdir()
            stat = target.lstat()
            identity = (stat.st_dev, stat.st_ino)
            shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)
        elif source.is_file():
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            stat = os.fstat(fd)
            identity = (stat.st_dev, stat.st_ino)
            os.close(fd)
            shutil.copy2(source, target, follow_symlinks=False)
        else:
            raise ValueError(f'No se puede copiar este tipo de archivo: {source}')
    except Exception:
        if identity is not None and os.path.lexists(target):
            current = target.lstat()
            if (current.st_dev, current.st_ino) == identity:
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
        raise


def _rename_exclusive(source: Path, target: Path) -> None:
    # Linux renameat2 protects against destination races without overwriting.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None:
        raise OSError('El sistema no ofrece renombrado seguro sin sobrescritura.')
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def execute_operation(kind: str, sources: list[str], destination: str = '') -> list[str]:
    """Execute copy/move/trash/mkdir/rename; return destination paths.

    mkdir takes a full destination path and no sources. rename takes one
    source and a full destination path. copy/move take an existing destination
    directory. trash returns the original paths successfully sent to the trash.
    Operations never intentionally overwrite. A batch can partially succeed;
    failure messages identify already completed paths.
    """
    if kind not in {'copy', 'move', 'trash', 'mkdir', 'rename'}:
        raise ValueError(f'Operación desconocida: {kind}')
    if kind == 'mkdir':
        if not destination:
            raise ValueError('Falta la ruta de la carpeta nueva.')
        target = Path(os.path.abspath(destination))
        validate_name(target.name)
        target.mkdir()
        return [str(target)]
    if not sources:
        raise ValueError('Selecciona al menos un archivo.')
    if any(not isinstance(p, str) or not p or '\x00' in p for p in sources):
        raise ValueError('La selección contiene una ruta vacía o inválida.')
    paths = [Path(os.path.abspath(p)) for p in sources]
    if len(set(paths)) != len(paths):
        raise ValueError('La selección contiene archivos duplicados.')
    for source in paths:
        if not os.path.lexists(source):
            raise FileNotFoundError(f'El archivo ya no existe: {source}')
        if source == Path(source.anchor):
            raise ValueError('No se puede operar sobre la raíz del sistema.')
    # Nested selections can invalidate later operations or duplicate copies.
    for source in paths:
        if any(parent in paths for parent in source.parents):
            raise ValueError('Selecciona la carpeta o sus elementos, no ambos.')
    if kind == 'rename' and len(paths) != 1:
        raise ValueError('Selecciona un solo archivo para renombrar.')
    if kind != 'trash' and not destination:
        raise ValueError('Falta la ruta de destino.')
    if kind in {'copy', 'move'} and not Path(destination).is_dir():
        raise NotADirectoryError(f'La carpeta de destino no existe: {destination}')
    targets = [Path(os.path.abspath(destination)) if kind == 'rename'
               else Path(os.path.abspath(destination)) / p.name for p in paths]
    if kind != 'trash':
        if len(set(targets)) != len(targets):
            raise FileExistsError('Varios archivos tienen el mismo nombre de destino.')
        for source, target in zip(paths, targets):
            validate_name(target.name)
            _check_target(source, target)
    completed = []
    try:
        for source, target in zip(paths, targets):
            if kind == 'trash':
                result = subprocess.run(['gio', 'trash', '--', str(source)],
                                        capture_output=True, text=True, check=False)
                if result.returncode:
                    raise OSError(result.stderr.strip() or f'No se pudo enviar a la papelera: {source}')
                completed.append(str(source))
                continue
            if kind == 'copy':
                _copy(source, target)
            else:
                try:
                    _rename_exclusive(source, target)
                except OSError as error:
                    if error.errno != errno.EXDEV or kind == 'rename':
                        raise
                    _copy(source, target)
                    try:
                        if source.is_dir() and not source.is_symlink():
                            shutil.rmtree(source)
                        else:
                            source.unlink()
                    except OSError as deletion_error:
                        raise OSError(f'Copia conservada en {target}, pero no se pudo retirar el origen {source}: {deletion_error}') from deletion_error
            completed.append(str(target))
    except Exception as error:
        if completed:
            raise RuntimeError(f'{error}\nOperaciones ya completadas: ' + ', '.join(completed)) from error
        raise
    return completed

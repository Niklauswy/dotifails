#!/usr/bin/env python3
"""Create the private qml-runtime: a venv with the PySide6 *bindings* that run on the shell's own Qt.

The Qt in the PySide6 wheel is binary-identical to the runtime Qt that ``runtime_build.py`` installs, so
the wheel's copy is deleted after installing and the apps preload the runtime's libraries instead
(``wysun_qml.bootstrap``). The venv keeps ``--system-site-packages`` so ``dbus``/``gi`` stay reachable.
Versions are in lockstep: PySide6 == ``qt.version`` of manifests/runtime.json, because libpyside6qml uses
private QtQml API. The stamp records the version; a mismatch reinstalls the wheels.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAMP = 'WYSUN_QML_RUNTIME.json'
# Headers, docs and binding-generator glue are build-time only.
BUILD_ONLY = ('include', 'doc', 'glue')
# Developer tools of the wheel; only the bindings and libpyside6* are needed at run time.
TOOLS = ('designer', 'assistant', 'linguist', 'qmlls', 'qmllint', 'qmlformat', 'qmlcachegen', 'qmltyperegistrar',
         'rcc', 'uic', 'lupdate', 'lrelease', 'qsb', 'balsam', 'svgtoqml', 'qmlimportscanner', 'qmltestrunner',
         'metaobjectdump', 'deployqt', 'androiddeployqt', 'balsamui', 'qtpy2cpp')


def wanted_version(manifest_path=None):
    """The Qt version of the shell runtime, which PySide6 must match."""
    manifest = json.loads(Path(manifest_path or ROOT / 'manifests/runtime.json').read_text())
    return manifest['qt']['version']


def default_prefix():
    override = os.environ.get('WYSUN_QML_RUNTIME')
    if override:
        return Path(override)
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'wysun/qml-runtime'


def stamp(prefix):
    try:
        value = json.loads((Path(prefix) / STAMP).read_text())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def needs_update(prefix, version):
    current = stamp(prefix)
    return (current is None or current.get('pyside6') != version or current.get('qt') != version
            or not (Path(prefix) / 'bin/python3').exists())


def _size(path):
    if path.is_dir() and not path.is_symlink():
        return sum(_size(child) for child in path.iterdir())
    try:
        return path.lstat().st_size
    except OSError:
        return 0


def prune(prefix):
    """Delete the wheel's Qt copy and its developer tools; returns the bytes freed."""
    prefix = Path(prefix)
    freed = 0
    for site in prefix.glob('lib/python*/site-packages'):
        pyside = site / 'PySide6'
        victims = [pyside / name for name in ('Qt', *BUILD_ONLY, *TOOLS)]
        victims += list(prefix.glob('bin/pyside6-*'))
        for victim in victims:
            if victim.exists() or victim.is_symlink():
                freed += _size(victim)
                shutil.rmtree(victim) if victim.is_dir() and not victim.is_symlink() else victim.unlink()
    return freed


def _run(cmd, **kw):
    print('+ ' + ' '.join(map(str, cmd)), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def ensure(prefix, version, *, runner=_run):
    """Create or refresh the venv; returns whether anything changed. Raises when pip fails (no stamp then)."""
    prefix = Path(prefix)
    if not needs_update(prefix, version):
        return False
    if not (prefix / 'bin/python3').exists():
        runner([sys.executable, '-m', 'venv', '--system-site-packages', prefix])
    runner([prefix / 'bin/python3', '-m', 'pip', 'install', '--no-deps', '--only-binary=:all:', '--no-cache-dir',
            '--disable-pip-version-check',
            f'PySide6_Essentials=={version}', f'shiboken6=={version}'])
    prune(prefix)
    tmp = prefix / (STAMP + '.tmp')
    tmp.write_text(json.dumps({'pyside6': version, 'qt': version}, indent=2) + '\n')
    os.replace(tmp, prefix / STAMP)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--prefix', default=str(default_prefix()))
    parser.add_argument('--version', default=wanted_version())
    parser.add_argument('--check', action='store_true', help='only report: exit 0 when up to date, 3 when not')
    args = parser.parse_args(argv)
    if args.check:
        stale = needs_update(args.prefix, args.version)
        print(('QML_RUNTIME_STALE ' if stale else 'QML_RUNTIME_OK ') + args.prefix)
        return 3 if stale else 0
    changed = ensure(args.prefix, args.version)
    print(('QML_RUNTIME_UPDATED ' if changed else 'QML_RUNTIME_OK ') + args.prefix)
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Bounded Wysun adapters for the original Wysun widgets (no Qt imports)."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def environment():
    env = dict(os.environ)
    for key in ('LD_LIBRARY_PATH', 'QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH',
                'QT_QPA_PLATFORM_PLUGIN_PATH', 'QTDIR'):
        env.pop(key, None)
    return env


def run(argv):
    result = subprocess.run(argv, env=environment(), capture_output=True, text=True, timeout=8)
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:300] or 'Proveedor no disponible')
    return result.stdout


def active_recordings():
    found = []
    for child in Path('/proc').glob('[0-9]*'):
        try:
            if child.stat().st_uid != os.getuid():
                continue
            argv = (child / 'cmdline').read_bytes().split(b'\0')
            index = argv.index(b'loomrec.worker')
            project = Path(os.fsdecode(argv[index + 1]))
            status = json.loads((project / 'status.json').read_text())
            if status.get('pid') != int(child.name) or time.time() - status.get('heartbeat', 0) > 15:
                continue
            if status.get('state') in ('starting', 'recording', 'paused', 'stopping'):
                found.append((project, status))
        except (OSError, ValueError, IndexError):
            continue
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('launch', 'preview', 'record-status', 'record-stop', 'record-pause'))
    parser.add_argument('value', nargs='?')
    args = parser.parse_args()
    if args.action.startswith('record-'):
        recordings = active_recordings()
        if args.action == 'record-status':
            status = recordings[0][1] if len(recordings) == 1 else {}
            print(json.dumps(dict(running=bool(recordings), paused=status.get('state') == 'paused',
                                  elapsed=status.get('elapsed', status.get('duration', 0)), ambiguous=len(recordings) > 1)))
        elif len(recordings) != 1:
            raise RuntimeError('Abre Wysun Recorder para elegir la grabación.')
        else:
            project, status = recordings[0]
            action = 'stop' if args.action == 'record-stop' else ('resume' if status.get('state') == 'paused' else 'pause')
            print(run(['wysun', 'recorder', '--' + action, str(project)]))
            if action == 'stop':
                # Detached: says where the MP4 ended up once it is ready.
                subprocess.Popen(['wysun', 'recorder', '--notify-when-ready', str(project)], start_new_session=True,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif args.action == 'launch':
        if args.value not in ('music', 'files', 'settings', 'colors', 'processes', 'power', 'recorder', 'screenshot', 'lock'):
            parser.error('Acción no permitida')
        os.execvpe('wysun', ['wysun', args.value], environment())
    else:
        # Import the existing single producer, never a second colour authority.
        source = Path(__file__).resolve().parents[2] / 'wysun'
        if not source.is_dir():
            source = Path.home() / '.local/share/orbit/app'
        sys.path.insert(0, str(source))
        import theme_core
        import wysun_scheme
        mode = theme_core.read_mode()
        print(json.dumps(wysun_scheme.generate_dynamic(Path(args.value), None if mode == 'auto' else mode)))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)

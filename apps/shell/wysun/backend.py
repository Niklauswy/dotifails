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


def history():
    value = json.loads(run(['dunstctl', 'history']))
    groups = value.get('data', [])
    rows = groups[0] if groups and isinstance(groups[0], list) else groups
    result = []
    for row in rows[:100]:
        if not isinstance(row, dict):
            continue
        def field(key, fallback=''):
            item = row.get(key, fallback)
            return item.get('data', fallback) if isinstance(item, dict) else item
        identifier = str(field('id'))
        if not identifier.isdecimal():
            continue
        urgency = str(field('urgency', 'normal')).lower()
        result.append(dict(notificationId=identifier, summary=str(field('summary'))[:512],
                           body=str(field('body'))[:4096], appName=str(field('appname'))[:128],
                           appIcon=str(field('icon_path'))[:1024],
                           urgency={'low': 0, 'normal': 1, 'critical': 2}.get(urgency, 1),
                           popup=False, actions=[]))
    return result


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
    parser.add_argument('action', choices=('history', 'dismiss', 'launch', 'schemes', 'current', 'preview', 'record-status', 'record-stop', 'record-pause', 'dnd'))
    parser.add_argument('value', nargs='?')
    args = parser.parse_args()
    if args.action.startswith('record-'):
        recordings = active_recordings()
        if args.action == 'record-status':
            status = recordings[0][1] if len(recordings) == 1 else {}
            print(json.dumps(dict(running=bool(recordings), paused=status.get('state') == 'paused',
                                  elapsed=status.get('duration', 0), ambiguous=len(recordings) > 1)))
        elif len(recordings) != 1:
            raise RuntimeError('Abre Wysun Recorder para elegir la grabación.')
        else:
            project, status = recordings[0]
            action = 'stop' if args.action == 'record-stop' else ('resume' if status.get('state') == 'paused' else 'pause')
            print(run(['wysun', 'recorder', '--' + action, str(project)]))
    elif args.action == 'dnd':
        import fcntl
        state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'loomrec'
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (state / 'concentration.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if (state / 'concentration.json').exists():
                raise RuntimeError('Recorder controla temporalmente No molestar.')
            run(['dunstctl', 'set-paused', 'toggle'])
            print(json.dumps({'paused': run(['dunstctl', 'is-paused']).strip() == 'true'}))
    elif args.action == 'history':
        print(json.dumps(history()))
    elif args.action == 'dismiss':
        if not (args.value or '').isdecimal():
            parser.error('Identificador Dunst inválido')
        run(['dunstctl', 'history-rm', args.value])
    elif args.action == 'launch':
        if args.value not in ('music', 'files', 'settings', 'notes', 'colors', 'connections',
                               'processes', 'tools', 'power', 'recorder', 'screenshot', 'lock'):
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
        if args.action == 'current':
            scheme = theme_core.read_scheme() or wysun_scheme.fixed_scheme(*theme_core.selection())
            print('\n'.join((scheme['name'], scheme['flavour'], scheme['variant'])))
        elif args.action == 'preview':
            print(json.dumps(wysun_scheme.generate_dynamic(Path(args.value))))
        else:
            result = {}
            for style, variant in [('space-black', 'space-black'), ('space-black', 'tokyo'),
                                   ('space-black', 'severance'), ('fluent', 'light'), ('fluent', 'dark')]:
                scheme = wysun_scheme.fixed_scheme(style, variant)
                key = 'fluent:' + variant if style == 'fluent' else variant
                result[key] = {'default': scheme['colours']}
            print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)

"""Structured Google Cloud instance operations, with explicit targets."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shlex
import sys
from .common import ToolError, require, run, plan, redact, report, check, emit, report_flags


def target(value):
    parts = value.split('/')
    if len(parts) != 3 or any(not re.fullmatch(r'[a-zA-Z0-9_.:-]+', p) for p in parts):
        raise argparse.ArgumentTypeError('Usa PROJECT/ZONE/NAME.')
    return parts


def base(args):
    return ['gcloud'] + (['--account', args.account] if args.account else [])


def instances(args):
    projects = args.project or []
    if args.all_projects:
        projects = [p['projectId'] for p in json.loads(run(base(args)+['projects','list','--format=json'], timeout=60).stdout)]
    if not projects:
        value = run(base(args)+['config','get-value','project']).stdout.strip()
        if not value or value == '(unset)':
            raise ToolError('Indica --project o --all-projects.')
        projects = [value]
    def fetch(project):
        result = run(base(args)+['compute','instances','list','--project',project,'--format=json'], timeout=90, check=False)
        if result.returncode:
            return project, [], redact(result.stderr.strip())[-600:]
        try:
            values = json.loads(result.stdout)
            for vm in values:
                vm['selector'] = f"{project}/{vm['zone'].rsplit('/',1)[-1]}/{vm['name']}"
            return project, values, None
        except (ValueError, KeyError, TypeError):
            return project, [], 'Respuesta JSON inválida.'
    result = report('gvm list'); values = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for project, rows, error in pool.map(fetch, sorted(set(projects))):
            check(result, project, 'fail' if error else 'pass', error or f'{len(rows)} instancias')
            values.extend(rows)
    result['data']['instances'] = [{'vm': v['selector'], 'status': v.get('status'),
        'machine': v.get('machineType','').rsplit('/',1)[-1]} for v in values]
    return result


def command(args, vm):
    project, zone, name = vm
    flags = ['--project',project,'--zone',zone]
    if args.action in ('start','stop','reset','delete'):
        return base(args)+['compute','instances',args.action,name]+flags+['--quiet'], None
    if args.action == 'ssh':
        return base(args)+['compute','ssh',name]+flags, None
    if args.action in ('upload','download'):
        remote = f'{name}:{args.remote}'
        paths = [str(args.local.expanduser().absolute()), remote] if args.action == 'upload' else [remote,str(args.local.expanduser().absolute())]
        return base(args)+['compute','scp',*paths,*flags], None
    script = args.script.read_text()
    if not script.strip(): raise ToolError('El script está vacío.')
    remote_command = 'bash -se'
    if args.directory:
        remote_command = f'cd -- {shlex.quote(args.directory)} && bash -se'
    return base(args)+['compute','ssh',name,*flags,'--command',remote_command], script


def execute(args):
    if args.action == 'ssh' and len(args.vm) != 1:
        raise ToolError('SSH abre una sesión a la vez; indica una VM.')
    if args.action == 'download' and len(args.vm) != 1:
        raise ToolError('Descarga desde una VM a la vez para evitar sobrescrituras.')
    if args.action == 'download' and args.local.exists():
        raise ToolError('El destino de descarga ya existe. Elige una ruta nueva.')
    if args.action == 'upload' and not args.local.is_file(): raise ToolError('El archivo local no existe.')
    commands = [(vm, *command(args, vm)) for vm in args.vm]
    if args.dry_run:
        for vm, argv, body in commands:
            plan(argv)
            if body: print(f'Entrada: {args.script} ({len(body.encode())} bytes)')
        return 0
    require('gcloud')
    if args.action in ('delete','reset') and not args.yes:
        expected = ','.join('/'.join(vm) for vm in args.vm)
        if not sys.stdin.isatty(): raise ToolError('Usa --yes o confirma desde una terminal.')
        if input(f'Confirma escribiendo {expected}: ').strip() != expected:
            raise ToolError('Cancelado.')
    if args.action == 'ssh':
        os.execvp(commands[0][1][0], commands[0][1])
        return 0
    result = report('gvm '+args.action)
    def perform(item):
        vm, argv, body = item
        try:
            done = run(argv, input=body, timeout=args.timeout, check=False)
            return '/'.join(vm), done.returncode, redact(done.stderr or '')[-800:]
        except ToolError as error:
            return '/'.join(vm), 2, str(error)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for vm, code, detail in pool.map(perform, commands):
            check(result, vm, 'pass' if code == 0 else 'fail', f'Código {code}. '+detail)
    return emit(result,args)


def remote_path(value):
    if not re.fullmatch(r'[a-zA-Z0-9_./~-]+',value) or value.startswith('-'):
        raise argparse.ArgumentTypeError('Usa una ruta remota sin espacios ni metacaracteres.')
    return value


def interactive():
    require('fzf'); require('gcloud')
    args = argparse.Namespace(account=None,project=[],all_projects=True,jobs=4)
    result = instances(args)
    for item in result['checks']:
        if item['status'] == 'fail': print(item['name']+': '+item['detail'],file=sys.stderr)
    rows = result['data']['instances']
    if not rows: raise ToolError('No hay instancias disponibles.')
    selection = run(['fzf','--multi','--prompt','VMs > '],input='\n'.join(v['vm']+'  '+v['status'] for v in rows),check=False)
    if selection.returncode: return 130 if selection.returncode == 130 else 0
    selectors = [line.split()[0] for line in selection.stdout.splitlines()]
    action = run(['fzf','--prompt','Acción > '],input='ssh\nstart\nstop\nreset\ndelete',check=False)
    if action.returncode: return 0
    argv = [action.stdout.strip()]
    for vm in selectors: argv += ['--vm',vm]
    return main(argv)

def main(argv=None):
    parser = argparse.ArgumentParser(prog='gvm', description='VMs de Google Cloud: selección explícita, operaciones paralelas y resultados verificables.')
    parser.add_argument('--account', help='Cuenta gcloud; no cambia la configuración global')
    parser.add_argument('--jobs',type=int,default=4,choices=range(1,9))
    sub = parser.add_subparsers(dest='action',required=True)
    p = sub.add_parser('list'); p.add_argument('--project',action='append'); p.add_argument('--all-projects',action='store_true'); report_flags(p)
    for action in ('start','stop','reset','delete','ssh','upload','download','run'):
        p = sub.add_parser(action); p.add_argument('--vm',type=target,action='append',required=True)
        p.add_argument('--dry-run',action='store_true'); p.add_argument('--timeout',type=int,default=600,choices=range(1,86401))
        p.add_argument('--yes',action='store_true'); report_flags(p)
        if action in ('upload','download'):
            p.add_argument('local',type=Path); p.add_argument('remote',type=remote_path,help='Ruta remota sin espacios ni metacaracteres')
        if action == 'run':
            p.add_argument('script',type=Path); p.add_argument('--directory')
    if argv == [] or (argv is None and len(sys.argv) == 1):
        if sys.stdin.isatty(): return interactive()
        parser.print_help(); return 0
    args = parser.parse_args(argv)
    if args.action == 'list': require('gcloud'); return emit(instances(args),args)
    return execute(args)

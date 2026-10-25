"""Opt-in native backports, without replacing the user's APT sources or keys.

References: https://backports.debian.org/Instructions/
https://www.parrotsec.org/docs/mirrors/mirrors-list/
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re


def repository_spec(fields):
    ident = fields.get('ID')
    major = fields.get('VERSION_ID', '').split('.')[0]
    if ident == 'debian' and major == '13':
        return ('trixie-backports', 'wysun-backports.sources',
                'Types: deb\nURIs: https://deb.debian.org/debian\nSuites: trixie-backports\n'
                'Components: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n')
    if ident == 'parrot' and major == '7':
        return ('echo-backports', 'wysun-backports.list',
                'deb https://deb.parrot.sh/parrot echo-backports main contrib non-free non-free-firmware\n')
    raise ValueError('Repositorios compatibles: Debian 13 y Parrot 7. No se mezclan distribuciones.')


def enabled(root, suite):
    apt = Path(root) / 'etc/apt'
    paths = [apt / 'sources.list', *sorted((apt / 'sources.list.d').glob('*.list')),
             *sorted((apt / 'sources.list.d').glob('*.sources'))]
    for path in paths:
        if not path.is_file():
            continue
        text = '\n'.join(line.split('#', 1)[0].rstrip() for line in path.read_text().splitlines()
                         if not line.lstrip().startswith('#'))
        if path.suffix == '.sources':
            for block in re.split(r'\n\s*\n', text):
                fields, previous = {}, None
                for line in block.splitlines():
                    if line[:1].isspace() and previous:
                        fields[previous] += ' ' + line.strip()
                    elif ':' in line:
                        key, value = line.split(':', 1)
                        previous = key.strip().lower()
                        fields[previous] = value.strip()
                if fields.get('enabled', 'yes').lower() != 'no' and 'deb' in fields.get('types', '').split() and suite in fields.get('suites', '').split():
                    return True
        elif any(re.match(r'^\s*deb\s+(?:\[[^]]*\]\s+)?\S+\s+' + re.escape(suite) + r'(?:\s|$)', line) for line in text.splitlines()):
            return True
    return False


def ensure(fields, root=Path('/')):
    root = Path(root)
    suite, filename, content = repository_spec(fields)
    if enabled(root, suite):
        return None
    if fields['ID'] == 'debian' and not (root / 'usr/share/keyrings/debian-archive-keyring.gpg').is_file():
        raise RuntimeError('Falta debian-archive-keyring; restaura las claves oficiales de Debian antes de continuar.')
    folder = root / 'etc/apt/sources.list.d'
    if folder.is_symlink() or (root / 'etc/apt').is_symlink():
        raise RuntimeError('El directorio de APT es un enlace; revisa su configuración antes de continuar.')
    target = folder / filename
    if target.exists() or target.is_symlink():
        raise RuntimeError('Ya existe ' + str(target) + ' con otra configuración. Revísala antes de continuar.')
    ident = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    backup = root / 'var/lib/dotifails/repositories/backups' / ident
    backup.mkdir(parents=True, mode=0o700)
    journal = backup / 'journal.json'
    journal.write_text(json.dumps({'path': str(target.relative_to(root)), 'before': None,
                                  'after': content, 'suite': suite}, indent=2) + '\n')
    journal.chmod(0o600)
    with journal.open('rb') as stream:
        os.fsync(stream.fileno())
    folder.mkdir(parents=True, exist_ok=True)
    with target.open('x') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    target.chmod(0o644)
    return str(backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Preparar backports nativos para Wysun')
    parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Este paso requiere autorización de administrador.')
    from install_model import read_os_release
    print(ensure(read_os_release()) or 'El repositorio nativo ya está habilitado.')

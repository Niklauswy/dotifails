"""Lossless Hyprland shortcut edits and bounded compositor settings."""
import datetime, hashlib, itertools, json, os, re, shutil, subprocess, tempfile
from pathlib import Path

HOME=Path.home()
SCHEMA={
 'window_gap':('Separación entre ventanas','int',0,80),
 'border_width':('Grosor del borde','int',0,12),
 'focused_border_color':('Borde de la ventana activa','color',None,None),
 'normal_border_color':('Borde de las demás ventanas','color',None,None),
 'split_ratio':('Proporción al dividir','float',.1,.9),
 'focus_follows_pointer':('Enfocar al pasar el puntero','bool',None,None),
 'pointer_follows_focus':('Mover el puntero con el foco','bool',None,None),
}

def checked(args):
    return subprocess.run(args,text=True,capture_output=True,timeout=4,check=True).stdout.strip()

def atomic_write(path,text,mode=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        os.fchmod(fd,mode or (path.stat().st_mode&0o777 if path.exists() else 0o600))
        with os.fdopen(fd,'w') as f:f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()

def backup_file(path,root=None):
    root=Path(root or HOME/'.local/share/orbit/settings-backups');root.mkdir(parents=True,exist_ok=True,mode=0o700)
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');dest=root/(stamp+'-'+Path(path).name)
    if Path(path).exists():shutil.copy2(path,dest);dest.chmod(0o600)
    return dest

def expand_sequence(text):
    match=re.search(r'(?<!\\)\{([^{}]*)\}',text)
    if not match:
        if re.search(r'(?<!\\)[{}]',text):raise ValueError('Llaves incompletas o anidadas.')
        return [text.replace(r'\{','{').replace(r'\}','}')]
    choices=[]
    for part in match[1].split(','):
        if re.fullmatch('[A-Za-z0-9]-[A-Za-z0-9]',part):
            start,end=ord(part[0]),ord(part[-1]);choices.extend(chr(i) for i in range(start,end+1))
        else:choices.append('' if part=='_' else part)
    tails=expand_sequence(text[match.end():]);rows=[text[:match.start()]+p+t for p,t in itertools.product(choices,tails)]
    if len(rows)>1000:raise ValueError('Demasiadas combinaciones.')
    return rows

def canonical(hotkey):
    aliases={'ctrl':'control','super':'mod4','alt':'mod1'};chords=[]
    for chord in re.split('[;:]',hotkey):
        parts=[x.strip() for x in chord.split('+')];chords.append('+'.join(sorted(aliases.get(x,x) for x in parts[:-1]))+'+'+parts[-1])
    return ';'.join(chords)


class ShortcutFile:
    """Compatibility facade returning the Hyprland binding model."""
    def __new__(cls,home=None,runner=None):
        from hypr_settings import HyprShortcutFile
        return HyprShortcutFile(home,runner)


class DesktopSettings:
    """Compatibility facade returning the Hyprland desktop settings model."""
    def __new__(cls,home=None,runner=checked):
        from hypr_settings import HyprDesktopSettings
        return HyprDesktopSettings(Path(home or HOME),runner)

    @staticmethod
    def validate(model,values,rules):
        clean={}
        for key,value in values.items():
            if key not in SCHEMA:raise ValueError('Ajuste desconocido.')
            title,kind,low,high=SCHEMA[key];value=str(value)
            if kind in ('int','float'):
                number=int(value) if kind=='int' else float(value)
                if not low<=number<=high:raise ValueError(title+': valor fuera de rango.')
                value=str(number)
            elif kind=='bool' and value not in ('true','false'):raise ValueError(title+': valor inválido.')
            elif kind=='color' and not re.fullmatch(r'#[0-9a-fA-F]{6}',value):raise ValueError(title+': usa #RRGGBB.')
            elif kind=='enum' and value not in low:raise ValueError(title+': opción inválida.')
            clean[key]=value
        for rule in rules:
            if not re.fullmatch(r'[A-Za-z0-9_.*:-]{1,120}',rule['class']):raise ValueError('La clase de la ventana no es válida.')
            if rule['state'] not in ('tiled','floating','fullscreen'):raise ValueError('Estado de ventana inválido.')
            if rule.get('desktop') and not re.fullmatch(r'[A-Za-z0-9_^.-]{1,40}',rule['desktop']):raise ValueError('Escritorio no válido.')
        if len({r['class'] for r in rules})!=len(rules):raise ValueError('Hay reglas repetidas para la misma clase.')
        return clean


def reload_shortcuts():
    """Hyprland applies managed binds through hyprctl eval; no daemon signal needed."""


# Structure preferences belong only to shell.json. Appearance, wallpaper and
# colour selection continue to use their existing files and producer.
SHELL_DEFAULTS = dict(schema_version=1, anchor='left', rail_enabled=True,
                      frame_enabled=True, monitors={}, primary_monitor='',
                      tray_monitor='', low_power=False)


def json_object(path):
    """Strict reads: never silently replace malformed or future preferences."""
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (ValueError, UnicodeError) as error:
        raise ValueError(f'{Path(path).name}: JSON inválido; se conservó el archivo.') from error
    if not isinstance(value, dict):
        raise ValueError(f'{Path(path).name}: se esperaba un objeto JSON.')
    return value


def validate_shell(value):
    if type(value.get('schema_version', 1)) is not int or value.get('schema_version', 1) != 1:
        raise ValueError('Versión de shell.json desconocida; no se modificó.')
    result = dict(SHELL_DEFAULTS, **value)
    # The integrated compositor currently supports only the left rail. Do not
    # offer placements which the compositor cannot yet honour.
    if result['anchor'] != 'left':
        raise ValueError('El riel de Wysun debe estar a la izquierda.')
    for key in ('rail_enabled', 'frame_enabled', 'low_power'):
        if type(result[key]) is not bool:
            raise ValueError(key + ': se esperaba verdadero o falso.')
    monitors = result['monitors']
    if not isinstance(monitors, dict) or any(not isinstance(k, str) or type(v) is not bool for k, v in monitors.items()):
        raise ValueError('Las salidas deben indicar un nombre y un estado.')
    for key in ('primary_monitor', 'tray_monitor'):
        if not isinstance(result[key], str) or any(ord(c) < 32 for c in result[key]):
            raise ValueError('Nombre de salida inválido.')
        if result[key] and monitors.get(result[key]) is False:
            raise ValueError('La salida principal o de bandeja está desactivada.')
    if monitors and not any(monitors.values()):
        raise ValueError('Deja al menos una salida habilitada.')
    return result


def restore_bytes(path, content, mode=0o600):
    """Restore exact bytes (including CRLF/UTF-8), atomically and privately."""
    path = Path(path)
    if content is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class PreferenceBackup:
    """A durable, bounded undo for Settings writes, never for private app data.

    The receipt names files by fixed keys instead of accepting arbitrary paths.
    Restore refuses to discard another writer's intervening changes.
    """
    def __init__(self, home, paths, label='preferences'):
        self.home = Path(home)
        self.paths = {key: Path(path) for key, path in paths.items()}
        self.before = {key: path.read_bytes() if path.exists() else None for key, path in self.paths.items()}
        self.modes = {key: path.stat().st_mode & 0o777 if path.exists() else 0o600 for key, path in self.paths.items()}
        root = self.home / '.local/share/orbit/settings-backups'
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.folder = Path(tempfile.mkdtemp(prefix=label + '-', dir=root))
        for key, content in self.before.items():
            if content is not None:
                restore_bytes(self.folder / key, content)
        atomic_write(self.folder / 'receipt.json', json.dumps({'version': 1, 'present': [k for k,v in self.before.items() if v is not None]}))
        self.after = None

    def seal(self):
        self.after = {key: path.read_bytes() if path.exists() else None for key, path in self.paths.items()}
        atomic_write(self.folder / 'receipt.json', json.dumps({
            'version': 1, 'present': [k for k,v in self.before.items() if v is not None],
            'modes': self.modes, 'after': {k: self.digest(v) for k,v in self.after.items()}}))

    @staticmethod
    def digest(content):
        return hashlib.sha256(content).hexdigest() if content is not None else None

    @classmethod
    def open(cls, home, paths, folder):
        root = (Path(home) / '.local/share/orbit/settings-backups').resolve()
        folder = Path(folder).resolve()
        if folder.parent != root:
            raise ValueError('La copia no pertenece a Ajustes.')
        receipt = json_object(folder / 'receipt.json')
        keys = set(receipt.get('after', {}))
        if receipt.get('version') != 1 or not keys or not keys.issubset(paths):
            raise ValueError('Copia de preferencias incompatible.')
        if not set(receipt.get('present', [])).issubset(keys):
            raise ValueError('Copia de preferencias inválida.')
        obj = cls.__new__(cls)
        obj.home, obj.folder = Path(home), folder
        obj.paths = {key: Path(paths[key]) for key in keys}
        obj.before = {key: (folder / key).read_bytes() if key in receipt['present'] else None for key in keys}
        obj.modes = {key: receipt.get('modes', {}).get(key, 0o600) & 0o777 for key in keys}
        obj.after = None
        obj.after_digests = receipt['after']
        return obj

    def restore(self, force=False):
        if not force and (self.after is not None or hasattr(self, 'after_digests')):
            for key, path in self.paths.items():
                current = path.read_bytes() if path.exists() else None
                expected = self.digest(self.after[key]) if self.after is not None else self.after_digests[key]
                if self.digest(current) != expected:
                    raise ValueError('Las preferencias cambiaron en otra ventana. Recarga antes de revertir.')
        current = {key: path.read_bytes() if path.exists() else None for key,path in self.paths.items()}
        restored = []
        try:
            for key, content in self.before.items():
                restore_bytes(self.paths[key], content, self.modes[key])
                restored.append(key)
        except Exception:
            for key in reversed(restored):
                restore_bytes(self.paths[key], current[key], self.modes[key])
            raise


class ShellPreferences:
    """Shared Python API for the shell's single structure configuration.

    QML consumes this same JSON through FileView; it must not write a second
    environment.bar or hypr-bar.json. Migration never deletes its input.
    """
    def __init__(self, home=None):
        from hypr_settings import config_dir
        self.home = Path(home or Path.home())
        self.root = config_dir(self.home) / 'orbit'
        self.path = self.root / 'shell.json'
        self.legacy = self.root / 'hypr-bar.json'
        self.migration_backup = None

    def values(self):
        self.migrate()
        return validate_shell(json_object(self.path))

    def migrate(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / 'shell.lock').open('a') as handle:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
            if self.path.exists():
                validate_shell(json_object(self.path))
                return False
            if not self.legacy.exists():
                return False
            # Preserve unknown module/geometry keys for rollback and future use.
            legacy = json_object(self.legacy)
            values = validate_shell(dict(legacy, schema_version=1, anchor='left'))
            backup = PreferenceBackup(self.home, {'shell.json': self.path, 'hypr-bar.json': self.legacy}, 'shell-migration')
            atomic_write(self.path, json.dumps(values, ensure_ascii=False, indent=2) + '\n')
            backup.seal()
            self.migration_backup = backup
            return True

    def save(self, values, expected=None, activate=None):
        self.migrate()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / 'shell.lock').open('a') as handle:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
            latest = json_object(self.path)
            validate_shell(latest)
            if expected is not None and validate_shell(latest) != expected:
                raise ValueError('El shell cambió en otra ventana. Recarga antes de guardar.')
            merged = validate_shell(dict(latest, **values))
            backup = PreferenceBackup(self.home, {'shell.json': self.path}, 'shell')
            try:
                atomic_write(self.path, json.dumps(merged, ensure_ascii=False, indent=2) + '\n')
                if activate:
                    activate()
            except Exception:
                backup.restore(force=True)
                raise
            backup.seal()
            return backup

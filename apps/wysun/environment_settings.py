"""Local Hyprland settings, display trials and lossless component configuration."""
from theme_tokens import apply_style

import configparser
import contextlib
import copy
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from settings_data import atomic_write, backup_file

ROOT = Path(__file__).resolve().parent
ROTATIONS = ('normal','left','right','inverted')
BAR_MODULES = {'orbit':'Wysun','title':'Ventana activa','workspaces':'Escritorios','resources':'CPU y memoria','network':'Red','volume':'Volumen','battery':'Batería','date':'Fecha y hora','notifications':'Notificaciones','power':'Sesión','tray':'Bandeja'}

def run(args):
    result = subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=12)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or 'No se pudo ejecutar '+str(args[0])).strip()[:500])
    output=result.stdout.strip()
    if list(args[:2]) in (['hyprctl','eval'],['hyprctl','dispatch']) and output!='ok':raise RuntimeError(output[:500])
    return output

def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return copy.deepcopy(default if default is not None else {})

def display_inventory(runner=run):
    from hypr_settings import inventory
    return inventory(runner)

def profile_key(outputs):
    return '|'.join(sorted(o['name'] for o in outputs if o['connected']))

def display_plan(outputs):
    return [{k:o[k] for k in ('name','enabled','primary','mode','rate','rotation','x','y')} | ({'scale':o['scale']} if 'scale' in o else {}) for o in outputs if o['connected']]

def display_command(plan, inventory):
    from hypr_settings import display_command as native_display_command
    return native_display_command(plan,inventory)

def restore_display(plan, runner=run):
    inventory = display_inventory(runner)
    current = display_plan(inventory)
    if not current:raise ValueError('No hay pantallas conectadas para recuperar la distribución.')
    old = {p['name']:p for p in plan}
    restored = [copy.deepcopy(old.get(p['name'],p)) for p in current]
    for target,actual in zip(restored,current):
        modes={m['name']:m['rates'] for o in inventory if o['name']==target['name'] for m in o['modes']}
        if target['mode'] not in modes or target['rate'] not in modes[target['mode']]:
            target['mode'],target['rate']=actual['mode'],actual['rate']
    if not any(p['enabled'] for p in restored):
        restored[0]['enabled'] = True
    active = [p for p in restored if p['enabled']]
    if not any(p['primary'] for p in active):
        active[0]['primary'] = True
    primary=next(p for p in active if p['primary'])
    for p in restored:p['primary']=p is primary
    runner(display_command(restored,inventory))

def after_display_change(backend):
    """Re-pin fixed workspaces for the new order and redraw shell surfaces."""
    try:
        from settings_runtime import restore_workspaces
        restore_workspaces(backend)
    except Exception as exc:print('Escritorios:',str(exc),file=sys.stderr)
    try:backend.runner(['wysun','shell','reload-preferences'])
    except Exception as exc:print('Shell:',str(exc),file=sys.stderr)

@contextlib.contextmanager
def trial_lock(folder):
    with (Path(folder)/'lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        yield

class DisplayTrial:
    """A separate watchdog restores the old layout if this app closes or hangs."""
    def __init__(self, backend, plan):
        self.backend = backend
        inventory=display_inventory(backend.runner)
        self.old = display_plan(inventory)
        from display_layout import normalize
        # Overlapping or separated monitors confuse Hyprland; always edge-to-edge.
        self.plan = normalize(plan)
        plan = self.plan
        self.key = profile_key(inventory)
        command = display_command(plan,inventory)
        folder = backend.home/'.cache/orbit/display-trials'
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.folder = Path(tempfile.mkdtemp(dir=folder))
        self.done=False
        atomic_write(self.folder/'trial.json',json.dumps({'old':self.old,'deadline':time.time()+35}))
        self.process = subprocess.Popen([sys.executable,str(ROOT/'settings_runtime.py'),'guard',str(self.folder)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:
            backend.runner(command)
            with trial_lock(self.folder):
                atomic_write(self.folder/'trial.json',json.dumps({'old':self.old,'deadline':time.time()+18}))
        except Exception:
            self.reject()
            raise

    def accept(self):
        if self.done:
            return
        if profile_key(display_inventory(self.backend.runner)) != self.key:
            self.reject()
            raise ValueError('Cambió la conexión de una pantalla; se revirtió la prueba.')
        with trial_lock(self.folder):
            if (self.folder/'reverted').exists() or (self.folder/'error').exists() or time.time() > read_json(self.folder/'trial.json')['deadline']:
                raise ValueError('La prueba venció. Vuelve a probar la distribución.')
            section = copy.deepcopy(self.backend.section('displays'))
            section.setdefault('profiles',{})[self.key] = self.plan
            self.backend.save_section('displays',section)
            from display_layout import monitors_fragment
            atomic_write(self.backend.config/'orbit/hypr-monitors.lua',monitors_fragment(self.plan))
            atomic_write(self.folder/'accepted','ok')
            self.done = True
        after_display_change(self.backend)

    def reject(self):
        if getattr(self,'done',False):
            return
        with trial_lock(self.folder):
            if not (self.folder/'reverted').exists():restore_display(self.old,self.backend.runner)
            atomic_write(self.folder/'reverted','ok')
        self.done = True
        after_display_change(self.backend)

def ini_value(text, section, key, default=''):
    parser = configparser.ConfigParser(interpolation=None,strict=False)
    parser.read_string(text)
    return parser.get(section,key,fallback=default)

def set_ini(text, section, values):
    match = re.search(r'(?m)^\['+re.escape(section)+r'\][^\n]*\n(?P<body>.*?)(?=^\[|\Z)',text,re.S)
    if not match:
        text += '\n['+section+']\n'
        match = re.search(r'(?m)^\['+re.escape(section)+r'\][^\n]*\n(?P<body>.*?)(?=^\[|\Z)',text,re.S)
    body = match['body']
    for key,value in values.items():
        pattern = r'(?m)^\s*'+re.escape(key)+r'\s*=.*$'
        line = key+' = '+str(value)
        body = re.sub(pattern,lambda _:line,body) if re.search(pattern,body) else body.rstrip()+'\n'+line+'\n'
    return text[:match.start('body')]+body+'\n'+text[match.end('body'):]

def kv_values(text):
    return {m[1]:m[2].strip().rstrip(';').strip().strip('"') for m in re.finditer(r'(?m)^([\w-]+)\s*=\s*(.*?)\s*$',text)}

def set_values(text, values, semicolon=False):
    for key,value in values.items():
        line = key+' = '+str(value)+(';' if semicolon else '')
        pattern = r'(?m)^'+re.escape(key)+r'\s*=.*$'
        text = re.sub(pattern,lambda _:line,text) if re.search(pattern,text) else text.rstrip()+'\n'+line+'\n'
    return text

def color(value):
    if not re.fullmatch(r'#[\da-fA-F]{6}',str(value)):
        raise ValueError('Usa un color #RRGGBB.')
    return value

def bounded(value, low, high, integer=False):
    value = int(value) if integer else float(value)
    if not low <= value <= high:
        raise ValueError(f'Valor fuera del intervalo {low}–{high}.')
    return value

class EnvironmentSettings:
    def __init__(self, home=None, runner=run):
        self.home = Path(home or Path.home())
        self.runner = runner
        from hypr_settings import config_dir
        self.config = config_dir(self.home)
        self.path = self.config/'orbit/environment.json'
        self.reload()

    def reload(self):
        self.data = read_json(self.path)

    def section(self, name):
        return self.data.get(name,{})

    def shell_values(self):
        """Validated shell.json (migrating hypr-bar.json once). See ShellPreferences."""
        from settings_data import ShellPreferences
        return ShellPreferences(self.home).values()

    def notify_shell(self):
        """Ask a running shell to re-read now. It also watches the files, so a
        missing shell is reported to the caller instead of failing the save."""
        try:
            self.runner(['wysun', 'shell', 'reload-preferences'])
            return None
        except Exception as error:
            return str(error)[:200] or 'El shell no respondió.'

    def apply_shell(self, values, expected=None):
        from settings_data import ShellPreferences
        return ShellPreferences(self.home).save(values, expected,
            lambda: self.runner(['wysun', 'shell', 'reload-preferences']))

    def preference_paths(self):
        import theme_core
        return {name: self.config / 'orbit' / name for name in (
            'shell.json', 'hypr-bar.json', 'appearance.json', 'environment.json', 'theme.json')} | {
            'scheme.json': theme_core.scheme_path(self.home)}

    def apply_panels(self, shell, appearance, expected_shell=None, expected_appearance=None):
        from settings_data import PreferenceBackup, json_object
        paths = self.preference_paths()
        # Validate both before the first write, then rollback as one operation.
        json_object(paths['appearance.json'])
        from settings_data import ShellPreferences
        ShellPreferences(self.home).migrate()  # before the snapshot: undo never un-migrates
        backup = PreferenceBackup(self.home, {k: paths[k] for k in ('shell.json', 'appearance.json')}, 'panels')
        try:
            ShellPreferences(self.home).save(shell, expected_shell, snapshot=False)
            self.apply_appearance(appearance, expected_appearance, snapshot=False)
        except Exception:
            backup.restore(force=True)
            self.notify_shell()
            raise
        backup.seal()
        backup.warning = self.notify_shell()
        return backup

    def colour_values(self):
        """Selection view only; all generation stays in wysun_scheme."""
        import theme_core, theme_intent
        intent = theme_intent.dynamic_intent(self.home)
        scheme = theme_core.read_scheme(self.home)
        return dict(dynamic=intent['enabled'],
                    selection=theme_core.read_file(self.home),
                    mode=intent.get('mode') or (scheme or {}).get('mode', 'dark'),
                    variant=intent.get('variant', 'auto'),
                    seed=intent.get('seed', ''))

    def apply_colour(self, values, wallpaper=None, expected=None):
        """Publish through the existing colour authority, with exact undo.

        No private wallpaper lists or unknown theme/environment fields are
        reconstructed from the form. Only the explicitly edited path changes.
        """
        import theme_core
        from types import SimpleNamespace
        from wysun_scheme import set_scheme, normalize_seed, VARIANTS
        from settings_data import PreferenceBackup, json_object
        paths = {'environment.json': self.path,
                 'theme.json': theme_core.selection_path(self.home),
                 'scheme.json': theme_core.scheme_path(self.home)}
        for key in ('environment.json', 'theme.json'):
            json_object(paths[key])
        if expected is not None and self.colour_values() != expected:
            raise ValueError('El color cambió en otra ventana. Recarga antes de guardar.')
        if values['mode'] not in ('light', 'dark'):
            raise ValueError('Elige modo claro u oscuro.')
        dynamic = values['dynamic']
        variant = values.get('variant') or 'auto'
        if variant != 'auto' and variant not in VARIANTS:
            raise ValueError('Variante Material desconocida.')
        seed = str(values.get('seed') or '').strip()
        seed = normalize_seed(seed) if seed else 'none'
        selected = theme_core.parse(values['selection']) if isinstance(values['selection'], str) else tuple(values['selection'])
        if not dynamic and (not selected or selected[0] not in theme_core.styles() or selected[1] not in theme_core.styles()[selected[0]]['variants']):
            raise ValueError('Elige uno de los cinco esquemas fijos.')
        backup = PreferenceBackup(self.home, paths, 'colour')
        old_wallpaper = copy.deepcopy(self.wallpaper_values())
        changed_wallpaper = wallpaper is not None and wallpaper != old_wallpaper.get('default', '')
        try:
            if changed_wallpaper:
                path = Path(wallpaper).expanduser()
                from PIL import Image
                with Image.open(path) as image:
                    image.verify()
                draft = copy.deepcopy(old_wallpaper)
                draft['default'] = str(path)
                # Save and render once; set_scheme below handles generation.
                self.save_section('wallpaper', draft)
                render_wallpaper(draft, display_inventory(self.runner), self.home, self.runner)
            result = set_scheme(SimpleNamespace(dynamic=dynamic,
                theme=None if dynamic else ':'.join(selected),
                mode=values['mode'] if dynamic else None, variant=variant if dynamic else None,
                seed=seed if dynamic else None), self.home)
            self.notify_shell()
        except Exception:
            backup.restore(force=True)
            self.reload()
            theme_core.invalidate()
            self.notify_shell()  # the bytes are restored verbatim; never re-render over them
            raise
        backup.seal()
        return dict(message=result, backup=backup)

    def appearance_values(self):
        from settings_data import json_object
        value = json_object(self.config / 'orbit/appearance.json')
        return dict(opacity=value.get('opacity', 80), reduced_motion=value.get('reduced_motion', False))

    def apply_appearance(self, values, expected=None, snapshot=True):
        from settings_data import json_object, PreferenceBackup
        path = self.config / 'orbit/appearance.json'
        latest = json_object(path)
        if expected is not None and self.appearance_values() != expected:
            raise ValueError('La apariencia cambió en otra ventana. Recarga antes de guardar.')
        if type(values['reduced_motion']) is not bool:
            raise ValueError('Movimiento reducido inválido.')
        latest.update(opacity=bounded(values['opacity'], 65, 100, True),
                      reduced_motion=values['reduced_motion'])
        text = json.dumps(latest, ensure_ascii=False, indent=2) + '\n'
        if not snapshot:
            atomic_write(path, text)
            return None
        backup = PreferenceBackup(self.home, {'appearance.json': path}, 'appearance')
        try:
            atomic_write(path, text)
        except Exception:
            backup.restore(force=True)
            raise
        backup.seal()
        backup.warning = self.notify_shell()
        return backup

    def undo_preferences(self, backup):
        """Restore the exact bytes of a sealed Settings write (refuses foreign edits)."""
        backup.restore()
        self.reload()
        import theme_core
        theme_core.invalidate()
        # Files are restored verbatim; the shell follows through its file watchers.
        return self.notify_shell()

    def save_section(self, name, values):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with (self.path.parent/'environment.lock').open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            self._save_section(name,values)

    def _save_section(self,name,values):
        latest = read_json(self.path)
        if latest.get(name,{}) != self.data.get(name,{}):
            raise ValueError('Esta sección cambió en otra ventana. Recarga antes de guardar.')
        latest[name] = values
        if self.path.exists():
            backup_file(self.path,self.home/'.local/share/orbit/settings-backups')
        atomic_write(self.path,json.dumps(latest,ensure_ascii=False,indent=2)+'\n')
        self.data[name] = copy.deepcopy(values)

    def edit_file(self,path,text,activate=None):
        path = Path(path)
        old = path.read_text()
        backup_file(path,self.home/'.local/share/orbit/settings-backups')
        atomic_write(path,text)
        try:
            if activate:
                activate()
        except Exception:
            atomic_write(path,old)
            raise

    def bar_theme_colors(self):
        """Bar colours of the active theme; stored colours are user overrides."""
        from theme_tokens import tokens
        external=tokens(self.home)['external']
        return {key:external[key].upper() for key in ('background','foreground','accent')}

    def bar_values(self):
        defaults=dict(height=36,offset=10,radius=12,opacity=65,**self.bar_theme_colors(),left=['orbit','workspaces'],center=['title'],right=['resources','network','volume','battery','date','notifications','power','tray'],monitors={},tray_monitor='')
        path=self.config/'orbit/hypr-bar.json'
        return defaults | read_json(path) if path.exists() else defaults

    def apply_bar(self, values):
        values=copy.deepcopy(values)
        for key,lo,hi in [('height',24,64),('offset',0,60),('radius',0,30),('opacity',10,100)]:
            values[key] = bounded(values[key],lo,hi,True)
        theme=self.bar_theme_colors()
        for key in ('background','foreground','accent'):
            color(values[key])
            # Unchanged theme colours are not saved, so the bar keeps following the theme.
            from theme_runtime import theme_colors
            if str(values[key]).upper()==theme[key] or str(values[key]).upper() in theme_colors():values.pop(key)
        for side in ('left','center','right'):
            if len(values[side]) != len(set(values[side])) or any(x not in BAR_MODULES for x in values[side]):
                raise ValueError('Módulo de barra desconocido o repetido.')
        if any('tray' in values[side] for side in ('left','center')):
            raise ValueError('La bandeja debe ir en la sección derecha.')
        if not any(values[side] for side in ('left','center','right')):
            raise ValueError('Deja al menos un módulo en la barra.')
        path=self.config/'orbit/hypr-bar.json';previous=path.read_text() if path.exists() else None
        backup_file(path,self.home/'.local/share/orbit/settings-backups')
        atomic_write(path,json.dumps(values,ensure_ascii=False,indent=2)+'\n')
        try:self.runner(['wysun','shell','reload-preferences'])
        except Exception:
            if previous is None:path.unlink(missing_ok=True)
            else:atomic_write(path,previous)
            try:self.runner(['wysun','shell','reload-preferences'])
            except Exception:pass
            raise

    def wallpaper_values(self):
        saved = copy.deepcopy(self.section('wallpaper'))
        if not saved.get('default'):
            from theme_tokens import tokens
            filename=tokens(self.home)['wallpaper']
            bundled=self.home/'.local/share/backgrounds'/filename
            if bundled.is_file():saved['default']=str(bundled)
        saved.setdefault('mode','fill')
        saved.setdefault('monitors',{})
        saved.setdefault('folders',[])
        return saved

    def apply_wallpaper(self, values):
        old=copy.deepcopy(self.section('wallpaper'))
        self.save_section('wallpaper',values)
        try:
            render_wallpaper(values,display_inventory(self.runner),self.home,self.runner)
            from wysun_scheme import regenerate_if_dynamic
            regenerate_if_dynamic(self.home,values)
        except Exception:
            self.save_section('wallpaper',old)
            raise

    def component_values(self, component):
        if component=='effects':
            from hypr_settings import effects_state
            return effects_state(self.runner)[0]
        paths = {'terminal':'ghostty/config','notifications':'wysun/dunstrc'}
        path = self.config/paths[component]
        text = path.read_text() if path.exists() else ''
        if component == 'notifications':
            return {key:ini_value(text,'global',key,default).strip('"') for key,default in [('origin','top-right'),('font','Inter 10'),('transparency','5'),('corner_radius','12'),('notification_limit','4'),('padding','18'),('gap_size','10')]} | {'timeout':ini_value(text,'urgency_normal','timeout','6')}
        return kv_values(text)

    def apply_component(self, component, values):
        if component == 'terminal':
            clean = {'font-size':bounded(values['font-size'],8,36),'background-opacity':bounded(values['background-opacity'],.1,1),'window-padding-x':bounded(values['window-padding-x'],0,60,True),'window-padding-y':bounded(values['window-padding-y'],0,60,True),'scrollback-limit':bounded(values['scrollback-limit'],1000,1000000,True)}
            font = values['font-family'].strip()
            if not font or '\n' in font or '"' in font:
                raise ValueError('Nombre de fuente inválido.')
            clean['font-family'] = '"'+font+'"'
            for k in ('background','foreground'):
                clean[k] = color(values[k])[1:]
            path = self.config/'ghostty/config'
            self.edit_file(path,set_values(path.read_text() if path.exists() else '',clean),lambda:self.runner(['ghostty','+validate-config']))
        elif component == 'effects':
            from hypr_settings import effects_script,config_dir,effects_state,apply_fragment
            text=effects_script(values);path=config_dir(self.home)/'orbit/hypr-effects.lua'
            rollback=effects_state(self.runner)[1]
            self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with (self.path.parent/'environment.lock').open('a') as handle:
                fcntl.flock(handle,fcntl.LOCK_EX)
                latest=read_json(self.path)
                if latest.get('hypr-effects',{})!=self.section('hypr-effects'):raise ValueError('Los efectos cambiaron. Recarga antes de guardar.')
                latest['hypr-effects']=values
                apply_fragment(self.runner,{path:text,self.path:json.dumps(latest,ensure_ascii=False,indent=2)+'\n'},text,rollback)
                self.data['hypr-effects']=copy.deepcopy(values)
        elif component == 'notifications':
            path = self.config/'wysun/dunstrc'
            if values['origin'] not in ('top-left','top-center','top-right','bottom-left','bottom-center','bottom-right'):
                raise ValueError('Posición de notificaciones inválida.')
            clean = {'origin':values['origin']}
            for key,lo,hi in [('transparency',0,60),('corner_radius',0,30),('notification_limit',1,12),('padding',4,40),('gap_size',0,30)]:
                clean[key] = bounded(values[key],lo,hi,True)
            if '\n' in values['font'] or '"' in values['font']:
                raise ValueError('Fuente inválida.')
            clean['font'] = values['font']
            text = set_ini(path.read_text(),'global',clean)
            text = set_ini(text,'urgency_normal',{'timeout':bounded(values['timeout'],1,60,True)})
            self.edit_file(path,text,lambda:self.runner(['dunstctl','reload',str(path)]))
        else:
            raise ValueError('Componente desconocido.')

    def effective_workspace_layout(self, outputs=None):
        """Stored fixed layout for the current outputs, or the automatic one."""
        import workspace_layout as layouts
        outputs = outputs if outputs is not None else display_inventory(self.runner)
        stored = layouts.normalize_layout(self.section('workspaces'),outputs)
        return stored or layouts.default_layout(outputs)

    def workspaces(self):
        """Live workspaces merged with the fixed layout still to be created."""
        import workspace_layout as layouts
        from desktop_backend import Desktop
        rows = Desktop(self.runner).workspaces()
        outputs = display_inventory(self.runner)
        mapping = self.effective_workspace_layout(outputs)
        live = {row['id']:dict(row) for row in rows}
        merged = []
        for output,numbers in mapping.items():
            for number in numbers:
                ident = str(number)
                row = live.pop(ident,None) or {'id':ident,'name':ident,'monitor':output,'windows':0,'active':False}
                merged.append(row | {'assigned':output,'fixed':True,'number':number,'label':layouts.workspace_label(number)})
        for row in live.values():
            number = None
            try:number = int(str(row['name']))
            except (TypeError,ValueError):pass
            merged.append(row | {'assigned':'','fixed':False,'number':number,
                                 'label':layouts.workspace_label(row.get('name',row['id']))})
        merged.sort(key=lambda row:layouts.sort_key(row['id']))
        return merged

    def apply_workspace_layout(self, mapping):
        """Validate, persist and apply a fixed workspace layout live."""
        import workspace_layout as layouts
        from hypr_settings import apply_fragment
        outputs = display_inventory(self.runner)
        clean = layouts.validate_layout(mapping,outputs)
        previous = layouts.normalize_layout(self.section('workspaces'),outputs)
        text = layouts.lua_fragment(clean)
        live = layouts.live_script(clean,previous)
        rollback = layouts.live_script(previous,clean)
        path = self.config/'orbit/hypr-workspaces.lua'
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with (self.path.parent/'environment.lock').open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX)
            latest = read_json(self.path)
            if latest.get('workspaces',{})!=self.data.get('workspaces',{}):
                raise ValueError('Los escritorios cambiaron en otra ventana. Recarga antes de guardar.')
            latest['workspaces'] = clean
            payload = json.dumps(latest,ensure_ascii=False,indent=2)+'\n'
            apply_fragment(self.runner,{path:text,self.path:payload},live,rollback)
            self.data['workspaces'] = copy.deepcopy(clean)

    def assign_workspace(self, number, monitor):
        """Move one numeric workspace to an active output and persist it."""
        import workspace_layout as layouts
        outputs = display_inventory(self.runner)
        active = [o['name'] for o in outputs if o.get('enabled',True)]
        if monitor not in active:raise ValueError('Esa pantalla no está activa.')
        number = layouts.workspace_number(number)
        mapping = self.effective_workspace_layout(outputs)
        for name in list(mapping):mapping[name] = [n for n in mapping[name] if n!=number]
        mapping.setdefault(monitor,[]).append(number)
        mapping = {name:sorted(values) for name,values in mapping.items() if values}
        self.apply_workspace_layout(mapping)

    def unassign_workspace(self, ident):
        """Remove one empty numeric workspace from the fixed layout."""
        import workspace_layout as layouts
        from desktop_backend import Desktop
        number = layouts.workspace_number(ident)
        live = Desktop(self.runner).workspaces()
        row = next((r for r in live if r['id']==str(ident) or r['name']==str(ident)),None)
        if row and row['windows']:raise ValueError('Solo se pueden quitar escritorios vacíos')
        mapping = self.effective_workspace_layout()
        for name in list(mapping):mapping[name] = [n for n in mapping[name] if n!=number]
        mapping = {name:values for name,values in mapping.items() if values}
        if not mapping:raise ValueError('Deja al menos un escritorio asignado.')
        self.apply_workspace_layout(mapping)

    def reset_workspace_layout(self):
        """Return to the automatic 1-5 / 6-9 / 10 distribution."""
        import workspace_layout as layouts
        self.apply_workspace_layout(layouts.default_layout(display_inventory(self.runner)))

    def workspace_action(self, action, ident='', value=''):
        if read_json(self.path).get('workspaces',{})!=self.section('workspaces'):
            raise ValueError('Los escritorios cambiaron en otra ventana. Recarga antes de editar.')
        if action in ('move','remove') and str(ident).isdecimal():
            import workspace_layout as layouts
            try:number = layouts.workspace_number(ident)
            except ValueError:number = None
            if number is not None:
                if action=='move':return self.assign_workspace(number,value)
                return self.unassign_workspace(number)
        rows = self.workspaces()
        if action in ('rename','add'):
            if not value.strip() or len(value)>40 or any(c in value for c in '\n\r\0'):
                raise ValueError('El nombre del escritorio debe tener entre 1 y 40 caracteres.')
            if any(r['name']==value and r['id']!=ident for r in rows):
                raise ValueError('Ya existe un escritorio con ese nombre.')
        from desktop_backend import Desktop
        Desktop(self.runner).workspace_action(action,ident,value)
        mapping={}
        for r in self.workspaces():mapping.setdefault(r['monitor'],[]).append(r['name'])
        self.save_section('workspaces',mapping)

    def autostart_entries(self):
        roots=[Path(p)/'autostart' for p in os.environ.get('XDG_CONFIG_DIRS','/etc/xdg').split(':')]+[self.home/'.config/autostart']
        files={}
        for folder in roots:
            for p in folder.glob('*.desktop'):files[p.name]=p
        result=[]
        for name,p in files.items():
            try:
                text=p.read_text();get=lambda k,d='':ini_value(text,'Desktop Entry',k,d)
                if get('Type','Application')!='Application':continue
                result.append(dict(id=name,name=get('Name',p.stem),command=get('Exec'),enabled=get('Hidden','false').lower()!='true',managed=name in self.section('autostart').get('entries',[]),path=str(p)))
            except (OSError,configparser.Error):continue
        return sorted(result,key=lambda r:r['name'].casefold())

    def set_autostart(self, entry, enabled):
        target=self.home/'.config/autostart'/entry['id']
        text=Path(entry['path']).read_text()
        if target.exists():backup_file(target,self.home/'.local/share/orbit/settings-backups')
        atomic_write(target,set_ini(text,'Desktop Entry',{'Hidden':'false' if enabled else 'true'}))
        entries=list(self.section('autostart').get('entries',[]))
        if entry['id'] not in entries:entries.append(entry['id'])
        self.save_section('autostart',{'entries':entries})

    def add_autostart(self, name, command):
        if not name.strip() or '\n' in name or '\n' in command or not command.strip():raise ValueError('Escribe un nombre y un comando en una sola línea.')
        argv=shlex.split(command)
        if not argv or not (shutil.which(argv[0]) or Path(argv[0]).is_file()):raise ValueError('No se encuentra el programa del comando.')
        ident='orbit-'+re.sub(r'[^a-z0-9]+','-',name.casefold()).strip('-')+'.desktop'
        path=self.home/'.config/autostart'/ident
        if path.exists():raise ValueError('Ya existe una entrada con ese nombre.')
        atomic_write(path,'[Desktop Entry]\nType=Application\nName='+name+'\nExec='+command+'\nTerminal=false\nHidden=false\n')
        self.save_section('autostart',{'entries':[*self.section('autostart').get('entries',[]),ident]})

def render_wallpaper(values, outputs, home=None, runner=run):
    from PySide6.QtGui import QImageReader
    home=Path(home or Path.home())
    active=[o for o in outputs if o['connected'] and o['enabled']]
    if not active:raise ValueError('No se encontraron pantallas activas.')
    selected_paths=[]
    for output in active:
        selected=values.get('monitors',{}).get(output['name'],{})
        path=Path(selected.get('path') or values.get('default','')).expanduser()
        if not path.is_file():raise ValueError('Elige un fondo para '+output['name'])
        if (selected.get('mode') or values.get('mode','fill')) not in ('fill','fit','stretch','center'):raise ValueError('Modo de fondo inválido')
        reader=QImageReader(str(path));size=reader.size()
        if not size.isValid() or size.width()*size.height()>70_000_000:raise ValueError('Imagen no disponible o demasiado grande')
        selected_paths.append(path)
    # Quickshell owns wallpaper surfaces; publish validated preferences.
    from hypr_settings import config_dir
    config=config_dir(home)/'orbit/environment.json';data=read_json(config);data['wallpaper']=copy.deepcopy(values)
    atomic_write(config,json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    try:runner(['wysun','shell','reload-preferences'])
    except Exception:pass  # the shell watches environment.json; a stopped shell is not a failed save
    return selected_paths[0]

"""Expanded bindings and application shortcut catalogues."""
import ast
import json
import re
import subprocess
from pathlib import Path
from settings_data import expand_sequence, canonical, backup_file, atomic_write

def expanded_rows(model):
    result = []
    for index,row in enumerate(model.rows):
        try:
            keys, commands = expand_sequence(row['key']), expand_sequence(row['command'])
            if len(commands) == 1:
                commands *= len(keys)
            if len(keys) != len(commands):
                raise ValueError('Grupo con distinto número de comandos y teclas')
            for part,(key,command) in enumerate(zip(keys,commands)):
                result.append(dict(row, key=key, command=command, source_index=index, part=part, scope='Global', editable=True))
        except ValueError as exc:
            result.append(dict(row, source_index=index, part=None, scope='Global', editable=True, error=str(exc)))
    return result

def change_binding(model, index, part, key=None, command=None, title=None):
    if part is None:
        return model.delete(index) if key is None else model.save(key,command,index,title)
    rows = [r for r in expanded_rows(model) if r['source_index'] == index]
    if key is not None:
        if len(expand_sequence(key)) != 1:
            raise ValueError('Edita una combinación por fila; usa «Editar grupo» para cambiar las llaves.')
        model.validate(key,command,index)
        if any(canonical(key) == canonical(r['key']) for r in rows if r['part'] != part):
            raise ValueError('La combinación ya existe dentro de este grupo.')
    if model.path.read_text() != model.original:
        raise ValueError('El archivo cambió fuera de Ajustes. Recarga antes de guardar.')
    replacement = []
    for row in rows:
        if row['part'] == part:
            if key is None:
                continue
            row = dict(row,key=key,command=command,title=title or row['title'])
        # Expanded sibling commands must not be expanded a second time by sxhkd.
        body=row['command'].strip()
        if row['part']!=part or key is None:body=body.replace('{',r'\{').replace('}',r'\}')
        replacement.append('# ' + row['title'].replace('\n',' ') + '\n' + row['key'].strip() + '\n    ' + body + '\n')
    original = model.rows[index]
    lines = model.lines.copy()
    lines[original['start']:original['end']] = ['\n'.join(replacement)]
    backup = backup_file(model.path)
    atomic_write(model.path,''.join(lines))
    model.reload()
    return backup

def application_shortcuts(root=None, home=None):
    root = Path(root or Path(__file__).parent)
    home = Path(home or Path.home())
    rows = []
    # Enumerate the installed default bindings, then overlay the user's bindings.
    bindings = {}
    try:
        output = subprocess.run(['ghostty','+list-keybinds'],capture_output=True,text=True,timeout=5,check=True).stdout
        for line in output.splitlines():
            if '=' in line:
                key,action = line.strip().removeprefix('keybind = ').split('=',1)
                bindings[key.strip()] = action.strip()
    except (OSError,subprocess.SubprocessError):
        pass
    path = home/'.config/ghostty/config'
    if path.exists():
        for line in path.read_text().splitlines():
            if re.match(r'^\s*keybind\s*=',line):
                key,action = line.split('=',1)[1].strip().split('=',1)
                bindings[key] = action
    for key,action in bindings.items():
        if action != 'unbind':
            rows.append(dict(key=key.replace('+',' + '),title=action.replace('_',' '),command=action,scope='Terminal',editable=False,path=str(path)))
    # Read the shortcuts declared by the installed native utilities themselves.
    action_labels={'paste_selected':'Pegar en la aplicación anterior','escape':'Volver o cerrar','actions':'Menú de acciones','new_snippet':'Crear snippet','pin_current':'Fijar o desfijar elemento','delete_current':'Eliminar elemento','edit_in_vim':'Editar en Neovim','quicklook':'Vista previa','save':'Guardar','close':'Cerrar ventana','apply':'Aplicar cambios','rescan':'Volver a buscar','setFocus':'Enfocar búsqueda','home':'Inicio','clipboard':'Historial','files':'Archivos','snippets':'Snippets','calculator':'Calculadora'}
    def label_action(node):
        if isinstance(node,ast.Lambda):return label_action(node.body)
        if isinstance(node,ast.Call):
            if isinstance(node.func,ast.Attribute) and node.func.attr=='set_mode' and node.args and isinstance(node.args[0],ast.Constant):return 'Abrir '+action_labels.get(node.args[0].value,str(node.args[0].value))
            if isinstance(node.func,ast.Attribute) and node.func.attr=='cycle_mode':return 'Cambiar sección'
            return label_action(node.func)
        if isinstance(node,ast.Attribute):return action_labels.get(node.attr,node.attr.replace('_',' '))
        return ast.unparse(node)
    for filename,scope in [('orbit.py','Órbita'),('desktop_v3.py','Órbita'),('enhanced.py','Órbita'),('connections_window.py','Conexiones'),('files_controller.py','Archivos'),('settings_hub.py','Ajustes'),('desktop_common.py','Ajustes')]:
        path = root/filename
        if not path.exists():
            continue
        try:
            source=path.read_text();tree = ast.parse(source)
            parents={child:parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
            for loop in ast.walk(tree):
                if not isinstance(loop,ast.For) or not isinstance(loop.iter,(ast.List,ast.Tuple)):continue
                if not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='QKeySequence' for n in ast.walk(loop)):continue
                for entry in loop.iter.elts:
                    if isinstance(entry,ast.Tuple) and len(entry.elts)==2 and isinstance(entry.elts[0],ast.Constant) and isinstance(entry.elts[0].value,str):
                        key=entry.elts[0].value;action=label_action(entry.elts[1]);rows.append(dict(key=key,title=action,command=ast.unparse(entry.elts[1]),scope=scope,editable=False,path=str(path)))
            for node in ast.walk(tree):
                if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name) or node.func.id != 'QKeySequence' or not node.args or not isinstance(node.args[0],ast.Constant):
                    continue
                key = node.args[0].value
                if isinstance(key,str):
                    parent=parents.get(node)
                    while parent is not None and not isinstance(parent,ast.Expr):parent=parents.get(parent)
                    handler=parent.value.args[0] if parent and isinstance(parent.value,ast.Call) and parent.value.args else None
                    action=label_action(handler) if handler else 'Acción de '+scope
                    rows.append(dict(key=key,title=action,command=ast.unparse(handler) if handler else action,scope=scope,editable=False,path=str(path)))
        except (SyntaxError,OSError):
            pass
    for i,title in enumerate(('Wi-Fi y Ethernet','Bluetooth','VPN','SSH','Conexiones guardadas')):
        rows.append(dict(key=f'Alt+{i+1}',title='Abrir '+title,command='Sección '+title,scope='Conexiones',editable=False,path=str(root/'connections_window.py')))
    # Neovim's own public mapping APIs include the user's and NvChad's bindings.
    lua = "require('mappings'); local r={}; for _,m in ipairs({'n','i','v','x','t'}) do for _,k in ipairs(vim.api.nvim_get_keymap(m)) do if k.desc and k.desc~='' then r[#r+1]={key=k.lhs,title=k.desc,mode=m} end end end; print('ORBIT_KEYS:'..vim.json.encode(r))"
    try:
        out = subprocess.run(['nvim','-n','-i','NONE','--headless','-c','lua '+lua,'-c','qa'],capture_output=True,text=True,timeout=8,check=True)
        match = re.search(r'ORBIT_KEYS:(\[.*\])',out.stdout+out.stderr)
        for row in json.loads(match[1]) if match else []:
            rows.append(dict(key=row['key'].replace('<Space>','Espacio '),title=row['title'],command='Modo '+row['mode'],scope='Neovim',editable=False,path=str(home/'.config/nvim/lua/mappings.lua')))
    except (OSError,ValueError,subprocess.SubprocessError):
        pass
    unique = {(r['scope'],r['key'],r['title']):r for r in rows}
    return list(unique.values())

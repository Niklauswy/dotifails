"""Desktop operations selected by session, never by the presence of DISPLAY.

XWayland is not a desktop backend. Keep opaque compositor IDs separate from XIDs.
All commands are argv arrays; window titles never become compositor commands.
"""
import json
import os
import re
import subprocess


def wayland():
    return os.environ.get('XDG_SESSION_TYPE') == 'wayland' or bool(os.environ.get('WAYLAND_DISPLAY'))


def run(args):
    result=subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=3).strip()
    if list(args[:2]) in (['hyprctl','eval'],['hyprctl','dispatch']) and result!='ok':raise RuntimeError(result[:500])
    return result


class Desktop:
    def __init__(self, runner=run, backend=None):
        self.run = runner
        self.backend = backend or ('hyprland' if wayland() and os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') else
                                   'sway' if wayland() and os.environ.get('SWAYSOCK') else
                                   'wayland' if wayland() else 'x11')

    def query(self, name):
        if self.backend == 'hyprland':return json.loads(self.run(['hyprctl', '-j', name]))
        return json.loads(self.run(['swaymsg', '-r', '-t', name]))

    def dispatch(self, method, **values):
        # Pinned Hyprland >=0.55 Lua API. Only code-owned method names are used.
        if not re.fullmatch(r'[a-z_]+(?:\.[a-z_]+)*',method):raise ValueError('Dispatcher inválido')
        def literal(value):
            if type(value) is bool:return 'true' if value else 'false'
            if type(value) is int:return str(value)
            if not isinstance(value,str) or any(ord(c)<32 for c in value):raise ValueError('Valor Lua inválido')
            return json.dumps(value,ensure_ascii=False)
        fields=', '.join(k+' = '+literal(v) for k,v in values.items())
        return self.run(['hyprctl','dispatch','hl.dsp.'+method+'('+('{ '+fields+' }' if values else '')+')'])

    def command(self, *args):
        result = json.loads(self.run(['swaymsg', '-r', *args]))
        if not result or any(not r.get('success') for r in result):
            raise RuntimeError('El compositor rechazó la operación: '+str(result))
        return result

    def windows(self):
        if self.backend == 'hyprland':
            active = self.query('activewindow').get('address')
            return [dict(id=w['address'], title=w.get('title') or w.get('class','Ventana'),
                         app=w.get('class',''), workspace=str(w.get('workspace',{}).get('id','')),
                         focused=w['address']==active, fullscreen=bool(w.get('fullscreen')),
                         rect=[*w.get('at',[0,0]), *w.get('size',[0,0])],pid=w.get('pid'),xwayland=bool(w.get('xwayland')))
                    for w in self.query('clients') if w.get('mapped',True)]
        if self.backend == 'sway':
            result=[]
            def visit(n, workspace=''):
                if n.get('type')=='workspace':workspace=n.get('name','')
                if n.get('app_id') or n.get('window'):
                    result.append(dict(id=str(n['id']), title=n.get('name') or 'Ventana',
                        app=n.get('app_id') or n.get('window_properties',{}).get('class',''),
                        workspace=workspace, focused=n.get('focused',False), fullscreen=bool(n.get('fullscreen_mode')),
                        rect=[n.get('rect',{}).get(k,0) for k in ('x','y','width','height')],pid=n.get('pid'),xwayland=bool(n.get('window'))))
                for c in n.get('nodes',[])+n.get('floating_nodes',[]):visit(c,workspace)
            visit(self.query('get_tree'));return result
        if self.backend == 'wayland':
            raise RuntimeError('El compositor no ofrece el backend de ventanas Hyprland/Sway de Wysun.')
        tree=json.loads(self.run(['bspc','wm','-d']));result=[]
        try:focused=self.run(['bspc','query','-N','-n','focused']).lower()
        except (OSError,subprocess.SubprocessError):focused=''
        def visit(n,workspace):
            if not n:return
            if n.get('client'):
                app=n['client'].get('className','');wid=hex(n['id']);title=app
                try:title=self.run(['xprop','-id',wid,'_NET_WM_NAME']).split(' = ',1)[-1].strip('"')
                except (OSError,subprocess.SubprocessError):pass
                result.append(dict(id=wid,title=title,app=app,workspace=workspace,focused=wid.lower()==focused,
                                   fullscreen=n['client'].get('state')=='fullscreen',xwayland=False))
            visit(n.get('firstChild'),workspace);visit(n.get('secondChild'),workspace)
        for m in tree['monitors']:
            for d in m['desktops']:visit(d.get('root'),d['name'])
        return result

    def focused(self):
        if self.backend=='hyprland':return self.query('activewindow').get('address','')
        if self.backend=='x11':return self.run(['bspc','query','-N','-n','focused'])
        return next((w['id'] for w in self.windows() if w['focused']),'')

    def focused_app(self):
        if self.backend=='hyprland':return self.query('activewindow').get('class','')
        if self.backend=='x11':
            props=self.run(['xprop','-id',self.focused(),'WM_CLASS'])
            names=re.findall(r'"([^"]+)"',props);return names[-1] if names else ''
        return next((w['app'] for w in self.windows() if w['focused']),'')

    def _id(self, ident):
        pattern=r'0x[0-9a-fA-F]+' if self.backend in ('hyprland','x11') else r'[0-9]+'
        if not re.fullmatch(pattern,str(ident)):raise ValueError('Identificador de ventana inválido')
        return str(ident)

    def activate(self, ident):
        ident=self._id(ident)
        if self.backend=='hyprland':self.dispatch('focus',window='address:'+ident)
        elif self.backend=='sway':self.command('[con_id='+ident+'] focus')
        elif self.backend=='x11':self.run(['bspc','node',ident,'-f'])
        else:raise RuntimeError('Activación no disponible en este compositor')

    def fullscreen(self, ident, enabled):
        ident=self._id(ident)
        if self.backend=='hyprland':self.dispatch('window.fullscreen_state',internal=2 if enabled else 0,client=2 if enabled else 0,window='address:'+ident)
        elif self.backend=='sway':self.command(f'[con_id={ident}] fullscreen '+('enable' if enabled else 'disable'))
        elif self.backend=='x11':self.run(['bspc','node',ident,'-t','fullscreen' if enabled else 'tiled'])

    def workspaces(self):
        if self.backend=='hyprland':
            monitors={m['name']:m for m in self.query('monitors')}
            return [dict(id=str(w['id']),name=w['name'],monitor=w['monitor'],windows=w.get('windows',0),
                         active=monitors.get(w['monitor'],{}).get('activeWorkspace',{}).get('id')==w['id']) for w in self.query('workspaces')]
        if self.backend=='sway':
            windows=self.windows()
            return [dict(id=str(w['num']) if w['num']>=0 else w['name'],name=w['name'],monitor=w['output'],
                windows=sum(x['workspace']==w['name'] for x in windows),active=w.get('visible',False)) for w in self.query('get_workspaces')]
        raise RuntimeError('Use el modelo BSPWM para escritorios X11')

    @staticmethod
    def quoted(value):
        if not isinstance(value,str) or not value.strip() or any(c in value for c in '\n\r\0;'):raise ValueError('Nombre inválido')
        return json.dumps(value,ensure_ascii=False)

    def workspace_action(self, action, ident='', value=''):
        rows=self.workspaces();current=next((w for w in rows if w['id']==str(ident)),None)
        if action!='add' and current is None:raise ValueError('El escritorio ya no existe')
        if action=='remove':
            if current['windows']:raise ValueError('Solo se pueden quitar escritorios vacíos')
            # Wayland compositors remove empty, unfocused workspaces themselves.
            other=next((w for w in rows if w['id']!=str(ident) and w['monitor']==current['monitor']),None)
            if not other:raise ValueError('Deja un escritorio en cada monitor')
            return self.workspace_action('activate',other['id'])
        if self.backend=='hyprland':
            # Names are literal, not numeric/relative/special workspace selectors.
            selector='name:'+current['name'] if current else None
            if action=='activate':return self.dispatch('focus',workspace=selector)
            if action=='rename':return self.dispatch('workspace.rename',workspace=selector,name=value)
            if action=='add':return self.dispatch('focus',workspace='name:'+value)
            if action=='move':return self.dispatch('workspace.move',workspace=selector,monitor=value)
        else:
            name=self.quoted(current['name']) if current else ''
            if action=='activate':return self.command('workspace '+name)
            if action=='rename':return self.command('rename workspace '+name+' to '+self.quoted(value))
            if action=='add':return self.command('workspace '+self.quoted(value))
            if action=='move':
                active=next((w for w in rows if w['active']),None)
                self.command('workspace '+name)
                try:return self.command('move workspace to output '+self.quoted(value))
                finally:
                    if active:self.command('workspace '+self.quoted(active['name']))
        raise ValueError('Acción de escritorio desconocida')

    def logout(self):
        if self.backend=='hyprland':return ['hyprctl','dispatch','hl.dsp.exit()']
        if self.backend=='sway':return ['swaymsg','exit']
        if self.backend=='x11':return ['bspc','quit']
        raise RuntimeError('Cierra sesión desde el compositor')


def previous_window():
    try:return Desktop().focused()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError):return ''

"""Hyprland operations for Wysun.

XWayland is not a desktop backend. All commands are argv arrays; window titles
and workspace names never become compositor command strings.
"""
import json
import os
import re
import subprocess


def wayland():
    """True when the current session is a Wayland session (always for Wysun)."""
    return os.environ.get('XDG_SESSION_TYPE') == 'wayland' or bool(os.environ.get('WAYLAND_DISPLAY'))


def run(args):
    result=subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=3).strip()
    if list(args[:2]) in (['hyprctl','eval'],['hyprctl','dispatch']) and result!='ok':raise RuntimeError(result[:500])
    return result


class Desktop:
    def __init__(self, runner=run, backend=None):
        if backend not in (None,'hyprland'):
            raise ValueError('Wysun usa Hyprland como único compositor.')
        self.run = runner
        self.backend = 'hyprland'

    def query(self, name):
        return json.loads(self.run(['hyprctl', '-j', name]))

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

    def windows(self):
        active = self.query('activewindow').get('address')
        return [dict(id=w['address'], title=w.get('title') or w.get('class','Ventana'),
                     app=w.get('class',''), workspace=str(w.get('workspace',{}).get('id','')),
                     focused=w['address']==active, fullscreen=bool(w.get('fullscreen')),
                     rect=[*w.get('at',[0,0]), *w.get('size',[0,0])],pid=w.get('pid'),xwayland=bool(w.get('xwayland')))
                for w in self.query('clients') if w.get('mapped',True)]

    def focused(self):
        return self.query('activewindow').get('address','')

    def focused_app(self):
        return self.query('activewindow').get('class','')

    def _id(self, ident):
        if not re.fullmatch(r'0x[0-9a-fA-F]+',str(ident)):raise ValueError('Identificador de ventana inválido')
        return str(ident)

    def activate(self, ident):
        ident=self._id(ident)
        self.dispatch('focus',window='address:'+ident)

    def fullscreen(self, ident, enabled):
        ident=self._id(ident)
        self.dispatch('window.fullscreen_state',internal=2 if enabled else 0,client=2 if enabled else 0,window='address:'+ident)

    def workspaces(self):
        monitors={m['name']:m for m in self.query('monitors')}
        return [dict(id=str(w['id']),name=w['name'],monitor=w['monitor'],windows=w.get('windows',0),
                     active=monitors.get(w['monitor'],{}).get('activeWorkspace',{}).get('id')==w['id']) for w in self.query('workspaces')]

    def workspace_action(self, action, ident='', value=''):
        rows=self.workspaces();current=next((w for w in rows if w['id']==str(ident)),None)
        if action!='add' and current is None:raise ValueError('El escritorio ya no existe')
        if action=='remove':
            if current['windows']:raise ValueError('Solo se pueden quitar escritorios vacíos')
            # Hyprland removes empty, unfocused workspaces itself.
            other=next((w for w in rows if w['id']!=str(ident) and w['monitor']==current['monitor']),None)
            if not other:raise ValueError('Deja un escritorio en cada monitor')
            return self.workspace_action('activate',other['id'])
        # Names are literal, not numeric/relative/special workspace selectors.
        selector='name:'+current['name'] if current else None
        if action=='activate':return self.dispatch('focus',workspace=selector)
        if action=='rename':return self.dispatch('workspace.rename',workspace=selector,name=value)
        if action=='add':return self.dispatch('focus',workspace='name:'+value)
        if action=='move':return self.dispatch('workspace.move',workspace=selector,monitor=value)
        raise ValueError('Acción de escritorio desconocida')

    def logout(self):
        return ['hyprctl','dispatch','hl.dsp.exit()']


def previous_window():
    try:return Desktop().focused()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError):return ''

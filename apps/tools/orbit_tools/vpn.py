"""Fail-closed exit-node protection in an owned nftables table."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
from .common import ToolError, require, run, private_write, read_json

TABLE = 'orbit_tailscale_lock'
MARKER = 'dotifails-tailscale-killswitch-v1'
STATE = Path('/var/lib/dotifails/tailscale-killswitch/state.json')


def rules(interface='tailscale0'):
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,15}',interface): raise ToolError('Interfaz inválida.')
    return f'''table inet {TABLE} {{
    comment "{MARKER}"
    chain output {{
        type filter hook output priority -10; policy drop;
        oifname "lo" accept
        oifname "{interface}" accept
        meta mark & 0xff0000 == 0x80000 accept
        udp sport 68 udp dport 67 accept
        udp sport 546 udp dport 547 accept
        icmpv6 type {{ nd-router-solicit, nd-neighbor-solicit, nd-neighbor-advert }} ip6 hoplimit 255 accept
    }}
}}
'''


def provider_json(argv):
    try:
        value = json.loads(run(argv).stdout)
        if not isinstance(value,dict): raise ValueError()
        return value
    except ValueError:
        raise ToolError('Tailscale no devolvió un objeto JSON válido.') from None


def owned_table():
    done = run([require('nft'),'list','table','inet',TABLE],check=False)
    if done.returncode:
        if 'No such file' in done.stderr: return False
        raise ToolError('No se pudo inspeccionar nftables: '+done.stderr.strip())
    if MARKER not in done.stdout: raise ToolError('La tabla existente no pertenece a dotifails.')
    return True


def restore_prefs(state):
    prefs = state['previous']
    run(['tailscale','set','--exit-node='+prefs['exit_node'],
         '--exit-node-allow-lan-access='+str(prefs['allow_lan']).lower(),
         '--accept-dns='+str(prefs['dns']).lower()])


def selected_node(status):
    selected = status.get('ExitNodeStatus') or {}
    if selected: return selected.get('ID',''), bool(selected.get('Online'))
    for key, peer in (status.get('Peer') or {}).items():
        if peer.get('ExitNode'): return peer.get('ID',key), bool(peer.get('Online'))
    return '', False


def on(args):
    # Plans are pure: no root, daemon calls, or firewall changes.
    if args.dry_run:
        print(rules(args.interface)); print('tailscale set --exit-node='+args.exit_node+' --exit-node-allow-lan-access=false --accept-dns=true')
        return 0
    if os.geteuid() != 0: raise ToolError('La activación requiere sudo; --dry-run no requiere privilegios.')
    require('tailscale'); require('nft')
    if STATE.exists() or owned_table(): raise ToolError('Ya existe un bloqueo o recuperación pendiente. Usa status y off primero.')
    legacy = run([require('iptables'),'-S','OUTPUT'],check=False)
    if legacy.returncode or 'TAILSCALE_KILLSWITCH' in legacy.stdout:
        raise ToolError('No se pudo descartar el bloqueo antiguo de iptables. Revisa sus reglas antes de activar.')
    if not Path('/sys/class/net',args.interface).exists(): raise ToolError('No existe la interfaz de Tailscale.')
    prefs = provider_json(['tailscale','debug','prefs'])
    status = provider_json(['tailscale','status','--json'])
    previous_node = prefs.get('ExitNodeIP') or ''
    if not previous_node and prefs.get('ExitNodeID'):
        for peer in (status.get('Peer') or {}).values():
            if peer.get('ID') == prefs['ExitNodeID']:
                previous_node = (peer.get('TailscaleIPs') or [''])[0]; break
        if not previous_node: raise ToolError('No se pudo resolver el exit node previo; no se modificó nada.')
    state = {'version':1,'phase':'preparing','previous':{'exit_node':previous_node,
        'allow_lan':bool(prefs.get('ExitNodeAllowLANAccess')), 'dns':bool(prefs.get('CorpDNS'))}}
    text = rules(args.interface)
    run([require('nft'),'-c','-f','-'],input=text)
    private_write(STATE,json.dumps(state))
    armed = False
    try:
        run([require('nft'),'-f','-'],input=text); armed = True
        state['phase'] = 'armed'; private_write(STATE,json.dumps(state))
        run(['tailscale','set','--exit-node='+args.exit_node,'--exit-node-allow-lan-access=false','--accept-dns=true'])
        status = provider_json(['tailscale','status','--json'])
        node, online = selected_node(status)
        peers = list((status.get('Peer') or {}).values())
        matching = [p for p in peers if args.exit_node.rstrip('.').lower() in
            [str(p.get('ID','')).lower(),str(p.get('HostName','')).lower(),str(p.get('DNSName','')).rstrip('.').lower(),*p.get('TailscaleIPs',[])]]
        if not node or not online or not any(p.get('ID') == node for p in matching):
            raise ToolError('El exit node solicitado no quedó conectado.')
        state['phase'] = 'active'; private_write(STATE,json.dumps(state)); print('Bloqueo activo.'); return 0
    except BaseException:
        try:
            restore_prefs(state)
            if armed: run([require('nft'),'delete','table','inet',TABLE])
            STATE.unlink(missing_ok=True)
        except Exception as recovery:
            raise ToolError('Recuperación pendiente; se conserva el estado. Ejecuta off. '+str(recovery)) from None
        raise


def off(args):
    if args.dry_run:
        print('Restaurar preferencias guardadas; eliminar únicamente table inet '+TABLE); return 0
    if os.geteuid() != 0: raise ToolError('La desactivación requiere sudo.')
    state = read_json(STATE)
    if not state: raise ToolError('No hay estado guardado; no se alteraron reglas existentes.')
    present = owned_table()
    restore_prefs(state)  # Keep protection until restoration succeeds.
    if present: run([require('nft'),'delete','table','inet',TABLE])
    STATE.unlink(); print('Preferencias restauradas; bloqueo retirado.'); return 0


def node(value):
    if not value or value.startswith('-') or not re.fullmatch(r'[a-zA-Z0-9_.:-]+',value):
        raise argparse.ArgumentTypeError('Exit node inválido.')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description='Kill switch Tailscale IPv4/IPv6 con restauración de preferencias.')
    sub = parser.add_subparsers(dest='action',required=True)
    p = sub.add_parser('on'); p.add_argument('exit_node',type=node); p.add_argument('--interface',default='tailscale0'); p.add_argument('--dry-run',action='store_true')
    p = sub.add_parser('off'); p.add_argument('--dry-run',action='store_true')
    sub.add_parser('status')
    p = sub.add_parser('plan'); p.add_argument('--interface',default='tailscale0')
    args = parser.parse_args(argv)
    if args.action == 'plan': print(rules(args.interface)); return 0
    if args.action == 'status':
        result = run([require('nft'),'list','table','inet',TABLE],check=False)
        if result.returncode:
            if 'No such file' in result.stderr: print('Sin bloqueo de dotifails.'); return 0
            raise ToolError('No se pudo comprobar el firewall. Ejecuta status con sudo.')
        if MARKER not in result.stdout: raise ToolError('Tabla ajena a dotifails.')
        print('Tabla de bloqueo presente. Estado: '+str((read_json(STATE) or {}).get('phase','sin registro'))); return 0
    return on(args) if args.action == 'on' else off(args)

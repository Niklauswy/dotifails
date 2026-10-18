#!/usr/bin/env python3
"""One command tree shared by terminal tools and the desktop."""
import importlib
import sys
from orbit_tools.common import entry, ToolError

GROUPS = {'dev':'web','audit':'security','share':'transfer','cloud':'cloud','vpn':'vpn','resets':'resets'}
ALIASES = {'web-dev':'dev','sec-audit':'audit','file-share':'share','gvm':'cloud','gvm.sh':'cloud',
           'tailscale-killswitch':'vpn','tailscale-killswitch.sh':'vpn','scrip.sh':'vpn','zzzz.py':'share','rezets':'resets'}

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('--help','-h'):
        print('orbit-tools <grupo> <acción>\n\n  dev     Proyectos web, tareas y puertos\n  audit   Web, TLS, redes y seguridad local\n  share   Compartir archivos\n  cloud   Máquinas de Google Cloud\n  vpn     Bloqueo de Tailscale\n  resets  Recordatorios personales\n  gui     Abrir el panel de Wysun\n\nConsulta: orbit-tools <grupo> --help')
        return 0
    if argv[0]=='gui':
        from orbit_tools.common import require
        import os
        os.execvp(require('orbit'),['orbit','tools'])
    group=ALIASES.get(argv[0],argv[0])
    if group not in GROUPS:raise ToolError('Grupo desconocido. Consulta orbit-tools --help.')
    return importlib.import_module('orbit_tools.'+GROUPS[group]).main(argv[1:])

if __name__=='__main__':entry(main)

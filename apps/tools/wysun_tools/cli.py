"""`wysun tools GRUPO ACCIÓN`: one command tree for the terminal tools."""
import importlib
import sys
from wysun_tools.common import entry, ToolError

GROUPS = {'dev':'web','audit':'security','share':'transfer','cloud':'cloud','vpn':'vpn','resets':'resets'}

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('--help','-h'):
        print('wysun tools <grupo> <acción>\n\n  dev     Proyectos web, tareas y puertos\n  audit   Web, TLS, redes y seguridad local\n  share   Compartir archivos\n  cloud   Máquinas de Google Cloud\n  vpn     Bloqueo de Tailscale\n  resets  Recordatorios personales\n\nConsulta: wysun tools <grupo> --help')
        return 0
    if argv[0] not in GROUPS:raise ToolError('Grupo desconocido. Consulta wysun tools --help.')
    return importlib.import_module('wysun_tools.'+GROUPS[argv[0]]).main(argv[1:])

def run():
    entry(main)

"""Dedicated screenshot process; no recorder services, capture/audio or globals."""
import argparse
import sys
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(prog='wysun screenshot',description='Capturas locales independientes · Wysun Screenshot')
    parser.add_argument('--version',action='version',version='Wysun Screenshot 0.1.0')
    parser.add_argument('--library',action='store_true',help='Abrir la biblioteca local')
    parser.add_argument('--region',action='store_true',help='Seleccionar una región del escritorio congelado')
    parser.add_argument('--accept-on-select',action='store_true',help='Capturar al soltar el botón, sin confirmar con Enter')
    parser.add_argument('--clipboard',action='store_true',help='Copiar el bitmap y terminar después de capturar')
    parser.add_argument('--path',type=Path,help='Guardar PNG en carpeta o archivo PNG/JPEG; nunca sobrescribir')
    parser.add_argument('--delay',type=int,choices=range(0,61),metavar='SEGUNDOS',help='Espera temporal sólo para esta captura (0–60)')
    args=parser.parse_args(argv)
    direct=args.region or args.accept_on_select or args.clipboard or args.path is not None or args.delay is not None
    if args.library and direct:parser.error('--library no admite acciones de captura')
    lease=None
    if direct:
        from .instance import CaptureLease
        lease=CaptureLease()
        if not lease.claim():return 0
    from PySide6.QtWidgets import QApplication
    from .ui.components import apply_theme
    from .ui.main import run
    app=QApplication.instance() or QApplication(['wybie-screenshot'])
    app.setApplicationName('Wysun Screenshot');app.setApplicationDisplayName('Wysun Screenshot')
    app.setDesktopFileName('wybie-screenshot');app.setOrganizationName('Wybie')
    apply_theme(app)
    if direct:
        from .actions import CaptureActions,run as run_actions
        try:return run_actions(app,CaptureActions(args.accept_on_select,args.clipboard,args.path,args.delay),lease=lease)
        finally:lease.release()
    return run(app,['--library'] if args.library else [])

if __name__=='__main__':sys.exit(main())

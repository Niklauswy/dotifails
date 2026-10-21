"""Dedicated screenshot process; no recorder services, capture/audio or globals."""
import argparse
import sys
from pathlib import Path


def prepare_event_loop():
    # Portal workers own GLib's default context. Qt must not acquire it for
    # the GUI's blocking exec() loop (Qt 6.8.2); keep native Wayland/Qt Unix.
    from loomrec.portal import is_wayland
    if is_wayland():
        import os
        os.environ['QT_NO_GLIB']='1'


def main(argv=None):
    parser=argparse.ArgumentParser(prog='wysun screenshot',description='Capturas locales independientes · Wysun Screenshot')
    parser.add_argument('--version',action='version',version='Wysun Screenshot 0.1.0')
    parser.add_argument('--cancel-selection',action='store_true',help='Recuperar selección de esta sesión, conservando anotaciones')
    parser.add_argument('--library',action='store_true',help='Abrir la biblioteca local')
    parser.add_argument('--region',action='store_true',help='Seleccionar una región del escritorio congelado')
    parser.add_argument('--accept-on-select',action='store_true',help='Capturar al soltar el botón, sin confirmar con Enter')
    parser.add_argument('--clipboard',action='store_true',help='Copiar el bitmap y terminar después de capturar')
    parser.add_argument('--path',type=Path,help='Guardar PNG en carpeta o archivo PNG/JPEG; nunca sobrescribir')
    parser.add_argument('--delay',type=int,choices=range(0,61),metavar='SEGUNDOS',help='Espera temporal sólo para esta captura (0–60)')
    args=parser.parse_args(argv)
    if args.cancel_selection:
        from .recovery import request_recovery
        closed, failed = request_recovery()
        print(f'Wysun Screenshot: {closed} selección(es) cerrada(s); {failed} pendiente(s), sin respuesta o sin guardar')
        return 1 if failed else 0
    direct=args.region or args.accept_on_select or args.clipboard or args.path is not None or args.delay is not None
    if args.library and direct:parser.error('--library no admite acciones de captura')
    lease=None;capture_busy=False
    if direct:
        from .instance import CaptureLease
        lease=CaptureLease()
        capture_busy=not lease.claim()
    prepare_event_loop()
    from PySide6.QtWidgets import QApplication
    from .ui.components import apply_theme
    from .ui.main import run
    app=QApplication.instance() or QApplication(['wybie-screenshot'])
    app.setApplicationName('Wysun Screenshot');app.setApplicationDisplayName('Wysun Screenshot')
    app.setDesktopFileName('wybie-screenshot');app.setOrganizationName('Wybie')
    apply_theme(app)
    from .recovery import RecoveryServer
    recovery = RecoveryServer(app)
    if direct:
        if capture_busy:
            recovery.close()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None,'Wysun Screenshot · Captura en curso',
                'Ya hay una selección de Wysun Screenshot en curso. '
                'Termina o cancela la selección anterior y vuelve a intentarlo. '
                'Si no aparece ninguna ventana, informa de una instancia anterior sin interfaz. '
                'No se ha iniciado otra captura.')
            return 0
        from .actions import CaptureActions,run as run_actions
        try:return run_actions(app,CaptureActions(args.accept_on_select,args.clipboard,args.path,args.delay),lease=lease)
        finally:
            recovery.close()
            lease.release()
    try:return run(app,['--library'] if args.library else [])
    finally:recovery.close()

if __name__=='__main__':sys.exit(main())

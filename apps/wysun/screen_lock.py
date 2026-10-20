"""Session locking for Wysun/Wayland; wysun-lock owns authentication and grabs."""
import os
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import QMessageBox


def lock_command():
    executable = Path(os.environ.get('WYSUN_LOCK', str(Path.home()/'.local/bin/wysun-lock'))).expanduser()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError('Falta wysun-lock para proteger la sesión Wayland.')
    return [str(executable)]


def start_lock(owner, suspend=False):
    """Run the Wayland locker without ever handling the user's password."""
    if getattr(owner,'lock_process',None) is not None:return False
    window=getattr(owner,'utilities',{}).get('power',owner)
    buttons=getattr(window,'action_buttons',[])
    def failure(message):
        QMessageBox.warning(window,'No se pudo bloquear',message)
    try:
        command=lock_command()
        if suspend:command.append('--suspend')
    except (OSError,RuntimeError) as error:
        failure(str(error));return False
    process=QProcess(owner);owner.lock_process=process
    from ui_motion import reduced_motion
    environment=QProcessEnvironment.systemEnvironment()
    environment.insert('ORBIT_REDUCED_MOTION','1' if reduced_motion(window) else '0')
    from theme_tokens import theme_id
    environment.insert('ORBIT_THEME',theme_id())
    process.setProcessEnvironment(environment)
    if buttons:buttons[0].setEnabled(False)
    finished=False
    def complete(code,status=QProcess.NormalExit):
        nonlocal finished
        if finished:return
        finished=True;owner.lock_process=None
        if buttons:buttons[0].setEnabled(True)
        if code==0 and status==QProcess.NormalExit:
            window.hide();owner.hide()
        else:
            failure('El bloqueador no pudo proteger la sesión. El panel sigue abierto; vuelve a intentarlo. Si el problema continúa, comprueba la instalación de wysun-lock.')
        process.deleteLater()
    process.finished.connect(complete)
    process.errorOccurred.connect(lambda error:complete(1,QProcess.CrashExit) if error==QProcess.FailedToStart else None)
    process.start(command[0],command[1:])
    return False

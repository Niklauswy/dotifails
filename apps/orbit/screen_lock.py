"""Wysun lock artwork; i3lock owns all authentication and X11 grabs."""
from theme_tokens import ThemeColor, apply_style

import os
import shutil
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QProcess, QProcessEnvironment
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QFont, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import QApplication, QMessageBox


def paint_lock_screen(painter, rect):
    """Leave the screen centre clear for i3lock's native password indicator."""
    painter.save();painter.setClipRect(rect);painter.translate(rect.topLeft())
    width,height=rect.width(),rect.height();scale=min(width/1440,height/900)
    painter.scale(scale,scale);width/=scale;height/=scale
    background=QLinearGradient(0,0,width,height)
    background.setColorAt(0,ThemeColor('#101929'));background.setColorAt(1,ThemeColor('#080E19'))
    painter.fillRect(QRectF(0,0,width,height),background)
    glow=QRadialGradient(width*.5,height*.43,height*.7)
    glow.setColorAt(0,ThemeColor(78,115,177,48));glow.setColorAt(1,ThemeColor(78,115,177,0))
    painter.fillRect(QRectF(0,0,width,height),glow)
    painter.setPen(QPen(ThemeColor(158,188,236,12),1))
    for radius in (height*.42,height*.61,height*.82):
        painter.drawEllipse(QRectF(width/2-radius,height/2-radius,2*radius,2*radius))
    painter.restore()


def render_background(path, screens=None):
    screens=screens or QApplication.screens()
    bounds=screens[0].virtualGeometry()
    image=QImage(bounds.size(),QImage.Format_RGB32);image.fill(ThemeColor('#101929'))
    painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing)
    for screen in screens:
        paint_lock_screen(painter,QRectF(screen.geometry().translated(-bounds.topLeft())))
    painter.end()
    if not image.save(str(path),'PNG'):raise OSError('No se pudo guardar el fondo de bloqueo')


def lock_command():
    native=Path(__file__).resolve().parent.parent/'bin/orbit-lock'
    executable=str(native) if native.is_file() and os.access(native,os.X_OK) else shutil.which('i3lock')
    if not executable:raise RuntimeError('Falta i3lock. Instálalo con: sudo apt install i3lock')
    if not os.environ.get('DISPLAY'):raise RuntimeError('El bloqueo requiere una sesión gráfica X11.')
    command=[executable,'--color=101929']
    try:
        cache=Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))/'orbit/lock'
        cache.mkdir(parents=True,exist_ok=True,mode=0o700)
        path=cache/'background.png';render_background(path)
        command+=['--image',str(path)]
    except OSError:
        # A full/readonly disk must not prevent secure locking.
        pass
    return command


def start_lock(owner):
    """Do not close the menu until i3lock reports successful lock acquisition.

    i3lock's default mode forks only after acquiring the pointer and keyboard.
    Its parent exits successfully then; no password is ever handled by Wysun.
    """
    if getattr(owner,'lock_process',None) is not None:return False
    window=getattr(owner,'utilities',{}).get('power',owner)
    buttons=getattr(window,'action_buttons',[])
    def failure(message):
        QMessageBox.warning(window,'No se pudo bloquear',message)
    try:command=lock_command()
    except (OSError,RuntimeError) as error:
        failure(str(error));return False
    process=QProcess(owner);owner.lock_process=process
    from ui_motion import reduced_motion
    environment=QProcessEnvironment.systemEnvironment();environment.insert('ORBIT_REDUCED_MOTION','1' if reduced_motion(window) else '0');process.setProcessEnvironment(environment)
    from theme_tokens import theme_id
    environment.insert('ORBIT_THEME',theme_id());process.setProcessEnvironment(environment)
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
            failure('El bloqueador no pudo proteger la sesión. El panel sigue abierto; vuelve a intentarlo. Si el problema continúa, comprueba la instalación de i3lock.')
        process.deleteLater()
    process.finished.connect(complete)
    process.errorOccurred.connect(lambda error:complete(1,QProcess.CrashExit) if error==QProcess.FailedToStart else None)
    process.start(command[0],command[1:])
    return False

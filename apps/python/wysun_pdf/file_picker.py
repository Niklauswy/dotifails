"""Run Wysun Files' selector in its own GUI process, alongside the reader."""
import json
from PySide6.QtCore import QEventLoop, QProcess, QProcessEnvironment, QTimer, QUrl
from PySide6.QtWidgets import QMessageBox
from wysun_core import launch


def picker_active(window):
    """True while ``window`` waits for a selector; its close is deferred until the selector ends."""
    return getattr(window, '_file_picker', None) is not None


def cancel_picker(window):
    """Close the selector ``window`` is waiting for; pick_file then returns '' and closes the window."""
    process = getattr(window, '_file_picker', None)
    if process is not None:
        window._close_after_picker = True
        process.kill()


def pick_file(parent, title, *, save=False, initial='', suffix='pdf'):
    """Local path chosen in Wysun Files, or '' when cancelled or failed.

    Waits in a local event loop with ``parent`` disabled. Only one selector per window: a second
    request returns ''. The caller must not touch a window that ``cancel_picker`` closed.
    """
    if parent is not None and picker_active(parent):
        return ''
    process = QProcess(parent)
    env = QProcessEnvironment()
    for key, value in launch.environment().items():
        env.insert(key, value)
    process.setProcessEnvironment(env)
    command = launch.argv('wysun_files.picker')
    process.setProgram(command[0])
    process.setArguments(command[1:])
    loop = QEventLoop()
    process.finished.connect(loop.quit)
    process.start()
    if not process.waitForStarted(3000):
        QMessageBox.warning(parent, title, 'No se pudo abrir el selector de Wysun Files.')
        process.deleteLater()
        return ''
    process.write(json.dumps(dict(title=title, save=save, initial=initial, suffix=suffix)).encode() + b'\n')
    process.closeWriteChannel()
    enabled = parent.isEnabled() if parent else False
    if parent:
        parent._file_picker = process
        parent.setEnabled(False)
    try:
        if process.state() != QProcess.NotRunning:
            loop.exec()
        if parent is not None and getattr(parent, '_close_after_picker', False):
            return ''
        raw = bytes(process.readAllStandardOutput())
        if process.exitStatus() != QProcess.NormalExit or process.exitCode() != 0 or len(raw) > 65536:
            raise ValueError('El selector no pudo completar la operación.')
        result = json.loads(raw)
        uris = result.get('uris', []) if result.get('code') == 0 else []
        url = QUrl(uris[0]) if uris else QUrl()
        return url.toLocalFile() if url.isLocalFile() else ''
    except (ValueError, IndexError, TypeError, AttributeError):
        QMessageBox.warning(parent, title, 'No se pudo completar la selección en Wysun Files.')
        return ''
    finally:
        if parent:
            parent._file_picker = None
            parent.setEnabled(enabled)
            if getattr(parent, '_close_after_picker', False):
                parent._close_after_picker = False
                QTimer.singleShot(0, parent.close)
        process.deleteLater()

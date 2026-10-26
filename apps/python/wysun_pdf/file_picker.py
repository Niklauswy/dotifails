"""Run Wysun Files' selector in its own GUI process, alongside the reader."""
import json
from PySide6.QtCore import QEventLoop, QProcess, QProcessEnvironment, QUrl
from PySide6.QtWidgets import QMessageBox
from wysun_core import launch


def pick_file(parent, title, *, save=False, initial='', suffix='pdf'):
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
    process.errorOccurred.connect(loop.quit)
    process.start()
    if not process.waitForStarted(3000):
        QMessageBox.warning(parent, title, 'No se pudo abrir el selector de Wysun Files.')
        process.deleteLater()
        return ''
    process.write(json.dumps(dict(title=title, save=save, initial=initial, suffix=suffix)).encode() + b'\n')
    process.closeWriteChannel()
    enabled = parent.isEnabled() if parent else False
    if parent:
        parent.setEnabled(False)
    try:
        if process.state() != QProcess.NotRunning:
            loop.exec()
        raw = bytes(process.readAllStandardOutput())
        if process.exitCode() != 0 or len(raw) > 65536:
            raise ValueError('El selector no pudo completar la operación.')
        result = json.loads(raw)
        uris = result.get('uris', []) if result.get('code') == 0 else []
        url = QUrl(uris[0]) if uris else QUrl()
        return url.toLocalFile() if url.isLocalFile() else ''
    except (ValueError, IndexError, TypeError):
        QMessageBox.warning(parent, title, 'No se pudo completar la selección en Wysun Files.')
        return ''
    finally:
        if parent:
            parent.setEnabled(enabled)
        process.deleteLater()

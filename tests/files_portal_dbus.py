"""Exercise the real public portal and FileManager1 on a private session bus, with the QML windows (F-68…F-71).

Run: dbus-run-session -- env QT_QPA_PLATFORM=offscreen python3 tests/files_portal_dbus.py
(it re-runs itself with the qml-runtime venv Python)."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'apps/python'))
sys.path.insert(0, str(root / 'tests'))
from qml import support  # noqa: E402

if not support.in_venv():
    python = support.venv_python()
    if python is None:
        print('SKIP no qml-runtime venv', flush=True)
        raise SystemExit(0)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(root / 'apps/python'), str(root / 'tests')]),
               WYSUN_QML_LIB=str(root / 'apps/qml'))
    raise SystemExit(subprocess.call([str(python), __file__], env=env))

from wysun_qml import bootstrap  # noqa: E402

bootstrap.preload_qt()
from dbus.mainloop.glib import DBusGMainLoop  # noqa: E402

DBusGMainLoop(set_as_default=True)
import dbus  # noqa: E402
import dbus.service  # noqa: E402
from gi.repository import GLib  # noqa: E402

h = support.Harness.get()                       # QGuiApplication + private theme home
from PySide6.QtCore import QCoreApplication, QEvent, QSettings  # noqa: E402
from wysun_files.quick.chooser import QmlChooserWindow  # noqa: E402
from wysun_files.quick.window import QmlFilesWindow  # noqa: E402
from wysun_files.service import MANAGER, Manager, Portal  # noqa: E402

tmp = tempfile.TemporaryDirectory(prefix='files-portal-', dir=Path.home() / '.cache/wysun-fase1/tmp')
base = Path(tmp.name)
(base / 'data/xdg-desktop-portal/portals').mkdir(parents=True)
(base / 'config/xdg-desktop-portal').mkdir(parents=True)
(base / 'data/xdg-desktop-portal/portals/wysun.portal').write_text(
    '[portal]\nDBusName=org.freedesktop.impl.portal.desktop.wysun\nInterfaces=org.freedesktop.impl.portal.FileChooser;\n')
(base / 'config/xdg-desktop-portal/portals.conf').write_text('[preferred]\ndefault=none\norg.freedesktop.impl.portal.FileChooser=wysun\n')
file = base / 'sample ñ.txt'
file.write_text('fixture')
settings = QSettings(str(base / 's.ini'), QSettings.IniFormat)
app = QCoreApplication.instance()


def chooser_window(mode, title, options):
    return QmlChooserWindow(mode, title, options, settings=settings, thumbnails=False)


def files_window(paths):
    return QmlFilesWindow(paths, settings=settings, thumbnails=False)


bus = dbus.SessionBus()
name = dbus.service.BusName('org.freedesktop.impl.portal.desktop.wysun', bus)
portal = Portal(bus, make_window=chooser_window)
manager_name = dbus.service.BusName(MANAGER, bus)
manager = Manager(bus, make_window=files_window)
env = dict(os.environ, XDG_DATA_HOME=str(base / 'data'), XDG_CONFIG_HOME=str(base / 'config'))
log = (base / 'portal.log').open('w')
frontend = subprocess.Popen(['/usr/libexec/xdg-desktop-portal', '--verbose'], env=env, stdout=log, stderr=log)
context = GLib.MainContext.default()


def wait(fn, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        for _ in range(32):
            if not context.pending():
                break
            context.iteration(False)
        time.sleep(.005)
        if fn():
            return
    raise AssertionError('Portal timeout: ' + (base / 'portal.log').read_text()[-2500:])


client = dbus.SessionBus(private=True)
try:
    wait(lambda: client.name_has_owner('org.freedesktop.portal.Desktop'))
    proxy = dbus.Interface(client.get_object('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop'),
                           'org.freedesktop.portal.FileChooser')
    responses, errors = [], []
    client.add_signal_receiver(lambda code, result: responses.append((int(code), result)), signal_name='Response',
                               dbus_interface='org.freedesktop.portal.Request')

    def request(method, options):
        responses.clear()
        errors.clear()
        handles = []
        getattr(proxy, method)('', 'Selector de prueba', dbus.Dictionary(options, signature='sv'),
                               reply_handler=lambda value: handles.append(value), error_handler=errors.append)
        wait(lambda: bool(portal.requests) or bool(errors))
        assert not errors, errors
        return next(iter(portal.requests.values()))[0]

    window = request('OpenFile', {'multiple': dbus.Boolean(True), 'current_folder': dbus.ByteArray(os.fsencode(base) + b'\0')})
    model = window.files.property('current').property('model')
    wait(lambda: model.rowOf(str(file)) >= 0)
    assert window.window.property('title') == 'Selector de prueba — Wysun Selector'
    model.selectPaths([str(file)])
    window.chooser.accept(str(base), [str(file)], '')
    wait(lambda: bool(responses))
    assert responses[0][0] == 0 and list(responses[0][1]['uris']) == [file.as_uri()], responses
    print('PASS real public OpenFile response and URI round trip', flush=True)

    window = request('SaveFile', {'current_folder': dbus.ByteArray(os.fsencode(base) + b'\0'), 'current_name': 'new.txt'})
    window.chooser.accept(str(base), [], 'new.txt')
    wait(lambda: bool(responses))
    assert responses[0][0] == 0 and not (base / 'new.txt').exists()
    print('PASS SaveFile response without modifying files', flush=True)

    window = request('OpenFile', {})
    public_handle = next(iter(portal.requests))
    client.get_object('org.freedesktop.portal.Desktop', public_handle).Close(
        dbus_interface='org.freedesktop.portal.Request', reply_handler=lambda: None, error_handler=errors.append)
    wait(lambda: not portal.requests)
    assert not errors, errors
    print('PASS cancellation propagates through public Request.Close', flush=True)

    backend = dbus.Interface(client.get_object('org.freedesktop.impl.portal.desktop.wysun', '/org/freedesktop/portal/desktop'),
                             'org.freedesktop.impl.portal.FileChooser')
    denied = []
    backend.OpenFile('/org/freedesktop/portal/desktop/request/x/y', 'app', '', 'Intruso', dbus.Dictionary({}, signature='sv'),
                     reply_handler=lambda *a: denied.append('replied'), error_handler=lambda e: denied.append(e.get_dbus_name()))
    wait(lambda: bool(denied))
    assert denied == ['org.freedesktop.DBus.Error.AccessDenied'] and not portal.requests, denied
    print('PASS an unauthorised caller is refused', flush=True)

    duplicate = []
    portal.requests['/dup'] = (None, None)
    portal.choose('open', '/dup', '', 't', {}, lambda *a: duplicate.append('reply'), lambda e: duplicate.append(type(e).__name__),
                  bus.get_name_owner('org.freedesktop.portal.Desktop'))
    portal.requests.pop('/dup')
    assert duplicate == ['ValueError'], duplicate
    print('PASS duplicate request handles are refused', flush=True)

    fm = dbus.Interface(client.get_object(MANAGER, '/org/freedesktop/FileManager1'), MANAGER)
    fm.ShowItems(dbus.Array([file.as_uri()], signature='s'), '', reply_handler=lambda: None, error_handler=errors.append)
    wait(lambda: manager.windows and manager.windows[-1].files.property('current').property('model').property('selectedPaths') == [str(file)])
    print('PASS FileManager1 ShowItems opens parent and selects file', flush=True)

    fm.ShowItemProperties(dbus.Array([file.as_uri()], signature='s'), '', reply_handler=lambda: None, error_handler=errors.append)
    wait(lambda: len(manager.windows) == 2 and bool(h.find_in(manager.windows[-1].window.contentItem(), 'propertiesDialog'))
         and h.find_in(manager.windows[-1].window.contentItem(), 'propertiesDialog').property('opened'))
    print('PASS FileManager1 ShowItemProperties shows the properties', flush=True)

    fm.ShowFolders(dbus.Array([base.as_uri()], signature='s'), '', reply_handler=lambda: None, error_handler=errors.append)
    wait(lambda: len(manager.windows) == 3 and manager.windows[-1].files.property('current').property('path') == str(base))
    print('PASS FileManager1 ShowFolders opens the folder', flush=True)
    assert not errors, errors
finally:
    for window, _request in list(portal.requests.values()):
        if window is not None:
            window.close()
    for window in list(manager.windows):
        manager._closed(window)
    frontend.terminate()
    frontend.wait(timeout=5)
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    portal.remove_from_connection()
    manager.remove_from_connection()
    bus.release_name(MANAGER)
    bus.release_name('org.freedesktop.impl.portal.desktop.wysun')
    log.close()
    tmp.cleanup()
    client.close()
print('PORTAL_INTEGRATION_OK', flush=True)

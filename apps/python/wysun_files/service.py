#!/usr/bin/env python3
"""D-Bus activation for Wysun FileManager1 and the file chooser portal (F-68…F-71), on the QML windows.

``org.freedesktop.impl.portal.FileChooser`` (version 4: OpenFile, SaveFile, SaveFiles) answers only the owner of
``org.freedesktop.portal.Desktop``, refuses duplicate handles and lets only the caller close its Request.
``org.freedesktop.FileManager1`` opens folders and selects items (after they are listed) or shows their properties;
if another file manager owns the name and does not let it go, only the chooser is offered. The GLib main loop that
dbus-python needs is driven from Qt's."""
import signal
import sys
from pathlib import Path

import dbus
import dbus.service

PORTAL = 'org.freedesktop.impl.portal.FileChooser'
REQUEST = 'org.freedesktop.impl.portal.Request'
MANAGER = 'org.freedesktop.FileManager1'


def local_path(value):
    from wysun_files.core.chooser import local_path as convert
    return convert(value)


class Request(dbus.service.Object):
    def __init__(self, service, path, window, sender):
        super().__init__(service.bus, path)
        self.window, self.sender = window, sender

    @dbus.service.method(REQUEST, in_signature='', out_signature='', sender_keyword='sender')
    def Close(self, sender=None):
        if sender == self.sender:
            self.window.close()               # replies «cancelled» once


def typed_results(result):
    out = dbus.Dictionary(signature='sv')
    if 'uris' in result:
        out['uris'] = dbus.Array(result['uris'], signature='s')
    if 'choices' in result:
        out['choices'] = dbus.Array([dbus.Struct(pair, signature='ss') for pair in result['choices']], signature='(ss)')
    if 'current_filter' in result:
        name, rules = result['current_filter']
        out['current_filter'] = dbus.Struct((str(name), dbus.Array(
            [dbus.Struct((dbus.UInt32(kind), str(pattern)), signature='us') for kind, pattern in rules], signature='(us)')),
            signature='sa(us)')
    return out


def _release(window):
    """Drop a closed QML window's engine on the next turn of the event loop."""
    window.engine.deleteLater()


class Portal(dbus.service.Object):
    def __init__(self, bus, make_window=None):
        super().__init__(bus, '/org/freedesktop/portal/desktop')
        self.bus = bus
        self.requests = {}
        self.make_window = make_window

    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='ss', out_signature='v')
    def Get(self, interface, name):
        if interface == PORTAL and name == 'version':
            return dbus.UInt32(4)
        raise dbus.exceptions.DBusException('Unknown property', name='org.freedesktop.DBus.Error.UnknownProperty')

    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        return {'version': dbus.UInt32(4)} if interface == PORTAL else {}

    def choose(self, mode, handle, parent, title, options, reply, error, sender):
        try:
            if sender != self.bus.get_name_owner('org.freedesktop.portal.Desktop'):
                raise dbus.exceptions.DBusException('Use the public file chooser portal.',
                                                    name='org.freedesktop.DBus.Error.AccessDenied')
            if str(handle) in self.requests:
                raise ValueError('Duplicate request handle')
            if self.make_window is None:
                from wysun_files.quick.chooser import QmlChooserWindow
                window = QmlChooserWindow(mode, str(title), dict(options))
            else:
                window = self.make_window(mode, str(title), dict(options))
            request = Request(self, str(handle), window, sender)
            self.requests[str(handle)] = (window, request)

            def complete(code, result):
                request.remove_from_connection()
                self.requests.pop(str(handle), None)
                reply(dbus.UInt32(code), typed_results(result))
                _release(window)

            window.chooser.completed.connect(complete)
            window.present()
        except Exception as exc:
            error(exc)

    @dbus.service.method(PORTAL, in_signature='osssa{sv}', out_signature='ua{sv}', async_callbacks=('reply', 'error'),
                         sender_keyword='sender')
    def OpenFile(self, handle, app_id, parent, title, options, reply, error, sender=None):
        self.choose('open', handle, parent, title, options, reply, error, sender)

    @dbus.service.method(PORTAL, in_signature='osssa{sv}', out_signature='ua{sv}', async_callbacks=('reply', 'error'),
                         sender_keyword='sender')
    def SaveFile(self, handle, app_id, parent, title, options, reply, error, sender=None):
        self.choose('save', handle, parent, title, options, reply, error, sender)

    @dbus.service.method(PORTAL, in_signature='osssa{sv}', out_signature='ua{sv}', async_callbacks=('reply', 'error'),
                         sender_keyword='sender')
    def SaveFiles(self, handle, app_id, parent, title, options, reply, error, sender=None):
        self.choose('savefiles', handle, parent, title, options, reply, error, sender)


class Manager(dbus.service.Object):
    def __init__(self, bus, make_window=None):
        super().__init__(bus, '/org/freedesktop/FileManager1')
        self.windows = []
        self.make_window = make_window

    def show(self, uris, items=False, properties=False):
        groups = {}
        for uri in uris:
            try:
                path = local_path(uri)
                if not path.exists():
                    continue
                folder = path.parent if items or path.is_file() else path
                groups.setdefault(str(folder), []).append(str(path))
            except (ValueError, OSError):
                continue
        if not groups:
            groups = {str(Path.home()): []}
        for folder, paths in groups.items():
            if self.make_window is None:
                from wysun_files.quick.window import QmlFilesWindow
                window = QmlFilesWindow([folder])
            else:
                window = self.make_window([folder])
            self.windows.append(window)
            tab = window.files.property('current')
            selected = [p for p in paths if p != folder]
            if selected:
                tab.select_when_loaded(selected)
            if properties and selected:
                window.window.setProperty('pendingProperties', selected[0])     # Main.qml opens it once listed
            window.window.closing.connect(lambda _event, w=window: self._closed(w))
            window.present()

    def _closed(self, window):
        if window in self.windows:
            self.windows.remove(window)
            window.close()
            _release(window)

    @dbus.service.method(MANAGER, in_signature='ass', out_signature='')
    def ShowItems(self, uris, startup_id):
        self.show(uris, items=True)

    @dbus.service.method(MANAGER, in_signature='ass', out_signature='')
    def ShowFolders(self, uris, startup_id):
        self.show(uris)

    @dbus.service.method(MANAGER, in_signature='ass', out_signature='')
    def ShowItemProperties(self, uris, startup_id):
        self.show(uris, items=True, properties=True)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    from wysun_qml import bootstrap
    bootstrap.ensure_runtime_python('wysun_files.service', argv[1:])
    bootstrap.require_qt()
    bootstrap.configure_qt()
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    app = QGuiApplication.instance() or QGuiApplication([argv[0], '-name', 'wysun-files'])
    app.setApplicationName('Wysun Files')
    app.setOrganizationName('Wysun')
    app.setDesktopFileName('wysun-files')
    app.setQuitOnLastWindowClosed(False)
    try:
        portal_name = dbus.service.BusName('org.freedesktop.impl.portal.desktop.wysun', bus, do_not_queue=True)  # noqa: F841
    except dbus.NameExistsException:
        return 0
    portal = Portal(bus)
    manager = None
    try:
        manager_name = dbus.service.BusName(MANAGER, bus, allow_replacement=True, replace_existing=True,  # noqa: F841
                                            do_not_queue=True)
        manager = Manager(bus)
    except dbus.NameExistsException:
        print('FileManager1 already owned; Wysun chooser is available.', flush=True)
    context = GLib.MainContext.default()
    timer = QTimer(interval=8)

    def dispatch():
        for _ in range(32):
            if not context.pending():
                break
            context.iteration(False)

    timer.timeout.connect(dispatch)
    timer.start()

    def stop(*_):
        # Open choosers reply «cancelled» and windows close before quitting (F-71).
        for window, _request in list(portal.requests.values()):
            window.close()
        if manager:
            for window in list(manager.windows):
                manager._closed(window)
        QTimer.singleShot(100, app.quit)

    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: QTimer.singleShot(0, stop))
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())

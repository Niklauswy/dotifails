#!/usr/bin/env python3
"""Ask where to save a screenshot through the XDG FileChooser portal (Wysun Files).

usage: save_as.py <image.png> <suggested folder> <suggested name>
Prints the saved path, or nothing when the dialog is cancelled. The scratch
image is copied, never moved, so a failed save keeps it.
"""
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import gi

gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib  # noqa: E402

PORTAL = 'org.freedesktop.portal.Desktop'
PATH = '/org/freedesktop/portal/desktop'


def ask(folder, name):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    token = 'wysun_screenshot_' + secrets.token_hex(6)
    sender = bus.get_unique_name()[1:].replace('.', '_')
    request = f'{PATH}/request/{sender}/{token}'
    loop = GLib.MainLoop()
    chosen = []

    def response(_bus, _sender, _path, _iface, _signal, params):
        code, results = params.unpack()
        if code == 0 and results.get('uris'):
            chosen.append(results['uris'][0])
        loop.quit()

    bus.signal_subscribe(PORTAL, 'org.freedesktop.portal.Request', 'Response', request, None,
                         Gio.DBusSignalFlags.NO_MATCH_RULE, response)
    options = {
        'handle_token': GLib.Variant('s', token),
        'current_name': GLib.Variant('s', name),
        'current_folder': GLib.Variant('ay', os.fsencode(folder) + b'\0'),
        'filters': GLib.Variant('a(sa(us))', [('PNG', [(0, '*.png')])]),
    }
    bus.call_sync(PORTAL, PATH, 'org.freedesktop.portal.FileChooser', 'SaveFile',
                  GLib.Variant('(ssa{sv})', ('', 'Save screenshot', options)), None,
                  Gio.DBusCallFlags.NONE, -1, None)
    loop.run()
    return Path(unquote(urlparse(chosen[0]).path)) if chosen else None


def main(argv):
    if len(argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    image, folder, name = Path(argv[1]), argv[2], argv[3]
    Path(folder).mkdir(parents=True, exist_ok=True)
    target = ask(folder, name)
    if not target:
        return 0
    if target.suffix.lower() != '.png':
        target = target.with_suffix(target.suffix + '.png') if target.suffix else target.with_suffix('.png')
    shutil.copyfile(image, target)
    subprocess.run(['notify-send', '-a', 'Wysun', '-i', str(target), 'Screenshot saved',
                    str(target).replace(str(Path.home()), '~', 1)], check=False)
    print(target)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))

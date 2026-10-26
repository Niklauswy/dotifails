"""MPRIS2 for one MediaPlayer, so media keys, playerctl and the shell widget can see and drive it.

dbus-python dispatches through the GLib main context that Qt's event loop already runs, so no thread or
timer is needed. Each service owns a private connection: one process can publish several players, each
under its own ``org.mpris.MediaPlayer2.wysun_player.instance<pid>_<n>`` name. Metadata carries one
vendor key, ``wysun:visibleVideo``, which the shell reads to keep the screen awake.
"""
import itertools
import os
import sys

from PySide6.QtCore import QTimer, QUrl

ROOT = 'org.mpris.MediaPlayer2'
PLAYER = ROOT + '.Player'
PROPERTIES = 'org.freedesktop.DBus.Properties'
INTROSPECTABLE = 'org.freedesktop.DBus.Introspectable'
OBJECT_PATH = '/org/mpris/MediaPlayer2'
TRACK = '/org/wysun/player/track/'
NO_TRACK = '/org/mpris/MediaPlayer2/TrackList/NoTrack'
VISIBLE_VIDEO = 'wysun:visibleVideo'
LOOP = {'None': False, 'Track': True, 'Playlist': True}
_numbers = itertools.count(1)
_classes = {}

INTROSPECTION = '''<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
 <interface name="org.freedesktop.DBus.Introspectable"><method name="Introspect"><arg direction="out" type="s"/></method></interface>
 <interface name="org.freedesktop.DBus.Properties">
  <method name="Get"><arg direction="in" type="s"/><arg direction="in" type="s"/><arg direction="out" type="v"/></method>
  <method name="GetAll"><arg direction="in" type="s"/><arg direction="out" type="a{sv}"/></method>
  <method name="Set"><arg direction="in" type="s"/><arg direction="in" type="s"/><arg direction="in" type="v"/></method>
  <signal name="PropertiesChanged"><arg type="s"/><arg type="a{sv}"/><arg type="as"/></signal>
 </interface>
 <interface name="org.mpris.MediaPlayer2">
  <method name="Raise"/><method name="Quit"/>
  <property name="CanQuit" type="b" access="read"/><property name="CanRaise" type="b" access="read"/>
  <property name="HasTrackList" type="b" access="read"/><property name="Identity" type="s" access="read"/>
  <property name="DesktopEntry" type="s" access="read"/><property name="SupportedUriSchemes" type="as" access="read"/>
  <property name="SupportedMimeTypes" type="as" access="read"/>
 </interface>
 <interface name="org.mpris.MediaPlayer2.Player">
  <method name="Next"/><method name="Previous"/><method name="Pause"/><method name="PlayPause"/><method name="Stop"/><method name="Play"/>
  <method name="Seek"><arg direction="in" type="x"/></method>
  <method name="SetPosition"><arg direction="in" type="o"/><arg direction="in" type="x"/></method>
  <method name="OpenUri"><arg direction="in" type="s"/></method>
  <signal name="Seeked"><arg type="x"/></signal>
  <property name="PlaybackStatus" type="s" access="read"/><property name="LoopStatus" type="s" access="readwrite"/>
  <property name="Rate" type="d" access="readwrite"/><property name="Shuffle" type="b" access="readwrite"/>
  <property name="Metadata" type="a{sv}" access="read"/><property name="Volume" type="d" access="readwrite"/>
  <property name="Position" type="x" access="read"/><property name="MinimumRate" type="d" access="read"/>
  <property name="MaximumRate" type="d" access="read"/><property name="CanGoNext" type="b" access="read"/>
  <property name="CanGoPrevious" type="b" access="read"/><property name="CanPlay" type="b" access="read"/>
  <property name="CanPause" type="b" access="read"/><property name="CanSeek" type="b" access="read"/>
  <property name="CanControl" type="b" access="read"/>
 </interface>
</node>'''

MIME = ['video/mp4', 'video/x-matroska', 'video/webm', 'video/quicktime', 'audio/mpeg', 'audio/flac', 'audio/ogg',
        'audio/mp4', 'audio/x-wav', 'audio/aac']


def _dbus():
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    return dbus, DBusGMainLoop


def track_id(player):
    """A new id for every file opened (the session's generation), so clients notice the change of track."""
    return f'{TRACK}{player.session.generation}'


def visible_video(player):
    """A video is on screen and playing: the one condition under which the display must stay on."""
    window = player.window()
    return (player.kind == 'video' and player.session.state == 'playing' and player.isVisible()
            and window is not None and not window.isMinimized())


def metadata_values(player):
    """The track description as plain Python values (converted to D-Bus types by the service)."""
    source, session = player.source, player.session
    if source is None:
        return {}
    tags = {str(key).lower(): value for key, value in (session.props.get('metadata') or {}).items()}
    values = {'xesam:title': tags.get('title') or source.name, 'xesam:url': QUrl.fromLocalFile(str(source.path)).toString(),
              VISIBLE_VIDEO: visible_video(player)}
    if session.duration:
        values['mpris:length'] = int(session.duration * 1_000_000)
    if tags.get('artist'):
        values['xesam:artist'] = [str(tags['artist'])]
    if tags.get('album'):
        values['xesam:album'] = str(tags['album'])
    return values


def _service_class(dbus):
    if dbus in _classes:
        return _classes[dbus]
    service = dbus.service

    class MprisService(service.Object):
        def __init__(self, bus, player, identity, desktop_entry):
            super().__init__(bus, OBJECT_PATH)
            self.player, self.identity, self.desktop_entry = player, identity, desktop_entry
            self._last = self.player_properties()
            self._seeking = False

        # ------------------------------------------------------------ properties
        def metadata(self):
            values = metadata_values(self.player)
            if not values:
                return dbus.Dictionary({'mpris:trackid': dbus.ObjectPath(NO_TRACK)}, signature='sv')
            out = {'mpris:trackid': dbus.ObjectPath(track_id(self.player))}
            for key, value in values.items():
                if key == 'mpris:length':
                    out[key] = dbus.Int64(value)
                elif key == VISIBLE_VIDEO:
                    out[key] = dbus.Boolean(value)
                elif isinstance(value, list):
                    out[key] = dbus.Array(value, signature='s')
                else:
                    out[key] = dbus.String(value)
            return dbus.Dictionary(out, signature='sv')

        def root_properties(self):
            return {'CanQuit': dbus.Boolean(True), 'CanRaise': dbus.Boolean(True), 'HasTrackList': dbus.Boolean(False),
                    'Identity': dbus.String(self.identity), 'DesktopEntry': dbus.String(self.desktop_entry),
                    'SupportedUriSchemes': dbus.Array(['file'], signature='s'),
                    'SupportedMimeTypes': dbus.Array(MIME, signature='s')}

        def player_properties(self):
            player, session = self.player, self.player.session
            state = session.state
            return {
                'PlaybackStatus': dbus.String({'playing': 'Playing', 'paused': 'Paused'}.get(state, 'Stopped')),
                'LoopStatus': dbus.String('Track' if session.looping else 'None'),
                'Rate': dbus.Double(session.speed), 'MinimumRate': dbus.Double(.25), 'MaximumRate': dbus.Double(4.0),
                'Shuffle': dbus.Boolean(False), 'Metadata': self.metadata(),
                'Volume': dbus.Double(0.0 if session.muted else session.volume / 100),
                'Position': dbus.Int64(int(session.position * 1_000_000)),
                'CanGoNext': dbus.Boolean(player.collection.neighbour(1) is not None),
                'CanGoPrevious': dbus.Boolean(player.collection.neighbour(-1) is not None),
                'CanPlay': dbus.Boolean(player.source is not None), 'CanPause': dbus.Boolean(player.source is not None),
                'CanSeek': dbus.Boolean(session.seekable), 'CanControl': dbus.Boolean(True)}

        def sync(self):
            """Signal what changed since the last call (Position is read on demand, never signalled)."""
            current = self.player_properties()
            changed = {k: v for k, v in current.items() if k != 'Position' and self._last.get(k) != v}
            self._last = current
            if changed:
                self.PropertiesChanged(PLAYER, dbus.Dictionary(changed, signature='sv'), dbus.Array([], signature='s'))
            seeking = self.player.session.seeking
            if self._seeking and not seeking:
                self.Seeked(dbus.Int64(int(self.player.session.position * 1_000_000)))
            self._seeking = seeking

        # ------------------------------------------------------------ D-Bus interfaces
        @service.method(INTROSPECTABLE, out_signature='s')
        def Introspect(self):
            return INTROSPECTION

        @service.method(PROPERTIES, in_signature='ss', out_signature='v')
        def Get(self, interface, name):
            return self.GetAll(interface)[name]

        @service.method(PROPERTIES, in_signature='s', out_signature='a{sv}')
        def GetAll(self, interface):
            if interface == ROOT:
                return self.root_properties()
            if interface == PLAYER:
                return self.player_properties()
            raise dbus.exceptions.DBusException('Interfaz desconocida', name='org.freedesktop.DBus.Error.UnknownInterface')

        @service.method(PROPERTIES, in_signature='ssv')
        def Set(self, interface, name, value):
            if interface != PLAYER:
                return
            if name == 'Volume':
                self.player.set_volume(max(0.0, min(1.5, float(value))) * 100)
            elif name == 'Rate':
                self.player.session.set_speed(float(value))
            elif name == 'LoopStatus':
                self.player.session.set_loop(LOOP.get(str(value), False))

        @service.signal(PROPERTIES, signature='sa{sv}as')
        def PropertiesChanged(self, interface, changed, invalidated):
            pass

        @service.method(ROOT)
        def Raise(self):
            window = self.player.window()
            window.raise_()
            window.activateWindow()

        @service.method(ROOT)
        def Quit(self):
            # After the reply: closing the window closes this very connection.
            QTimer.singleShot(0, self.player.window().close if self.player.mode == 'full' else self.player.close_media)

        @service.method(PLAYER)
        def Play(self):
            self.player.session.set_paused(False)

        @service.method(PLAYER)
        def Pause(self):
            self.player.session.set_paused(True)

        @service.method(PLAYER)
        def PlayPause(self):
            self.player.toggle()

        @service.method(PLAYER)
        def Stop(self):
            self.player.session.set_paused(True)
            self.player.session.seek(0)

        @service.method(PLAYER)
        def Next(self):
            self.player.step_collection(1)

        @service.method(PLAYER)
        def Previous(self):
            self.player.step_collection(-1)

        @service.method(PLAYER, in_signature='x')
        def Seek(self, offset):
            self.player.session.seek_relative(offset / 1_000_000)

        @service.method(PLAYER, in_signature='ox')
        def SetPosition(self, track, position):
            if str(track) == track_id(self.player):
                self.player.session.seek(position / 1_000_000)

        @service.method(PLAYER, in_signature='s')
        def OpenUri(self, uri):
            from .errors import MediaError
            from .source import open_source
            try:
                open_source(str(uri))                        # file: URLs of regular media files only
            except MediaError:
                return
            self.player.open(str(uri))

        @service.signal(PLAYER, signature='x')
        def Seeked(self, position):
            pass

    _classes[dbus] = MprisService
    return MprisService


class Mpris:
    """The published service of one player; ``close()`` releases the name."""

    def __init__(self, player, identity='Wysun Player', desktop_entry='wysun-player'):
        self.service = self.bus = self._claim = None
        self.name = ''
        try:
            dbus, loop = _dbus()
            self.bus = dbus.SessionBus(mainloop=loop(set_as_default=True), private=True)
            self.bus.set_exit_on_disconnect(False)       # a vanished bus must never take the player down with it
            self._claim = dbus.service.BusName(f'{ROOT}.wysun_player.instance{os.getpid()}_{next(_numbers)}', self.bus, do_not_queue=True)
            self.name = str(self._claim.get_name())
            self.service = _service_class(dbus)(self.bus, player, identity, desktop_entry)
        except Exception as error:                            # no session bus, no dbus-python: the player works without it
            print('Wysun Player: MPRIS no disponible:', error, file=sys.stderr)
            self.close()

    @property
    def active(self):
        return self.service is not None

    def sync(self):
        if self.service is not None:
            self.service.sync()

    def close(self):
        service, bus, self.service, self.bus = self.service, self.bus, None, None
        if service is not None:
            service.remove_from_connection()
        self._claim = None                  # dbus-python releases the name when this object dies: do it before the connection closes
        if bus is not None:
            bus.close()

"""MPRIS2 on the session bus, so the shell media widget and media keys see us.

dbus-python dispatches through the GLib main context, which Qt's event loop
already runs, so no extra thread or timer is needed. Property changes are
diffed and only real changes are signalled.
"""
import re
import sys

ROOT = 'org.mpris.MediaPlayer2'
PLAYER = 'org.mpris.MediaPlayer2.Player'
PROPERTIES = 'org.freedesktop.DBus.Properties'
INTROSPECTABLE = 'org.freedesktop.DBus.Introspectable'
BUS_NAME = 'org.mpris.MediaPlayer2.wysun_music'
OBJECT_PATH = '/org/mpris/MediaPlayer2'
NO_TRACK = '/org/mpris/MediaPlayer2/TrackList/NoTrack'
LOOP = {'off': 'None', 'all': 'Playlist', 'one': 'Track'}

INTROSPECTION = '''<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
 <interface name="org.freedesktop.DBus.Introspectable">
  <method name="Introspect"><arg direction="out" type="s"/></method>
 </interface>
 <interface name="org.freedesktop.DBus.Properties">
  <method name="Get"><arg direction="in" type="s"/><arg direction="in" type="s"/><arg direction="out" type="v"/></method>
  <method name="GetAll"><arg direction="in" type="s"/><arg direction="out" type="a{sv}"/></method>
  <method name="Set"><arg direction="in" type="s"/><arg direction="in" type="s"/><arg direction="in" type="v"/></method>
  <signal name="PropertiesChanged"><arg type="s"/><arg type="a{sv}"/><arg type="as"/></signal>
 </interface>
 <interface name="org.mpris.MediaPlayer2">
  <method name="Raise"/><method name="Quit"/>
  <property name="CanQuit" type="b" access="read"/>
  <property name="CanRaise" type="b" access="read"/>
  <property name="HasTrackList" type="b" access="read"/>
  <property name="Identity" type="s" access="read"/>
  <property name="DesktopEntry" type="s" access="read"/>
  <property name="SupportedUriSchemes" type="as" access="read"/>
  <property name="SupportedMimeTypes" type="as" access="read"/>
 </interface>
 <interface name="org.mpris.MediaPlayer2.Player">
  <method name="Next"/><method name="Previous"/><method name="Pause"/>
  <method name="PlayPause"/><method name="Stop"/><method name="Play"/>
  <method name="Seek"><arg direction="in" type="x"/></method>
  <method name="SetPosition"><arg direction="in" type="o"/><arg direction="in" type="x"/></method>
  <method name="OpenUri"><arg direction="in" type="s"/></method>
  <signal name="Seeked"><arg type="x"/></signal>
  <property name="PlaybackStatus" type="s" access="read"/>
  <property name="LoopStatus" type="s" access="readwrite"/>
  <property name="Rate" type="d" access="readwrite"/>
  <property name="Shuffle" type="b" access="readwrite"/>
  <property name="Metadata" type="a{sv}" access="read"/>
  <property name="Volume" type="d" access="readwrite"/>
  <property name="Position" type="x" access="read"/>
  <property name="MinimumRate" type="d" access="read"/>
  <property name="MaximumRate" type="d" access="read"/>
  <property name="CanGoNext" type="b" access="read"/>
  <property name="CanGoPrevious" type="b" access="read"/>
  <property name="CanPlay" type="b" access="read"/>
  <property name="CanPause" type="b" access="read"/>
  <property name="CanSeek" type="b" access="read"/>
  <property name="CanControl" type="b" access="read"/>
 </interface>
</node>'''


def track_id(key):
    return '/org/wysun/music/track/' + (re.sub(r'[^A-Za-z0-9_]', '_', key) or 'unknown')


def start(player, covers, present, quit_app, instance=None):
    """Publish the player; returns the service, or None without a session bus.

    ``instance`` publishes ``…wysun_music.instance<N>`` (MPRIS convention), so
    tests never take the name of a real running player."""
    try:
        import dbus
        import dbus.service
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        name = dbus.service.BusName(BUS_NAME + (f'.instance{instance}' if instance else ''), bus, do_not_queue=True)
    except Exception as error:  # No bus (tests, TTY): the app still plays.
        print('Wysun Music: MPRIS no disponible:', error, file=sys.stderr)
        return None
    return _service_class(dbus)(bus, name, player, covers, present, quit_app)


def _service_class(dbus):
    service = dbus.service

    class MprisService(service.Object):
        def __init__(self, bus, name, player, covers, present, quit_app):
            super().__init__(bus, OBJECT_PATH)
            self._name = name  # Keep the bus name owned for the object's lifetime.
            self.player, self.covers = player, covers
            self.present, self.quit_app = present, quit_app
            self._last = {}
            player.track_changed.connect(lambda _: self.sync())
            player.state_changed.connect(self.sync)
            player.queue_changed.connect(self.sync)
            player.duration_changed.connect(lambda _: self.sync())
            player.seeked.connect(lambda seconds: self.Seeked(dbus.Int64(int(seconds * 1e6))))
            covers.updated.connect(lambda key: self.sync() if key == player.current else None)
            self._last = self._player_properties()

        # ------------------------------------------------------- properties
        def _metadata(self):
            key = self.player.current
            if not key:
                return dbus.Dictionary({'mpris:trackid': dbus.ObjectPath(NO_TRACK)}, signature='sv')
            library = self.player.library
            track = library.track(key)
            values = {
                'mpris:trackid': dbus.ObjectPath(track_id(key)),
                'mpris:length': dbus.Int64(int((self.player.duration or 0) * 1e6)),
                'xesam:title': dbus.String(track.get('title', '')),
                'xesam:artist': dbus.Array([track.get('artist', '')], signature='s'),
                'xesam:album': dbus.String(library.album(key)),
                'xesam:url': dbus.String('file://' + library.playable(key).get('path', '')),
            }
            cover = self.covers.path(key)
            if cover:
                values['mpris:artUrl'] = dbus.String('file://' + cover)
            return dbus.Dictionary(values, signature='sv')

        def _root_properties(self):
            return {
                'CanQuit': dbus.Boolean(True), 'CanRaise': dbus.Boolean(True),
                'HasTrackList': dbus.Boolean(False), 'Identity': dbus.String('Wysun Music'),
                'DesktopEntry': dbus.String('orbit-music'),
                'SupportedUriSchemes': dbus.Array(['file'], signature='s'),
                'SupportedMimeTypes': dbus.Array(['audio/mpeg', 'audio/ogg', 'audio/flac', 'audio/mp4',
                                                  'audio/opus', 'audio/x-wav', 'audio/aac'], signature='s'),
            }

        def _player_properties(self):
            player = self.player
            has_track = bool(player.current)
            return {
                'PlaybackStatus': dbus.String('Playing' if player.playing else 'Paused' if has_track else 'Stopped'),
                'LoopStatus': dbus.String(LOOP[player.repeat]),
                'Rate': dbus.Double(1.0), 'MinimumRate': dbus.Double(1.0), 'MaximumRate': dbus.Double(1.0),
                'Shuffle': dbus.Boolean(player.shuffle),
                'Metadata': self._metadata(),
                'Volume': dbus.Double(player.volume / 100),
                'Position': dbus.Int64(int(player.position * 1e6)),
                'CanGoNext': dbus.Boolean(player.can_next()),
                'CanGoPrevious': dbus.Boolean(player.can_previous()),
                'CanPlay': dbus.Boolean(has_track or bool(player.library.all_keys())),
                'CanPause': dbus.Boolean(has_track),
                'CanSeek': dbus.Boolean(has_track),
                'CanControl': dbus.Boolean(True),
            }

        def sync(self):
            current = self._player_properties()
            changed = {k: v for k, v in current.items() if k != 'Position' and self._last.get(k) != v}
            self._last = current
            if changed:
                self.PropertiesChanged(PLAYER, dbus.Dictionary(changed, signature='sv'), dbus.Array([], signature='s'))

        # ------------------------------------------------- D-Bus interfaces
        @service.method(INTROSPECTABLE, out_signature='s')
        def Introspect(self):
            return INTROSPECTION

        @service.method(PROPERTIES, in_signature='ss', out_signature='v')
        def Get(self, interface, name):
            return self.GetAll(interface)[name]

        @service.method(PROPERTIES, in_signature='s', out_signature='a{sv}')
        def GetAll(self, interface):
            if interface == ROOT:
                return self._root_properties()
            if interface == PLAYER:
                return self._player_properties()
            raise dbus.exceptions.DBusException('Unknown interface', name='org.freedesktop.DBus.Error.UnknownInterface')

        @service.method(PROPERTIES, in_signature='ssv')
        def Set(self, interface, name, value):
            if interface != PLAYER:
                return
            if name == 'Volume':
                self.player.set_volume(round(float(value) * 100))
            elif name == 'Shuffle':
                self.player.set_shuffle(bool(value))
            elif name == 'LoopStatus':
                self.player.set_repeat({v: k for k, v in LOOP.items()}.get(str(value), 'off'))

        @service.signal(PROPERTIES, signature='sa{sv}as')
        def PropertiesChanged(self, interface, changed, invalidated):
            pass

        @service.method(ROOT)
        def Raise(self):
            self.present()

        @service.method(ROOT)
        def Quit(self):
            self.quit_app()

        @service.method(PLAYER)
        def Next(self):
            self.player.next()

        @service.method(PLAYER)
        def Previous(self):
            self.player.previous()

        @service.method(PLAYER)
        def Pause(self):
            self.player.set_paused(True)

        @service.method(PLAYER)
        def PlayPause(self):
            self.player.toggle()

        @service.method(PLAYER)
        def Stop(self):
            self.player.set_paused(True)

        @service.method(PLAYER)
        def Play(self):
            self.player.set_paused(False)

        @service.method(PLAYER, in_signature='x')
        def Seek(self, offset):
            self.player.seek(self.player.position + offset / 1e6)

        @service.method(PLAYER, in_signature='ox')
        def SetPosition(self, track, position):
            if self.player.current and track == track_id(self.player.current):
                self.player.seek(position / 1e6)

        @service.method(PLAYER, in_signature='s')
        def OpenUri(self, uri):
            pass

        @service.signal(PLAYER, signature='x')
        def Seeked(self, position):
            pass

    return MprisService

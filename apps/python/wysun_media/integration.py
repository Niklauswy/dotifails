"""What a playing MediaPlayer does for the rest of the desktop: MPRIS, a screen-awake hint, and pausing Music.

``MediaPlayer.enable_integration()`` adds one of these; it listens to the player and never blocks it.
"""
from .mpris import Mpris

MUSIC = 'org.mpris.MediaPlayer2.wysun_music'
PLAYER = 'org.mpris.MediaPlayer2.Player'
PROPERTIES = 'org.freedesktop.DBus.Properties'
OBJECT_PATH = '/org/mpris/MediaPlayer2'
REPLY_TIMEOUT = 1.0            # seconds: Music answering slowly (or not at all) can never stall playback


_bus = None


def pause_music():
    """Pause Wysun Music if it is running and playing; never starts it, never waits for it."""
    global _bus
    try:
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        if _bus is None:
            _bus = dbus.SessionBus(mainloop=DBusGMainLoop(set_as_default=True), private=True)
            _bus.set_exit_on_disconnect(False)
        proxy = _bus.get_object(MUSIC, OBJECT_PATH, introspect=False)
        properties = dbus.Interface(proxy, PROPERTIES)
        player = dbus.Interface(proxy, PLAYER)
    except Exception:
        _bus = None                                    # no bus, or no Music: nothing to coordinate
        return False

    def answered(status):
        if str(status) == 'Playing':
            player.Pause(reply_handler=lambda: None, error_handler=lambda _: None, timeout=REPLY_TIMEOUT)

    properties.Get(PLAYER, 'PlaybackStatus', reply_handler=answered, error_handler=lambda _: None, timeout=REPLY_TIMEOUT)
    return True


class Integration:
    def __init__(self, identity='Wysun Player', desktop_entry='wysun-player', pause_music_callback=pause_music):
        self.identity, self.desktop_entry = identity, desktop_entry
        self.mpris = None
        self._audible = False
        self._pause_music = pause_music_callback

    def wanted(self, player):
        """Publish while a video or song is open and has been started (immediately, in a player window)."""
        if player.kind not in ('video', 'audio'):
            return False
        started = player.mode == 'full' or player.activated
        return started and player.session.state in ('loading', 'playing', 'paused', 'ended')

    def sync(self, player):
        if self.wanted(player):
            if self.mpris is None:
                self.mpris = Mpris(player, self.identity, self.desktop_entry)
            self.mpris.sync()
        elif self.mpris is not None:
            self.close_mpris()
        audible = player.session.audible
        if audible and not self._audible:
            self._pause_music()                          # sound begins: Wysun Music steps aside, once per start
        self._audible = audible

    def close_mpris(self):
        mpris, self.mpris = self.mpris, None
        if mpris is not None:
            mpris.close()

    def close(self):
        self.close_mpris()

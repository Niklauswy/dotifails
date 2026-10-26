"""Wysun Music: local library player.

Layers, from the bottom up (each one only imports the ones before it):

- ``engine``   mpv process and JSON IPC; knows nothing about tracks.
- ``queue``    playback order plus the user's "up next" list.
- ``library``  read-only view of the download manifest and user playlists.
- ``covers``   artwork cache, mosaics and dominant tones.
- ``player``   the single controller every surface talks to.
- ``mpris``    MPRIS2 adapter, so the shell media widget sees the player.
- ``ui``       Qt widgets; they observe ``player`` and never drive mpv directly.
"""

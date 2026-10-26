"""Wysun's media foundation: a reusable player widget for video, audio and images.

Build a :class:`Host` from the embedding app's theme (``install_host``), then::

    player = MediaPlayer(mode='embedded')       # or mode='full' for a window of its own
    player.open(path, paused=True)

Everything below is decoding-free until a file is opened: importing starts no thread and no decoder.
"""
from .errors import MediaError
from .host import Host, install as install_host
from .source import MediaSource, kind_of, open_source

__all__ = ['Host', 'MediaError', 'MediaPlayer', 'MediaSource', 'capabilities', 'install_host', 'kind_of', 'open_source']


def capabilities():
    """What this installation can do, for diagnostics and for choosing fallbacks."""
    from . import mpv, video
    try:
        api = mpv.library().mpv_client_api_version()
        libmpv = f'{api >> 16}.{api & 0xffff}'
    except RuntimeError:
        libmpv = None
    return {'libmpv': libmpv, 'opengl': video.gl_available(), 'renderer': 'opengl' if video.gl_available() else 'software'}


def __getattr__(name):
    if name == 'MediaPlayer':                       # imported on demand: it pulls in every widget
        from .player import MediaPlayer
        return MediaPlayer
    raise AttributeError(name)

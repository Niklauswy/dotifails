"""Wysun's media engine, without any interface: libmpv, the playback session, the collection of files, remembered
positions, covers and the desktop integration (MPRIS). Wysun Player draws it in QML.

    session = MediaSession(...); session.open(open_source(path))

Everything below is decoding-free until a file is opened: importing starts no thread and no decoder.
"""
from .errors import MediaError
from .source import MediaSource, kind_of, open_source

__all__ = ['MediaError', 'MediaSource', 'kind_of', 'open_source']

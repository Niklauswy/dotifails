"""Structured progress and cooperative cancellation at durable boundaries."""
import json
import os
from pathlib import Path

PREFIX = '@@DOTIFAILS@@'


class InstallationCancelled(RuntimeError):
    pass


def emit(event, **payload):
    if os.environ.get('DOTIFAILS_EVENTS') == '1':
        print(PREFIX + json.dumps(dict(event=event, **payload), ensure_ascii=False), flush=True)


def checkpoint():
    path = os.environ.get('DOTIFAILS_CANCEL_FILE')
    if path and Path(path).is_file():
        raise InstallationCancelled('Instalación detenida entre operaciones. Los cambios realizados tienen respaldo.')

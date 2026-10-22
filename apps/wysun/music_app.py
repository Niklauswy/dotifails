#!/usr/bin/env python3
"""Wysun Music launcher: a dedicated single-instance process (see wysun_music.app)."""
import sys

from wysun_music.app import main

if __name__ == '__main__':
    sys.exit(main())

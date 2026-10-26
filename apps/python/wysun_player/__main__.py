"""Wysun Player: `python3 -m wysun_player [--paused] [--fullscreen] [--start S] [--] ARCHIVO...`."""
import sys

from wysun_player.app import main

sys.exit(main())

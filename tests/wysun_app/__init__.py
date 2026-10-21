"""Tests of the Qt applications in apps/wysun; they import its modules by their flat names."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps/wysun'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

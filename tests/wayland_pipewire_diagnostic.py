#!/usr/bin/env python3
"""Observe only the consented stream in a guarded private synthetic portal run."""
import os
from pathlib import Path
import sys
from wayland_test_pointer import SyntheticPointer
ROOT=Path(os.environ['WYSUN_TEST_SOURCE'])
sys.path.insert(0,str(ROOT/'apps/quickshell/tests'))
from installed_apps_probe import private_environment
from wayland_portal_probe import main
if __name__=='__main__':
    env,_,_=private_environment();pointer=SyntheticPointer(env)
    try:pointer.keyboard();main(stream_diagnostic=True)
    finally:pointer.close()

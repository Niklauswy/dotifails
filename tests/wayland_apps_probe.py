#!/usr/bin/env python3
"""Run installed app tests with a persistent standard-keymap synthetic seat.

The underlying tests launch real installed apps. No device input is read.
"""
import os
from pathlib import Path
import sys
from wayland_test_pointer import SyntheticPointer
ROOT=Path(os.environ['WYSUN_TEST_SOURCE'])
sys.path.insert(0,str(ROOT/'apps/shell/tests'))
from installed_apps_probe import private_environment,main
if __name__=='__main__':
    env,_,_=private_environment();pointer=SyntheticPointer(env)
    try:pointer.keyboard();main()
    finally:pointer.close()

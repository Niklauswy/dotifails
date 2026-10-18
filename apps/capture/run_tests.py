#!/usr/bin/env python3
"""Run capture tests with disposable HOME/XDG roots, never user preferences."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    with tempfile.TemporaryDirectory(prefix='wysun-capture-tests-') as temporary:
        home = Path(temporary)
        env = dict(os.environ, HOME=str(home), QT_QPA_PLATFORM='offscreen')
        for variable, folder in (('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'),
                                 ('XDG_STATE_HOME', 'state'), ('XDG_CACHE_HOME', 'cache'),
                                 ('XDG_RUNTIME_DIR', 'run')):
            path = home / folder
            path.mkdir(mode=0o700)
            env[variable] = str(path)
        return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                               *(sys.argv[1:] or ['-v'])], cwd=Path(__file__).resolve().parent,
                              env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())

"""Helpers for the QML suites: locating the qml-runtime venv and running code in it.

The QML suites only run with the venv Python (the system PySide6 has no QtQuick). Run them through
``tests/test_qml_runtime.py`` or directly::

    <venv>/bin/python3 -m unittest discover -s tests/qml -t tests -p 'check_*.py'
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STAMP = 'WYSUN_QML_RUNTIME.json'


def candidate_prefixes():
    override = os.environ.get('WYSUN_QML_RUNTIME')
    if override:                      # an explicit override is authoritative (also to force the skip)
        return [Path(override)]
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return [Path.home() / '.cache/wysun-fase1/qml-runtime', data / 'wysun/qml-runtime']


def venv_python():
    """The venv's python3 when it exists and its stamp is complete; else None."""
    for prefix in candidate_prefixes():
        python = prefix / 'bin/python3'
        try:
            stamp = json.loads((prefix / STAMP).read_text())
        except (OSError, ValueError):
            continue
        if python.exists() and isinstance(stamp, dict) and stamp.get('pyside6'):
            return python
    return None


def in_venv():
    """True when this process already runs in a qml-runtime venv."""
    return (Path(sys.prefix) / STAMP).exists()


def run_in_venv(args, **env):
    python = venv_python()
    if python is None:
        raise RuntimeError('no qml-runtime venv')
    full = dict(os.environ, QT_QPA_PLATFORM='offscreen', WYSUN_REDUCED_MOTION='0',
                PYTHONPATH=os.pathsep.join([str(ROOT / 'apps/python'), str(ROOT / 'apps/python/vendor'), str(ROOT / 'tests')]),
                TMPDIR=str(Path.home() / '.cache/wysun-fase1/tmp'))
    full.update({k: str(v) for k, v in env.items()})
    Path(full['TMPDIR']).mkdir(parents=True, exist_ok=True)
    return subprocess.run([str(python), *args], cwd=ROOT, env=full, capture_output=True, text=True)

#!/usr/bin/env python3
"""Restore saved material settings from a legacy install, if unchanged."""
import hashlib
import json
import os
from pathlib import Path


def restore(state=None):
    state=Path(state) if state else Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'loomrec/materials-integration.json'
    if not state.exists():return {'restored':False,'reason':'No managed material settings'}
    if state.is_symlink():raise ValueError('Refusing symlinked material state')
    data=json.loads(state.read_text());config=Path(data['config']);prefs=Path(data['materials'])
    for path,expected in ((config,data['applied_sha256']),(prefs,data['applied_materials_sha256'])):
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Preserving modified material/compositor settings: '+str(path))
    # Import the same atomic-write helper used by the versioned application installer.
    import importlib.util
    spec=importlib.util.spec_from_file_location('loom_installer',Path(__file__).with_name('install-local.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.atomic_write(config,data['original_config'].encode())
    if data['original_materials'] is None:prefs.unlink()
    else:module.atomic_write(prefs,data['original_materials'].encode())
    state.unlink()
    return {'restored':True,'compositor_reloaded':False}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--state');args=parser.parse_args()
    print(json.dumps(restore(args.state),indent=2))

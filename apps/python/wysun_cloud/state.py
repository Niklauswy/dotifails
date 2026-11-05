"""The small runtime file the bar reads: which VMs are running right now."""
from wysun_core import paths
from wysun_core.jsonio import atomic_write_json


def write_state(instances, now):
    """Write ``state.json`` (private directory and file, atomically) and return its path."""
    directory = paths.private_dir(paths.runtime('wysun-cloud'))
    path = directory / 'state.json'
    payload = {
        'updated': float(now),
        'running': [{'project': inst.project, 'name': inst.name, 'zone': inst.zone}
                    for inst in instances if inst.running],
        'total': len(instances),
    }
    return atomic_write_json(path, payload, mode=0o600)

"""The last known projects and VMs (fast first paint) and the daily project discovery.

``last.json`` holds ``{'projects', 'instances', 'saved'}`` for the TUI's first frame;
``projects.json`` holds ``{'projects', 'updated'}`` and decides whether a full project
search is due. Both live in ``~/.cache/wysun/cloud`` and are written atomically.
"""
import time

from wysun_core import paths
from wysun_core.jsonio import atomic_write_json, read_json

PROJECTS_TTL = 24 * 3600


def _last_path():
    return paths.cache('wysun', 'cloud', 'last.json')


def _projects_path():
    return paths.cache('wysun', 'cloud', 'projects.json')


def load():
    """The cached ``last.json`` payload, or None when it is missing or malformed."""
    data = read_json(_last_path(), default=None)
    if not isinstance(data, dict) or not isinstance(data.get('projects'), list) \
            or not isinstance(data.get('instances'), list):
        return None
    return data


def save(projects, instances, now=None):
    """Remember the projects and VMs just read from gcloud."""
    payload = {
        'projects': [str(project) for project in projects],
        'instances': [instance.to_dict() for instance in instances],
        'saved': time.time() if now is None else float(now),
    }
    return atomic_write_json(_last_path(), payload)


def load_projects():
    """The project list kept by the last full search, or None when there is none."""
    data = read_json(_projects_path(), default=None)
    if not isinstance(data, dict) or not isinstance(data.get('projects'), list):
        return None
    return [str(project) for project in data['projects']]


def save_projects(projects, now=None):
    """Keep the projects that answered with at least one VM, with the time of the search."""
    payload = {
        'projects': [str(project) for project in projects],
        'updated': time.time() if now is None else float(now),
    }
    return atomic_write_json(_projects_path(), payload)


def projects_stale(now):
    """True when a full project search is due (older than 24 h, missing or malformed)."""
    data = read_json(_projects_path(), default=None)
    if not isinstance(data, dict) or not isinstance(data.get('projects'), list):
        return True
    updated = data.get('updated')
    if not isinstance(updated, (int, float)):
        return True
    return now - float(updated) > PROJECTS_TTL

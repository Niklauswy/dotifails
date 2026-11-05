"""One refresh of the user's projects and VMs, shared by `--estado` and the TUI.

A refresh never makes things look worse than the last good answer: a project whose
`instances list` fails keeps its previously cached VMs (and stays in the project list),
and a refresh in which nothing answered changes neither the caches nor the bar state.
"""
from wysun_core import paths
from wysun_core.jsonio import read_json
from wysun_cloud import cache, state
from wysun_cloud.model import Instance


def config():
    """`~/.config/wysun/cloud.json`: optional fixed `projects` list and `hidden` projects."""
    data = read_json(paths.config('wysun', 'cloud.json'), default={})
    return data if isinstance(data, dict) else {}


def _previous_instances(projects):
    """Cached VMs of `projects` from `last.json` (to stand in for projects that failed now)."""
    data = cache.load() or {}
    wanted = set(projects)
    found = []
    for item in data.get('instances') or []:
        if isinstance(item, dict) and item.get('project') in wanted:
            found.append(Instance.from_dict(item))
    return found


def refresh(gcloud, now, discover=False):
    """Read every VM; returns `(projects, instances, messages)` or raises `GcloudError`.

    `messages` maps a failing project to its Spanish one-line error. When at least one
    project answered, `last.json` and the bar's `state.json` are written; when none did,
    both stay as they were (the caller shows the messages over the cached data).
    """
    settings = config()
    hidden = {str(project) for project in settings.get('hidden') or []}
    fixed = settings.get('projects')
    if isinstance(fixed, list) and fixed:
        projects = [str(project) for project in fixed if str(project) not in hidden]
        instances, messages = gcloud.instances_all(projects)
    else:
        known = cache.load_projects()
        if discover or known is None or cache.projects_stale(now):
            candidates = [project for project in gcloud.projects() if project not in hidden]
            instances, messages = gcloud.instances_all(candidates)
            if not instances and messages:
                return known or [], [], messages          # nothing answered: keep every cache
            # Projects with VMs, plus known ones that failed now (a blip must not hide them for a day).
            projects = [project for project in candidates
                        if any(instance.project == project for instance in instances)
                        or (project in messages and project in (known or []))]
            cache.save_projects(projects, now)
        else:
            projects = [project for project in known if project not in hidden]
            instances, messages = gcloud.instances_all(projects)
    instances = [instance for instance in instances if instance.project not in hidden]
    if messages and not instances and len(messages) >= len(projects):
        return projects, [], messages
    if messages:
        instances = instances + _previous_instances([p for p in messages if p in projects])
    state.write_state(instances, now)
    cache.save(projects, instances, now)
    return projects, instances, messages

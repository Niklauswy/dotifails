"""`python3 -m wysun_cloud` (what `wysun cloud` runs)."""
import sys
import time

from wysun_core import paths
from wysun_core.jsonio import read_json
from wysun_cloud import cache, state
from wysun_cloud.gcloud import Gcloud, GcloudError


def _config():
    data = read_json(paths.config('wysun', 'cloud.json'), default={})
    return data if isinstance(data, dict) else {}


def estado():
    """One gcloud read for the bar: write the private state file, save the cache, stay silent.

    Any gcloud failure exits 0 and leaves the previous state file alone, so the bar keeps
    showing what it last knew instead of flashing an error.
    """
    now = time.time()
    config = _config()
    hidden = {str(project) for project in config.get('hidden') or []}
    try:
        gcloud = Gcloud()
        fixed = config.get('projects')
        if isinstance(fixed, list) and fixed:
            projects = [str(project) for project in fixed if str(project) not in hidden]
            instances, messages = gcloud.instances_all(projects)
        else:
            projects = cache.load_projects()
            if cache.projects_stale(now):
                projects = None
            if projects is None:
                candidates = [project for project in gcloud.projects() if project not in hidden]
                instances, messages = gcloud.instances_all(candidates)
                projects = [project for project in candidates
                            if any(instance.project == project for instance in instances)]
                cache.save_projects(projects, now)
            else:
                projects = [project for project in projects if project not in hidden]
                instances, messages = gcloud.instances_all(projects)
        instances = [instance for instance in instances if instance.project not in hidden]
        if not instances and messages:
            return 0
        state.write_state(instances, now)
        cache.save(projects, instances)
    except GcloudError:
        return 0
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if '--estado' in args:
        return estado()
    print('Wysun Cloud: interfaz pendiente')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

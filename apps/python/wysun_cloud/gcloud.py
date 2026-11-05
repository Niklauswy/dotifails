"""The gcloud commands Wysun Cloud runs, with JSON answers and short Spanish failures."""
import json
import shutil
import subprocess
from concurrent import futures

from wysun_cloud.model import Instance

DEFAULT_TIMEOUT = 30


def _last_line(text):
    lines = [line.strip() for line in (text or '').splitlines() if line.strip()]
    return (lines[-1] if lines else '')[:200]


class GcloudError(Exception):
    """A failed gcloud call; ``message`` is the one line the UI shows."""

    def __init__(self, message='gcloud falló'):
        self.message = message
        super().__init__(message)


class GcloudMissing(GcloudError):
    def __init__(self, message='gcloud no está instalado'):
        super().__init__(message)


class GcloudAuth(GcloudError):
    def __init__(self, message='gcloud no tiene sesión: ejecuta gcloud auth login'):
        super().__init__(message)


class Gcloud:
    """Thin wrapper over the user's gcloud; it never sees or stores credentials."""

    def __init__(self, executable='gcloud'):
        self.executable = executable

    def json(self, args, timeout=DEFAULT_TIMEOUT):
        """Run gcloud with ``args`` and return its parsed JSON (``[]`` for empty output)."""
        executable = shutil.which(self.executable)
        if executable is None:
            raise GcloudMissing()
        argv = [executable, *args, '--format=json', '--quiet']
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        except FileNotFoundError:
            raise GcloudMissing() from None
        except subprocess.TimeoutExpired:
            raise GcloudError('gcloud no respondió a tiempo') from None
        if result.returncode != 0:
            stderr = result.stderr or ''
            lowered = stderr.lower()
            if 'gcloud auth login' in lowered or 'reauthentication' in lowered or 'reauth' in lowered:
                raise GcloudAuth()
            line = _last_line(stderr)
            raise GcloudError(f'gcloud falló: {line}' if line else 'gcloud falló')
        text = (result.stdout or '').strip()
        if not text:
            return []
        try:
            return json.loads(text)
        except ValueError:
            raise GcloudError('gcloud devolvió una respuesta ilegible') from None

    def projects(self):
        """Every project id the active account can see."""
        data = self.json(['projects', 'list'])
        return [str(item['projectId']) for item in data if item.get('projectId')]

    def instances(self, project):
        """The VMs of one project."""
        data = self.json(['compute', 'instances', 'list', '--project', project])
        return [Instance.from_gcloud(project, item) for item in data]

    def instances_all(self, projects):
        """Every VM of ``projects`` in parallel; a broken project becomes a message, never an exception."""
        projects = list(projects)
        if not projects:
            return [], {}
        instances = []
        messages = {}
        with futures.ThreadPoolExecutor(max_workers=min(8, len(projects))) as pool:
            results = list(pool.map(self._project, projects))
        for project, found, error in results:
            if error is None:
                instances.extend(found)
            else:
                messages[project] = error
        return instances, messages

    def _project(self, project):
        try:
            return project, self.instances(project), None
        except GcloudError as error:
            return project, [], error

    def action_argv(self, verb, inst):
        """The argv for start/stop/reset, without the executable."""
        return ['compute', 'instances', verb, inst.name, '--zone', inst.zone, '--project', inst.project]

    def operations(self, inst, limit=10):
        """The most recent GCP operations that targeted this VM."""
        data = self.json(['compute', 'operations', 'list', '--project', inst.project,
                          f'--filter=targetLink~{inst.name}'])
        suffix = f'/zones/{inst.zone}/instances/{inst.name}'
        matching = [item for item in data if str(item.get('targetLink') or '').endswith(suffix)]
        return matching[:limit]

    def firewall(self, inst):
        """The rules that apply to this VM: same network and an empty or intersecting target tag list."""
        data = self.json(['compute', 'firewall-rules', 'list', '--project', inst.project])
        rules = []
        for rule in data:
            network = str(rule.get('network') or '').rstrip('/').rsplit('/', 1)[-1]
            if network and network != inst.network:
                continue
            target_tags = rule.get('targetTags') or []
            if target_tags and not set(target_tags) & set(inst.tags):
                continue
            rules.append(rule)
        return rules

    def disks(self, inst):
        """The persistent disks attached to this VM, with ``lastSnapshot`` when gcloud reported one."""
        data = self.json(['compute', 'disks', 'list', '--project', inst.project])
        disks = []
        for disk in data:
            zone = str(disk.get('zone') or '').rstrip('/').rsplit('/', 1)[-1]
            if zone and zone != inst.zone:
                continue
            users = disk.get('users') or []
            if users and not any(inst.name in str(user) for user in users):
                continue
            disks.append(disk)
        return disks

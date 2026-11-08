"""The VM data Wysun Cloud reads from gcloud, without anything from the UI."""
from dataclasses import dataclass
from datetime import datetime


def _basename(url):
    """The last path component of a gcloud resource URL (``''`` for missing values)."""
    if not isinstance(url, str) or not url:
        return ''
    return url.rstrip('/').rsplit('/', 1)[-1]


def _epoch(text):
    """An ISO timestamp as seconds since the epoch, or None when gcloud sent nothing useful."""
    if not isinstance(text, str) or not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


@dataclass
class Instance:
    """One Compute Engine VM, as ``gcloud compute instances list`` describes it."""
    project: str
    name: str
    zone: str
    status: str
    machine_type: str
    external_ip: str | None
    internal_ip: str | None
    spot: bool
    os: str
    disks: list[str]
    network: str
    tags: list[str]
    started: float | None

    @property
    def running(self):
        return self.status == 'RUNNING'

    @property
    def alias(self):
        return f'{self.name}.{self.zone}.{self.project}'

    def to_dict(self):
        return {
            'project': self.project,
            'name': self.name,
            'zone': self.zone,
            'status': self.status,
            'machine_type': self.machine_type,
            'external_ip': self.external_ip,
            'internal_ip': self.internal_ip,
            'spot': self.spot,
            'os': self.os,
            'disks': list(self.disks),
            'network': self.network,
            'tags': list(self.tags),
            'started': self.started,
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild an instance from ``to_dict()`` (the cache format); missing keys become empty values."""
        return cls(
            project=str(data.get('project') or ''),
            name=str(data.get('name') or ''),
            zone=str(data.get('zone') or ''),
            status=str(data.get('status') or ''),
            machine_type=str(data.get('machine_type') or ''),
            external_ip=data.get('external_ip') or None,
            internal_ip=data.get('internal_ip') or None,
            spot=bool(data.get('spot')),
            os=str(data.get('os') or ''),
            disks=[str(item) for item in data.get('disks') or []],
            network=str(data.get('network') or ''),
            tags=[str(item) for item in data.get('tags') or []],
            started=data.get('started'),
        )

    @classmethod
    def from_gcloud(cls, project, data):
        """One entry of ``gcloud compute instances list`` for ``project``."""
        interfaces = data.get('networkInterfaces') or [{}]
        interface = interfaces[0] or {}
        access = interface.get('accessConfigs') or [{}]
        disks = data.get('disks') or []
        boot = next((disk for disk in disks if disk.get('boot')), disks[0] if disks else {})
        licenses = boot.get('licenses') or []
        return cls(
            project=project,
            name=str(data.get('name') or ''),
            zone=_basename(data.get('zone')),
            status=str(data.get('status') or ''),
            machine_type=_basename(data.get('machineType')),
            external_ip=(access[0] or {}).get('natIP') or None,
            internal_ip=interface.get('networkIP') or None,
            spot=(data.get('scheduling') or {}).get('provisioningModel') == 'SPOT',
            os=_basename(licenses[0]) if licenses else '',
            disks=[_basename(disk.get('source')) or str(disk.get('deviceName') or '') for disk in disks],
            network=_basename(interface.get('network')),
            tags=[str(tag) for tag in (data.get('tags') or {}).get('items') or []],
            started=_epoch(data.get('lastStartTimestamp')),
        )


@dataclass
class Sample:
    """One second of a VM's live metrics, computed from two consecutive probe lines."""
    cpu: float                                   # 0..1, all cores
    cores: list[float]                           # 0..1 per core
    load: tuple[float, float, float]
    ram_used_gb: float
    ram_total_gb: float
    cache_gb: float
    swap_used_gb: float
    swap_total_gb: float
    rx_mbs: float
    tx_mbs: float
    read_mbs: float
    write_mbs: float
    mounts: list[tuple[str, float, float]]       # (mount, used_gb, size_gb)
    uptime_s: int
    top: list[tuple[int, float, float, str]]     # (pid, cpu %, ram_gb, command)
    autostop: object = None                      # autostop.Live, when the probe sent one


@dataclass
class TabData:
    """The answer of one on-demand tab command run over SSH."""
    kind: str                                    # 'ports' | 'journal' | 'docker' | 'failed' | 'du'
    lines: list[str]
    limited: bool = False                        # ran without sudo: some data needs permissions
    error: str | None = None

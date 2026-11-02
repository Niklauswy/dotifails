"""Where a LANShare can be reached: LAN addresses and, when the network allows it, NAME.local."""
import json
import os
import socket
import subprocess

# Interfaces that never lead to another device on the LAN (containers, VMs, bridges).
VIRTUAL = ('lo', 'docker', 'br-', 'veth', 'virbr', 'vmnet', 'vboxnet', 'podman', 'cni', 'flannel', 'lxc', 'lxd')


def _from_ip_command():
    try:
        out = subprocess.run(['ip', '-j', '-4', 'addr'], capture_output=True, timeout=3, check=False).stdout
        data = json.loads(out or b'[]')
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    found = []
    for link in data:
        name = link.get('ifname', '')
        if name.startswith(VIRTUAL) or link.get('operstate') == 'DOWN':
            continue
        for info in link.get('addr_info', []):
            ip = info.get('local')
            if info.get('family') == 'inet' and ip and not ip.startswith('127.'):
                found.append({'name': name, 'ip': ip})
    return found


def _from_route():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('10.255.255.255', 1))
            return [{'name': '', 'ip': probe.getsockname()[0]}]
    except OSError:
        return []


def addresses():
    """[{name, ip}] of every LAN interface; 127.0.0.1 when there is no network at all."""
    return _from_ip_command() or _from_route() or [{'name': 'lo', 'ip': '127.0.0.1'}]


def mdns_available():
    """Only avahi answers NAME.local here; without it the easy address is not shown."""
    return os.path.exists('/run/avahi-daemon/socket')


def easy_name(port):
    if not mdns_available():
        return None
    host = socket.gethostname().split('.')[0]
    return f'http://{host}.local:{port}' if host else None

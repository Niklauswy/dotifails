"""System-wide figures for Wysun Processes: CPU per core, memory, pressure (PSI), disk and network rates, GPU
utilisation and temperatures. Every reader tolerates a missing or unreadable file (containers, other kernels)."""
import os
from pathlib import Path
import shutil
import subprocess
import time


def _read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ''


def pressure(proc_root):
    result = {}
    for resource in ('cpu', 'memory', 'io'):
        value = None
        for line in _read(Path(proc_root) / 'pressure' / resource).splitlines():
            if line.startswith('some '):
                try:
                    value = float(dict(w.split('=', 1) for w in line.split()[1:])['avg10'])
                except (KeyError, ValueError):
                    pass
        result[resource] = value
    return result


class System:
    def __init__(self, proc_root='/proc', sys_root='/sys'):
        self.proc = Path(proc_root)
        self.sys = Path(sys_root)
        self.last_cpu = None
        self.last_io = None
        self.nvidia = shutil.which('nvidia-smi') if str(sys_root) == '/sys' else None
        self.hwmon = self._hwmon()

    def _hwmon(self):
        found = {}
        for folder in sorted((self.sys / 'class/hwmon').glob('hwmon*')):
            name = _read(folder / 'name').strip()
            kind = ('cpu' if name in ('k10temp', 'coretemp', 'zenpower', 'cpu_thermal') else
                    'gpu' if name in ('amdgpu', 'nouveau', 'nvidia', 'i915', 'xe') else
                    'disk' if name in ('nvme', 'drivetemp') else None)
            if kind and kind not in found and (folder / 'temp1_input').exists():
                found[kind] = folder / 'temp1_input'
        return found

    def cpu(self):
        lines = [line.split() for line in _read(self.proc / 'stat').splitlines() if line.startswith('cpu')]
        now = [(int(f[4]) + int(f[5]), sum(int(x) for x in f[1:9])) for f in lines if len(f) > 8]
        old, self.last_cpu = self.last_cpu, now
        if not now:
            return None, [0.0] * (os.cpu_count() or 1)
        if not old or len(old) != len(now):
            return None, [0.0] * (len(now) - 1)
        usage = []
        for (idle0, total0), (idle1, total1) in zip(old, now):
            span = total1 - total0
            usage.append(max(0.0, min(100.0, 100 * (1 - (idle1 - idle0) / span))) if span > 0 else 0.0)
        return usage[0], usage[1:]

    def memory(self):
        values = {}
        for line in _read(self.proc / 'meminfo').splitlines():
            name, _, rest = line.partition(':')
            try:
                values[name] = int(rest.split()[0]) * 1024
            except (IndexError, ValueError):
                pass
        total = values.get('MemTotal', 0)
        available = values.get('MemAvailable', values.get('MemFree', 0))
        return dict(total_memory=total, memory=max(0, total - available),
                    cached=values.get('Cached', 0) + values.get('Buffers', 0),
                    modified=values.get('Dirty', 0) + values.get('Writeback', 0),
                    swap=values.get('SwapTotal', 0) - values.get('SwapFree', 0), total_swap=values.get('SwapTotal', 0))

    def counters(self):
        read = write = rx = tx = 0
        devices = {p.name for p in (self.sys / 'block').glob('*') if not p.name.startswith(('loop', 'ram', 'dm-', 'zram'))}
        for line in _read(self.proc / 'diskstats').splitlines():
            f = line.split()
            if len(f) > 9 and f[2] in devices:
                read += int(f[5]) * 512
                write += int(f[9]) * 512
        for line in _read(self.proc / 'net/dev').splitlines()[2:]:
            name, _, values = line.partition(':')
            fields = values.split()
            if name.strip() != 'lo' and len(fields) > 8:
                rx += int(fields[0])
                tx += int(fields[8])
        return read, write, rx, tx

    def gpu(self):
        utilisation = memory = None
        for path in (self.sys / 'class/drm').glob('card[0-9]*/device/gpu_busy_percent'):
            try:
                utilisation = max(utilisation or 0.0, float(path.read_text()))
            except (OSError, ValueError):
                pass
        for path in (self.sys / 'class/drm').glob('card[0-9]*/device/mem_info_vram_used'):
            try:
                memory = (memory or 0) + int(path.read_text())
            except (OSError, ValueError):
                pass
        if utilisation is None and self.nvidia:
            try:
                reply = subprocess.run([self.nvidia, '--query-gpu=utilization.gpu,memory.used',
                                        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=0.8,
                                       check=True)
                values = [line.split(',') for line in reply.stdout.splitlines()]
                utilisation = max(float(v[0]) for v in values)
                memory = sum(float(v[1]) * 1048576 for v in values)
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        return utilisation, memory

    def temps(self):
        out = {}
        for kind, path in self.hwmon.items():
            try:
                out[kind] = int(_read(path).strip()) / 1000
            except ValueError:
                pass
        return out

    def read(self, rows, engines_gpu=None):
        now = time.monotonic()
        cpu, cores = self.cpu()
        result = dict(cpu=cpu, cores=cores, **self.memory())
        counters = self.counters()
        old, self.last_io = self.last_io, (now, counters)
        if old and now > old[0]:
            span = now - old[0]
            rates = [max(0, (b - a) / span) for a, b in zip(old[1], counters)]
        else:
            rates = [0, 0, 0, 0]
        result.update(disk_read=rates[0], disk_write=rates[1], net_rx=rates[2], net_tx=rates[3])
        result['gpu'], result['gpu_memory'] = self.gpu()
        if result['gpu'] is None and engines_gpu is not None:
            result['gpu'] = engines_gpu
        uptime = _read(self.proc / 'uptime').split()
        result.update(pressure=pressure(self.proc), load=os.getloadavg(), temps=self.temps(),
                      uptime=float(uptime[0]) if uptime else 0.0, count=len(rows),
                      running=sum(r['state'] == 'R' for r in rows), threads=sum(r['threads'] for r in rows))
        return result

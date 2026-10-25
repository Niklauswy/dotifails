#!/usr/bin/env python3
"""Read-only CPU/RSS/DRM sampling for Quickshell and Hyprland, excluding other apps.

Run outside a PID sandbox. CPU percentages are per logical CPU. DRM render
percentages are engine time, not whole-device utilization. Missing counters
remain null. Keep other workloads and monitor settings stable when comparing.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import time


def gpu(directory):
    clients = {}
    try:
        files = list((directory / 'fdinfo').iterdir())
    except OSError:
        return None
    for file in files:
        try:
            fields = dict(line.split(':', 1) for line in file.read_text().splitlines() if ':' in line)
            key = (fields.get('drm-pdev'), fields.get('drm-client-id'))
            if 'drm-engine-render' in fields and key[1] is not None:
                clients[key] = int(fields['drm-engine-render'].strip().split()[0])
        except (OSError, ValueError):
            continue
    return clients or None


def snapshot():
    result = {}
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():
            continue
        try:
            name = (directory / 'comm').read_text().strip()
            if name not in ('quickshell', 'Hyprland'):
                continue
            text = (directory / 'stat').read_text()
            fields = text[text.rfind(')') + 2:].split()
            result[directory.name] = dict(name=name, ticks=int(fields[11]) + int(fields[12]),
                rss_mb=int(fields[21]) * os.sysconf('SC_PAGE_SIZE') / 1048576,
                start=fields[19], gpu=gpu(directory))
        except (OSError, ValueError):
            continue
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--seconds', type=int, default=30)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error('--seconds must be positive')
    previous = snapshot()
    if not previous:
        parser.error('No desktop processes visible; run outside the PID sandbox.')
    started = last = time.monotonic()
    rows = []
    for _ in range(args.seconds):
        time.sleep(1)
        current = snapshot()
        now = time.monotonic()
        for pid, value in current.items():
            old = previous.get(pid)
            if not old or old['start'] != value['start']:
                continue
            row = dict(second=round(now-started, 3), pid=pid, name=value['name'],
                cpu=(value['ticks']-old['ticks']) / os.sysconf('SC_CLK_TCK') / (now-last) * 100,
                rss_mb=value['rss_mb'])
            if value['gpu'] is not None and old['gpu'] is not None and value['gpu'].keys() == old['gpu'].keys():
                delta = sum(value['gpu'][key]-old['gpu'][key] for key in value['gpu'])
                if delta >= 0:
                    row['gpu_render_pct'] = delta / ((now-last)*1e9)*100
            rows.append(row)
        previous, last = current, now
    summary = {}
    for name in ('quickshell', 'Hyprland'):
        samples = [row for row in rows if row['name'] == name]
        cpu = sorted(row['cpu'] for row in samples)
        render = [row['gpu_render_pct'] for row in samples if 'gpu_render_pct' in row]
        if not cpu:
            continue
        summary[name] = dict(samples=len(samples), pids=sorted({row['pid'] for row in samples}),
            cpu_mean=round(statistics.mean(cpu), 2), cpu_median=round(statistics.median(cpu), 2),
            cpu_p95=round(cpu[min(len(cpu)-1, int(len(cpu)*.95))], 2),
            rss_mean_mb=round(statistics.mean(row['rss_mb'] for row in samples), 1),
            gpu_render_mean_pct=round(statistics.mean(render), 3) if render else None)
    result = dict(label=args.label, seconds=time.monotonic()-started,
        cpu_units='percent of one logical CPU', summary=summary, samples=rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(label=args.label, summary=summary), indent=2))


if __name__ == '__main__':
    main()

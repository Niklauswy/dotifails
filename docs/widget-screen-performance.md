# Widget placement and performance

Settings → Displays → **Widgets on** selects **All displays** or **Primary display**.
Existing installations retain all displays until this preference is changed. The value is
`displays.widgetScreens` (`all` or `primary`) in the user's `orbit/environment.json`.

The primary output comes from the saved display profile, never from keyboard focus.
If that output disconnects, selection falls back to an available output. Reconnecting
the saved configuration restores its primary. Disabled shell outputs are excluded.

Primary-only mode creates the drawer surface (bar, dashboard, session, notifications,
OSD and other drawers) and its exclusion zones only on that output. Desktop clocks
and audio visualizers on secondary screens are unloaded, not merely made transparent.
Wallpapers remain on every enabled background output. Capture, recording overlays,
overview and the on-demand launcher retain their multi-monitor behavior. Drawer
shortcuts from another monitor route to the primary; the launcher follows focus.

`wysun-shell status` reports `primaryScreen`, `widgetMode`, `widgetScreens` and
`openByScreen`, allowing placement to be checked without opening private applications.

## Repeatable comparison

Use the installed display bridge to change the preference (or use Settings):

```sh
python3 ~/.local/share/wysun/quickshell/wysun/display_bridge.py displays.widgets '{"mode":"all"}'
python3 tests/benchmark_shell.py --label all-1 --seconds 30 --output /tmp/all-1.json
python3 ~/.local/share/wysun/quickshell/wysun/display_bridge.py displays.widgets '{"mode":"primary"}'
python3 tests/benchmark_shell.py --label primary-1 --seconds 30 --output /tmp/primary-1.json
```

Allow at least eight seconds after each switch before sampling. Repeat all/primary
twice, keep the same Quickshell process, and avoid tests, builds, screenshots and
opening panels during the samples. Record screen resolutions/rates and background
activity. The sampler is read-only, does not collect other applications' CPU, titles
or command lines, and must run where host processes are visible.

CPU is percent of one logical processor. RSS includes shared mappings and retained
Qt caches, so a live switch is not a measurement of clean-start memory savings.
DRM render percentages are per-client engine time, deduplicated by DRM client;
unavailable counters are null, never zero. This does not measure widget-level GPU
cost, frame latency or responsiveness. If several shell processes exist, inspect
the recorded PIDs and run the comparison with a single desktop shell.

When the browser remains in active use, its changing workload also affects Hyprland
and scheduling. Repeated differences are useful observations, not a controlled
causal measurement of compositor savings.

## Observed comparison — 2026-10-23

Three 1920×1080 outputs (60/144/60 Hz), with the saved 144 Hz output primary.
The browser remained in active use and was neither stopped nor included in the
process samples. Four 30-second rounds, eight seconds settling after each switch,
same Quickshell and Hyprland PIDs throughout. Builds and test suites had completed
before these rounds; no profiling overlay was enabled.

| Round | Quickshell CPU | Quickshell render engine | Hyprland CPU |
|---|---:|---:|---:|
| All displays 1 | 22.76% | 5.206% | 26.43% |
| Primary only 1 | 13.95% | 3.806% | 24.81% |
| All displays 2 | 20.94% | 5.058% | 25.54% |
| Primary only 2 | 10.94% | 1.114% | 21.66% |
| All displays mean | **21.85%** | **5.132%** | **25.99%** |
| Primary only mean | **12.44%** | **2.460%** | **23.24%** |

Observed reductions: about 43% in Quickshell CPU and 52% in its render-engine time.
Hyprland CPU was about 11% lower, but browser activity confounds that comparison.
Both pairs favored primary-only mode. These are live-use observations, not an idle
benchmark or proof of a particular widget's cost. Hyprland DRM counters were not
available. Mean RSS was 882.8 versus 875.2 MiB; changing cache residency between
rounds prevents claiming a meaningful memory saving.

Validation: selection/fallback tests, saved-primary versus focus, preservation of
preferences, drawer routing, installed deployment smoke and utility UI tests passed.
The installed Settings page was opened and visually checked; its new selector showed
Primary display, with the saved primary marked correctly. IPC and compositor layers
confirmed a single live drawer surface on the primary and backgrounds on all outputs.
Hyprland also listed one old drawer entry with PID -1, not a live Quickshell client.

The broad suite ran 483 tests: clipboard OCR (`clip_kind`) and offscreen glass-alpha
checks failed in untouched code; 13 socket failures were sandbox restrictions.
All 37 tools tests passed when rerun with host socket access. Recorder ran 178 tests
with one skip and two sandbox socket errors; both socket tests passed on the host.
These suite limitations do not constitute a fully green repository test run.

Local raw samples and logs are retained under
`~/.local/state/wysun/benchmarks/2026-10-23-widget-screens/`.

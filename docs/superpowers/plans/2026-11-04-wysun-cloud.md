# Wysun Cloud Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `wysun cloud`, a full-screen terminal UI to watch and start/stop/reset the user's Compute Engine VMs (project-column mosaic, 7-tab detail, animated transitions), a minimal bar indicator, and the reusable stdlib terminal engine `wysun_core.tui` it is built on.

**Architecture:** `wysun_core.tui` owns the terminal (raw mode, input, a cell canvas diffed to ANSI, layers with opacity, token-driven tweens, one `selectors` loop with timers and child processes). `wysun_cloud` owns Google Cloud: `gcloud` JSON calls, persistent SSH probe sessions per running VM (alias + fresh `HostName`, or IAP), Cloud Monitoring REST for CPU history, a cache for sub-second first paint, and the UI screens built on the engine. The shell reads a runtime state file written by `wysun cloud --estado` (polled every 2 min) and by the open TUI.

**Tech Stack:** Python 3.13 stdlib only (`termios`, `tty`, `selectors`, `subprocess`, `urllib.request`, `json`, `signal`, `pty` in tests); external programs `gcloud` and `ssh`; Quickshell QML + a pure JS logic file for the bar.

**Spec:** `docs/superpowers/specs/2026-11-04-wysun-cloud-design.md` (visual and motion reference: `docs/superpowers/specs/2026-11-04-wysun-cloud-prototipo.html`, open it in a browser — layout, copy and animations come from it).

## Global Constraints

- Standard library only. External programs: `gcloud`, `ssh` (and `node` only in shell-logic tests, skipped when missing).
- Package layout per `docs/utilities.md`: `apps/python/wysun_cloud/` with `__main__.py`; `'cloud': ('app', 'wysun_cloud', [])` in `MODULES` of `bin/wysun` plus one help line; add `wysun_cloud` to `PACKAGES` in `tests/test_python_layout.py`; a dispatcher test in `tests/shell_bridge/test_dispatcher.py`; a section in `docs/utilities.md`.
- The engine lives in `apps/python/wysun_core/tui/` and must not import anything from `wysun_cloud`.
- Data outside the repo: cache `paths.cache('wysun', 'cloud')`, optional config `paths.config('wysun', 'cloud.json')`, bar state `paths.runtime('wysun-cloud', 'state.json')` (private dir `0o700`, file `0o600`, atomic via `wysun_core.jsonio`).
- Colours only from theme roles (`wysun_core.theme`); no colour literals (`tests/test_theme_literals.py`). State colours: ok = `success`, warn = `tertiary`, error = `error`.
- Motion from `tokens.json` `anim.durations` / `anim.curves` (multi-segment curves: use the first cubic segment). `WYSUN_REDUCED_MOTION=1` makes every tween finish instantly.
- Live theme: the TUI repaints when `wysun_core.theme.revision()` changes (checked every 1.5 s).
- Credentials: the Monitoring token comes from `gcloud auth print-access-token` right before each request, goes only in the `Authorization` header over HTTPS to `monitoring.googleapis.com`, and is never written, cached, logged or included in any error text. Tests use synthetic tokens only; never run commands that print real tokens.
- Never edit `~/.ssh/config` and never run `gcloud compute config-ssh`.
- SSH: VM with external IP and an alias `NAME.ZONE.PROJECT` in `~/.ssh/config` → `ssh -o BatchMode=yes -o ConnectTimeout=5 -o HostName=<current external IP> ALIAS`; otherwise `gcloud compute ssh NAME --zone ZONE --project PROJECT --tunnel-through-iap -- …`.
- `sudo -n` only for tab commands (`ss -tlnp`, `journalctl`, `docker ps -a`, `du`), on opening that tab; on failure retry without sudo and mark missing data «necesita permisos». The 1 s probe never uses sudo.
- Refresh: projects full search at most daily (or key `p`); instance list every 30 s with the TUI open and right after each action; probes every 1 s; bar poll every 120 s.
- First paint under 1 s from `last.json` cache.
- Spanish UI copy, as in the prototype. Name «Wysun» only (`tests/test_legacy_names.py`).
- The agent never starts/stops/resets real VMs and never prints real tokens. Live checks are read-only (`instances list`, opening the TUI).
- Commit with pathspec (`git commit -m … -- <paths>`): the user keeps unrelated staged changes in the index.
- Run test suites one at a time (no parallel suites).

## Review Focus

1. **gcloud missing, not logged in, or a project erroring** → the TUI opens and shows a readable one-line Spanish message (e.g. «gcloud no tiene sesión: ejecuta gcloud auth login»), never a traceback; `--estado` exits 0 with an empty state. Test in Task 6 and Task 11.
2. **Terminal resized during an animation, or smaller than 80×24** → no crash; the frame relayouts at the new size, animations snap to their end; below 60×16 a centered «Agranda la terminal» message. Test in Task 5 and Task 9.
3. **SSH session dies mid-run** (VM stopped from the console, network drop) → the card shows «reconectando…» and the session retries with backoff (2, 5, 15, 30 s); no exception reaches the loop. Test in Task 7.
4. **Crash or Ctrl+C or SIGTERM inside the loop** → the terminal is restored (cooked mode, main screen, cursor and mouse off) before the traceback or exit. Test in Task 2/5.
5. **Long VM names / many VMs in one project** → names truncate with «…» inside the card title; a column with more cards than fit scrolls with the selection (the selected card always visible). Test in Task 9.

---

## File Structure

```
apps/python/wysun_core/tui/
  __init__.py      one line + re-exports of the public names below
  canvas.py        Style, Canvas (cells, clip, text, fill, blend toward a colour)
  screen.py        Screen: diff two canvases → ANSI bytes (truecolor / 256), synchronized update
  terminal.py      Terminal: raw mode, alt screen, mouse, size, restore (context manager)
  keys.py          Key, Mouse, Paste events; Parser.feed(bytes) -> list[event]
  theme.py         Palette (role -> rgb), load(home), reload-if-changed
  anim.py          bezier(points), Tween, Animator, lerp_rect, Rect, reduced motion
  draw.py          box, braille_graph, bar, tabs, spinner_frame, truncate
  app.py           App: selectors loop, timers, child processes, layers, frame scheduling, run()
  testing.py       VirtualTerminal (in-memory) for tests and for App(term=...)
apps/python/wysun_core/launch.py   + TERMINALS, terminal_argv(command: list[str]) -> list[str] | None
apps/python/wysun_cloud/
  __init__.py, __main__.py   CLI: `wysun cloud` (TUI) and `--estado`
  model.py         Instance, Sample, TabData dataclasses
  gcloud.py        Gcloud: projects, instances, actions, operations, firewall, disks
  cache.py         last.json / projects.json read-write
  probe.sh         POSIX metrics loop (one line per second)
  ssh.py           route(), ProbeSession (parse), tab commands with sudo -n fallback
  monitoring.py    cpu_history(instance, hours) via REST
  pricing.py       hourly(machine_type, zone) -> float | None
  state.py         write_state(instances) for the bar
  ui/mosaic.py     layout + card / off-line rendering, navigation
  ui/detail.py     header + 7 tab renderers
  ui/cloudapp.py   CloudApp(App): screens, transitions, modal, actions, toasts
apps/shell/services/CloudVms.qml, apps/shell/services/CloudVmsLogic.js
apps/shell/modules/bar/components/StatusIcons.qml  (+ one entry)
tests/tui/…, tests/cloud/…, tests/fixtures/cloud/…, tests/shell_bridge/test_cloud_logic.py
```

---

### Task 1: Canvas and screen diff

**Files:**
- Create: `apps/python/wysun_core/tui/__init__.py`, `canvas.py`, `screen.py`
- Test: `tests/tui/__init__.py`, `tests/tui/test_canvas_screen.py`

**Interfaces:**
- Produces:
  - `Style(fg: tuple[int,int,int] | None = None, bg: tuple | None = None, bold=False, dim=False, underline=False)` frozen dataclass.
  - `Canvas(width: int, height: int, bg: tuple)`; `.put(x, y, char, style)`, `.text(x, y, s, style, max_width=None) -> int` (columns written; clipped), `.fill(rect, char=' ', style=None)`, `.clip(rect)` context manager, `.blend(rect, toward: tuple, amount: float)` (mixes fg/bg of cells inside rect toward a colour, amount 0..1), `.paste(other: Canvas, x, y, opacity: float = 1.0)`, `.cell(x, y) -> (char, Style)`, `.row_text(y) -> str`.
  - `Screen(truecolor: bool = True)`; `.render(prev: Canvas | None, cur: Canvas) -> bytes` (only changed cells; full repaint when prev is None or sizes differ; wrapped in `\x1b[?2026h` … `\x1b[?2026l`).
  - Wide characters are out of scope: every char occupies one cell (braille, box drawing, block elements are single-width).

- [ ] **Step 1: Write failing tests** `test_text_clips_to_width`, `test_blend_half_mixes_colours` (fg (200,0,0) blended 0.5 toward (0,0,0) → (100,0,0)), `test_paste_with_opacity_blends_toward_bg`, `test_render_full_then_only_changed_cells` (second render after changing one cell contains exactly one cursor move `\x1b[{y+1};{x+1}H` and that char, and nothing for unchanged rows), `test_render_256_colour_fallback` (`Screen(truecolor=False)` emits `38;5;N`, never `38;2;`).
- [ ] **Step 2:** `python3 -m unittest tests.tui.test_canvas_screen -v` → FAIL (module missing).
- [ ] **Step 3: Implement** canvas as a flat list of `(char, Style)`; screen groups consecutive changed cells in a row into one cursor move and emits SGR only when the style changes. 256 fallback: nearest of the 6×6×6 cube + grey ramp.
- [ ] **Step 4:** same command → PASS.
- [ ] **Step 5: Commit** `feat(tui): cell canvas with blending and a diffing screen writer` (pathspec: the files above).

### Task 2: Terminal and input parser

**Files:**
- Create: `apps/python/wysun_core/tui/terminal.py`, `keys.py`, `testing.py`
- Test: `tests/tui/test_keys.py`, `tests/tui/test_terminal.py`

**Interfaces:**
- Produces:
  - `Key(name: str, char: str = '', alt=False, ctrl=False)`; names: `'up','down','left','right','enter','escape','tab','backtab','backspace','home','end','pageup','pagedown','delete','f1'…'f12'`, printable keys have `name='char'` and `char` set; Ctrl+C → `Key('c', ctrl=True)`.
  - `Mouse(kind: 'press'|'release'|'drag'|'wheelup'|'wheeldown', button: int, x: int, y: int)` (0-based cells), `Paste(text: str)`, `Resize(width, height)`.
  - `Parser().feed(data: bytes) -> list[Key|Mouse|Paste]`; a lone `\x1b` is returned as `Key('escape')` only by `Parser().flush()` (the app calls it when 30 ms pass with no more input).
  - `Terminal(fd_in=0, fd_out=1)`: context manager entering raw mode, alt screen `\x1b[?1049h`, hide cursor, SGR mouse `\x1b[?1000;1002;1006h`, bracketed paste `\x1b[?2004h`; `.size() -> (w, h)`; `.write(bytes)`; `.read(timeout) -> bytes`; restores everything on exit, on exception, and from `atexit`/SIGTERM.
  - `VirtualTerminal(width, height)` with the same methods plus `.feed_input(bytes)`, `.resize(w, h)`, `.canvas_text() -> list[str]` (last rendered frame decoded back to text).

- [ ] **Step 1: Write failing tests** `test_arrows_and_ctrl_c`, `test_alt_letter`, `test_sgr_mouse_press_and_wheel` (`b'\x1b[<0;10;5M'` → `Mouse('press',0,9,4)`), `test_bracketed_paste`, `test_split_escape_sequence_across_feeds`, `test_lone_escape_needs_flush`; in `test_terminal.py`: `test_restores_on_exception` using `pty.openpty()` — inside `with Terminal(slave, slave): raise RuntimeError` then assert `termios.tcgetattr(slave)` equals the original and the master side received `\x1b[?1049l` and `\x1b[?25h`.
- [ ] **Step 2:** `python3 -m unittest tests.tui.test_keys tests.tui.test_terminal -v` → FAIL.
- [ ] **Step 3: Implement** parser as a small state machine over a byte buffer (CSI, SS3, SGR mouse `<b;x;yM|m`, paste `200~`…`201~`, UTF-8 decoding of printable input).
- [ ] **Step 4:** same command → PASS.
- [ ] **Step 5: Commit** `feat(tui): raw terminal with guaranteed restore and an input parser`.

### Task 3: Theme palette and animation

**Files:**
- Create: `apps/python/wysun_core/tui/theme.py`, `anim.py`
- Test: `tests/tui/test_theme_anim.py`

**Interfaces:**
- Consumes: `wysun_core.theme.active_mode(home)`, `.read_scheme(home)`, `.data()`, `.revision(home)`.
- Produces:
  - `Palette.load(home=None) -> Palette`; `palette[role] -> (r,g,b)` for Material role names (`'primary','onPrimary','surface','onSurface','onSurfaceVariant','outline','outlineVariant','primaryContainer','surfaceContainerHigh','tertiary','error','success'`, …). Source: the scheme's `colours` when `read_scheme()` exists and its `mode == active_mode()`, else `data()['palettes'][mode]['scheme']`. `palette.revision` stores `theme.revision(home)`; `palette.changed(home=None) -> bool`.
  - `Rect(x, y, w, h)` namedtuple; `lerp_rect(a, b, t) -> Rect` (each field rounded to int).
  - `bezier(points: list[float]) -> Callable[[float], float]` using the first 4 numbers (x1,y1,x2,y2) of a token curve; solve x→t by Newton + bisection.
  - `curve(name) -> Callable` and `duration(name) -> float` (seconds) from `theme.data()['anim']`.
  - `Tween(duration: float, curve: Callable, on_step: Callable[[float], None], on_done=None)`; `Animator.add(tween)`, `.step(now) -> bool` (True while any running), `.finish_all()`; reduced motion (`WYSUN_REDUCED_MOTION=1`) → `add()` calls `on_step(1.0)` and `on_done` immediately.
  - `fade_steps(t) -> float` = round(t*8)/8.

- [ ] **Step 1: Write failing tests** `test_palette_uses_scheme_when_mode_matches` (temp HOME with a `scheme.json` in `<state>/wysun/scheme.json`, set `WYSUN_THEME` unset; assert primary equals the scheme's), `test_palette_falls_back_to_base_palette` (no scheme; `WYSUN_THEME=light` → light palette primary), `test_palette_changed_after_scheme_write`, `test_bezier_endpoints_and_monotonic` (standard curve: f(0)=0, f(1)=1, f(0.5) in (0.5,1)), `test_lerp_rect_rounds_to_cells`, `test_reduced_motion_finishes_instantly`, `test_animator_runs_until_duration`.
- [ ] **Step 2:** `python3 -m unittest tests.tui.test_theme_anim -v` → FAIL.
- [ ] **Step 3: Implement** as specified (hex → rgb tuples).
- [ ] **Step 4:** → PASS.
- [ ] **Step 5: Commit** `feat(tui): palette from the wallpaper scheme and token-driven tweens`.

### Task 4: Drawing pieces

**Files:**
- Create: `apps/python/wysun_core/tui/draw.py`
- Test: `tests/tui/test_draw.py`

**Interfaces:**
- Consumes: `Canvas`, `Style`, `Rect`.
- Produces:
  - `box(canvas, rect, style, title_segments: list[tuple[str, Style]] = (), selected_style=None)` — rounded `╭╮╰╯─│`; with `selected_style` heavy `┏┓┗┛━┃`; title drawn on the top border at x+2 with one space padding, truncated with «…».
  - `braille_graph(values: Sequence[float], width: int, rows: int) -> list[str]` — one value per column (0..1, newest last, left-padded with 0), levels `⠀⣀⣤⣶⣿` per row from the bottom, minimum one level on the bottom row (as the prototype's `graph()`).
  - `bar(fraction: float, width: int) -> tuple[str, str]` — filled `█` + one partial of `▏▎▍▌▋▊▉` (when remainder > 0.12) and the empty part `░`.
  - `tabs(canvas, x, y, labels: list[str], active: int, styles: dict, badges: dict[int, tuple[str, Style]] = {}) -> list[Rect]` (hit boxes for mouse).
  - `spinner_frame(n: int) -> str` over `◐◓◑◒`; `truncate(s, width) -> str` (adds «…»).
- [ ] **Step 1: Write failing tests** `test_braille_graph_levels` (`braille_graph([0,1], 2, 2)` == `['⠀⣿', '⣀⣿']`), `test_bar_partial_and_empty` (`bar(0.5, 4)` == `('██', '░░')`; `bar(0.55, 4)` == `('██▏', '░')`), `test_box_title_truncated`, `test_selected_box_uses_heavy_border`, `test_tabs_returns_hitboxes`.
- [ ] **Step 2–4:** run `python3 -m unittest tests.tui.test_draw -v` FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat(tui): boxes, braille graphs, bars and tabs`.

### Task 5: App loop

**Files:**
- Create: `apps/python/wysun_core/tui/app.py`
- Modify: `apps/python/wysun_core/tui/__init__.py` (export `App`, `Layer`)
- Test: `tests/tui/test_app.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - `Layer(rect: Rect, z: int = 0, opacity: float = 1.0, visible=True)` with `draw(canvas: Canvas, palette)` overridden by users; a layer draws into its own sub-canvas pasted at `rect` with `opacity`.
  - `App(term=None, home=None)`: `.layers: list[Layer]`, `.palette`, `.animator`, `.size`; overridables `on_key(event)`, `on_mouse(event)`, `on_resize(w, h)`, `draw(canvas)` (background before layers), `on_theme()`; scheduling `.after(seconds, fn) -> handle`, `.every(seconds, fn) -> handle`, `.cancel(handle)`; children `.spawn(argv, on_line: Callable[[str], None], on_exit: Callable[[int], None], stdin: bytes | None = None, env=None) -> Child` (non-blocking line reader via `selectors`; `Child.kill()`); `.invalidate()` (request a frame); `.quit()`; `.run() -> int`.
  - Frames: at most 60 fps while `animator` runs, otherwise only after `invalidate()`; input 30 ms escape flush; theme check every 1.5 s (`palette.changed()` → reload, `on_theme()`, full repaint).
  - Size below 60×16: draws only a centered «Agranda la terminal» (Review Focus 2).
  - Colour depth: `Screen(truecolor=os.environ.get("COLORTERM") in ("truecolor", "24bit"))`.
- [ ] **Step 1: Write failing tests** with `VirtualTerminal`: `test_key_reaches_on_key`, `test_after_and_every_fire_in_order`, `test_spawn_reads_lines_and_exit_code` (spawn `[sys.executable, '-c', 'print("a");print("b")']`), `test_resize_during_animation_snaps_and_redraws` (start a 1 s tween, resize, assert `animator.finish_all` happened and next frame has new size), `test_tiny_terminal_message`, `test_exception_in_handler_restores_terminal_and_reraises`, `test_theme_change_triggers_on_theme` (rewrite scheme.json under temp HOME).
- [ ] **Step 2:** `python3 -m unittest tests.tui.test_app -v` → FAIL.
- [ ] **Step 3: Implement** a single `selectors.DefaultSelector` loop: terminal input fd, child stdout fds, timeout = min(next timer, next frame, escape flush). `SIGWINCH` via `signal.set_wakeup_fd` on a self-pipe.
- [ ] **Step 4:** → PASS. Also run `python3 -m unittest discover -s tests/tui -t tests -v` → all PASS.
- [ ] **Step 5: Commit** `feat(tui): app loop with timers, child processes, layers and frame scheduling`.

### Task 6: gcloud data, cache and the CLI entry

**Files:**
- Create: `apps/python/wysun_cloud/__init__.py`, `__main__.py`, `model.py`, `gcloud.py`, `cache.py`, `state.py`, `pricing.py`
- Create fixtures: `tests/fixtures/cloud/gcloud` (fake executable, Python, answers from JSON files in the same folder keyed by argv), `projects.json`, `instances-mi-proyecto-prod.json`, `instances-personal-lab.json`, `instances-cliente-x.json`, `operations.json`, `firewall.json`, `disks.json`
- Modify: `bin/wysun` (MODULES + help line `  cloud                  VMs de Google Cloud en la terminal (--estado: para la barra)`), `tests/test_python_layout.py` (PACKAGES), `tests/shell_bridge/test_dispatcher.py`, `apps/python/wysun_core/launch.py` (move `TERMINALS`, add `terminal_argv`), `apps/python/wysun_files/quick/operations.py` (import `TERMINALS` from `wysun_core.launch`)
- Test: `tests/cloud/__init__.py`, `tests/cloud/test_gcloud.py`, `tests/cloud/test_state_pricing.py`

**Interfaces:**
- Produces:
  - `Instance(project: str, name: str, zone: str, status: str, machine_type: str, external_ip: str | None, internal_ip: str | None, spot: bool, os: str, disks: list[str], network: str, tags: list[str], started: float | None)`; `status` is gcloud's (`RUNNING`, `TERMINATED`, `STOPPING`, `PROVISIONING`, `STAGING`, `SUSPENDED`, `REPAIRING`); `.running` property = `status == 'RUNNING'`; `.alias` = `f'{name}.{zone}.{project}'`.
  - `class GcloudError(Exception)` with a short Spanish `.message`; `GcloudMissing(GcloudError)`, `GcloudAuth(GcloudError)` (detected from stderr containing `gcloud auth login` / `reauthentication`).
  - `Gcloud(executable='gcloud')`: `.json(args: list[str], timeout=30) -> object` (adds `--format=json --quiet`); `.projects() -> list[str]`; `.instances(project) -> list[Instance]`; `.instances_all(projects) -> tuple[list[Instance], dict[str, str]]` (parallel threads; errors per project as messages, never raising for one project); `.action_argv(verb: 'start'|'stop'|'reset', inst) -> list[str]` (`compute instances VERB NAME --zone Z --project P`); `.operations(inst, limit=10) -> list[dict]`; `.firewall(inst) -> list[dict]` (rules whose network matches and whose `targetTags` intersect the VM tags or are empty); `.disks(inst) -> list[dict]` (with `lastSnapshot` when present).
  - `cache.load() -> dict | None` (`{'projects': [...], 'instances': [Instance-dicts], 'saved': float}` from `paths.cache('wysun','cloud','last.json')`); `cache.save(projects, instances)`; `cache.projects_stale(now) -> bool` (projects list older than 24 h or missing).
  - `state.write_state(instances, now) -> Path` writes `{'updated': now, 'running': [{'project','name','zone'}...], 'total': N}` to `paths.runtime('wysun-cloud','state.json')`, private dir and 0o600 file.
  - `pricing.hourly(machine_type: str, zone: str) -> float | None` — table for `e2-micro, e2-small, e2-medium, e2-standard-2/4/8/16, n2-standard-2/4/8, n1-standard-1/2/4, g2-standard-4`; region multiplier: `us-*` 1.0, `europe-*` 1.1, `southamerica-*` 1.5, `asia-*` 1.15; unknown type → None. Values: approximate on-demand USD/h for us-central1 (builder fills from public list prices; precision is not required).
  - CLI: `python3 -m wysun_cloud` → TUI (Task 12; until then prints «Wysun Cloud: interfaz pendiente»); `python3 -m wysun_cloud --estado` → load cached project list (refresh if stale), list instances, `state.write_state`, `cache.save`, print nothing, exit 0 on any gcloud error (writes an empty `running` list only when gcloud answered; on error leaves the previous file).
  - `launch.TERMINALS` (moved tuple) and `launch.terminal_argv(command: list[str]) -> list[str] | None` (`ghostty` → `[ghostty, '--gtk-single-instance=false', '-e', *command]`, others `[term, '-e', *command]`; None when none found).
- [ ] **Step 1: Write failing tests** (fake `gcloud` first in `PATH`, temp HOME/XDG): `test_projects_and_instances_parse` (names, zones, external IP from `networkInterfaces[0].accessConfigs[0].natIP`, spot from `scheduling.provisioningModel == 'SPOT'`, machine type basename, os from the boot disk license basename or `''`), `test_one_project_failing_does_not_hide_others`, `test_missing_gcloud_raises_gcloud_missing` (empty PATH), `test_auth_error_is_gcloud_auth_with_spanish_message`, `test_estado_writes_private_state_file` (mode 0o600, dir 0o700, running names), `test_estado_exits_zero_without_gcloud`, `test_cache_roundtrip_and_projects_stale`, `test_pricing_known_and_unknown`, `test_dispatcher_runs_wysun_cloud` (in `test_dispatcher.py`: `self.invoke(('cloud', '--estado'))` → `assert_module('wysun_cloud', ['--estado'])`), `test_terminal_argv_ghostty`.
- [ ] **Step 2:** `python3 -m unittest tests.cloud.test_gcloud tests.cloud.test_state_pricing -v` and `python3 -m unittest discover -s tests/shell_bridge -t tests -p 'test_dispatcher.py'` → FAIL.
- [ ] **Step 3: Implement.** Projects: `gcloud projects list` then keep those whose `instances list` answered with ≥1 VM; saved in `projects.json` with timestamp; `~/.config/wysun/cloud.json` keys `"projects": [...]` (fixed list, skips discovery) and `"hidden": [...]` honoured when present.
- [ ] **Step 4:** both commands → PASS; `python3 -m unittest tests.test_python_layout -v` → PASS; run Files' check: `python3 -c "import sys;sys.path.insert(0,'tests');from qml import support;print(support.run_in_venv(['-m','unittest','qml.check_files_operations']).returncode)"` → `0`.
- [ ] **Step 5: Commit** `feat(cloud): gcloud data, cache, bar state and the wysun cloud entry`.

### Task 7: SSH probe sessions and tab commands

**Files:**
- Create: `apps/python/wysun_cloud/probe.sh`, `apps/python/wysun_cloud/ssh.py`
- Create fixtures: `tests/fixtures/cloud/probe-lines.txt` (recorded output), `tests/fixtures/cloud/ssh` (fake ssh: echoes its argv to a file and replays `probe-lines.txt` one line per 0.05 s, or exits 255 when `FAKE_SSH_FAIL=1`)
- Test: `tests/cloud/test_ssh.py`

**Interfaces:**
- Consumes: `Instance`, `App.spawn`, `App.after`.
- Produces:
  - `probe.sh`: POSIX `sh`, reads `INTERVAL` (default 1), loops forever printing one line per sample: `S <epoch> cpu=<user nice system idle iowait irq softirq steal> cores=<per-core totals as a,b;a,b;…> load=<1 5 15> mem=<MemTotal MemAvailable Cached SwapTotal SwapFree kB> net=<rx_bytes tx_bytes summed over non-lo> disk=<read_sectors write_sectors summed> df=<mount:used_kB:size_kB,…> up=<seconds> top=<pid:pcpu:rss_kB:comm|…>` (top 8 by CPU from `ps -eo pid,pcpu,rss,comm --sort=-pcpu`). Rates and percentages are computed on the client from consecutive samples.
  - `ssh_command(inst: Instance, remote: list[str], ssh_config: Path = ~/.ssh/config) -> list[str]` — alias route when `inst.external_ip` and the alias `Host` line exists in the config (simple `Host` token scan), else the IAP route (Global Constraints).
  - `Sample` (in `model.py`): `cpu: float` (0..1), `cores: list[float]`, `load: tuple[float,float,float]`, `ram_used_gb, ram_total_gb, cache_gb, swap_used_gb, swap_total_gb: float`, `rx_mbs, tx_mbs, read_mbs, write_mbs: float`, `mounts: list[tuple[str, float, float]]` (mount, used_gb, size_gb), `uptime_s: int`, `top: list[tuple[int, float, float, str]]` (pid, cpu%, ram_gb, command).
  - `ProbeParser().feed(line: str) -> Sample | None` (None for the first sample and malformed lines).
  - `ProbeSession(app, inst, on_sample: Callable[[Sample], None], on_state: Callable[[str, str], None])` — states `'conectando'`, `'activo'`, `'reconectando'`, `'sin-ssh'` with a Spanish reason (`'falta el alias: ejecuta gcloud compute config-ssh'` only when the alias route is unavailable and IAP also failed; `'llave rechazada'` on `Permission denied`; `'sin respuesta'` on timeout; IAP firewall message when stderr mentions `4033` or `failed to connect to backend`); `.start()`, `.stop()`; reconnect backoff 2, 5, 15, 30 s (Review Focus 3).
  - `run_tab_command(app, inst, kind: 'ports'|'journal'|'docker'|'failed'|'du', on_done: Callable[[TabData], None])` — tries `sudo -n <cmd>`, on non-zero with `sudo:` in stderr retries without sudo and sets `TabData.limited = True`. Commands: ports `ss -tlnp`; journal `journalctl -p warning --since -1h --no-pager -o short-iso`; docker `docker ps -a --format '{{json .}}'`; failed `systemctl --failed --no-legend --plain`; du `du -x -d2 -k / 2>/dev/null | sort -rn | head -12`.
  - `TabData(kind: str, lines: list[str], limited: bool, error: str | None)` (in `model.py`).
- [ ] **Step 1: Write failing tests** `test_probe_script_runs_locally_and_parses` (run `sh probe.sh` with `INTERVAL=0.2` locally for 2 lines via `subprocess`, feed both to `ProbeParser`, assert `0 <= cpu <= 1`, `ram_total_gb > 0`, at least one mount), `test_parser_rates_from_recorded_lines` (exact values from `probe-lines.txt`), `test_ssh_command_alias_with_fresh_hostname` (temp `~/.ssh/config` with `Host api-backend.us-central1-a.mi-proyecto-prod`; argv contains `-o HostName=34.122.10.7` and `-o BatchMode=yes`), `test_ssh_command_iap_without_external_ip`, `test_session_reconnects_after_drop` (fake ssh exits after 3 lines; with a VirtualTerminal app, assert states `conectando → activo → reconectando → activo`), `test_session_permission_denied_reason`, `test_tab_command_falls_back_without_sudo` (fake ssh returns `sudo: a password is required` for argv containing `sudo -n`).
- [ ] **Step 2:** `python3 -m unittest tests.cloud.test_ssh -v` → FAIL.
- [ ] **Step 3: Implement.** The probe runs as `ssh … sh -s` with `probe.sh` on stdin (`App.spawn(stdin=…)`), so nothing is installed on the VM.
- [ ] **Step 4:** → PASS.
- [ ] **Step 5: Commit** `feat(cloud): persistent SSH probes (alias or IAP) and tab commands with sudo -n fallback`.

### Task 8: Cloud Monitoring CPU history

**Files:**
- Create: `apps/python/wysun_cloud/monitoring.py`
- Test: `tests/cloud/test_monitoring.py`

**Interfaces:**
- Consumes: `Gcloud`, `Instance`.
- Produces: `cpu_history(gcloud: Gcloud, inst: Instance, hours: int) -> list[tuple[float, float]]` (epoch, 0..1), 5-min alignment (`ALIGN_MEAN`, `alignmentPeriod` `300s` for 24 h, `3600s` for 168 h); filter `metric.type="compute.googleapis.com/instance/cpu/utilization" AND metric.labels.instance_name="NAME"`; URL `https://monitoring.googleapis.com/v3/projects/P/timeSeries`; token via `gcloud.token()` (new `Gcloud.token() -> str` running `auth print-access-token`, stripped, never stored on the object); in-memory cache 5 min per (instance, hours) of the *results* only. Raises `GcloudError('Monitoring no respondió')`-style messages without the token or headers.
- [ ] **Step 1: Write failing tests** (patch `urllib.request.urlopen`, fake gcloud returning the synthetic token `ya29.SYNTHETIC-TEST-TOKEN`): `test_request_shape_and_parse`, `test_token_only_in_authorization_header` (inspect the `Request`: header `Authorization: Bearer ya29.SYNTHETIC-TEST-TOKEN`, scheme https, host monitoring.googleapis.com), `test_errors_never_contain_the_token` (urlopen raises HTTPError whose body echoes the token; the raised message and `logging` output (captured with `assertLogs` on root, or no logs) do not contain it), `test_token_never_written_to_disk` (walk temp HOME/XDG after the call: no file contains the token), `test_results_cached_not_token` (second call within 5 min does not run gcloud again).
- [ ] **Step 2–4:** `python3 -m unittest tests.cloud.test_monitoring -v` FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat(cloud): CPU history from Cloud Monitoring with a token that never leaves the request`.

### Task 9: Mosaic screen

**Files:**
- Create: `apps/python/wysun_cloud/ui/__init__.py`, `apps/python/wysun_cloud/ui/mosaic.py`
- Test: `tests/cloud/test_mosaic.py`

**Interfaces:**
- Consumes: `Canvas`, `draw.*`, `Rect`, `Instance`, `Sample`, `pricing.hourly`.
- Produces:
  - `VmView(inst: Instance, sample: Sample | None, cpu_hist: deque[float], state: str, reason: str, busy: str | None)` (`busy` ∈ `None,'encendiendo','apagando','reiniciando'`; the UI keeps one per VM).
  - `layout(views: list[VmView], projects: list[str], width: int, height: int) -> dict[str, Rect]` keyed by `inst.alias`: one column per project (column width = `(width-2 - gap*(n-1)) // n`, gap 2, min 34; with 1 project and >1 running VM the VMs spread over up to 3 columns; if columns don't fit, stack projects vertically); running cards height 8 starting at row 4, off VMs height 1 at the end of their column; project names at row 2.
  - `draw_card(canvas, rect, view, palette, selected: bool, spin: int)` — content exactly as the prototype card (2-row CPU braille + percent, RAM bar + `x,x/NG`, `/` bar + percent with `▲` over 85, `↓rx ↑tx MB/s · uptime`, `top <command> <cpu>%` + `· <failed service> ✗` when known); states without sample: `conectando…`, `reconectando…`, `sin SSH · <reason>`.
  - `draw_off(canvas, rect, view, palette, selected, spin)` — `○ name  zone  apagada` or spinner + `encendiendo…`.
  - `draw_header(canvas, width, views, palette, age_s: int, refreshing: bool)` / `draw_footer(canvas, width, height, hints: list[tuple[str,str]], palette)`.
  - `navigate(views, projects, selected_alias, key_name) -> str` (up/down within column, left/right to the same index in the neighbour column, clamped).
  - Number format Spanish (`11,2`), uptime `12 d` / `6 h` / `5 min`.
- [ ] **Step 1: Write failing tests** rendering into a 120×36 `Canvas` and reading `row_text`: `test_three_projects_three_columns` (project names on row 2 at their column x), `test_off_vms_are_one_line_at_the_end`, `test_one_project_spreads_cards`, `test_narrow_terminal_stacks_projects` (80 wide, 3 projects), `test_long_name_truncated_in_title` (Review Focus 5), `test_column_overflow_keeps_selected_visible` (12 running VMs in one project at height 36), `test_card_shows_sin_ssh_reason`, `test_navigate_between_columns`, `test_disk_over_85_shows_warning`.
- [ ] **Step 2–4:** `python3 -m unittest tests.cloud.test_mosaic -v` FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat(cloud): project-column mosaic with live cards`.

### Task 10: Detail screen

**Files:**
- Create: `apps/python/wysun_cloud/ui/detail.py`
- Test: `tests/cloud/test_detail.py`

**Interfaces:**
- Consumes: `VmView`, `TabData`, `cpu_history` results, `Gcloud.operations/firewall/disks` results, `draw.*`.
- Produces:
  - `TABS = ['Resumen','Procesos','Disco','Red','Servicios','Registro','Historial']`.
  - `DetailData` (dataclass on the UI side): `tabs: dict[str, TabData]`, `history: dict[int, list[tuple[float,float]]] | None` (keys 24, 168), `operations: list[dict]`, `firewall: list[dict]`, `disks: list[dict]`, `errors: dict[str,str]`.
  - `draw_detail_header(canvas, rect, view, palette, tab: int, badges)` (data line + tabs + rule; returns tab hit boxes).
  - `draw_tab(canvas, rect, tab: int, view, data: DetailData, palette, range_hours: int)` — content per the prototype: Resumen (6-row CPU 2 min graph, cores, RAM with cache/swap, mounts with read/write, net in/out 1-row graphs, top 5 processes, Salud block from `failed` + `docker` + journal count); Procesos (all `top` rows sorted by CPU, `m` sorts by RAM); Disco (mounts, `du` result after key `d`, GCP disks with last snapshot); Red (ports with `0.0.0.0` highlighted in warn, firewall rules with `0.0.0.0/0` outside 22/80/443 flagged `!`); Servicios (failed units first, containers); Registro (journal lines coloured by priority); Historial (graph of `history[range]`, time axis, operation markers, operations list, note «RAM y disco históricos aparecen aquí si la VM tiene Ops Agent.»).
  - A tab whose data is missing shows «cargando…»; `limited` shows «necesita permisos» on the affected block; an error shows its message.
- [ ] **Step 1: Write failing tests** `test_resumen_has_cpu_ram_disk_net_blocks`, `test_red_flags_open_firewall_rule` (fixture rule `allow-3000-dev` with `0.0.0.0/0` → line contains `!`), `test_limited_tab_says_necesita_permisos`, `test_historial_lists_operations_and_toggles_range`, `test_missing_data_says_cargando`.
- [ ] **Step 2–4:** `python3 -m unittest tests.cloud.test_detail -v` FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat(cloud): seven-tab VM detail`.

### Task 11: CloudApp — transitions, actions, live data

**Files:**
- Create: `apps/python/wysun_cloud/ui/cloudapp.py`
- Modify: `apps/python/wysun_cloud/__main__.py` (run `CloudApp().run()`)
- Test: `tests/cloud/test_cloudapp.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `CloudApp(App)` with `CloudApp(term=None, home=None, gcloud: Gcloud | None = None)`; behaviour:
  - Start: paint from `cache.load()` immediately (header shows «actualizando…»), then `instances_all` in a worker thread whose result is posted back with `app.after(0, …)`; every 30 s refresh; `state.write_state` + `cache.save` after each refresh; probes for running VMs (stop probes of VMs that stop).
  - Intro: cards and project names enter staggered (45 ms apart), each tweening from 2 rows lower with `fade_steps` opacity, curve `emphasizedDecel`, duration `expressiveDefaultEffects`.
  - Enter on a card: the card layer tweens its rect to the full content area (`y=2`, `h=height-3`) with `expressiveDefaultSpatial` / `emphasizedDecel`, the other layers fade out (`expressiveFastEffects`), then detail lines reveal top to bottom 14 ms apart. Esc/q/Backspace reverses (lines fade, rect returns to its mosaic slot, others fade in).
  - Tabs `1`–`7`, `←`/`→`, mouse click on a tab: body slides 8 cells out and in from the opposite side (`small` duration), header fixed. Opening Red/Servicios/Registro/Disco tabs launches their `run_tab_command`s once per open; Historial calls `cpu_history` in a worker thread (24 h first; `h` toggles 168 h).
  - `x` / `r` on a running VM (mosaic or detail): modal 56×8 grows from the centre (`expressiveFastSpatial`), backdrop blends the screen 45 % toward `scrim`; copy from the prototype («¿Apagar NAME?», «El disco se conserva; la IP externa efímera cambiará.», count of SSH sessions when the sample has it; reset: «Es un reinicio forzado (reset): no espera a los procesos.»). Enter runs `gcloud compute instances VERB … --quiet` via `App.spawn`; the card shows spinner + `apagando…`/`reiniciando…` until the command exits, then a refresh. Success toast «NAME apagada/reiniciada/encendida»; failure toast with gcloud's last stderr line (trimmed to 80 columns) and the real state restored.
  - `s` on an off VM: spinner `encendiendo…` on its line, then on success relayout: every VM layer tweens from its old rect to the new one (`normal` duration) — the off line grows into a card and pushes the others; stopping shrinks a card into a line the same way. If the VM's detail is open when it stops, close the detail first.
  - `c`: `terminal_argv(ssh_command(inst, []))` launched detached (`start_new_session=True`, stdio to DEVNULL); toast when no terminal is found.
  - `/`: one-line filter at the footer (Esc clears); `?`: help overlay listing keys; `p`: full project search now; `q` in the mosaic quits.
  - Mouse: click selects, double click (≤ 400 ms) opens, wheel scrolls an overflowing column / detail body.
  - Keys pressed during an animation: `animator.finish_all()` first, then handle the key.
  - gcloud errors: one-line message under the header in `error` colour (Review Focus 1); with cached data the mosaic still shows the cache marked «sin actualizar».
- [ ] **Step 1: Write failing tests** with `VirtualTerminal(120, 36)`, fake `gcloud` and fake `ssh` in `PATH`, `WYSUN_REDUCED_MOTION=1` (except the animation test): `test_first_paint_comes_from_cache_before_gcloud_answers` (fake gcloud sleeps 2 s; after one loop iteration the frame already shows the cached VM names), `test_enter_opens_detail_and_escape_returns`, `test_open_animation_grows_the_card` (motion on: sample frames during the tween; the selected card's border width grows monotonically to 120), `test_stop_needs_confirmation_and_runs_gcloud` (press `x` → modal text present; Esc → fake gcloud log has no `stop`; `x` + Enter → log has `compute instances stop api-backend --zone us-central1-a --project mi-proyecto-prod`), `test_failed_action_toast_shows_gcloud_error`, `test_start_relayouts_off_line_into_card`, `test_gcloud_auth_error_shows_message_not_traceback`, `test_ssh_key_launches_terminal` (patch `subprocess.Popen`), `test_state_file_written_after_refresh`.
- [ ] **Step 2:** `python3 -m unittest tests.cloud.test_cloudapp -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** → PASS; then `python3 -m unittest discover -s tests/cloud -t tests -v` and `python3 -m unittest discover -s tests/tui -t tests -v` → all PASS.
- [ ] **Step 5: Manual check in a real terminal with fake data:** `PATH=tests/fixtures/cloud:$PATH PYTHONPATH=apps/python python3 -P -m wysun_cloud` inside a Ghostty window you open yourself; compare against the prototype (open/close detail, tabs, modal, start/stop relayout, theme change with `wysun scheme` not needed — switch mode by editing a temp HOME's theme.json). Capture only your own window (memory: never a stale rect).
- [ ] **Step 6: Commit** `feat(cloud): wysun cloud TUI with animated transitions and VM actions`.

### Task 12: Bar indicator

**Files:**
- Create: `apps/shell/services/CloudVms.qml`, `apps/shell/services/CloudVmsLogic.js`
- Modify: `apps/shell/modules/bar/components/StatusIcons.qml` (one `Item` with `name: "cloudvms"` next to LanShare's)
- Test: `tests/shell_bridge/test_cloud_logic.py`

**Interfaces:**
- Consumes: `state.json` contract from Task 6 (`{updated, running: [{project,name,zone}], total}`).
- Produces:
  - `CloudVmsLogic.js` (`.pragma library`): `running(state, nowSec) -> array` (empty when state missing/malformed or `updated` older than 600 s), `tooltip(list) -> string` (lines grouped by project: `proyecto: a, b`), `label(list) -> string` (count as string).
  - `CloudVms.qml` singleton: `FileView` on `Paths`' runtime dir `wysun-cloud/state.json` with `watchChanges`; a `Timer` every 120 s (and once at start) running `Process { command: ["wysun", "cloud", "--estado"] }`; `readonly property var vms`, `readonly property bool active: vms.length > 0`; `function open(): void` → `Quickshell.execDetached(["wysun", "cloud", "--terminal"])`.
  - `wysun cloud --terminal` (add to `__main__.py`): re-launches itself through `launch.terminal_argv([...wysun cloud])` detached; exits 1 with a message if no terminal.
  - Bar item: visible only when `CloudVms.active`; a `MaterialIcon` `cloud` (filled) in `root.colour` with a small dot in `Colours.palette.m3success` and a `StyledText` count; tooltip from `tooltip()`; click → `CloudVms.open()`. All sizes from `Tokens`.
- [ ] **Step 1: Write failing tests** (node, like `test_lanshare_logic.py`): `test_running_ignores_stale_and_broken`, `test_tooltip_groups_by_project`, plus static checks `test_status_icons_has_cloud_entry_bound_to_active` (file text contains `name: "cloudvms"` and `visible: CloudVms.active`) and `test_service_polls_estado_every_two_minutes` (`interval: 120000`, command includes `"--estado"`); in `tests/cloud/test_gcloud.py` add `test_terminal_option_launches_detached` (patch `Popen`).
- [ ] **Step 2–4:** `python3 -m unittest discover -s tests/shell_bridge -t tests -p 'test_cloud_logic.py' -v` FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat(shell): bar indicator for running VMs`.

### Task 13: Docs, full checks and deploy

**Files:**
- Modify: `docs/utilities.md` (section «Wysun Cloud»: commands, keys, data sources, SSH routes, `sudo -n` rule, refresh cadence, `cloud.json` keys, credentials rule), `ARCHITECTURE.md` only if it lists utilities (check with `grep -n lanshare ARCHITECTURE.md`; the user has uncommitted edits there — add a line with Edit and commit only if the user's hunk is untouched, otherwise leave it and mention it).
- [ ] **Step 1:** `python3 -m unittest discover -s tests -v` → only the known pre-existing failure `test_legacy_names` (wysun_music/covers.py) may fail; nothing else. Then `python3 -m unittest discover -s tests/shell_bridge -t tests`, `python3 tests/check_manifest.py` → PASS (add new files to the manifest if the check requires it).
- [ ] **Step 2: Commit** `docs(cloud): Wysun Cloud in utilities` (pathspec).
- [ ] **Step 3: Deploy:** `wysun update` (conflicts `hyprland.lua`, `xdph.conf`, `mimeapps.list` are pre-existing), `wysun reload`, then restart only the shell (`pkill -x quickshell; setsid wysun-shell &`) because `apps/shell` changed.
- [ ] **Step 4: Live read-only check:** run `wysun cloud --estado` and confirm `state.json` exists (do not print tokens; do not cat credential files); ask the user to open `wysun cloud` and confirm their projects/VMs appear and the bar icon shows when VMs run. No start/stop/reset on real VMs unless the user asks.

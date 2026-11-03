# Wysun Processes (app QML + integraciones) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sustituir el panel `processes` del shell por la app QML `wysun_processes` (cinco secciones, movimiento
expresivo) e integrar miniaturas, localizar, app colgada, `Super+Shift+Esc`, avisos y lanzador.

**Architecture:** Núcleo sin Qt en `apps/python/wysun_processes/core/` (muestreo de `/proc`, vistas, servicios,
inicio, Hyprland); puente Qt en `wysun_processes/quick/` (modelos y controlador); UI en `apps/qml/processes/` sobre
`WysunM3` (componentes nuevos reutilizables en la base). El shell aporta IPC (`wysunShell`) para miniaturas,
localizar y forzar cierre, un módulo para el diálogo de app colgada y el panel de proceso del lanzador. Los avisos
los vigila el residente `wysun daemon` leyendo `cpu.stat` de los cgroups de app.

**Tech Stack:** Python 3.13, PySide6 (venv qml-runtime) + QML/WysunM3, Quickshell/QML del shell, Hyprland 0.55 (Lua),
systemd --user, D-Bus de notificaciones.

**Spec:** `docs/superpowers/specs/2026-11-02-wysun-processes-app-design.md` (mockup:
`docs/superpowers/specs/2026-11-02-wysun-processes-mockup.html`).

## Global Constraints

- Colores, radios, espaciado, tipografía y duraciones solo de tokens (`Theme.*`, `Metrics`, `Motion`; en el shell
  `Colours.palette`, `Tokens`). Tinte por app: excepción declarada `theme-exception: tinte derivado del icono`.
- Textos de interfaz en español. Sin indicadores circulares ondulados.
- Nada de datos de procesos en disco persistente; miniaturas solo en `$XDG_RUNTIME_DIR/wysun-processes/`.
- La app nunca escribe `hyprland.lua`; `exec-once` (bloques `hl.on("hyprland.start", … hl.exec_cmd("…"))`) es de
  solo lectura. Autostart XDG por anulaciones en `~/.config/autostart/` sin tocar el original.
- No se cambia `misc:enable_anr_dialog`.
- `bin/wysun` único punto de entrada; módulos con `python3 -P -m`; nada en `~/.local/share/wysun/app/`.
- Pruebas serializadas, una compilación a la vez; QML con el venv `~/.cache/wysun-fase1/qml-runtime`.
- Procesos de otros usuarios: sin ayudante privilegiado; el error del kernel se muestra.
- Avisos desactivados por defecto; umbrales en `~/.config/wysun/processes.json`.

## Review Focus

1. Un PID que muere o se reutiliza entre muestra y acción → la acción se rechaza con «El PID cambió de proceso»
   (pidfd + `start`), nunca se señala a otro proceso. Prueba en Task 1.
2. Sistema con miles de procesos / `/proc` con entradas que desaparecen a mitad de lectura → el muestreo no lanza
   y cuesta < 60 ms por pasada con 2000 procesos sintéticos. Prueba en Task 1.
3. `systemctl --user` o `journalctl` ausentes o lentos → Servicios muestra un estado vacío explicado, la UI no se
   bloquea (llamadas en hilo con tiempo límite). Prueba en Task 2.
4. Shell no disponible (IPC falla) → la app funciona sin miniaturas (vista dibujada con icono) y «Localizar» avisa.
   Prueba en Task 3.
5. Segunda ejecución `wysun processes firefox` con la app abierta → enfoca la ventana existente y aplica la
   consulta, sin abrir otra. Prueba en Task 4.

---

## Parte 1 — La app

### Task 1: Núcleo de muestreo y vistas (sin Qt)

**Files:**
- Create: `apps/python/wysun_processes/__init__.py`, `apps/python/wysun_processes/core/__init__.py`,
  `core/sampler.py`, `core/views.py`, `core/system.py`, `core/actions.py`
- Test: `tests/test_processes_core.py`

**Interfaces:**
- Produces:
  - `core.sampler.Sampler(proc_root='/proc', sys_root='/sys')` con `.sample() -> Snapshot`.
    `Snapshot.rows: list[dict]` (claves de `process_data.process_record` + `cpu, mem, gpu|None, read_rate,
    write_rate, io, app, app_id, user, state_label, ema:{cpu,gpu,io}, key:(pid,start)`), `Snapshot.system: dict`
    (`cpu, cores:list[float], memory, total_memory, cached, swap, total_swap, gpu|None, gpu_memory|None, disk_read,
    disk_write, net_rx, net_tx, pressure:{cpu,memory,io}, load, uptime, count, running, temps:{cpu,gpu,disk}`).
    `app` sale de `application_group()` (lógica de `apps/shell/modules/processes/backend.py`, movida aquí).
  - `core.views.parse_query(text) -> Query` (`.tokens: list[str]`, `.words`, `.match(row) -> bool`); filtros
    `cpu|mem|gpu[<>]=?N[kmg]`, `user: state: pid: ppid: app:` (state acepta `running/sleeping/stopped/idle/zombie`
    y las etiquetas en español).
  - `core.views.build(rows, mode:'apps'|'tree'|'list', query, sort, descending, expanded:set, mine:bool, uid) ->
    (list[ViewRow], matched:int)`; `ViewRow` dict con `key` (`'g:<app>'` o `'p:<pid>:<start>'`), `depth`, `group`,
    `kids`, `expanded`, agregados `cpu mem gpu io threads`. Orden por `ema` cuando existe (no baila).
  - `core.actions.act(sampler, key, action)` con `action in {'terminate','kill','pause','resume'}` sobre un proceso
    o todos los de un grupo; `core.actions.set_priority(key, nice)`; errores `PermissionError`/`RuntimeError` con
    mensaje en español.
- Consumes: `wysun_services.process_data` (`process_record`, `io_counters`, `safe_command`, `thread_snapshot`,
  `Processes.action_reason/checked/details`).

- [ ] Step 1: Escribir `tests/test_processes_core.py`: `test_query_filters` (`parse_query('cpu>5 mem>1g user:root
  fire')` acepta/rechaza filas sintéticas; `state:running` y `state:ejecutando` equivalen), `test_build_apps_groups`
  (tres filas de dos apps → 1 grupo con 2 hijos al expandir, 1 fila suelta), `test_build_tree_keeps_ancestors`
  (filtrar un nieto conserva padre y abuelo), `test_sort_uses_ema`, `test_sampler_reads_self` (la muestra contiene
  `os.getpid()` con `app` y `key`), `test_sampler_survives_vanishing` (`proc_root` sintético con un PID cuyo `stat`
  falta → sin excepción), `test_sampler_cost` (2000 PIDs sintéticos en `tmp`, < 60 ms la segunda pasada),
  `test_act_rejects_reused_pid` (`key` con `start` falso → `RuntimeError('El PID cambió de proceso…')`),
  `test_application_group` (casos de `backend.application_group`).
- [ ] Step 2: `python3 -m unittest tests.test_processes_core -v` → FALLA (módulo inexistente).
- [ ] Step 3: Implementar los cuatro módulos. `system.py` lee `/proc/stat` por núcleo, `/proc/meminfo`,
  `/proc/pressure/*` (avg10), `/proc/diskstats` (sumando discos enteros), `/proc/net/dev` (sin `lo`), `hwmon`
  (`k10temp|coretemp` → cpu, `amdgpu|nvidia` → gpu, `nvme` → disco), GPU como en `backend.py`.
- [ ] Step 4: La prueba pasa.
- [ ] Step 5: Commit `feat(processes): Qt-free sampler, views and actions for the new app`.

### Task 2: Servicios de usuario e Inicio (sin Qt)

**Files:**
- Create: `core/services.py`, `core/startup.py`
- Test: `tests/test_processes_services.py`

**Interfaces:**
- Produces:
  - `services.Services(run=subprocess.run, timeout=3)`: `.list() -> list[dict]` (`unit, description, kind:
    'service'|'timer', state:'active'|'inactive'|'failed', since, enabled:bool, memory, cpu_ns, tasks, main_pid,
    error, next_ms, last`), `.action(unit, 'start'|'stop'|'restart'|'enable'|'disable'|'run')`,
    `.journal(unit, lines=200) -> list[(level, time, text)]`, `.follow(unit) -> Popen` (`journalctl --user -u U -f
    -o json`). Fuente: `systemctl --user list-units --all --type=service,timer -o json`, `list-timers -o json`,
    `show -p …`. Sin systemctl → `list()` devuelve `[]` y `.available=False`.
  - `startup.Startup(home, hypr_config, proc_root='/proc')`: `.items() -> list[dict]` (`id, name, source:
    'session'|'exec-once'|'systemd'|'autostart', editable, enabled, delay, impact:1-3, started_s, ready_s`),
    `.set_enabled(id, bool)`, `.set_delay(id, 0|5|10)`, `.ready_at() -> float`. Autostart: lee
    `$XDG_CONFIG_DIRS/autostart` y `~/.config/autostart`; desactivar escribe una copia en `~/.config/autostart`
    con `Hidden=true`; retrasar escribe `Exec=sh -c 'sleep N; exec …'` y `X-Wysun-Delay=N`; volver a 0 y activado
    borra la anulación si solo existe por Wysun. `exec-once` parseado de `hyprland.lua`, `editable=False`.
    Tiempos: inicio de cada proceso (`/proc/<pid>/stat` campo 22) menos el de Hyprland.
- [ ] Step 1: Pruebas: `test_list_parses_json` (runner falso con JSON de `systemctl` y un `failed`),
  `test_missing_systemctl` (runner que lanza `FileNotFoundError` → `[]`, `available False`),
  `test_timeout_does_not_raise`, `test_journal_levels` (`PRIORITY` 3→`err`, 4→`warn`, otro→`info`),
  `test_autostart_disable_override` (HOME temporal: el original intacto, la anulación con `Hidden=true`),
  `test_delay_wrapper_and_revert`, `test_exec_once_read_only` (parsea las dos líneas reales de
  `config/.config/wysun/hyprland.lua` como `editable False`; `set_enabled` lanza `PermissionError`).
- [ ] Step 2: Fallan. Step 3: implementar. Step 4: pasan.
- [ ] Step 5: Commit `feat(processes): user services and session startup sources`.

### Task 3: Hyprland y shell (sin Qt)

**Files:**
- Create: `core/hypr.py`
- Test: `tests/test_processes_hypr.py`

**Interfaces:**
- Produces: `hypr.Hypr(run=subprocess.run)`: `.windows() -> list[dict]` (`address, pid, app_id(class), title,
  workspace, active, monitor`), `.active_workspace() -> int`, `.focus(address)`, `.close(address)` (graceful
  `closewindow`), `.thumbnails(addresses) -> dict[address, path]` (IPC `wysun-shell thumbs a,b`; `{}` si falla),
  `.locate(address) -> bool` (IPC `wysun-shell locate ADDR`). `pid_app(pid, rows)` asocia ventanas con su grupo.
- [ ] Step 1: Pruebas con runner falso: parseo de `hyprctl clients -j`, IPC que falla → `{}`/`False` sin lanzar.
- [ ] Step 2–4: fallan, implementar, pasan.
- [ ] Step 5: Commit `feat(processes): Hyprland windows and shell IPC client`.

### Task 4: Puente Qt, arranque e instancia única

**Files:**
- Create: `wysun_processes/__main__.py`, `wysun_processes/app.py`, `wysun_processes/quick/__init__.py`,
  `quick/controller.py`, `quick/models.py`, `quick/icons.py`, `quick/window.py`,
  `config/.local/share/applications/wysun-processes.desktop` (`Icon=utilities-system-monitor`, `Exec=wysun processes`)
- Modify: `bin/wysun` (`MODULES['processes'] = ('app', 'wysun_processes', [])`)
- Test: `tests/qml/check_processes_controller.py`

**Interfaces:**
- Produces (contexto QML): `procs` (`ProcessesController`): propiedades `rows` (`RowModel`, roles = claves de
  `ViewRow` + `icon`, `tint`), `selected` (dict del seleccionado + `history:{cpu,mem,gpu,io}` de 60 muestras),
  `summary`, `systemHistory`, `mode`, `query`, `tokens`, `sort`, `descending`, `mine`, `interval` (1000|2000),
  `frozen`, `page`; slots `select(key)`, `move(delta)`, `toggle(key)`, `setMode`, `setQuery`, `removeToken`,
  `sortBy`, `act(action)` (señal `confirmNeeded(action, label, count)` para terminate/kill/priority; `pause` directo
  con `snack(text, undo)`), `confirm(action, nice)`, `undo()`, `details(tab)`, `copyPid()`, `focusWindow()`,
  `locate()`; `apps` (ventanas por espacio + segundo plano, miniaturas cada 3 s solo de las visibles),
  `services`, `startup`. `quick/icons.py`: proveedor de imagen `image://appicon/<app_id>` y `tint(app_id) -> str`
  (color dominante saturado del icono, `QColor.name()`).
- Instancia única: `QLocalServer` en `wysun-processes-<uid>` dentro de `$XDG_RUNTIME_DIR`; una segunda ejecución
  envía la consulta y sale con 0; la primera aplica `setQuery`, selecciona el primer grupo y `present()`.
- [ ] Step 1: Pruebas (venv, offscreen, `Sampler` con `proc_root` sintético): filtrar y seleccionar,
  `confirmNeeded` para `terminate`, `pause` emite `snack` con deshacer, segunda instancia aplica consulta
  (dos `QLocalSocket` en el mismo proceso), historia acotada a 60.
- [ ] Step 2–4: fallan, implementar (muestreo en `QThread` con `collect_on_gui_thread()`), pasan.
- [ ] Step 5: Commit `feat(processes): Qt bridge, single instance and wysun processes [query]`.

### Task 5: Componentes nuevos de WysunM3

**Files:**
- Create: `apps/qml/WysunM3/feedback/RollingNumber.qml`, `feedback/LiveChart.qml`, `shapes/StateShape.qml`
- Modify: `apps/qml/WysunM3/qmldir`, `apps/qml/WysunM3/Metrics.qml`, `apps/qml/gallery/pages/` (página nueva),
  `docs/qml-base.md` (catálogo)
- Test: `tests/qml/check_processes_components.py`

**Interfaces:**
- `RollingNumber { text; role: "display.small" }` — dígitos en columnas que ruedan con `Motion` `defaultSpatial`;
  otros caracteres estáticos; movimiento reducido = salto.
- `LiveChart { series: [[...]], colors: [color], maxValue; grid; fill; dot; scrub: bool; markers: [{index, icon,
  color}]; formatValue: function; labelAt: function(index) -> string }` — `Canvas` con desplazamiento continuo
  entre muestras (`progress` 0–1 animado), guía y etiqueta al pasar el cursor; señal `hovered(index)`.
- `StateShape { state: "R"|"S"|"T"|"Z"|"G"; color; size }` — `MaterialShape` de M3Shapes (Cookie9 girando en R,
  Circle en S, Square redondeado en T, Burst en Z, Sunny en G) con morfo; respaldo sin M3Shapes: rectángulo con
  radio animado.
- [ ] Step 1: Pruebas: `RollingNumber` muestra el texto final (grab) y con movimiento reducido no anima;
  `LiveChart` con `scrub` emite `hovered` al mover el ratón y no pinta colores literales; `StateShape` cambia de
  forma sin warnings; `check_gallery` y `check_purity` siguen pasando.
- [ ] Step 2–4. Step 5: Commit `feat(qml): RollingNumber, LiveChart and StateShape in WysunM3`.

### Task 6: Interfaz QML de la app

**Files:**
- Create: `apps/qml/processes/Main.qml` y `apps/qml/processes/parts/`: `ProcessesMetrics.qml`, `ProcessTable.qml`,
  `ProcessRow.qml`, `TableHeader.qml`, `QueryBar.qml`, `DetailPane.qml`, `PerfPage.qml`, `PerfTile.qml`,
  `AppsPage.qml`, `WindowTile.qml`, `AppSheet.qml` (ContainerTransform), `ServicesPage.qml`, `StartupPage.qml`,
  `StartupTimeline.qml`, `CommandPalette.qml`, `ShortcutsHelp.qml`, `ConfirmDialog.qml`, `AppIcon.qml`
- Test: `tests/qml/check_processes_window.py`

Comportamiento: el del mockup v4 (secciones, atajos y textos del spec). Rail con `AdaptiveNavigation` (Procesos,
Rendimiento, Apps, Servicios con insignia de fallos, Inicio). Tabla virtualizada (`ListView`) con filas que se
desplazan por `y` animado y píldora de selección; celdas con calor (`Theme.m3primary` con opacidad).
- [ ] Step 1: Pruebas: carga sin warnings en claro y oscuro y con dos paletas; `↓`/`j` mueve la selección; `/`
  enfoca el buscador; `cpu>5` crea una etiqueta; `V` cambia de vista; `Supr` abre `ConfirmDialog`, `Esc` lo
  cierra; `1`–`5` cambian de sección; en Apps `Enter` abre `AppSheet` y `Esc` lo cierra; Servicios sin systemctl
  muestra `EmptyState`; Inicio muestra `exec-once` sin `Switch`.
- [ ] Step 2–4. Step 5: Commit `feat(processes): QML window — processes, performance, apps, services, startup`.

### Task 7: Retirar el panel del shell y desplegar

**Files:**
- Delete: `apps/shell/modules/processes/` (entero)
- Modify: `apps/shell/wysun/WysunBridge.qml` (quitar import, `processes: ''`, `Processes {}` y sus ramas),
  `config/.config/wysun/hyprland.lua` (quitar la regla `wysun-processes`), pruebas que lo citan
  (`tests/shell_bridge/test_process_widget.py` → retirar o reescribir sobre `wysun_processes`, `test_dispatcher`,
  `test_shared_components`, `test_session_shortcut`, `benchmark_shell.py`), `ARCHITECTURE.md`, `docs/wysun.md`,
  manifiesto de instalación si lista el módulo.
- [ ] Step 1: `grep -rn "modules/processes\|modules.processes" apps tests installer` vacío salvo historia.
- [ ] Step 2: Suites: `python3 -m unittest discover -s tests -v`, `… -s tests/shell_bridge -t tests`,
  `python3 -m unittest tests.test_qml_runtime -v`, `python3 tests/check_manifest.py` → pasan.
- [ ] Step 3: `./instalar.sh --wysun-only`; migrar `~/.config/wysun/hyprland.lua` con respaldo (quitar solo la regla
  `wysun-processes`), `hyprctl reload` no (no reiniciar Hyprland: la regla nueva aplica al abrir); `wysun reload`;
  reiniciar solo el shell.
- [ ] Step 4: Abrir `wysun processes firefox` y comprobar en la sesión real (captura solo de la ventana propia):
  ventana en mosaico, cinco secciones, consulta aplicada; segunda ejecución enfoca.
- [ ] Step 5: Commit `feat(processes)!: the QML app replaces the shell panel`.

## Parte 2 — Integraciones del shell

### Task 8: Miniaturas y localizar

**Files:**
- Create: `apps/shell/modules/locate/Locate.qml`, `apps/shell/services/WindowThumbs.qml`
- Modify: `apps/shell/wysun/WysunBridge.qml` (IPC `thumbs(addresses: string): string`, `locate(address: string):
  bool`), `bin/wysun-shell` (`thumbs`, `locate`), shell root que instancia el módulo
- Test: `tests/shell_bridge/test_locate.py` (lógica JS pura: geometría del halo, espacio distinto → aviso)

Miniaturas: `ScreencopyView` por cliente fuera de pantalla → `grabToImage` → `$XDG_RUNTIME_DIR/wysun-processes/
thumbs/<address>.png` (máx. 480 px de ancho); devuelve JSON `{address: path}`. Localizar: capa Overlay sin foco;
halo `m3primary` que palpita sobre la geometría del cliente, resto atenuado con `m3scrim`, 2,5 s o `Esc`; si el
cliente está en otro espacio, cápsula «está en el espacio N».
- [ ] Steps: prueba → falla → implementar → pasa → comprobar en sesión real → commit
  `feat(shell): window thumbnails and locate-on-screen for Processes`.

### Task 9: App que no responde

**Files:**
- Create: `apps/shell/modules/anr/Anr.qml`, `apps/shell/modules/anr/AnrLogic.js`
- Test: `tests/shell_bridge/test_anr_logic.py`

Escucha `Hyprland.rawEvent` `openwindow` con clase `hyprland-dialog`; lee `/proc/<pid>/cmdline` del diálogo para el
título del cliente colgado; empareja con `Hypr.toplevels`; muestra la tarjeta sobre la ventana (gris + brillo),
y solo después mueve el diálogo de Hyprland a `special:wysun-anr` silencioso. Esperar → `closewindow` del diálogo;
Forzar cierre → `kill -KILL <pid del cliente>` y cerrar el diálogo. Si la tarjeta falla, el diálogo queda visible.
- [ ] Steps: prueba de `AnrLogic.parseDialog(argv)` y `matchClient` → implementar → simular en sesión con un
  proceso detenido (`kill -STOP` a una ventana de prueba propia) → commit `feat(shell): Wysun card for
  unresponsive windows`.

### Task 10: `Super+Shift+Esc`

**Files:**
- Create: `apps/shell/modules/forcequit/ForceQuit.qml`
- Modify: `WysunBridge.qml` (IPC `forceQuit(): bool`), `bin/wysun-shell` (`forcequit`),
  `config/.config/wysun/hyprland.lua` (`hl.bind("SUPER + SHIFT + Escape", hl.dsp.exec_cmd("wysun-shell forcequit"),
  {description="Wysun | extra | Forzar cierre de la ventana activa"})`), `manifests/wayland-shortcuts.json`, cheat
  sheet si lista atajos
- Test: `tests/shell_bridge/test_forcequit.py` (procesos de sesión protegidos no se ofrecen)
- [ ] Steps: prueba → implementar → migrar la configuración activa con respaldo, comprobando que el atajo está libre
  → probar en sesión con una ventana propia → commit `feat(shell): Super+Shift+Esc force-quits the active window`.

### Task 11: Avisos de consumo con acciones

**Files:**
- Create: `apps/python/wysun_services/process_watch.py`
- Modify: `apps/python/wysun_services/daemon.py` (arranca el vigilante si está activado; recarga al cambiar el
  JSON), `apps/shell/modules/nexus/pages/services/NotificationsPage.qml` (sección «Avisos de consumo»: interruptor,
  umbral de CPU 50–100 %, minutos 1–10, memoria GB)
- Test: `tests/test_process_watch.py`

`ProcessWatch(cgroup_root, config_path, notify)`: cada 5 s lee `cpu.stat` (`usage_usec`) y `memory.current` de
`…/app.slice/*`; un app por encima del umbral durante N min → un aviso (`org.freedesktop.Notifications.Notify`
con acciones `ver`, `terminar`, `silenciar` e imagen de la gráfica en `$XDG_RUNTIME_DIR`); `ver` → `wysun processes
<app>`; `terminar` → `systemctl --user stop <scope>` (pide confirmar con un segundo aviso); `silenciar` → 1 h.
Configuración: `{"alerts": false, "cpu": 90, "minutes": 3, "memory_gb": 0}`.
- [ ] Steps: pruebas con árbol cgroup sintético y reloj inyectado (no avisa antes de N min, avisa una vez, silencio
  1 h, desactivado no lee nada) → implementar → `wysun reload` y prueba real con un proceso de carga propio →
  commit `feat(daemon): opt-in resource alerts with actions`.

## Parte 3 — Lanzador

### Task 12: «En ejecución» y panel de proceso

**Files:**
- Modify: `apps/shell/modules/launcher/services/Quick.js` (`runningRows(q, procs, clients)`; `killRows` con
  agrupación por app y PIDs), `services/Results.js`, `LauncherPanel.qml` (acciones `go`, `processes`, `locate`,
  `close`, `kill` con segunda pulsación en la fila; atajos `Ctrl+Enter`, `Ctrl+L`, `Ctrl+W`, `Ctrl+Shift+W`),
  `PreviewPane.qml` (modo `process`: `ScreencopyView` en vivo, `StateShape`/forma, CPU/Memoria/Procesos, gráfica,
  lista de acciones con atajos), `services/Suggest.qml` (muestreo por app cada 1 s solo con el panel abierto)
- Test: `tests/shell_bridge/test_launcher_logic.py`, `test_launcher_actions.py` (ampliar)

Cerrar = `closewindow` a cada ventana del app y `SIGTERM` a sus procesos sin ventana; forzar = `SIGKILL`; nunca
procesos de `PROTECTED`.
- [ ] Steps: pruebas de lógica → implementar → probar el lanzador real (`wysun launcher`, escribir «fire», «kill»)
  → commit `feat(launcher): running apps with a live process pane and actions`.

### Task 13: Cierre

- [ ] Todas las suites de AGENTS.md (serializadas), `python3 apps/recorder/run_tests.py`,
  `python3 tests/wysun_installed_smoke.py`.
- [ ] `./instalar.sh --wysun-only`, `wysun reload`, reiniciar solo el shell, comprobar en sesión: Processes, avisos,
  `Super+Shift+Esc`, lanzador, localizar.
- [ ] `ARCHITECTURE.md` y `docs/qml-base.md` al día. Commit `docs: Processes app and its integrations`.

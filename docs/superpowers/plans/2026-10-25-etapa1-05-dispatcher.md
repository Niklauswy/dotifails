# Etapa 1 · Plan 05 — despachador único, borrado de alias y documentación final

> **Para agentes:** ejecutar con superpowers:executing-plans + TDD; cada tarea termina en verde y en su propio commit.

**Objetivo.** `bin/wysun` es el único punto de entrada de Wysun: manda las superficies al shell por IPC y lanza
las apps con `python3 -P -m`. Desaparecen el puente `wysun_services.client`, los lanzadores sucesores de los
`orbit-*` y todos los alias; el instalador retira de `~/.local/bin` lo que ya no publica; la documentación
describe la realidad sin reglas de compatibilidad.

**Encargo:** `.superpowers/orca/plan05-spec.md`. **Diseño:** `docs/superpowers/specs/2026-10-24-wysun-limpieza-base-comun-design.md`
§5, §6, «Decisiones tomadas», paso 7 y «Verificación». **Antes:** plan 04 (`2026-10-25-etapa1-04-rename.md`).

## Restricciones globales

- Sin capas de compatibilidad nuevas: ni alias, ni shims, ni migraciones de datos en el repo.
- No desplegar, no tocar el HOME real (solo `grep`), no reiniciar quickshell ni Hyprland.
- Plugin C++ solo con `installer/runtime_build.py --only plugin --jobs 3 --prefix <temporal>`; este plan no toca C++.
- Suites de una en una; pruebas en HOME/XDG temporales.

## Decisiones

| Tema | Decisión | Por qué |
|---|---|---|
| Lista de superficies | Vive solo en el shell: `surfaces` de `apps/shell/wysun/WysunBridge.qml` (incluye `colors` y `processes`, que tienen módulo propio, con valor `''`). `bin/wysun-shell` y `bin/wysun` no la repiten: reenvían el nombre y el shell responde `false` si no existe (salida 2, «superficie desconocida»). IPC nuevo `surfaces()` para listarlas (`wysun-shell surfaces`). | El shell es quien sabe qué superficies tiene; un JSON aparte sería una segunda fuente que leer en QML y en sh. |
| Forma corta | `wysun <superficie>` y `wysun-shell <superficie>` alternan (`toggle`); `open`/`toggle <superficie>` siguen. `colors` y `processes` dejan de ser solo `open`. | Arregla `wysun shell colors` / `wysun-shell processes` («argument was not expected»). |
| Alias de superficies | Se borran `toggle`, `power`, `audio`, `calendar`, `system`, `color`, `network`, `settings-PÁGINA`, la superficie `test`. El Catálogo pasa a `wysun quicksettings`/`wysun dashboard`. Quedan `menu`/`quicksettings` y `notifications`/`sidebar` porque son superficies con nombre propio en binds y catálogo. | Diseño: «Se borran también los alias internos». |
| Rutas del shell que no son superficies | `clipboard` → `category clip`, `calculator` → `category calc`, `color-pick`, `settings [PÁGINA]` → `nexus`. Cualquier otra palabra se manda como `toggle PALABRA` (nunca llega a los comandos propios de `wysun-shell` ni de Quickshell). | Son acciones, no alias. |
| Apps | `music`, `music-mini`, `files`, `pdf`, `player`, `scheme`, `wallpaper`, `workspaces`, `tools`, `daemon`, `reload` → `python3 -P -m …`. `music-mini` arranca Music en segundo plano y abre el widget de media. | Un solo lanzador. |
| Residente | `wysun daemon` = `python3 -m wysun_services.daemon` (en primer plano, lo arranca `wysun-session-services`; ignora opciones desconocidas para que un residente anterior pueda reejecutarse con el código nuevo). `wysun reload` = `python3 -m wysun_services.daemon reload`: reinicia el residente o, si no hay, lo arranca desacoplado. El residente solo guarda el portapapeles (`ping`, `reload`). | Antes enrutaba `music`, `color`, `power`, que ya no son suyos. |
| Lanzadores borrados | `bin/wysun-tools` (→ `wysun tools`), `bin/wysun-player` (→ `wysun player`), `bin/wysun-workspaces` (→ `wysun workspaces`), los envoltorios generados `wysun-files`/`wysun-music`/`wysun-pdf`, los redirectores `wysun-screenshot`/`wybie-screenshot` (→ `wysun-shell screenshot`), los alias de `~/scripts` (`web-dev`, `sec-audit`, `file-share`, `gvm`, `gvm.sh`, `tailscale-killswitch[.sh]`, `scrip.sh`, `rezets`, `zzzz.py`) y `wysun_services/client.py`. `wysun tools gui` se borra (el panel ya no existe). | Sucesores de `orbit-*`/`orbit-client` y alias. |
| Se quedan | `wysun-shell`, `wysun-lock`, `wysun-wm`, `wysun-control` (atajos de alta frecuencia en sh), `wysun-idle`, `wysun-session`, `wysun-session-services`, `wysun-recover` (debe funcionar sin el shell), `wysun-share-picker` (ruta absoluta en `xdph.conf`), `wysun-recorder` (apunta a la release inmutable), `wysun-terminal`, `wysun-install`/`wysun-installer`. | Programas propios, no alias. |
| `wysun install` / `wysun doctor` | Se quedan como subcomandos que reenvían a `wysun-install`. `wysun-install` sigue existiendo porque el instalador se publica también sin el componente `desktop` (solo `wayland`) y vive en `~/.local/share/wysun/installer`, independiente de la app. | Diseño: «`wysun install` (o equivalente bajo `wysun`)». |
| Herramientas sin escritorio | El componente `tools` también publica `~/.local/bin/wysun`; `wysun tools` usa `~/.local/share/wysun/tools` como `PYTHONPATH` y ejecuta `-m wysun_tools` (nuevo `wysun_tools/__main__.py`; `apps/tools/cli.py` se mueve ahí). | Sin `wysun-tools` hace falta `wysun` en ese componente. |
| Retirada | `installer/main.py: RETIRED_COMMANDS` (= `DESKTOP_RETIRED` + `TOOLS_RETIRED`) y `Deployment.retire_commands()`: retira lo que el recibo marca como nuestro y sin cambios; uno modificado pasa a ser del usuario (sale del recibo, se conserva, sin conflicto); uno ajeno se deja; uno que `~/.config/wysun/*.lua` sigue llamando se conserva hasta que deje de llamarlo. `configure_wysun` retira todo; `--scripts-only` solo las herramientas y no toca `wysun` si el escritorio está instalado. | «los lanzadores viejos se eliminan de `~/.local/bin` en una actualización». |
| Migraciones heredadas | Se borran `ShellPreferences.migrate`/`translate_legacy_bar` (y el código muerto de la barra vieja `bar_values`/`apply_bar`/`BAR_MODULES`/limpieza de `hypr-bar.json`), `migrate_legacy_names` (la configuración del shell con el nombre del proyecto de origen), la de `scripts/.rezets`, `scripts/uploads`, `scripts/__pycache__`/`.codex`, y la adopción del manifiesto de `wybie-screenshot`. Ninguno de esos orígenes existe en esta máquina. | Solo compatibilidad. |
| Avisos del shell | `ProcessWindow`: las celdas usan `cells.full` (id de la fila) y todas llevan `tone`. `OverlayWindow`: `Config.screen` además de `Tokens.screen`; `EmojiPicker` mide con `contentItem.Tokens`; `WysunBridge.available` usa `GlobalConfig.forScreen(...)`; la animación de `LauncherPanel` usa `root.Tokens`. | Avisos vistos en el log del shell vivo. |

## Tareas

1. **Superficies en el shell.** Prueba (`tests/shell_bridge/test_bridges.py`): `wysun-shell <s>` y `toggle <s>` para cada
   superficie de `surfaces` llegan a `ipc call wysunShell toggle <s>`; respuesta `false` → código 2; `ipc …` y
   flags siguen arrancando/pasando al runtime. Implementar en `bin/wysun-shell` y `WysunBridge.qml` (`colors`,
   `processes`, sin `test`, `surfaces()`); `test_session_shortcut` ajustado.
2. **Despachador.** Prueba nueva `tests/shell_bridge/test_dispatcher.py`: cada superficie del bridge → `wysun-shell <s>`;
   rutas de acción; apps → `-m`; alias borrados → código ≠ 0 sin tocar el shell; `--help` sin alias. Reescribir
   `bin/wysun`; actualizar `test_launcher_dispatch.py`, `test_wysun_distribution.py`.
3. **Residente.** `test_resident.py`: `daemon.main(['reload'])` sin residente arranca uno desacoplado; el residente no
   tiene `show_mode`. Borrar `client.py`; Catálogo, `backend.py` (`launch` muerto), cheatsheet.
4. **Lanzadores fuera.** Player, workspaces, tools, envoltorios, `.desktop`, `hyprland.lua`, Recorder → `wysun player`;
   `RETIRED_COMMANDS` + pruebas del instalador (`test_wysun_distribution`, `test_tools`, `test_player_integration`,
   `check_manifest`, `install_model`).
5. **Migraciones heredadas fuera** (con sus pruebas).
6. **Avisos QML.**
7. **Documentación** (`AGENTS.md`, `ARCHITECTURE.md`, `README.md`, `docs/*.md`, READMEs de apps).
8. **Verificación:** todas las suites, instalación en HOME temporal, revisor nuevo, rebase sobre `main`.

## Foco de revisión

- `wysun` sin argumentos con el shell caído: debe fallar visible, no colgarse (timeout 4 s).
- `wysun-shell` sin argumentos o con flags (`wysun-session-services`, `wysun-recover`) debe seguir arrancando el shell.
- `sudo ~/.local/bin/wysun tools vpn …` debe encontrar el motor por la ruta del propio script, no por `$HOME`.
- Una actualización con un lanzador retirado que el usuario modificó: conflicto, nunca borrado.
- `wysun reload` desde una terminal no debe quedarse como residente en primer plano.

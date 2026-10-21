# Wysun · arquitectura

Entorno de escritorio personal sobre **Hyprland (Wayland)**: shell en Quickshell/QML con plugin C++ propio, aplicaciones Qt
(PySide6), captura de pantalla/vídeo, instalador reversible y sesión registrada de forma independiente. Este documento es la
referencia para quien modifique el repositorio (atajos, lanzador, Ajustes, tema).

Nombres visibles: **Wysun**, **Wysun Recorder**, **Wysun Screenshot**, **Wysun Settings**. Las identidades técnicas heredadas de
Orbit (`orbit`, `~/.local/share/orbit`, `orbit-files.desktop`, sockets `orbit-*.sock`) se conservan por compatibilidad con datos y
atajos existentes (sección 7). El código derivado del shell GPL-3.0 de terceros conserva créditos en `THIRD_PARTY.md`,
`apps/shell/LICENSE` y `apps/shell/UPSTREAM.json`; ningún identificador de ejecución depende ya de ese proyecto.

## 1. Estructura del repositorio

```
apps/
  shell/        Shell Quickshell (QML) + plugin C++ `Wysun.*`        → ~/.local/share/wysun/quickshell
  wysun/        Lanzador y apps Qt/PySide6 (Music, Files, Settings…) → ~/.local/share/orbit/app
  capture/      Wysun Recorder (loomrec/) y Screenshot (wybieshot/)  → ~/.local/share/wysun/capture/releases/<hash>
  tools/        `orbit-tools` (dev, audit, share, cloud, vpn, resets) → ~/.local/share/orbit/tools
bin/            Lanzadores públicos (wysun, wysun-shell, wysun-session, wysun-lock, wysun-wm, …) → ~/.local/bin
config/         Configuración GENERAL (dotfiles): .config/{wysun,ghostty,nvim,gtk-*,…}, .local/{bin,share/applications,icons}
machines/       Perfiles opcionales por equipo (p. ej. samsung-touchscreen.sh); nunca se aplican por defecto
installer/      Instalador (CLI + GUI), constructor del runtime, registro de sesión, limpieza, arranque (GRUB/Plymouth)
manifests/      Versiones y sumas fijadas: packages.json, runtime.json, artifacts.json, themes.json, mason/plugins
assets/         Iconos, fuentes, fondos
system/boot/    Temas de arranque opcionales (GRUB, Plymouth, greeter) — componente `boot`
native/         `blue-crt` (efecto de terminal, componente opcional)
docs/           Guías por tema (instalador, wayland, temas, validación…)
tests/          Todas las pruebas (ver sección 8)
```

Fuente única: el escritorio instalado es una **copia** de estos directorios. No se edita lo instalado (los conflictos se
detectan por huella y se guardan como `incoming/`).

## 2. Componentes en ejecución

| Componente | Qué es | Arranca |
|---|---|---|
| Hyprland 0.55.x | Compositor, configuración Lua `~/.config/wysun/hyprland.lua` (de `config/.config/wysun/hyprland.lua`) | `wysun-session` (sesión “Wysun / Hyprland”) |
| `wysun-session-services` | Supervisor: `wysun-shell`, `wysun-idle` (swayidle configurable: bloqueo/pantalla), `wysun daemon`, `dunst`, polkit | Hyprland `exec` |
| Shell (`wysun-shell` → `runtime.sh` → Quickshell) | Barra, dashboard, lanzador QML, menús, notificaciones (vista), OSD, sesión, fondos | supervisor |
| `wysun daemon` (`orbit.py --daemon`) | Residente Qt: lanzador, portapapeles, Notas, procesos, OCR; socket `$XDG_RUNTIME_DIR/orbit-<uid>.sock` | supervisor |
| Dunst | Único dueño de D-Bus de notificaciones | supervisor |
| Apps (Music, Files, Settings, Recorder, Screenshot) | Ventanas Qt bajo demanda (`wysun <modo>`) | usuario |

### Shell (`apps/shell`)

`shell.qml` carga `Background`, `Drawers` (barra y paneles por pantalla), `AreaPicker`, `WysunBridge` y los demonios
`BatteryMonitor`, `IdleInhibit`. `daemons/Shortcuts.qml` (atajos globales de Quickshell) existe pero **no se carga**: los atajos
viven en `hyprland.lua`.

- **IPC**: `wysunShell` (en `apps/shell/wysun/WysunBridge.qml`): `toggle|open <superficie>`, `close`, `status`, `reloadPreferences`,
  `theme`, `openThemeSettings`. Superficies: `dashboard, launcher, menu, quicksettings, notifications, sidebar, windows, session`.
  Acceso: `wysun-shell <acción> [superficie]` (o `wysun shell …`). `wysun-shell status` devuelve JSON (pantallas, abiertas, esquema).
- **Capas Layer Shell**: espacio de nombres `wysun-*` (`wysun-drawers`, `wysun-background`, `wysun-border-exclusion`…). Las reglas de
  Hyprland usan `^wysun-.*$`.
- **Módulos QML del plugin** (`import Wysun.<X>`): `Config`, `Services`, `Components`, `Models`, `Blobs`, `Images`, `I18n`,
  `Multimedia`, `Settings`, `State`, `Shaders`, más `M3Shapes` (dependencia externa). Fuente en `apps/shell/plugin/src/Wysun/`.
- **Configuración del shell** (dato del usuario): `~/.config/wysun/shell/shell.json`, `shell-tokens.json` y
  `monitors/<salida>/…` (por pantalla). Antes `~/.config/wysun/caelestia` (el instalador la copia; la antigua se retira con
  `installer/clean_legacy.py`).
- **Colores**: `~/.local/state/wysun/scheme.json`, producido por `wysun scheme` (`apps/wysun/wysun_scheme.py`) a partir de los
  tokens de `apps/wysun/wysun_theme.json` (copia idéntica en `apps/capture/loomrec/ui/`; lo comprueba
  `tests/test_theme_tokens.py`). El shell los lee solo desde `scheme.json` (`services/Colours.qml`); `Appearance.qml` ya no existe.
  Ver `docs/themes.md`.

### Aplicaciones Qt (`apps/wysun`)

Módulos planos Python (se importan por nombre): `orbit.py` (lanzador/daemon), `music_*`, `files_*`, `notes_window`, `color_window`, `power_window`,
`theme_*`, `wayland_clipboard`, etc. `orbit-client` es el cliente ligero (socket) que invoca `bin/wysun`. Las preferencias de
usuario viven en `~/.config/orbit/` y `~/.local/share/orbit/` (sección 7).

### Captura (`apps/capture`)

Paquetes `loomrec` (Recorder) y `wybieshot` (Screenshot). Se instalan por **versiones inmutables** en
`~/.local/share/wysun/capture/releases/<hash>/` con wrappers `wysun-recorder`/`wysun-screenshot` que fijan `PYTHONPATH` a la
versión actual; no importan código de `~/.local/share/orbit/app`. Sus datos son independientes (`~/.local/share/loomrec`,
`~/.local/share/wybie-screenshot`). Tiene su propia suite: `python3 apps/capture/run_tests.py`.

## 3. Runtime del shell (Qt / Quickshell / plugin)

El shell no usa el Qt ni el Quickshell del sistema. `installer/runtime_build.py` construye un prefijo autocontenido:

```
$XDG_DATA_HOME/wysun/runtime/            (por defecto ~/.local/share/wysun/runtime; WYSUN_RUNTIME lo cambia)
  qt/6.9.3/gcc_64/        Qt de aqtinstall (base, declarative, shadertools, svg, tools, wayland, multimedia, qt5compat, imageformats)
  deps/                   libcava, M3Shapes y wayland-protocols 1.47 (XML) → lib/, lib/qt6/qml/M3Shapes, share/
  quickshell/bin/quickshell   Quickshell fijado (commit en manifests/runtime.json), DISTRIBUTOR=Wysun
  shell/lib/qt6/qml/Wysun/…   Plugin `Wysun.*`;  shell/lib/wysun/version
  RUNTIME.json            Sellos: qt, deps, quickshell, hash del plugin (para recompilar solo lo que cambió)
```

- **Reproducible**: todo está fijado en `manifests/runtime.json` (commits, versión de Qt/aqtinstall, suma de wayland-protocols). Las
  dependencias de compilación (`build_packages`) las instala el instalador con APT junto al componente `wayland`.
- **Idempotente**: `python3 installer/runtime_build.py` solo reconstruye lo que cambió (el plugin se recompila si cambia
  `apps/shell/{plugin,extras,CMakeLists.txt}`). Opciones: `--prefix`, `--cache`, `--jobs`, `--only qt,deps,quickshell,plugin`,
  `--print-packages`. Caché de compilación: `~/.cache/wysun/build`.
- **Arranque**: `apps/shell/wysun/runtime.sh` exporta `QML_IMPORT_PATH=<runtime>/shell/lib/qt6/qml:<runtime>/deps/lib/qt6/qml` y
  `WYSUN_LIB_DIR`, y ejecuta `quickshell -p <config>`. Los RPATH de los binarios eligen Qt; no se exporta `LD_LIBRARY_PATH`.
- **Cambiar el plugin C++**: editar `apps/shell/plugin`, `python3 installer/runtime_build.py` (o `./instalar.sh --orbit-only`),
  reiniciar el shell (sección 5).
- **Otra máquina**: `./instalar.sh` (componente `wayland`) instala paquetes de build, ejecuta `runtime_build.py` y despliega el
  shell. La construcción limpia Debian 13 terminó; el artefacto se revalidó tras corregir `libpulse0` (alcance en `docs/validation.md`).

## 4. Instalador (`instalar.sh` → `installer/main.py`)

Python estándar (+ PySide6 para la GUI). Instala por **componentes** (`desktop, wayland, terminal, editor, tools, boot`), con plan
(`--plan`, `--dry-run`), diario escrito antes de cada cambio, huellas por archivo, respaldo en
`~/.local/state/dotifails/backups/<id>/` y `flock`. Modos parciales que no tocan paquetes:

| Modo | Efecto |
|---|---|
| `--orbit-only` (`--wysun-only`) | Despliega `apps/wysun`, `apps/tools`, `apps/shell`, `apps/capture`, `bin/*`, migra nombres antiguos y reconstruye el runtime si cambió. No cambia atajos, notas, historial ni colores |
| `--scripts-only` | Herramientas y migración de scripts |
| `--installer-only` | El propio instalador y su CLI `dotifails` |
| `--boot-only` | GRUB/Plymouth/greeter (respalda `/etc` y `/boot`) |
| `--config-only` | Archivos de usuario sin paquetes |

Piezas: `main.py` (despliegue, restauración, `doctor`), `install_model.py` (componentes, paquetes, comprobaciones),
`wayland.py` (sesión Hyprland, shell, runtime, portales), `runtime_build.py`, `capture_distribution.py` (releases de captura),
`session_registration.py` (entrada de sesión en el gestor de acceso, reversible), `clean_legacy.py`, `boot*.py`, `gui.py`.
`WYSUN_SKIP_RUNTIME=1` omite el runtime (pruebas).

### Configuración general vs. de la máquina

- **General** (versionada): `config/`. Nada de monitores concretos, rutas personales ni nombres de equipo
  (`tests/check_manifest.py` rechaza `/home/<usuario>` y similares).
- **De esta máquina** (dato del usuario, nunca sobrescrito): `~/.config/wysun/local.lua` (plantilla
  `config/.config/wysun/local.lua.example`: monitores, escalas, atajos privados), `~/.config/orbit/hypr-monitors.lua` (disposición
  confirmada en Ajustes › Pantallas), `~/.config/wysun/shell/monitors/`, `~/.config/dotifails/machine.sh` (de `machines/`).
  `hyprland.lua` los carga al final, de modo que ganan sobre lo general.

## 5. Despliegue y rollback en un escritorio activo

Procedimiento seguro (el que se usó para el rebranding):

1. **Probar** en el repo: `python3 -m unittest discover -s tests`, y el runtime con HOME/XDG temporales.
2. **Respaldar**: `cp -a ~/.config/wysun ~/.config/orbit ~/.local/bin/wysun* ~/.local/share/wysun-backups/<fecha>/`,
   más `tar` de `~/.local/share/{wysun/quickshell,orbit/app}`. El instalador además guarda su propio respaldo por ejecución.
3. **Desplegar**: `./instalar.sh --orbit-only`. Si hay conflictos, no sobrescribe; revisar `incoming/` en el respaldo.
4. **Reiniciar solo el shell** (no Hyprland): `pkill -x quickshell; setsid ~/.local/bin/wysun-shell >~/.local/state/wysun/shell.log 2>&1 &`.
   `~/.local/bin/orbit reload` recarga solo el residente Qt.
5. **Validar** en la sesión real: `wysun-shell status`, `hyprctl layers | grep wysun`, abrir dashboard/launcher/menu/session,
   comprobar cada monitor (`hyprctl monitors`), y hacer capturas con `grim -o <salida>`.

**Rollback**

| Qué | Cómo |
|---|---|
| Archivos desplegados | `dotifails restore [id]` (o `~/.local/share/dotifails/installer/main.py restore`) devuelve el respaldo del instalador |
| Hyprland | Restaurar `~/.config/wysun/hyprland.lua` del respaldo y `hyprctl reload` |
| Runtime | El runtime es otro directorio; para volver a uno anterior mover/restaurar `…/wysun/runtime` (la copia previa queda en `~/.local/share/wysun-backups/`) |
| Limpieza de restos | `installer/clean_legacy.py --restore <vault>` (mueve, no borra) |
| Sesión no arranca | Elegir otra sesión en el gestor de acceso; `installer/session_registration.py` desregistra Wysun sin tocar el predeterminado |
| Shell caído | `wysun-shell` lo relanza; si el plugin falla: `python3 installer/runtime_build.py --only plugin` |

Nunca reiniciar Hyprland ni el login para actualizar un panel.

## 6. Atajos, tema y ajustes (para las siguientes olas)

- **Atajos**: `config/.config/wysun/hyprland.lua` (Hyprland 0.55, Lua). Atajos privados en `~/.config/wysun/local.lua`.
  Los de captura apuntan a `wysun screenshot …` / `wysun recorder …`. `apps/shell/daemons/Shortcuts.qml` está disponible si se decide mover atajos al shell.
- **Cheat sheet** (`Super+/`, `apps/shell/modules/cheatsheet`): `backend.py` vuelve a leer `~/.config/wysun/hyprland.lua`
  en cada apertura, sin caché. Un bind nuevo aparece solo si lleva `description="Wysun | <Categoría> | <texto>"`
  (por ejemplo `{description="Wysun | Notes | Quick note"}`): se lista en esa categoría con ese texto y una categoría
  nueva se crea sola, al final de las conocidas (Shell, Apps, Windows, Workspaces, Capture, Media, Session). El texto
  va en inglés. Las etiquetas de procedencia heredadas (`equivalent`, `adapted`, `extra`, `no-equivalent`, `private`,
  `session`, `overview`, `cheatsheet`, `emoji`) no cuentan como categoría: esos binds conservan la etiqueta
  derivada del dispatcher. Si dos binds usan las mismas teclas, el último gana. Prueba: `tests/shell_bridge/test_cheatsheet.py`.
- **Lanzador** (estilo Raycast): `wysun` abre un único panel flotante (`apps/shell/modules/launcher`: `Launcher.qml` ventana
  overlay, `LauncherPanel.qml` lógica y vistas, `services/LauncherIndex.qml` índices en memoria). No existe lanzador Qt ni
  alternativo: si el shell no responde, el comando falla con un mensaje. Sin pestañas ni prefijos: una lista agrupada
  (Suggestions, Applications, Files, Commands, Windows, Clipboard, Snippets) filtrada en JS (`Search.js`, `Results.js`,
  `Calc.js` para la calculadora en línea) sobre datos precalculados; archivos por `find` asíncrono en streaming con
  debounce de 120 ms; portapapeles y snippets se cargan una vez al abrir con `apps/wysun/launcher_data.py` (mismo
  almacén que el residente). Las «vistas» (Clipboard History, Snippets, Windows, Files, Applications, System…) se
  apilan con push/pop (Escape o Backspace con la búsqueda vacía vuelven). Ctrl+K abre las acciones del elemento
  (`Actions.js`), Ctrl+1..9 selecciona, Tab enfoca la vista previa. `wysun clipboard|snippets|windows|calculator` abren la
  vista correspondiente y `emoji` el cajón de emojis; `power|audio|notifications|calendar|system` abren las superficies del
  shell. El residente Qt (`orbit.py`) ya no muestra menús: aloja utilidades (Notas, Música, Herramientas…) y registra el
  historial del portapapeles.
- **Panel de sesión**: `Super+X` alterna el panel lateral de sesión (salir, apagar, suspender, reiniciar) en el monitor
  enfocado y Escape lo cierra. `Ctrl+X` no está asignado: vuelve a ser Cortar en las aplicaciones. Los paneles invocados explícitamente conservan máscara interactiva y capa overlay
  sobre fullscreen; no dejan un foco invisible.
- **Settings y conexiones**: páginas nativas de Nexus (`apps/shell/modules/nexus`). `wysun settings [ruta]`
  abre las páginas registradas por `SettingsRoutes.js`; Displays y Workspaces son entradas principales en inglés.
  `apps/shell/wysun/display_bridge.py` atiende exclusivamente distribución de monitores (prueba, confirmación y
  reversión con watchdog independiente) y asignaciones persistentes de workspaces por monitor. Reutiliza
  `environment_settings.py`, `display_layout.py` y `hypr_settings.py`. No hay sección Escritorio ni páginas
  Terminal, Notificaciones, Inicio, Archivos y copias, Efectos, Ventanas, Atajos, SSH o Processes en Settings.
  Wi-Fi, VPN y Bluetooth usan Red y Dispositivos conectados. `wysun processes` se gestiona fuera de Nexus.
- **Tema**: Space Black (`space-black`, `tokyo`, `severance`) y Fluent (`light`, `dark`); selección en
  `~/.config/orbit/theme.json`. Los tokens viven en `apps/wysun/wysun_theme.json`; Quickshell los lee por
  `apps/shell/services/Colours.qml` (vía `scheme.json`); `tests/test_theme_literals.py` rechaza colores literales
  (excepciones: `theme-exception: motivo`). Guía: `docs/themes.md`.

## 7. Identidades técnicas heredadas (se conservan a propósito)

| Identidad | Uso |
|---|---|
| `~/.local/share/orbit/{app,tools,music,notes,…}`, `~/.config/orbit/`, `orbit.sqlite3` | Código instalado y datos privados del lanzador/apps |
| Comando `orbit`, `orbit-files`, `orbit-tools`, sockets `orbit-*.sock`, `orbit-files.desktop` (portal de archivos) | Compatibilidad con atajos, portales y asociaciones MIME |
| `loomrec`, `wybie-screenshot` (paquetes, wrappers, `~/.local/share/loomrec`) | Identidades de captura y sus datos |

Retirados en esta parte: nombres Caelestia (módulos, plugin, rutas, IPC, namespaces de capa), alias `musica`/`musika`, perfiles
`profiles/` (ahora `machines/`), módulos Python sin uso (`files_preview`, `service_runtime`, `theme_widgets`), demonios QML sin
uso (`GameMode`, `IdleMonitors`) y la infraestructura de CI/nix del shell original.

## 8. Pruebas

```sh
python3 -m unittest discover -s tests -v                       # núcleo: instalador, temas, sesión, wayland, herramientas…
python3 -m unittest discover -s tests/wysun_app -t tests       # apps Qt (antes apps/wysun/test_*.py y apps/wysun/tests)
python3 -m unittest discover -s tests/shell_bridge -t tests    # puente del shell (backend.py, dispatcher wysun-shell)
QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py
python3 tests/check_manifest.py
python3 apps/capture/run_tests.py                              # captura (medios serializados)
python3 tests/wysun_installed_smoke.py                         # sobre la instalación real
```

Pruebas de sockets/compositor requieren acceso de sesión; un bloqueo de sandbox no prueba un fallo del producto. Las seis
expectativas antiguas de `tests/wysun_app` se corrigieron en `d5017d01`; la suite general P2-B pasó 374 pruebas antes de integrar
P2-A. Las comprobaciones dirigidas de integración y el alcance del despliegue están en `docs/validation.md`.

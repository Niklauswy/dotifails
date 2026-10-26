# Wysun · arquitectura

Entorno de escritorio personal sobre **Hyprland (Wayland)**: shell en Quickshell/QML con plugin C++ propio, aplicaciones Qt
(PySide6), captura de pantalla/vídeo, instalador reversible y sesión registrada de forma independiente. Este documento es la
referencia para quien modifique el repositorio (atajos, lanzador, Ajustes, tema).

Nombres visibles: **Wysun**, **Wysun Recorder**, **Wysun Settings**. Wysun es también el único nombre técnico: comandos,
paquetes, rutas, sockets, variables y desktop ids (sección 7). El código derivado del shell GPL-3.0 de terceros conserva créditos en `THIRD_PARTY.md`,
`apps/shell/LICENSE` y `apps/shell/UPSTREAM.json`; ningún identificador de ejecución depende ya de ese proyecto.

## 1. Estructura del repositorio

```
apps/
  shell/        Shell Quickshell (QML) + plugin C++ `Wysun.*`        → ~/.local/share/wysun/quickshell
  python/       Raíz de paquetes Python (un paquete por app, nada suelto)  → ~/.local/share/wysun/app
                wysun_core, wysun_music, wysun_files, wysun_media, wysun_player, wysun_pdf,
                wysun_settings, wysun_services (backends del shell y residente), vendor/
  recorder/     Wysun Recorder (paquete wysun_recorder)              → ~/.local/share/wysun/capture/releases/<hash>
  tools/        `wysun tools` (dev, audit, share, cloud, vpn, resets) → ~/.local/share/wysun/tools
bin/            `wysun` (único punto de entrada) y los programas de la sesión (wysun-shell, wysun-session, wysun-lock, wysun-wm, …) → ~/.local/bin
config/         Configuración GENERAL (dotfiles): .config/{wysun,ghostty,nvim,gtk-*,…}, .local/{bin,share/applications,icons}
machines/       Perfiles opcionales por equipo (p. ej. samsung-touchscreen.sh); nunca se aplican por defecto
installer/      Instalador (CLI + GUI), constructor del runtime, registro de sesión, limpieza, arranque (GRUB/Plymouth)
manifests/      Versiones y sumas fijadas: packages.json, runtime.json, artifacts.json, themes.json, mason/plugins
assets/         Iconos, fuentes, fondos
system/boot/    Arranque Macrodata (GRUB, Plymouth) y su generador; la pantalla de acceso (greetd) es apps/shell/greeter.qml
docs/           Guías por tema (instalador, wayland, temas, validación…)
tests/          Todas las pruebas (ver sección 8)
```

Fuente única: el escritorio instalado es una **copia** de estos directorios. No se edita lo instalado (los conflictos se
detectan por huella y se guardan como `incoming/`).

**Punto de entrada único: `bin/wysun`** (solo biblioteca estándar; no importa la app). Superficies y acciones del shell van a
`wysun-shell` por IPC (`wysun`, `wysun SUPERFICIE`, `clipboard`, `calculator`, `color-pick`, `settings [PÁGINA]`); apps y servicios
se ejecutan con `python3 -P -m <módulo>` y `~/.local/share/wysun/app` (o `…/tools`) en `PYTHONPATH` (`music`, `music-mini`,
`files`, `pdf`, `player`, `scheme`, `wallpaper`, `workspaces`, `tools`, `daemon`, `reload`); `shell`, `lock`, `recover`,
`recorder`, `session-check`, `install`, `doctor` y `activate` pasan a su programa (`wysun-shell`, `wysun-lock`, `wysun-recover`,
`wysun-recorder`, `wysun-session`, `wysun-install`, `wysun-wm`). No hay alias; `wysun --help` lista las órdenes y
`tests/shell_bridge/test_dispatcher.py` lo comprueba. `wysun-install` sigue existiendo porque el instalador también se publica
sin el componente `desktop`.

## 2. Componentes en ejecución

| Componente | Qué es | Arranca |
|---|---|---|
| Hyprland 0.55.x | Compositor, configuración Lua `~/.config/wysun/hyprland.lua` (de `config/.config/wysun/hyprland.lua`) | `wysun-session` (sesión “Wysun / Hyprland”) |
| `wysun-session-services` | Supervisor: `wysun-shell`, `wysun-idle` (swayidle configurable: bloqueo/pantalla), `wysun daemon`, polkit | Hyprland `exec` |
| Shell (`wysun-shell` → `runtime.sh` → Quickshell) | Barra, dashboard, lanzador QML, menús, notificaciones (vista), OSD, sesión, fondos | supervisor |
| `wysun daemon` (`python3 -m wysun_services.daemon`) | Residente Qt sin ventanas: registra el historial del portapapeles; `wysun reload` lo reinicia con el código instalado; socket `$XDG_RUNTIME_DIR/wysun-daemon-<uid>.sock`. El lanzador, Colors, Processes y Settings son del shell; Music y Files son procesos propios | supervisor |
| Shell (Quickshell) | Único dueño de D-Bus de notificaciones (`NotificationServer` en `apps/shell/services/Notifs.qml`); No molestar: `wysun-shell dnd on\|off\|toggle\|status` | supervisor |
| Apps (Music, Files, Player, Recorder) | Ventanas Qt bajo demanda (`wysun <modo>`), cada una en su proceso | usuario |

### Shell (`apps/shell`)

`shell.qml` carga `Background`, `Drawers` (barra y paneles por pantalla), `AreaPicker`, `WysunBridge` y los demonios
`BatteryMonitor`, `IdleInhibit`. Los atajos viven en `hyprland.lua`.

- **IPC**: `wysunShell` (en `apps/shell/wysun/WysunBridge.qml`): `toggle|open <superficie>`, `surfaces`, `close`, `status`,
  `reloadPreferences`, `theme`, `openThemeSettings`. La **única lista de superficies** es `surfaces` de ese archivo
  (`wysun-shell surfaces` la imprime: dashboard, windows, overview, cheatsheet, wallpapers, launcher, emoji, menu, quicksettings,
  notifications, sidebar, session, ai, colors, processes). `wysun SUPERFICIE` y `wysun-shell SUPERFICIE` la alternan; ningún
  lanzador repite la lista y el shell responde `false` a un nombre que no conoce. `wysun-shell status` devuelve JSON.
- **Capas Layer Shell**: espacio de nombres `wysun-*` (`wysun-drawers`, `wysun-background`, `wysun-border-exclusion`…). Las reglas de
  Hyprland usan `^wysun-.*$`.
- **Módulos QML del plugin** (`import Wysun.<X>`): `Config`, `Services`, `Components`, `Models`, `Blobs`, `Images`, `I18n`,
  `Multimedia`, `Settings`, `State`, `Shaders`, más `M3Shapes` (dependencia externa). Fuente en `apps/shell/plugin/src/Wysun/`.
- **Configuración del shell** (dato del usuario): `~/.config/wysun/shell/shell.json` y
  `monitors/<salida>/…` (por pantalla).
- **Transición de fondos**: `background.wallpaperTransition = "ZoomBlurPull"` usa un acercamiento gradual del fondo
  anterior, fundido con la imagen nueva nítida y un asentamiento final. Sus parámetros viven en
  `appearance.wallpaperMotion` de los tokens nativos (`plugin/src/Wysun/Config/tokens.hpp`), con duración propia de
  1400 ms, multiplicada por la escala de animaciones del usuario. Son exclusivos del shell y no están en `tokens.json`.
  El desenfoque solo muestrea cinco veces la imagen saliente; la entrante conserva su nitidez. Los demás efectos
  mantienen su duración y curva. Funciona con el mismo compositor de transición para imágenes, GIF y vídeo.
- **Captura de pantalla** (`modules/areapicker`): `wysun-shell screenshot [--annotate] [--path DIR] [--no-save]` (IPC
  `picker screenshot|region|accept|close`). Congela cada salida con wlr-screencopy en el propio shell, sin otro proceso ni ventana:
  el puntero no se mueve, los cajones ignoran el hover (`ShellState.capturing`) y un atajo repetido no abre otra. La selección
  cuelga de cuatro hilos atados a las esquinas (física de muelle, tokens `sizes.screenshot`). Clic = ventana, arrastrar =
  región, Enter = salida completa; luego se ajusta por sus nodos. Barra: copiar y guardar (Enter), anotar (A: lápiz,
  rotulador, línea, flecha, rectángulo, elipse, texto, numerador y pixelado, con deshacer) o texto por OCR (T, Tesseract
  `spa+eng`, editable antes de copiar).
- **Uso de IA** (`modules/aiusage`, servicio `services/AiUsage.qml`): panel que baja de la esquina superior derecha al pasar
  el ratón (o `wysun-shell toggle ai`). Pestañas: Resumen y una por cuenta (Alt+1…9, Ctrl+Tab, Ctrl+R refresca, Esc cierra;
  mientras está abierto toma el teclado con el mismo `HyprlandFocusGrab` que los demás paneles). Cada cuenta muestra plan, límites
  con su ritmo y tokens/coste estimado de 24 h, 7, 30 y 90 días. `backend.py` no lee credenciales: Codex responde con su propia
  sesión vía `codex app-server` (`account/read`, `account/rateLimits/read`) y Claude Code deja el estado de cada cuenta en
  `~/.local/state/wysun/ai-usage` mediante `modules/aiusage/statusline-hook.py`, que llama la statusline de cada carpeta de Claude:
  `claude-<clave>.json` (límites y carpeta; la clave es un hash de `CLAUDE_CONFIG_DIR`, así que carpetas con el mismo nombre no se
  pisan, y un snapshot sin límites nunca borra ni tapa uno que sí los trae) y `sessions/<id de sesión>` (la clave de la cuenta que
  corrió esa sesión; los logs de Claude no nombran su cuenta, así que con esto los tokens se reparten por cuenta aunque compartan
  `projects/` por enlace simbólico). Las sesiones de Claude anteriores al hook y las carpetas sin marcador se asignan a la primera
  cuenta que lee esos logs; los marcadores se borran a los 90 días. Las cuentas de Claude se descubren solas: cada carpeta cuyo hook
  ha corrido aparece sin tocar `ai-accounts.json` (y desaparece si se borra la carpeta). Los nombres anteriores (`claude.json` y
  `claude-<carpeta>.json`) se siguen leyendo; el segundo solo mientras ninguna otra cuenta de Claude tenga esa carpeta. El plan de
  Claude sale de `oauthAccount` en `.claude.json`.
  Las sesiones de Codex llevan `creator_account_id`, así que el historial se reparte por cuenta y las cuentas sin sesión iniciada
  aparecen como pestañas de solo historial. Etiquetas y carpetas extra: `~/.config/wysun/ai-accounts.json`
  (`{"accounts": [{"provider": "codex", "home": "…"} | {"provider": "codex", "accountId": "…", "label": "…"}]}`).
  Cuenta nueva de Codex: iniciar sesión en la misma carpeta (aparece sola por su historial) o en otra con
  `CODEX_HOME=<carpeta> codex login`, que se añade a ese archivo para tener límites en vivo. Cuenta nueva de Claude: basta con que
  su `settings.json` tenga una statusline que llame al hook (el comando exacto, con y sin script de
  statusline propio, está en el docstring de `statusline-hook.py`); no hay nada más que
  configurar, y `ai-accounts.json` solo sirve para ponerle etiqueta. Las carpetas de logs se leen por su ruta real, de modo que una
  carpeta compartida por enlace simbólico entre cuentas cuenta una sola vez.
  Caché incremental en `~/.cache/wysun/ai-usage`; precios en `modules/aiusage/pricing.json`, ampliables en
  `~/.config/wysun/ai-pricing.json`; logotipos de lobe-icons (MIT) en `Logos.js`.
  También hay desglose por proyecto (carpeta de la sesión; los worktrees se suman a su repo) y una entrada `aiUsage` en la barra
  con el límite más ajustado. Fuera del panel se refresca cada `backgroundInterval` y avisa con `notify-send` una vez por ventana al
  llegar a `alertThreshold` (10 % por defecto) y otra al reiniciarse; lo ya avisado vive en `~/.local/state/wysun/ai-usage/alerts.json`.
  La última instantánea se guarda en `~/.cache/wysun/ai-usage/snapshot.json`, así el primer hover tras reiniciar ya tiene datos.
- **Colores**: `~/.local/state/wysun/scheme.json`, producido por `wysun scheme` (`wysun_services.scheme`) a partir de los
  tokens de `apps/python/wysun_core/tokens.json` (las releases del Recorder lo llevan dentro de su `wysun_core`).
  El shell los lee desde `scheme.json` (`services/Colours.qml`) y, mientras no exista, pinta la paleta base
  `palettes.<modo>.scheme` de `~/.local/share/wysun/theme/tokens.json`; `Appearance.qml` ya no existe.
- **Tokens de forma y movimiento del shell**: el instalador (`installer/wayland.py`, `deploy_tokens`) copia
  `apps/python/wysun_core/tokens.json` a `~/.local/share/wysun/theme/tokens.json`; el plugin lo lee una vez al arrancar
  (`TokenConfig`) y `plugin/src/Wysun/Config/tokens.hpp` es solo el respaldo (paridad en `tests/test_shell_tokens.py`).
  Ver `docs/themes.md`.

### Aplicaciones Qt (`apps/python`)

El lector local **Wysun PDF** (`wysun pdf`) es el paquete `wysun_pdf` (`app`, `window` y un proceso `engine` aislado
para PyMuPDF); documentación y límites en `docs/pdf-reader.md`.

`apps/python` es una raíz de paquetes: cada app se ejecuta como módulo (`python3 -P -m wysun_music`, `wysun_files`,
`wysun_player`, `wysun_pdf`) con esa raíz en `PYTHONPATH`, que fijan los lanzadores de `bin/` (`bin/wysun` la deduce de su
propia ubicación: `../share/wysun/app` instalado, `../apps/python` en el repositorio) y el shell (`Paths.python()` en
`apps/shell/utils/Paths.qml`: `env PYTHONPATH=<app> python3 -s -P -m …`; `-I` no sirve porque ignora `PYTHONPATH`). Un
proceso que lanza otro módulo usa `wysun_core.launch` (misma raíz, `-P`). Ningún código añade rutas a `sys.path`, salvo
`wysun_services.scheme`, que pone `vendor/` (materialyoucolor) junto a los paquetes. `wysun_settings` reúne Ajustes
(`environment`, `hypr`, `data`, `runtime`, `display_layout`, `workspace_layout`, `theme_runtime`) y `wysun_services` los
backends del shell (`launcher_data`, `code_preview`, `process_data`, `utility_data`, `color_data`, `scheme`, `wallpaper_media`…),
y el residente (`daemon`). Las preferencias de usuario viven en `~/.config/wysun/` y los datos en
`~/.local/share/wysun/` (sección 7).

### Wysun Player y `wysun_media` (`apps/python/wysun_media`, `wysun_player`)

Visor único de imágenes, video y audio (`wysun player`) y el componente reutilizable que lo implementa
(`MediaPlayer`). Un proceso por usuario atiende todas las ventanas mientras haya alguna (socket en `$XDG_RUNTIME_DIR`); Files
abre ahí cualquier medio y embebe el mismo componente en su panel de detalles; Recorder lo embebe en su página de reproducción.
El paquete no importa ningún módulo del anfitrión: cada app instala un `Host` con su tema (`wysun_player.host` en Wysun,
`wysun_recorder/ui/media_host.py` en Recorder). Reproduce con libmpv (OpenGL y decodificación por hardware con copia de vuelta;
respaldo por software), decodifica imágenes con `QImageReader` en segundo plano y publica MPRIS. Detalle, atajos, decisiones y
diagnóstico: `docs/player.md`. `apps/recorder/wysun_media` es un enlace al mismo código y cada release de Recorder lleva su copia.

### Captura (`apps/recorder`)

Paquete `wysun_recorder` (Recorder). Se instala por **versiones inmutables** en
`~/.local/share/wysun/capture/releases/<hash>/` con el wrapper `wysun-recorder`, que fija `PYTHONPATH` a la versión actual; no
importa código de `~/.local/share/wysun/app`. Sus datos son independientes (`~/.local/share/wysun/recorder`). Tiene su propia suite:
`python3 apps/recorder/run_tests.py`. Las capturas de pantalla son del shell
(`wysun-shell screenshot`).

**Grabación de pantalla**: la elección (ventana/región/pantalla), la cuenta atrás y el HUD viven en el shell
(`wysun-shell record [start|toggle|pause|stop]`, IPC `recorder`; `modules/areapicker` en modo `record` + `modules/recorder`);
el worker independiente de `wysun_recorder` hace la captura y `wysun recorder --start JSON` lo arranca sin ventana. La ventana Qt
`wysun recorder` es solo biblioteca, reproducción con el componente compartido `wysun_media` y ajustes (`wysun_recorder/ui/app_*.py`, patrón de Music/Files). Atajos:
`Super+Shift+L`/`R` alternan (elegir y grabar / terminar), `Ctrl+Shift+R` pausa, `Ctrl+Shift+S` termina.

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
- **Cambiar el plugin C++**: editar `apps/shell/plugin`, `python3 installer/runtime_build.py` (o `./instalar.sh --wysun-only`),
  reiniciar el shell (sección 5).
- **Otra máquina**: `./instalar.sh` (componente `wayland`) instala paquetes de build, ejecuta `runtime_build.py` y despliega el
  shell. La construcción limpia Debian 13 terminó; el artefacto se revalidó tras corregir `libpulse0` (alcance en `docs/validation.md`).

## 4. Instalador (`instalar.sh` → `installer/main.py`)

Python estándar (+ PySide6 para la GUI). Instala por **componentes** (`desktop, wayland, terminal, editor, tools, boot`), con plan
(`--plan`, `--dry-run`), diario escrito antes de cada cambio, huellas por archivo, respaldo en
`~/.local/state/wysun/install/backups/<id>/` y `flock`. Modos parciales que no tocan paquetes:

| Modo | Efecto |
|---|---|
| `--wysun-only` | Despliega `apps/python`, `apps/tools`, `apps/shell`, `apps/recorder`, `bin/*`, retira los lanzadores de versiones anteriores (`RETIRED_COMMANDS`: solo los suyos sin cambios y que `~/.config/wysun/*.lua` ya no llama) y reconstruye el runtime si cambió. No cambia atajos, notas, historial ni colores |
| `--scripts-only` | Herramientas de terminal (`wysun tools`) y el lanzador `wysun` |
| `--installer-only` | El propio instalador y su CLI `wysun-install` (`wysun install`) |
| `--boot-only` | GRUB/Plymouth/greeter (respalda `/etc` y `/boot`) |
| `--config-only` | Archivos de usuario sin paquetes |

Piezas: `main.py` (despliegue, restauración, `doctor`), `install_model.py` (componentes, paquetes, comprobaciones),
`wayland.py` (sesión Hyprland, shell, runtime, portales), `runtime_build.py`, `capture_distribution.py` (releases de captura),
`session_registration.py` (entrada de sesión en el gestor de acceso, reversible), `boot*.py`, `gui.py`.
`WYSUN_SKIP_RUNTIME=1` omite el runtime (pruebas).

La nueva base gráfica se abre con `./wysun-installer`; `./wysun-installer-preview` recorre una instalación nueva con
operaciones simuladas en memoria. `preview_process.py` separa esa demostración de `process_runner.py`. El gestor instalado
lleva un subconjunto de los controles Material de Music/Files, fuentes y tokens mediante `ui_support.py`, por lo que puede
abrir antes de instalar el escritorio y sin conservar el checkout. Recorrido y piezas visuales en `scenes.py`;
`docs/installer.md` documenta el funcionamiento y los límites de validación.

Las opciones explícitas `--prepare-repositories` y `--upgrade-system` preparan backports nativos y actualizaciones de la
distribución actual, respectivamente. Se actualizan índices y se resuelven dependencias antes del upgrade. La preparación
de fuentes tiene su propio diario bajo `/var/lib/wysun/repositories/backups/`; no se reemplazan fuentes ajenas ni claves.
La recuperación de archivos no revierte paquetes. Estos modos no se combinan con `--config-only` o `--only`.

### Configuración general vs. de la máquina

- **General** (versionada): `config/`. Nada de monitores concretos, rutas personales ni nombres de equipo
  (`tests/check_manifest.py` rechaza `/home/<usuario>` y similares).
- **De esta máquina** (dato del usuario, nunca sobrescrito): `~/.config/wysun/local.lua` (plantilla
  `config/.config/wysun/local.lua.example`: monitores, escalas, atajos privados), `~/.config/wysun/hypr-monitors.lua` (disposición
  confirmada en Ajustes › Pantallas), `~/.config/wysun/shell/monitors/`, `~/.config/wysun/machine.sh` (de `machines/`).
  `hyprland.lua` los carga al final, de modo que ganan sobre lo general.

## 5. Despliegue y rollback en un escritorio activo

Procedimiento seguro (el que se usó para el rebranding):

1. **Probar** en el repo: `python3 -m unittest discover -s tests`, y el runtime con HOME/XDG temporales.
2. **Respaldar**: `cp -a ~/.config/wysun ~/.local/bin/wysun* ~/.local/share/wysun-backups/<fecha>/`,
   más `tar` de `~/.local/share/wysun/{quickshell,app}`. El instalador además guarda su propio respaldo por ejecución.
3. **Desplegar**: `./instalar.sh --wysun-only`. Si hay conflictos, no sobrescribe; revisar `incoming/` en el respaldo.
4. **Recargar**: `wysun reload` reinicia el residente del portapapeles con el código nuevo; las apps toman el código nuevo al
   abrirse. Si cambió `apps/shell` o el plugin, reiniciar solo el shell (no Hyprland):
   `pkill -x quickshell; setsid ~/.local/bin/wysun-shell >~/.local/state/wysun/shell.log 2>&1 &`.
5. **Validar** en la sesión real: `wysun-shell status`, `hyprctl layers | grep wysun`, abrir dashboard/launcher/menu/session,
   comprobar cada monitor (`hyprctl monitors`), y hacer capturas con `grim -o <salida>`.

**Rollback**

| Qué | Cómo |
|---|---|
| Archivos desplegados | `wysun-install restore [id]` (o `~/.local/share/wysun/installer/main.py restore`) devuelve el respaldo del instalador |
| Hyprland | Restaurar `~/.config/wysun/hyprland.lua` del respaldo y `hyprctl reload` |
| Runtime | El runtime es otro directorio; para volver a uno anterior mover/restaurar `…/wysun/runtime` (la copia previa queda en `~/.local/share/wysun-backups/`) |
| Sesión no arranca | Elegir otra sesión en el gestor de acceso; `installer/session_registration.py` desregistra Wysun sin tocar el predeterminado |
| Shell caído | `wysun-shell` lo relanza; si el plugin falla: `python3 installer/runtime_build.py --only plugin` |

Nunca reiniciar Hyprland ni el login para actualizar un panel.

## 6. Atajos, tema y ajustes (para las siguientes olas)

- **Atajos**: `config/.config/wysun/hyprland.lua` (Hyprland 0.55, Lua). Atajos privados en `~/.config/wysun/local.lua`.
  Los de captura apuntan a `wysun-shell screenshot …` / `wysun recorder …`.
- **Cheat sheet** (`Super+/`, `apps/shell/modules/cheatsheet`): `backend.py` vuelve a leer `~/.config/wysun/hyprland.lua`
  en cada apertura, sin caché. Un bind nuevo aparece solo si lleva `description="Wysun | <Categoría> | <texto>"`
  (por ejemplo `{description="Wysun | Notes | Quick note"}`): se lista en esa categoría con ese texto y una categoría
  nueva se crea sola, al final de las conocidas (Shell, Apps, Windows, Workspaces, Capture, Media, Session). El texto
  va en inglés. Las etiquetas de procedencia heredadas (`equivalent`, `adapted`, `extra`, `no-equivalent`, `private`,
  `session`, `overview`, `cheatsheet`, `emoji`) no cuentan como categoría: esos binds conservan la etiqueta
  derivada del dispatcher. Si dos binds usan las mismas teclas, el último gana. Prueba: `tests/shell_bridge/test_cheatsheet.py`.
- **Wallpapers animados y carrusel** (`Super+Shift+W`, `wysun shell wallpapers`, Settings > Wallpaper & style > Browse as carousel):
  el fondo puede ser PNG/JPEG/WebP/… o vídeo `mp4`/`webm`/`mkv`/GIF. `modules/background/WallpaperVisual.qml` usa `Visual`
  (QtMultimedia, decodificación por hardware VAAPI cuando existe) para vídeo y `AnimatedImage` para GIF, en todos los monitores.
  `Wallpapers.suspendedOn(pantalla)` pausa la reproducción bajo una ventana fullscreen de esa pantalla o con batería baja
  (≤30 % y descargando). El esquema Material You sale de un fotograma (`wallpaper_media.scheme_frame`, ffmpeg, caché en
  `~/.cache/wysun/wallpapers/frames`). Las miniaturas del carrusel las genera un worker (`wysun wallpaper thumbs`, caché en
  `~/.cache/wysun/wallpapers/thumbs`) bajo demanda; `wysun wallpaper list` enumera `~/Pictures/Wallpapers[/Animated]`,
  `~/.local/share/backgrounds` y `wallpaper.folders` de `environment.json`. El carrusel solo mantiene vivas ±8 tarjetas
  (`modules/wallpaperpicker`) y reproduce en vivo la tarjeta central animada tras 450 ms de reposo. IPC de diagnóstico:
  `wysun-shell`'s `ipc call wallpapers go|select|filter|apply|state` (solo con el selector abierto). Pruebas: `tests/test_wallpaper_media.py`.
- **Lanzador** (estilo Raycast): `wysun` abre un único panel flotante (`apps/shell/modules/launcher`: `Launcher.qml` ventana
  overlay, `LauncherPanel.qml` lógica y vistas, `services/LauncherIndex.qml` índices en memoria). No existe lanzador Qt ni
  alternativo: si el shell no responde, el comando falla con un mensaje. Diseño Material 3 Expressive (superficie sólida,
  cápsula de búsqueda con forma M3 que se transforma, filas con selección tonal y entrada escalonada). Pestañas All, Apps,
  Files y Clipboard (Ctrl+Tab las recorre); «All» es una lista agrupada (Suggestions, Applications, Commands, Files,
  Clipboard) filtrada en JS (`Search.js`, `Results.js`, `Calc.js` para la calculadora en línea; el JS de QML no admite
  lookbehind en expresiones regulares) sobre datos precalculados; archivos por un índice en memoria de todo el home (`launcher_data.py files-index` lo escribe en
  `~/.local/share/wysun/launcher-files.idx`; incluye ocultos y `~/.config`) que `FileSearch.mjs` recorre en cada tecla dentro de un
  `WorkerScript` (`FileSearchWorker.mjs`, fuera del hilo de la interfaz; las teclas pulsadas durante una búsqueda se
  agrupan en la última consulta):
  recursivo, con carpeta de ámbito dentro de una carpeta, tokens AND sobre nombre y ruta, subsecuencias y estrechamiento
  incremental; las imágenes del portapapeles se buscan por el texto reconocido con Tesseract (`act ocr-pending` rellena
  las pendientes; Alt+K › Copy Text from Image). Los archivos de texto, código y dotfiles se abren en Neovim: la vista
  previa de código se despega del panel, se expande sobre el espacio de trabajo y se asienta en la baldosa de la terminal, una ventana normal en mosaico de clase `wysun.edit` (`EditMorph.qml`,
  `services/Editor.qml`; `wysun-shell ipc call editor open <ruta>` lo reproduce) y la vista previa de código usa la paleta del
  NvChad activo (`nvim_theme.py`, marcado StyledText de Qt, no RichText: se maqueta ~7 veces más rápido) servida por
  `apps/python/wysun_services/code_preview.py` (primeras 120 líneas, caché en `~/.cache/wysun/code-preview` por archivo, fecha y tema; la
  vista previa guarda además en memoria las ya vistas); el portapapeles se carga una vez al abrir con `apps/python/wysun_services/launcher_data.py` (mismo almacén que el residente).
  Ranking aprendido (`services/Usage.js`, guardado en `launcher.json`): frecencia por entrada (últimos usos con vida media de
  5 días y horas habituales) y lo que se eligió tras cada texto escrito (`picks`); solo reordena coincidencias, nunca
  añade resultados. Las sugerencias vacías mezclan fijados, frecencia y la frecuencia histórica de AppDb, con 3 archivos
  como máximo. Las páginas de Ajustes (`Catalog.settings()`, palabras clave en español e inglés) aparecen como grupo
  «Settings» y se abren con `wysun settings <ruta>`. Las
  vistas (Clipboard History, Files, Applications, Calculator History, Open With) se apilan con push/pop (Escape o Backspace
  con la búsqueda vacía vuelven). La vista previa (`PreviewPane.qml`) cambia según el tipo: imagen sobre su copia difuminada,
  vídeo en bucle y sin sonido, primera página de PDF, código con números de línea, Markdown renderizado, contenido de
  carpetas, colores y enlaces. Alt+K abre las acciones del elemento (`Actions.js`; Alt+Enter para la secundaria y Alt+Supr para borrar), Ctrl+1..9 selecciona, Tab enfoca la
  vista previa. Flecha derecha o clic en la imagen/vídeo amplía la vista dentro del lanzador; Escape/izquierda vuelve.
  Los emojis y números tienen composición ampliada; los enlaces muestran una cabecera de imagen con título y descripción.
  `launcher_web.py` entrega metadatos antes de la imagen, limita las descargas y guarda hasta 32 previews en
  `~/.cache/wysun/link-previews` (una hora; fallos, un minuto). El highlight lo posiciona el propio ListView para seguir el scroll. No hay snippets, vista de ventanas ni comandos de energía en el lanzador (Alt+Tab abre el overview).
  `wysun clipboard|calculator` abren la vista correspondiente y `wysun emoji` el cajón de emojis; cualquier otra superficie
  (`session`, `quicksettings`, `notifications`, `dashboard`…) se alterna con `wysun SUPERFICIE`. El residente Qt (`wysun_services.daemon`) ya no muestra menús ni aloja utilidades: registra el historial del portapapeles.
  Music (`wysun_music`) y Files (`wysun_files`) se lanzan como procesos independientes.
- **Colores** (`wysun colors`; cuentagotas directo `wysun color-pick`): panel nativo de Quickshell en
  `apps/shell/modules/colors/`, capa overlay `wysun-colors` en la pantalla enfocada. Usa los controles,
  tipografía, radios y paleta M3 del shell. Incluye plano HSV con teclado, formatos HEX/RGB/HSL,
  contraste de texto, recientes y favoritos. `backend.py` serializa las operaciones en el almacén
  existente `~/.local/share/wysun/colors.json`; el parser compartido vive en `wysun_services.color_data`.
  La captura oculta el panel y llama a `hyprpicker`; vuelve tanto al elegir como al
  cancelar. Escape o pérdida de foco cierran el panel; Ctrl+P captura y Ctrl+C copia HEX fuera del
  campo de edición. No hay ventana Qt de Color.
- **Bloqueo** (`wysun-lock`, `apps/shell/lock.qml`, `modules/lockscreen/`): terminal de refinamiento. Un campo de
  números en un shader (`field.frag`, atlas de glifos con la fuente mono del shell) reacciona al puntero; cada tecla agita
  un grupo y envía dígitos a una de cinco cajas; Enter barre el campo, el rechazo lo revuelve en rojo y el acierto lo vacía
  en las cajas antes de apagar el CRT (`screen.frag`: curvatura, convergencia RGB, resplandor, apagado). Easter egg: una
  caja al 100 % muestra «QUOTA MET»; las cinco hacen bailar el campo y dibujar una W. Colores de `scheme.json`
  (`LockPalette.qml`), sin cargar servicios del shell. Proceso propio con `WlSessionLock` y PAM vía `/etc/pam.d/login`;
  swaylock queda como alternativa y respaldo. Vista previa sin bloqueo: `wysun-lock --preview`. Pruebas:
  `tests/test_wysun_lock.py`. Detalles y recuperación en `docs/wayland.md`.
  La misma escena es la pantalla de acceso (`apps/shell/greeter.qml`, `GreeterRoot.qml`, con greetd y el Quickshell de
  Debian: por eso `LockScene.qml` no importa el plugin `Wysun.*`); al entrar, las puertas del ascensor se cierran
  (`screen.frag`). GRUB y Plymouth reutilizan sus shaders para el arte de arranque (`BootArt.qml`,
  `system/boot/render_assets.py`). Ver `docs/boot.md`.
- **Panel de sesión**: `Super+X` alterna el panel lateral de sesión (salir, apagar, suspender, reiniciar) en el monitor
  enfocado y Escape lo cierra. `Ctrl+X` no está asignado: vuelve a ser Cortar en las aplicaciones. Los paneles invocados explícitamente conservan máscara interactiva y capa overlay
  sobre fullscreen; no dejan un foco invisible.
- **Settings y conexiones**: páginas nativas de Nexus (`apps/shell/modules/nexus`). `wysun settings [ruta]`
  abre las páginas registradas por `SettingsRoutes.js`; Displays y Workspaces son entradas principales en inglés.
  `apps/shell/wysun/display_bridge.py` atiende exclusivamente distribución de monitores (prueba, confirmación y
  reversión con watchdog independiente) y asignaciones persistentes de workspaces por monitor. Reutiliza
  `environment_settings.py`, `display_layout.py` y `hypr_settings.py`. No hay sección Escritorio ni páginas
  Terminal, Notificaciones, Inicio, Archivos y copias, Efectos, Ventanas, Atajos, SSH o Processes en Settings.
  Wi-Fi, VPN y Bluetooth usan Red y Dispositivos conectados. `wysun processes` alterna su propio panel, fuera de Nexus.
- **Tema**: un solo estilo, Material You; el color sale del wallpaper (`scheme.json`) y la selección, en
  `~/.config/wysun/theme.json`, es solo el modo (`auto`, `light`, `dark`). Los tokens viven en `apps/python/wysun_core/tokens.json`; Quickshell lee los colores por
  `apps/shell/services/Colours.qml` (vía `scheme.json`) y la forma del mismo `tokens.json` instalado; `tests/test_theme_literals.py` rechaza colores literales
  (excepciones: `theme-exception: motivo`). Guía: `docs/themes.md`.

## 7. Nombres y rutas

| Qué | Dónde |
|---|---|
| App instalada (paquetes Python) | `~/.local/share/wysun/app/` |
| Datos privados (portapapeles `wysun.sqlite3`, colores, notas, música, respaldos de Ajustes) | `~/.local/share/wysun/` |
| Preferencias (`theme.json`, `environment.json`, `hypr-*.lua`, `idle.json`, `local.lua`, `resets/`, `tools.json`) | `~/.config/wysun/` |
| Estado (`scheme.json`, registros, respaldos de tema) / caché | `~/.local/state/wysun/` / `~/.cache/wysun/` |
| Recorder | datos `~/.local/share/wysun/recorder`, preferencias `~/.config/wysun/recorder`, estado `~/.local/state/wysun/recorder`, releases `~/.local/share/wysun/capture/releases` |
| Instalador | CLI `wysun-install` (`wysun install`), código `~/.local/share/wysun/installer`, estado y respaldos `~/.local/state/wysun/install`, artefactos fijados `~/.local/share/wysun/artifacts`, estado del sistema `/var/lib/wysun` |
| Herramientas | `wysun tools`, motor `~/.local/share/wysun/tools` (`python3 -m wysun_tools`) |
| Sockets / variables / desktop ids | `wysun-*` en `$XDG_RUNTIME_DIR`; `WYSUN_*`; `wysun`, `wysun-files`, `wysun-music`, `wysun-settings`, `wysun-recorder`, portal `org.freedesktop.impl.portal.desktop.wysun` |

`tests/test_legacy_names.py` impide que vuelvan los nombres anteriores. La URL del repositorio en GitHub conserva su nombre.

Retirados: los nombres del proyecto de origen (módulos, plugin, rutas, IPC, namespaces de capa), todos los alias de comandos
(`wysun image`, `wysun color`, `wysun screenshot`, `wysun power`…) y los lanzadores sueltos (`wysun-tools`, `wysun-player`,
`wysun-files`, `wysun-music`, `wysun-pdf`, `wysun-workspaces`, `wysun-screenshot`), que una actualización retira; perfiles
`profiles/` (ahora `machines/`), módulos Python sin uso (`files_preview`, `service_runtime`, `theme_widgets`), demonios QML sin
uso (`GameMode`, `IdleMonitors`) y la infraestructura de CI/nix del shell original.

## 8. Pruebas

```sh
python3 -m unittest discover -s tests -v                       # núcleo: instalador, temas, sesión, wayland, herramientas…
python3 -m unittest discover -s tests/wysun_app -t tests       # apps Qt
python3 -m unittest discover -s tests/shell_bridge -t tests    # puente del shell (backend.py, dispatcher wysun-shell)
QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py
python3 tests/check_manifest.py
python3 apps/recorder/run_tests.py                              # captura (medios serializados)
python3 tests/wysun_installed_smoke.py                         # sobre la instalación real
python3 -m unittest discover -s tests -p 'test_media_*.py'     # reproductor: componente, widget, tema y MPRIS (D-Bus propio)
python3 tests/wayland_media_case.py                            # reproductor sobre el compositor real (OpenGL, fugas)
```

Pruebas de sockets/compositor requieren acceso de sesión; un bloqueo de sandbox no prueba un fallo del producto. Las seis
expectativas antiguas de `tests/wysun_app` se corrigieron en `d5017d01`; la suite general P2-B pasó 374 pruebas antes de integrar
P2-A. Las comprobaciones dirigidas de integración y el alcance del despliegue están en `docs/validation.md`.

# Wysun — Etapa 1: limpieza, base común y arquitectura escalable

> Diseño (brainstorming de Superpowers). Al aprobarse se guarda en
> `docs/superpowers/specs/2026-10-24-wysun-limpieza-base-comun-design.md` y se hace el plan de
> implementación con `superpowers:writing-plans`.

## Contexto e intención

`wysun-shell` son los dotfiles de Nicolas. La meta es clonar el repo en cualquier máquina
basada en Debian (la nueva, por ejemplo), correr el instalador y obtener el mismo entorno,
pero sin datos personales. Nicolas es el único usuario, así que la compatibilidad con nombres
y formatos antiguos no tiene valor. Hoy el repo arrastra:

- **Cinco sistemas de tema.** Los colores sí salen de una sola fuente (`scheme.json`), pero
  radios, espaciado, fuentes y movimiento se definen por separado:
  - `apps/wysun/wysun_theme.json` para Python;
  - `apps/shell/plugin/src/Wysun/Config/tokens.hpp` para QML;
  - una copia a mano en `apps/capture/loomrec/ui/{theme_core.py,wysun_theme.json,tokens.py}`.
  Las fuentes no coinciden (Inter, Rubik y GoogleSans), hay cinco watchers sobre los mismos
  archivos y quedan restos de los temas fijos (alias `tokyo`, `fluent`, variantes y wallpapers
  borrados).
- **Un kit de widgets dentro de Music.** El kit de facto vive en `apps/wysun/wysun_music/ui/`.
  Files (`wysun_files/kit.py`) y el instalador (`installer/ui_support.py`) dependen del
  paquete de Music, y el Recorder lo copia (`loomrec/ui/app_kit.py`).
- **Lógica duplicada:**

  | Lógica | Copias |
  |---|---|
  | JSON atómico | ~15 |
  | Rutas XDG escritas a mano | ~40 archivos |
  | Ventana sin bordes con redimensionado | 4 |
  | Instancia única con socket | 4 |
  | "Buscar `orbit/app` y meterlo al `sys.path`" | 6 |
  | Toast | 4 |
  | Iconos/fuentes de símbolos | 4–5 |

- **Código muerto.** El lock QML viejo (`apps/shell/modules/lock/`, 2.9k líneas sin uso), la
  copia Qt de Color, módulos que solo importan las pruebas, la UI vieja del Recorder, carpetas
  vacías y referencias a archivos borrados.
- **Despachador en cadena.** `bin/wysun` → `config/.local/bin/orbit` → `orbit-client` →
  `orbit.py`, y `orbit-client` vuelve a ejecutar `wysun`.

**Wysun Color** ya es un panel QML del shell (`apps/shell/modules/colors/`) y **se queda así**,
porque es una herramienta overlay rápida como la captura. Lo que se borra es su copia Qt.

## Metas

1. Borrar definitivamente todo lo que no se usa.
2. Quitar los nombres `orbit` y `loom` del código, los comandos, las rutas, los sockets y las
   variables. Todo pasa a llamarse `wysun`.
3. Un paquete Python compartido, `wysun_core`, del que dependan todas las apps Python.
4. Una sola fuente de tokens de forma, espacio, tipografía y movimiento, que lean Python y el
   shell.
5. En el shell, una base común para las ventanas overlay y componentes repetidos consolidados
   en `components/`.
6. Carpetas con una responsabilidad clara cada una.
7. Un instalador que deje el entorno completo en una Debian limpia.

## No-metas

- Migrar Music, Files, Player o Recorder a QML. Es la etapa 2 (ver al final).
- Cambiar funciones visibles, rediseñar pantallas o añadir apps.
- Tocar el login, el gestor de acceso o la sesión predeterminada.

## Anti-metas (fallaría aunque "funcione")

- Perder una función que hoy existe, o datos de Nicolas en esta máquina.
- Dejar una capa de compatibilidad nueva: alias, shims o código de migración en el repo.
- Cambiar una duplicación por una abstracción más difícil de seguir que las copias.
- Que el entorno instalado deje de funcionar en algún momento intermedio sin poder volver atrás.

## Restricciones

- Las reglas de `AGENTS.md` siguen vigentes, salvo las de compatibilidad, que este trabajo
  retira. Se mantienen:
  - probar y luego desplegar con `./instalar.sh --orbit-only` (pasará a `--wysun-only`);
  - no reiniciar Hyprland;
  - pruebas de medios y compositor serializadas, con HOME/XDG temporales;
  - no instalar dependencias del host sin autorización;
  - la UI toma valores de los tokens.
- **El Recorder conserva sus releases inmutables por hash** (`installer/capture_distribution.py`),
  porque los procesos de captura activos no deben ver código nuevo a medio grabar. Recibe
  `wysun_core` con el mismo mecanismo que ya usa para `wysun_media`: un enlace simbólico en el
  árbol fuente que se copia dentro de cada release. Nunca importa de la app instalada.
- El árbol ya está limpio (commit `e336be92 "Cleaning tree"`), que sirve de base para revertir.
  Cada paso va en su propia rama o commits.
- Los paquetes del sistema siguen siendo apt (`manifests/packages.json`).

## Decisiones tomadas (de Nicolas)

- Etapa 1 ahora. La migración a QML queda documentada como algo a tener en cuenta y se decide
  con un prototipo después.
- Se borra toda la compatibilidad vieja.
- Los datos actuales de esta máquina se **migran una sola vez** con respaldo, mediante un
  script desechable que no se queda en el repo.
- **Mandan los tokens del shell.** Music, Files, Settings, el instalador y el Recorder adoptan
  sus radios, espaciado, movimiento y Google Sans Flex. Este cambio visual está aceptado y es la
  única excepción a la no-meta de "no rediseñar". Al consolidar componentes QML duplicados
  también gana la variante que siga los tokens.
- **Se borran también los alias internos:**
  - `wysun image` (queda solo `player`);
  - `wysun color` (queda solo `colors`; el muestreo directo sigue siendo `color-pick`);
  - los redirectores `wysun screenshot` con flags viejos, `wysun-screenshot` y
    `wybie-screenshot` (queda `wysun-shell screenshot`);
  - `--orbit-only` (queda `--wysun-only`).
  Antes de borrar se revisan los binds (`hyprland.lua`, `local.lua`) y los scripts de Nicolas,
  y se actualizan.
- **`dotifails` se renombra.** El CLI del instalador pasa a `wysun install` (o equivalente bajo
  `wysun`). Su estado y sus respaldos pasan de `~/.local/state/dotifails` a
  `~/.local/state/wysun/install`, y `DOTIFAILS_*` pasa a `WYSUN_*`. Las huellas y el historial
  de respaldos se migran en el mismo script único.

## Diseño

### 1. Estructura de carpetas objetivo

```
apps/
  shell/                 QML/Quickshell + plugin C++ (como hoy)
    components/          ← única biblioteca QML compartida (se amplía)
    modules/             cada módulo usa components/; sin controles propios repetidos
  python/                (antes apps/wysun) raíz de paquetes Python; sin módulos sueltos
    wysun_core/          NUEVO: base compartida (ver §2)
    wysun_music/  wysun_files/  wysun_media/
    wysun_player/        (antes player_app.py, player_window.py, player_client.py)
    wysun_settings/      (environment_settings, hypr_settings, settings_*, display/workspace_layout)
    wysun_services/      backends del shell: launcher_data, code_preview, process_data,
                         nvim_theme, wysun_scheme, utility_data, clipboard…
    vendor/materialyoucolor/
  recorder/              (antes apps/capture) paquete wysun_recorder (antes loomrec)
  tools/                 (antes orbit_tools) → wysun_tools
bin/                     solo wysun, wysun-shell, wysun-lock (+ los que sigan siendo
                         necesarios, sin alias orbit-*)
installer/  config/  manifests/  docs/  tests/
```

- Ruta instalada: `~/.local/share/wysun/app/`, en vez de `~/.local/share/orbit/app/`. La
  configuración pasa a `~/.config/wysun/` y el estado a `~/.local/state/wysun/`.
- Cada app se ejecuta como módulo (`python3 -m wysun_music`) con `apps/python` en el
  `PYTHONPATH`. Así desaparecen los seis bloques que manipulan `sys.path`.
- Si un nombre de carpeta sale mejor de otra forma, lo decide quien construye. Se mantienen los
  principios: un paquete por app, la base en `wysun_core` y nada suelto en la raíz.

### 2. `wysun_core` (Python)

| Submódulo | Sustituye a |
|---|---|
| `paths` | XDG config/data/state/cache/runtime de Wysun; las ~40 rutas a mano y `settings-backups` ×6 |
| `jsonio` | `read_json` y `atomic_write_json`; las ~15 copias |
| `instance` | instancia única (flock + socket unix) y cliente de envío; `orbit.py`, `local_ipc.py`, `player_client.py`, `loomrec/ui/instance.py` |
| `theme` | lectura de `theme.json`/`scheme.json`, tokens y un único watcher (antes `theme_core`, `theme_tokens`, `loomrec/ui/tokens.py`) |
| `ui` | kit de widgets Qt sacado de `wysun_music/ui` y `app_kit.py`: StateLayer, IconButton, PillButton, Chip, Switch, Slider, Toast, Panel, NavItem, Segmented, Sheet, formas (cookie/squircle/pill), ventana sin bordes con redimensionado y animaciones (`reduced_motion`, `reveal_content`) |
| `icons` / `fonts` | símbolos e iconos Lucide; `load_fonts` |
| `desktop` | parseo de `.desktop` |

- Music, Files, Player, Settings, el instalador y el Recorder importan solo de `wysun_core`, sin
  importar unos de otros. Files deja de importar `wysun_music`.
- `installer/ui_support.package_runtime` copia `wysun_core` entero en lugar de su lista de
  módulos sueltos.
- Desaparecen `apps/capture/loomrec/ui/{theme_core.py,wysun_theme.json,tokens.py,app_kit.py,icons.py,material*.py,components.py,motion.py}`
  y su duplicado `installer/material_widgets.py` en lo que repita el kit.

### 3. Tema: una sola fuente de verdad

- **Un archivo de tokens**, `wysun_core/theme/tokens.json`. Contiene los roles Material y la
  paleta de respaldo, más forma (radios), espaciado, tipografía (familias y escala) y movimiento
  (duraciones y curvas M3). Se eliminan `styles`, `variants`, `aliases` y las entradas de temas
  retirados.
- El instalador copia `tokens.json` a `~/.local/share/wysun/theme/tokens.json`. **El plugin C++
  lo lee al arrancar** (`appearanceconfig.cpp`). Los valores de `tokens.hpp` quedan solo como
  respaldo, y una prueba comprueba que coinciden con el JSON. Se elimina el override
  `shell-tokens.json`, salvo que algo lo use de verdad.
- **Esquema de `tokens.json`:** sigue los nombres y valores del shell (`rounding.*`,
  `spacing.*`, `padding.*`, `anim.*` y la escala de `tokens.hpp`). El adaptador Qt de
  `wysun_core.theme` expone esos mismos nombres. Los nombres Python antiguos (`radius_s`,
  `corner_*`, `space_*`) se reemplazan en los consumidores sin dejar alias.
- **Tipografía:** Google Sans Flex para la interfaz, decidido por Nicolas al elegir los tokens del
  shell, y CaskaydiaCove para el monoespaciado. Se dejan de forzar Rubik e Inter.
- **El modo se resuelve en un solo lugar.** `wysun scheme` escribe en `scheme.json` el modo final
  (`light`/`dark`) ya resuelto desde `theme.json`. Python, `Colours.qml` y `LockPalette.qml`
  solo leen eso. `LockPalette.qml` pasa a usar `Colours`, salvo que el lock necesite aislamiento.
  En ese caso se documenta.
- La paleta de respaldo de `Colours.qml` (el rosa heredado del proyecto original) se sustituye por la del JSON.
- `theme.json` solo admite `{"mode": ...}`. Se borran `migrate`, `LEGACY_KEYS`, `theme_id()`,
  `ORBIT_THEME`, `RETIRED_BAR_COLORS`, `manifests/themes.json` y el código muerto
  (`_resolved`, `_cache`, `reloadHyprRules`, `--dynamic`).

### 4. Shell QML

- Un componente base `components/OverlayWindow.qml` que reúna Variants, HyprlandFocusGrab,
  foco de teclado OnDemand, Escape e IPC. Lo usan Launcher, EmojiPicker, Cheatsheet,
  WallpaperPicker, Colors y Processes.
- Se consolidan en `components/` los Toggle (Bluetooth, Network, Toggles), Chip (aiusage,
  TranslateCard, ColorWindow), Tabs/Segmented (dashboard, aiusage) y HeroCard (launcher,
  dashboard). Las filas genéricas de `nexus/common/` (ToggleRow, SliderRow, SectionHeader,
  NavRow) se mueven a `components/` para que otros módulos las usen.
- Los campos de búsqueda usan `SearchBar` en todas partes.

### 5. Despachador único

- `bin/wysun` es el único punto de entrada. Envía las rutas del shell por IPC a `wysun-shell` y
  lanza las apps con `python3 -m …`.
- `wysun daemon` es el residente del portapapeles (antes `orbit.py`), dentro de
  `wysun_services`.
- Se borran `config/.local/bin/orbit`, `orbit-client`, `bin/orbit-files` y `bin/orbit-tools`, y
  se actualizan los atajos de `hyprland.lua`.
- La lista de superficies del shell vive en un solo sitio y `bin/wysun-shell` no la repite.

### 6. Borrado definitivo (inventario inicial; quien construye confirma con grep antes de cada borrado)

- **Shell:** `apps/shell/modules/lock/`, `daemons/Shortcuts.qml`, `nexus/common/TextFieldRow.qml`
  y la carpeta vacía `apps/shell/tests/`.
- **Python:** `utilities.py`, `color_window.py`, `enhanced.py`, `utility_material.py`,
  `desktop_common.py`, `terminal_args.py`, `clipboard_data.py`, `energy_data.py`,
  `files_motion.py`, `link_preview.py`, `screen_lock.py`, `system_panels.py`, `wysun_fonts.py`,
  `theme_demo.py`, el modo de prueba de `orbit.py` y la carpeta vacía `apps/wysun/tests/`. Si
  alguno resulta usado en producción, se queda y se documenta.
- **Recorder:** la UI vieja (`components.py`, `materials.py` y las partes no usadas de
  `material.py`), `apps/capture/wybieshot/` y `loomrec --pick-color` si nada lo usa.
- **Pruebas y documentación** que solo cubren lo borrado: `tests/utility_ui.py` (parte Color),
  `tests/theme_snapshots.py`, las referencias a `mpv_embed`/`wysun_files/player` en
  `tests/media_benchmark.py` y `docs/multimedia-architecture-plan.md`, las entradas obsoletas de
  `UPSTREAM.json`/`THIRD_PARTY.md`, `docs/maintenance.md` (`notes_window.py`) y los wallpapers
  y temas `azul`/`space-black`/`tokyo`.
- `installer/clean_legacy.py` y su prueba, si solo existen por compatibilidad vieja.

### 7. Migración de datos de esta máquina (una vez, fuera del repo)

- Es un script desechable en el scratchpad. **Corte en una sola ventana** (mi decisión):
  1. Detener los residentes (`orbit.py`/daemon del portapapeles, Music, Player, Recorder). No se
     toca Hyprland.
  2. Ejecutar el script de migración.
  3. Desplegar con `./instalar.sh --wysun-only`.
  4. Reiniciar solo el shell y los residentes.
  Así ninguna app crea datos vacíos en las rutas nuevas antes de migrar.
- Volver atrás = restaurar el `.tar` + `git revert` + volver a desplegar. Ese procedimiento queda
  escrito en el propio script antes de ejecutarlo.
- Mueve datos y configuración de las rutas `orbit` a las rutas `wysun`: colores, ajustes,
  respaldos, música, historial, `appearance.json`, `theme.json` y sockets/estado. Deja un
  respaldo completo `.tar` de lo antiguo.
- Actualiza la configuración activa de Hyprland con respaldo, preservando las asignaciones del
  usuario.
- No se commitea.

### 8. Instalador y Debian limpia

- El instalador instala la estructura nueva en las rutas `wysun` y no contiene nada de `orbit`.
- Verificación de instalación limpia con `tests/container-install.sh` (Debian) y con un HOME/XDG
  temporal vacío.

### Orden de trabajo (cada paso deja el entorno funcionando y en su propio commit)

1. Commit base del estado actual (con permiso).
2. Borrado de código muerto y pruebas asociadas.
3. Crear `wysun_core` y mover dentro las piezas comunes una a una, apuntando a ellas a todos los
   consumidores. Primero paths/jsonio/instance, luego theme y por último ui.
4. Fuente única de tokens: el JSON nuevo, la lectura en el plugin C++ y la tipografía unificada.
5. Reorganización de carpetas y renombrado `orbit`/`loom` → `wysun`, con instalador,
   despachador y `hyprland.lua` actualizados. Después, la migración de datos una vez.
6. Componentes QML compartidos y `OverlayWindow`.
7. Actualizar `AGENTS.md`, `ARCHITECTURE.md`, `docs/themes.md`, `docs/wayland.md` y el README a
   la nueva realidad, sin reglas de compatibilidad.

### Lo que se deja a quien construye

- Los nombres exactos de submódulos y archivos dentro de los principios anteriores.
- Cómo partir los commits dentro de cada paso.
- Si `LockPalette` necesita seguir aislado.
- El reparto fino de módulos entre `wysun_services` y `wysun_settings`.

## Verificación

En cada paso:

- `python3 -m unittest discover -s tests -v`
- `python3 -m unittest discover -s tests/wysun_app -t tests`
- `python3 -m unittest discover -s tests/shell_bridge -t tests`
- `QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py`
- `python3 tests/check_manifest.py`
- `python3 apps/capture/run_tests.py` (con la ruta nueva)
- `python3 tests/wysun_installed_smoke.py`

Las pruebas de medios van serializadas. Además:

- `tests/test_theme_literals.py` sigue rechazando colores literales, y una prueba nueva asegura
  que no queda ningún `orbit`/`loom`/`ORBIT_` en el código (salvo vendor y THIRD_PARTY).
- El plugin se reconstruye con `installer/runtime_build.py` tras tocar C++, y luego
  `pkill -x quickshell; setsid wysun-shell &`.
- Despliegue con `./instalar.sh --wysun-only` y apertura real de los paneles y apps tocados:
  Launcher, Colors (`Super+Shift+C`), Processes, Settings, Music, Files, Player y Recorder.
  Cada uno se prueba en modo claro y oscuro y con dos wallpapers de colores distintos.
- La instalación limpia en el contenedor Debian deja el entorno completo sin datos personales.

## Etapa 2 (a tener en cuenta): ¿migrar las apps a QML?

**Por qué se plantea:**
- Hoy conviven dos tecnologías de interfaz: QML en el shell y widgets Qt en Python en Music,
  Files, Player y Recorder.
- Un componente de una no sirve en la otra. Ni siquiera con `wysun_core` el shell y las apps
  comparten botones, listas o animaciones; solo comparten tokens.
- Además, las apps usan PySide6 6.8 del sistema y el shell usa Qt 6.9.3 privado, así que son dos
  versiones de Qt.

**Cómo sería:** cada app correría como una **instancia propia de Quickshell**
(`quickshell -p …`). Sería un proceso aparte, así que si falla no tumba la barra. Compartiría
runtime, plugin `Wysun.*`, `components/` y tokens con el shell. Python quedaría solo como
backend, el mismo patrón que ya usan Colors y Processes (QML + `backend.py`).

**Qué se ganaría:**
- una sola librería de componentes;
- un solo sistema de tokens;
- una sola versión de Qt;
- PySide6 ya no sería necesario para la interfaz;
- animaciones M3 por GPU.

**Qué costaría:**
- reescribir ~15k líneas de interfaz;
- un elemento C++ de mpv en el plugin;
- comprobar que Quickshell aguanta listas enormes, arrastrar y soltar y ventanas normales de app.

**Cómo se decide:** con un prototipo desechable de la vista principal de Music como instancia de
Quickshell, medido contra la versión actual en arranque, memoria y fluidez. Si sale bien, se
migra app por app, con el Recorder al final. Si no, `wysun_core.ui` queda como el kit definitivo.
La etapa 1 sirve en ambos casos.

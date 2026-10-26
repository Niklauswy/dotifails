# Fase 1 — base QML compartida Material 3 Expressive: plan de implementación

> **Para workers agénticos:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para ejecutar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`). Nunca dos compilaciones/suites a la vez; `free -g` ≥ 4 GB antes de algo pesado; caches, venvs y `TMPDIR` bajo `~/.cache` (nunca `/tmp`).

**Meta:** una biblioteca QML pura (`apps/qml/WysunM3/`) con tema M3 directo en vivo, muelles expressive, patrones de transición y ~40 componentes con las medidas de los tokens oficiales, más el runtime privado `qml-runtime` que la ejecuta bajo PySide6 y una galería para verla en ventana real.

**Arquitectura:** PySide6 6.9.3 solo como bindings sobre el Qt privado del shell (spec, «Recomendación»). Un paquete Python nuevo `wysun_qml` re-ejecuta con el Python del venv, precarga `libQt6*` del runtime, fija plugins/imports y alimenta a `Theme` (singleton QML) con `scheme.json` + `tokens.json`. La biblioteca nunca importa `Quickshell`, `qs.*` ni `Wysun.*`.

**Tecnología:** Python 3.13 (venv `--system-site-packages`), PySide6_Essentials/shiboken6 == `qt.version` de `RUNTIME.json` (6.9.3), QtQuick (+ `QtQuick.Shapes`, ver decisión D3), M3Shapes opcional, `unittest`, `QT_QPA_PLATFORM=offscreen` + `grabToImage`.

**Spec:** `docs/superpowers/specs/2026-10-26-wysun-qml-music-files-design.md` («Fase 1», «Resultado de la fase 0», «Consecuencias», «Aprobación»). Maqueta: `docs/design/qml-migration/files-adaptive-nav.html`. Referencia (solo leer): `/home/nicolas/orca/workspaces/wysun-shell/qml-spike/spike/`. Tokens oficiales: `~/.cache/wysun-ref/material-web/tokens/versions/v0_192/`.

## Decisiones que necesito que confirmes (D1–D5)

Todas tienen un valor por defecto con el que implemento si no hay objeción.

- **D1 · Estilos y variantes.** `AGENTS.md` habla de dos estilos (Space Black con `space-black/tokyo/severance`, y Fluent claro/oscuro) con `~/.config/orbit/theme.json`. **El código de esta rama no los tiene**: `docs/themes.md`, `wysun_core/theme.py` y `tests/check_manifest.py` ("one style") dicen que hay **un solo estilo, Material You**, con `theme.json = {"mode": ...}` y Fluent 2 solo como tarjeta *WIP*. Por defecto: la base soporta el único estilo real (`material3`) y las pruebas barren **claro/oscuro × 4 paletas** (la del wallpaper por defecto de `tokens.json` + 3 sintéticas). `Theme.style` existe como propiedad (valor `"material3"`) y los barridos de prueba son una lista `STYLES` para añadir Fluent cuando exista. Si quieres que implemente ya Space Black/Fluent, es otra fase (requiere clave `style` en `wysun_core`, Recorder y `Colours.qml`).
- **D2 · Ancho del drawer: 280 px (maqueta aprobada), no 360 px (token `container-width` de v0_192).** Se define una sola vez en `Metrics.drawerWidth`, con comentario. El resto de medidas (indicador 56, rail 80, indicador de rail 56×32…) sí son las oficiales.
- **D3 · Imports permitidos.** La spec dice «solo `import QtQuick` (+ M3Shapes)». Propongo permitir también `QtQuick.Shapes` (mismo módulo `qtdeclarative` del runtime, sin dependencias nuevas; da arcos nítidos para el progreso circular y el recorte del ripple). Sigue prohibido todo lo que acople al shell: `Quickshell*`, `qs.*`, `Wysun.*`, `QtQuick.Controls`, `QtQuick.Effects`. Un test lo hace cumplir (lista blanca).
- **D4 · Ubicación.** `apps/qml/` (no dentro de `apps/python`, cuya raíz solo admite paquetes: `tests/test_python_layout.py`). Se despliega a `~/.local/share/wysun/qml/` (junto a `quickshell/`). El módulo se llama **`WysunM3`** (evita choque con el plugin C++ `Wysun.*`).
- **D5 · Cuándo crea el venv el instalador.** En el componente `wayland` (instalación completa y `--wysun-only`, donde ya se reconstruye el runtime del shell si cambió) y solo si falta o el sello difiere de `qt.version`; `WYSUN_SKIP_RUNTIME=1` lo omite. `AGENTS.md` dice que `--wysun-only` no instala dependencias; esto es una descarga PyPI aprobada por ti (spec, «Aprobación»), no un paquete del host. Fallo de red → aviso claro, no aborta el despliegue; las apps QML aún no existen, así que nada se rompe.

## Restricciones globales (valen para todas las tareas)

- Idioma: comentarios de código en inglés (como el resto del repo), docs y mensajes de usuario en español.
- **Nada literal**: colores solo de `Theme.m3*`; radios, espacios y duraciones de `Theme.rounding/spacing/padding/anim` (de `tokens.json`); **medidas de componente** (56, 40, 32, 80…) solo de `Metrics.qml`, que cita el token M3 de origen. `tests/test_theme_literals.py` pasa a escanear `apps/qml` y `apps/python/wysun_qml` (ya incluye `.qml`). Excepciones con `// theme-exception: motivo`.
- Roles QML con prefijo `m3*` (`m3onSurface`, no `onSurface`, que QML interpreta como manejador).
- Estados: capa 8 % hover / 12 % foco / 12 % pulsado / 16 % arrastre; deshabilitado: contenido 38 %, contenedor 10 % de `m3onSurface`. Foco accesible visible con teclado (anillo de 3 px en `m3secondary` separado 2 px del control).
- Movimiento: espaciales (posición, tamaño, forma) con `*Spatial` (pueden sobrepasar), efectos (color, opacidad) con `*Effects` (sin rebote). `Motion.reduced` → duración 0. Tokens: `anim.curves.expressive{Fast,Default,Slow}{Spatial,Effects}` y `anim.durations.*`.
- Tamaños de ventana: `<600` modal, `600–839` rail, `≥840` drawer estándar (`Metrics.windowClass(w)`).
- Fuentes: `font.family.sans` (Google Sans Flex) y `font.family.icon` (Material Symbols Rounded) de `wysun_core/fonts/`; el host las registra. Tipografía por rol M3 `font.<headline|title|body|label>.<large|medium|small>.{size(pt),weight}`.
- Runtime: PySide6 en lockstep con `qt.version`; sin `LD_LIBRARY_PATH`; el venv de desarrollo vive en `~/.cache/wysun-fase1/qml-runtime`, nunca en la ruta viva. No desplegar, no push.
- Commits pequeños, convencionales, terminados en `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus (entradas que la spec implica y ninguna tarea «feliz» ejercita)

1. **`scheme.json` ausente, a medias o reemplazado atómicamente en marcha**, y esquema sin algún rol (p. ej. sin `success*`): el tema conserva el último válido / cae a `tokens.json` base; ni parpadeo transparente ni excepción. → Tarea 3 (`check_theme.py`).
2. **Anchos en los límites y degenerados**: `windowWidth` 0, 599/600, 839/840, 3000; el modo no oscila al animar el ancho y el drawer modal no queda abierto al pasar a rail. → Tarea 11.
3. **Solo teclado**: Tab recorre y muestra el anillo de foco, Espacio/Enter activan, Escape cierra menú/diálogo/drawer modal y devuelve el foco; elementos deshabilitados no toman foco. → Tareas 6, 7, 12.
4. **Movimiento reducido en mitad de una animación** (el ajuste cambia con el menú abierto o con una transición corriendo): termina al destino sin saltos ni estados colgados. → Tarea 5.
5. **Faltan M3Shapes o la fuente de iconos**: `ShapeEmblem` degrada a forma redondeada y `Icon` no muestra nombres de ligadura en texto plano (se oculta); el aviso va a stderr una sola vez. → Tareas 3 y 8.

(Además, versión de PySide6 ≠ Qt del runtime: aviso, no crash → Tarea 2; venv ausente: pruebas saltadas con aviso → Tarea 1.)

## Estructura de archivos

| Ruta | Responsabilidad |
|---|---|
| `installer/qml_runtime.py` (nuevo) | Crea/valida/sella `qml-runtime` (venv, `pip install --no-deps`, poda de `PySide6/Qt` y herramientas). CLI `--prefix`, `--version`, `--check`. |
| `installer/wayland.py` (mod.) | `ensure_qml_runtime(d)`; despliega `apps/qml` → `.local/share/wysun/qml` en `configure` y `update_runtime`. |
| `apps/python/wysun_qml/` (nuevo paquete) | `bootstrap.py` (re-exec, precarga, rutas, comprobación de versión), `engine.py` (motor, import paths, fuentes), `theme_bridge.py` (`ThemeBridge` QObject en vivo), `gallery.py` + `__main__.py`. |
| `apps/qml/WysunM3/` (nuevo) | La biblioteca: `qmldir`, `Theme.qml`, `Metrics.qml`, `Motion.qml`, `Anim.qml`, `CAnim.qml`, y componentes en `controls/ navigation/ containers/ feedback/ motion/ shapes/`. |
| `apps/qml/gallery/` (nuevo) | `Gallery.qml` y páginas de demostración (no es parte de la biblioteca). |
| `apps/python/wysun_core/theme.py` (mod.) | Expone `m3<Rol>` directos (arreglo Widgets). |
| `tests/test_qml_runtime.py` (nuevo) | Pruebas del instalador (sin PySide) y *runner* que lanza las suites QML con el Python del venv. |
| `tests/qml/` (nuevo, paquete) | `support.py` + `check_*.py` (se ejecutan solo con el Python del venv; el patrón de descubrimiento es `check_*.py`). `capture_matrix.py` (script de capturas, no test). |
| `docs/qml-base.md` (nuevo) | Guía de uso de la base. Se enlaza desde `ARCHITECTURE.md`, `docs/themes.md` y `AGENTS.md`. |
| `tests/test_python_layout.py`, `tests/test_theme_literals.py` (mod.) | Registrar `wysun_qml`; escanear `apps/qml`. |

## Medidas de referencia (v0_192 salvo indicación) — `Metrics.qml`

| Componente | Medida |
|---|---|
| Navigation drawer | indicador alto 56, esquina full; ancho contenedor **280 (D2)**; icono 24; título de sección title-small `m3onSurfaceVariant`; contenedor `m3surfaceContainerLow`, esquina `large` (lado final); modal elevación 1 + scrim |
| Navigation rail | ancho 80; indicador 56×32 full; icono 24; etiqueta label-medium |
| Search bar | alto 56, full, `m3surfaceContainerHigh`, texto body-large, icono 24 |
| Text field | outlined: esquina `extraSmall`, borde 1 (hover 1, foco 2 `m3primary`), etiqueta flotante; filled: esquina superior `extraSmall`, indicador 1 (foco 2); iconos 24; alto 56 |
| Botones | alto 40, icono 18; filled/tonal/outlined(1 px)/text/elevated; esquina full, pulsado → `medium`/`small` (morfo como `ButtonBase` del shell) |
| Icon button | área 40, icono 24 (standard/filled/tonal/outlined, toggle) |
| FAB | 56 (small 40, large 96, icono 36); extended alto 56 |
| Chips | alto 32, esquina `small`, borde 1 (seleccionado 0), icono 18, avatar 24 |
| Lista | 1/2/3 líneas = 56/72/88; avatar 40, imagen 56, icono 24; espacios 16 |
| Cards | elevated/filled/outlined(1 px), esquina `medium`, icono 24 |
| Dialog | esquina `extraLarge`; ancho 280–560; botones text |
| Snackbar | alto 48 (dos líneas 68), esquina `extraSmall`, icono 24 |
| Tooltip | plain alto 24, esquina `extraSmall`; rich esquina `medium` |
| Progreso | lineal 4; circular 48, trazo 4 |
| Pestañas | alto 48; indicador primario 3, secundario 2; icono 24 |
| Segmented | alto 40, borde 1, icono 18 |
| Top app bar | small 64, medium 112, large 152; iconos 24 |
| Badge | 6 (pequeño), 16 (grande) |

---

### Tarea 1: Runtime `qml-runtime` en el instalador y arnés de pruebas con venv

**Archivos:**
- Crear: `installer/qml_runtime.py`, `tests/test_qml_runtime.py`, `tests/qml/__init__.py`, `tests/qml/support.py`
- Modificar: `installer/wayland.py` (`configure`, `update_runtime`, nueva `ensure_qml_runtime`), `tests/test_wayland_install.py` (si comprueba la lista de despliegue)

**Interfaces:**
- Produce `installer/qml_runtime.py`:
  - `wanted_version(manifest_path=None) -> str` (lee `qt.version` de `manifests/runtime.json`).
  - `default_prefix() -> Path` (`$WYSUN_QML_RUNTIME` o `$XDG_DATA_HOME/wysun/qml-runtime`).
  - `stamp(prefix) -> dict | None` (lee `<prefix>/WYSUN_QML_RUNTIME.json`: `{"pyside6": X, "qt": X}`).
  - `needs_update(prefix, version) -> bool`.
  - `prune(prefix) -> int` (borra `site-packages/PySide6/Qt/` y herramientas `designer, assistant, linguist, qmlls, qmllint, qmlformat, qmlcachegen, rcc, uic, lupdate, lrelease, pyside6-*`; devuelve bytes liberados).
  - `ensure(prefix, version, *, runner=subprocess.run) -> bool` (crea si falta/difiere; `runner` inyectable para pruebas; devuelve si cambió algo).
  - `main(argv) -> int` con `--prefix`, `--version`, `--check` (código 0 si al día, 3 si requiere actualización).
- Produce `tests/qml/support.py`: `venv_python() -> Path | None` (orden: `$WYSUN_QML_RUNTIME`, `~/.cache/wysun-fase1/qml-runtime`, `~/.local/share/wysun/qml-runtime`; solo si existe `bin/python3` y el sello coincide), `require_runtime(testcase)` (llama `skipTest` con aviso a stderr si falta), `run_in_venv(args, **env) -> CompletedProcess`.
- Produce en `wayland.py`: `ensure_qml_runtime(deployment) -> None` y el despliegue de `apps/qml`.

- [ ] **Paso 1: pruebas que fallan** (`tests/test_qml_runtime.py`, sin descargar nada; `runner` falso): `test_wanted_version_matches_runtime_manifest` (== `json["qt"]["version"]`), `test_ensure_creates_venv_with_system_site_packages_and_pinned_wheels` (el runner recibe `[... '-m','venv','--system-site-packages', prefix]` y luego `[pip,'install','--no-deps','PySide6_Essentials==6.9.3','shiboken6==6.9.3']`), `test_ensure_is_idempotent_when_stamp_matches` (segunda llamada no invoca el runner y devuelve `False`), `test_version_bump_rebuilds` (sello 6.9.2 → `needs_update`), `test_prune_removes_qt_tree_and_tools_only` (árbol falso: borra `PySide6/Qt`, `designer`; conserva `QtQuick*.abi3.so`, `libpyside6qml*`), `test_skip_env_leaves_installer_alone` (`WYSUN_SKIP_RUNTIME=1`), `test_network_failure_is_a_warning_not_an_abort`, `test_deploys_qml_library_next_to_quickshell`.
- [ ] **Paso 2:** `python3 -m unittest tests.test_qml_runtime -v` → falla (módulo inexistente).
- [ ] **Paso 3:** implementar `installer/qml_runtime.py` (sello JSON escrito atómicamente tras `prune`; `pip` del propio venv; stdout con `+ cmd` como `runtime_build.run`). Cablear `ensure_qml_runtime` en `wayland.configure` y `update_runtime` (tras `ensure_runtime`), con `_publish_asset(d, d.source/'apps/qml', '.local/share/wysun/qml')` en ambos. Si `pip` falla: `d.warn`/`emit` equivalente y continuar.
- [ ] **Paso 4:** la misma suite pasa. Además `python3 tests/check_manifest.py` y `python3 -m unittest tests.test_wayland_install tests.test_installer -v`.
- [ ] **Paso 5 (única descarga real):** `free -g`; `python3 installer/qml_runtime.py --prefix ~/.cache/wysun-fase1/qml-runtime` → crea el venv de desarrollo (~97 MB de PyPI, ~21 MB tras la poda). `--check` devuelve 0; `du -sh` ≤ 30 MB; comprobar que no queda `PySide6/Qt`.
- [ ] **Paso 6:** `tests/qml/support.py` + `tests/qml/__init__.py` y, en `tests/test_qml_runtime.py`, `QmlSuiteRunner.test_qml_suites_with_venv_python`: si no hay venv → `skipTest` con aviso; si hay → `run_in_venv(['-m','unittest','discover','-s','tests/qml','-t','tests','-p','check_*.py'])` debe devolver 0 (stdout al fallo). Verificar el salto: `WYSUN_QML_RUNTIME=/no/existe`.
- [ ] **Paso 7: commit** `feat(installer): private qml-runtime venv (PySide6 bindings on the shell Qt)`.

### Tarea 2: Arranque de apps QML (`wysun_qml.bootstrap` y `engine`)

**Archivos:** Crear `apps/python/wysun_qml/{__init__,bootstrap,engine}.py`, `tests/qml/check_bootstrap.py`. Modificar `tests/test_python_layout.py` (`PACKAGES` += `wysun_qml`).

**Interfaces:**
- Consume: `wysun_core.launch.argv/environment`, `wysun_core.paths`.
- Produce `bootstrap`:
  - `runtime_dir() -> Path` (`WYSUN_RUNTIME` o `~/.local/share/wysun/runtime`), `qt_prefix() -> Path` (`<runtime>/qt/<qt.version>/gcc_64`, versión leída de `RUNTIME.json`).
  - `qml_runtime_python() -> Path | None`.
  - `ensure_runtime_python(module, argv) -> None`: si `sys.prefix` no es el del venv y existe, `os.execv` con `launch.argv(module, *argv, python=…)` y `launch.environment()` (como `wysun_pdf/app.py`); si no existe, sale con mensaje de uso y código 2.
  - `preload_qt(prefix=None) -> list[str]`: `ctypes.CDLL(ruta absoluta, RTLD_GLOBAL)` de `Core Gui DBus Network OpenGL Qml QmlMeta QmlModels QmlWorkerScript Quick WaylandClient` presentes; devuelve las cargadas. **Antes** de importar PySide6; no toca `LD_LIBRARY_PATH`.
  - `configure_qt(prefix=None) -> list[Path]`: `QCoreApplication.setLibraryPaths([prefix/plugins])`, devuelve import paths (`prefix/qml`, `runtime/deps/lib/qt6/qml` si existe, `<qml_lib>` de la biblioteca, ver abajo).
  - `check_versions() -> str | None`: `qVersion() != PySide6.__version__` → texto de aviso (stderr una vez), sin lanzar.
  - `library_path() -> Path`: `$WYSUN_QML_LIB`, `~/.local/share/wysun/qml` si existe, si no `apps/qml` relativo al repo.
- Produce `engine.create_engine(app_name, extra_imports=()) -> (QGuiApplication, QQmlApplicationEngine)`: registra las fuentes de `wysun_core/fonts/`, añade los import paths, desactiva `LD_LIBRARY_PATH` heredado en hijos (no exporta nada).

- [ ] **Paso 1: pruebas** (`check_bootstrap.py`, corre en el venv): `test_preload_maps_runtime_qt_only` (tras `preload_qt()`, `/proc/self/maps` contiene `runtime/qt/…/libQt6Core` y **ninguna** `PySide6/Qt/lib` aunque se renombrase), `test_no_ld_library_path_exported`, `test_version_check_matches_runtime` (`check_versions() is None`), `test_version_mismatch_warns_without_raising` (simulado con `qVersion` parcheado → texto con ambas versiones), `test_import_paths_include_library_and_runtime`, `test_reexec_selects_venv_python` (con interpreter falso: `os.execv` parcheado recibe `-P -m <module>` y `PYTHONPATH` correcto), `test_missing_venv_prints_install_hint`, y en `tests/test_python_layout.py` la lista de paquetes.
- [ ] **Paso 2:** ejecutar con `~/.cache/wysun-fase1/qml-runtime/bin/python3 -m unittest tests.qml.check_bootstrap -v` → falla.
- [ ] **Paso 3:** implementar según las firmas. La precarga reproduce `spike/pyside/main.py::preload_runtime_qt` pero tolerante a bibliotecas ausentes.
- [ ] **Paso 4:** pasan; `python3 -m unittest tests.test_python_layout tests.test_theme_literals -v`.
- [ ] **Paso 5: commit** `feat(qml): bootstrap that runs PySide6 on the shell Qt (no LD_LIBRARY_PATH)`.

### Tarea 3: Biblioteca base — `Theme`, `Metrics`, `Label`, `Icon`, puente de tema y matriz de paletas

**Archivos:** Crear `apps/qml/WysunM3/{qmldir,Theme.qml,Metrics.qml,Label.qml,Icon.qml,ThemeFeed.qml}`, `apps/python/wysun_qml/theme_bridge.py`, `tests/qml/support.py` (ampliar), `tests/qml/check_theme.py`, `tests/qml/check_purity.py`. Modificar `tests/test_theme_literals.py` (`SCANNED` += `apps/qml`, `apps/python/wysun_qml` si falta).

**Interfaces:**
- `Theme` (singleton): `property var scheme` (`{mode, colours}`), `property var tokens`, `property bool reducedMotion`, `readonly property string style: "material3"`, `readonly property bool dark`, un `readonly property color m3<Rol>` por cada rol M3 de `scheme.json` (background, on*, surface*, surfaceContainerLowest…Highest, surfaceVariant, outline, outlineVariant, inverse*, shadow, scrim, surfaceTint, primary/secondary/tertiary/error + `*Container` + `on*`, `success*`), `readonly property var rounding/spacing/padding/anim/font`, `function curve(name)`, `function duration(name)`, `function typeFont(role)` (`"body.medium"` → `{family,pointSize,weight}`), `function fullRadius(height)`, `function stateOpacity(kind)` (`hover .08, focus .12, pressed .12, dragged .16`), `function load(scheme, tokens)`.
  - Rol ausente en `scheme` → valor del último esquema válido, o de `tokens.palettes[mode].scheme`, o `"transparent"` (con aviso único). Un `scheme` inválido (no objeto, sin `colours`) se ignora y conserva el actual.
- `ThemeFeed` (Item sin UI): `property var scheme; property var tokens; property bool reducedMotion` → aplica a `Theme` por `Binding`. El anfitrión solo lo instancia en el QML raíz.
- `Metrics` (singleton): constantes de la tabla anterior (`searchBarHeight`, `drawerWidth`, `railWidth`, `indicatorHeight`, `buttonHeight`, `chipHeight`…), `function windowClass(width) -> "modal"|"rail"|"standard"`.
- `Label`: `property string role: "body.medium"`; `Icon`: `property string name; property bool filled; property int size: Metrics.iconSize` (usa `Theme.tokens.font.family.icon`; si la fuente no está cargada, no pinta el nombre).
- `ThemeBridge` (Python, `QObject`): propiedades `scheme`, `tokens`, `reducedMotion` (QVariant/bool, señal de cambio); `reload()`; `setPreview(scheme|None)` (galería); vigila `theme.scheme_path()`, `theme.selection_path()` y el `appearance.json` con `QFileSystemWatcher` sobre fichero **y** directorio (reemplazo atómico, creación tardía), *debounce* 40 ms, compara `wysun_core.theme.revision()`; mientras no haya `scheme.json` válido entrega `{mode: active_mode(), colours: tokens.palettes[mode].scheme}`; `WYSUN_THEME` fuerza modo; `WYSUN_REDUCED_MOTION=1` lo respeta (`wysun_core.appearance.reduced_motion`).
- `tests/qml/support.py` añade: `PALETTES` (`default` = `tokens.json` por modo, `green` 2e7d32 *tonalspot*, `orange` e65100 *vibrant*, `blue` 1565c0 *expressive*, cada una en `light` y `dark`, generadas con `wysun_services.scheme.gen_scheme` como `spike/theme_live.py`), `STYLES = ('material3',)`, `Harness` (QGuiApplication offscreen única, `render(qml, width, height, scheme=…) -> QImage` con `QQuickView`+`grabToImage`, `pixel(image, x, y)`, `load_component(...)`, `process_until(cond, ms)`) y `close_to(color, rolename, tol)`.

- [ ] **Paso 1: pruebas** `check_theme.py`: `test_every_m3_role_is_exposed_and_equals_scheme` (por cada paleta y modo, `Theme.m3<Rol>` == `#`+valor), `test_roles_use_m3_prefix` (`m3onSurface` existe; no hay propiedades `onSurface`), `test_live_switch_light_dark_repaints` (rectángulo `m3surfaceContainerHigh`: píxel cambia al cambiar `scheme`), `test_live_wallpaper_change_from_file` (escribir `scheme.json` atómico en `XDG_STATE_HOME` temporal → `ThemeBridge` → píxel cambia ≤ 1 s), `test_tokens_exposed` (`Theme.rounding.extraLarge == 28`, `Theme.duration('expressiveFastSpatial') == 350`, `Theme.curve('expressiveFastSpatial')` == lista de `tokens.json`), `test_missing_or_broken_scheme_keeps_last_good` (foco de revisión 1), `test_role_missing_falls_back_to_base_palette` (sin `success`), `test_string_type_roles_resolve` (`typeFont('body.medium').pointSize == 14`, peso 400), `test_state_opacities`. `check_purity.py`: `test_library_imports_only_allowed_modules` (lista blanca D3: `QtQuick`, `QtQuick.Shapes`, `M3Shapes`, `WysunM3` y módulos relativos), `test_no_literal_colours_or_ms_in_library` (regex de colores/`duration: <número>` salvo `0`/`Metrics`), `test_qmldir_lists_every_component_file`, `test_icon_without_font_renders_nothing`.
- [ ] **Paso 2:** ejecutar con el Python del venv → fallan.
- [ ] **Paso 3:** implementar `Theme`, `Metrics`, `Label`, `Icon`, `ThemeFeed`, `qmldir` (singletons con la palabra `singleton`; los componentes con subcarpetas se listan como `Button 1.0 controls/Button.qml`) y `ThemeBridge`. La generación de roles se hace a mano en QML (lista explícita, sin metaprogramación) para que `qmllint` y el autocompletado funcionen.
- [ ] **Paso 4:** pasan. `python3 -m unittest tests.test_theme_literals -v`.
- [ ] **Paso 5: commit** `feat(qml): WysunM3 theme (direct M3 roles, live) and ThemeBridge`.

### Tarea 4: Arreglo en Widgets — `wysun_core.theme` expone roles M3 directos

**Archivos:** Modificar `apps/python/wysun_core/theme.py`, `apps/python/wysun_core/qt_theme.py` (solo si `color()` filtra por lista), `tests/test_core_theme.py`, `tests/test_core_tokens.py` (si cuenta tokens), `docs/themes.md`.

**Interfaces:**
- Produce `theme.m3_roles(colours: dict) -> dict[str, str]` (`{'m3primary': '#rrggbb', …}` para todo rol de `scheme.json`/`palettes.<modo>.scheme`, valores en minúsculas con `#`); `resolve(mode)` y `overlay_material_roles` los añaden, de modo que `resolve_active()` los tiene siempre (base del modo, luego esquema del wallpaper encima). `qt_theme.color('m3secondaryContainer')` devuelve un `QColor`.

- [ ] **Paso 1: pruebas:** `test_resolve_has_direct_m3_roles` (claves `m3primaryContainer`, `m3secondaryContainer`, `m3tertiaryContainer`, `m3surfaceContainerLow`, `m3outlineVariant` en ambos modos), `test_overlay_replaces_m3_roles_with_scheme_values`, `test_existing_tokens_unchanged` (los 108 nombres previos con idéntico valor), `test_color_accepts_m3_role` (Qt, offscreen).
- [ ] **Paso 2:** `python3 -m unittest tests.test_core_theme tests.test_core_tokens tests.test_core_qt_theme -v` → falla lo nuevo.
- [ ] **Paso 3:** implementar `m3_roles` (filtra claves no-M3 como `term*`, `k*`, `*PaletteKeyColor` para no inflar el diccionario: solo roles de `MATERIAL_ROLE_NAMES`, constante nueva compartida con `Theme.qml` vía test de paridad `check_theme.test_role_list_matches_python`).
- [ ] **Paso 4:** esas suites + `tests/test_token_consumers.py`, `tests/test_wysun_scheme.py`.
- [ ] **Paso 5: commit** `feat(core): wysun_core.theme exposes direct M3 roles for Widgets apps`.

### Tarea 5: Movimiento — muelles expressive y patrones de transición

**Archivos:** Crear `apps/qml/WysunM3/{Motion,Anim,CAnim}.qml`, `apps/qml/WysunM3/motion/{FadeThrough,SharedAxis,ContainerTransform}.qml`, `tests/qml/check_motion.py`.

**Interfaces:**
- `Motion` (singleton): `readonly property bool reduced: Theme.reducedMotion`, `function ms(kind) -> int` (0 si `reduced`), `function bezier(kind) -> list` (de `Theme.curve`).
- `Anim` (`NumberAnimation`): `property string kind: "defaultSpatial"` con valores `fastSpatial|defaultSpatial|slowSpatial|fastEffects|defaultEffects|slowEffects`; mapea a `expressive<Kind>` de los tokens (`Easing.BezierSpline`); `CAnim` igual para `ColorAnimation`. Al ponerse `reduced` en mitad de una animación en curso, completa al destino (`complete()`).
- `FadeThrough` (Item): `property Component current`, `function show(component, properties = {})`: saliente se desvanece (`fastEffects`, 90 %→0 en 90 ms de los 150), entrante entra con escala 0,92→1 (`defaultSpatial`) y opacidad (`defaultEffects`); `signal finished()`.
- `SharedAxis` (Item): como `FadeThrough` más `axis: "x"|"y"|"z"` y `show(component, properties, forward=true)`; desplazamiento 30 px (token `spacing.extraLargeIncreased`), salida y entrada con `fastEffects`/`defaultSpatial`.
- `ContainerTransform` (Item): `function open(sourceItem, component)` (anima de la geometría y esquina de `sourceItem` al contenedor completo, `slowSpatial`; contenido por fundido cruzado `defaultEffects`), `function close()` revierte; `readonly property bool opened`.

- [ ] **Paso 1: pruebas:** `test_anim_uses_token_duration_and_bezier` (`Anim{kind:'fastSpatial'}.duration == 350` y `easing.bezierCurve` == token), `test_spatial_curves_overshoot_effects_do_not` (máximo de la curva >1 en `*Spatial`, ≤1 en `*Effects`), `test_reduced_motion_makes_duration_zero`, `test_reduced_motion_mid_animation_completes` (revisión 4), `test_fade_through_swaps_content_and_ends_clean` (tras `finished`, el saliente destruido, opacidad 1, escala 1), `test_shared_axis_direction` (forward entra desde +x; back desde −x), `test_container_transform_open_close_roundtrip` (geometría final == contenedor; tras `close()` == `sourceItem`), `test_patterns_complete_instantly_when_reduced`.
- [ ] **Paso 2:** fallan. **Paso 3:** implementar (sin duraciones literales: solo `Motion.ms`). **Paso 4:** pasan. **Paso 5: commit** `feat(qml): expressive springs and M3 transition patterns (reduced-motion aware)`.

### Tarea 6: Primitivas de interacción — `StateLayer`, `FocusRing`, `Surface`

**Archivos:** Crear `apps/qml/WysunM3/{StateLayer,FocusRing,Surface}.qml` (en la raíz), `tests/qml/check_interaction.py`.

**Interfaces:**
- `StateLayer` (MouseArea-less `Item` + `MouseArea` interno): `property color tint: Theme.m3onSurface`, `property bool disabled`, `property bool focused`, `property bool dragged`, `property real radius`, `readonly property bool hovered/pressed`, `signal clicked(var mouse)`, `signal pressAndHold()`; opacidad 0,08/0,12/0,12/0,16 de `Theme.stateOpacity`; ripple opcional (`property bool ripple: true`) con `slowEffects`; deshabilitado: sin capa.
- `FocusRing` (Item): `property Item target; property bool visibleOnFocus` → anillo 3 px con separación 2 px, solo con foco por teclado (`activeFocus` + `focusReason ∈ {Tab, Backtab, Shortcut}`).
- `Surface` (Rectangle): `property color container`, `property int level` (0–5, aplica tinte tonal con `m3surfaceTint` a 5/8/11/12/14 % — tabla en `Metrics.elevationTint`), `property int outline` (ancho, color `m3outline`/`m3outlineVariant`), `property bool disabled`.

- [ ] **Paso 1: pruebas:** `test_state_layer_opacities` (hover → pixel con alfa 0,08 sobre `m3surface`; pressed 0,12; con `dragged` 0,16, tolerancia ±2 niveles), `test_disabled_has_no_layer_and_no_hover`, `test_focus_ring_only_for_keyboard` (revisión 3: foco por ratón no lo muestra, por Tab sí), `test_surface_tint_levels_monotonic`, `test_disabled_container_10_percent_content_38_percent`.
- [ ] **Pasos 2–5:** fallan → implementar → pasan → commit `feat(qml): StateLayer, FocusRing and Surface primitives`.

### Tarea 7: Botones — `Button`, `IconButton`, `Fab`, `SegmentedButtons`

**Archivos:** Crear `apps/qml/WysunM3/controls/{Button,IconButton,Fab,SegmentedButtons}.qml`, `tests/qml/check_buttons.py`.

**Interfaces:**
- `Button`: `property string type: "filled"` (`filled|tonal|outlined|text|elevated`), `property string text`, `property string icon`, `property bool checkable/checked`, `property bool disabled`, `signal clicked()`; `implicitHeight == Metrics.buttonHeight (40)`; morfo de esquina full → `Theme.rounding.small` al pulsar con `fastSpatial`; contenido `label-large`.
- `IconButton`: `type: "standard|filled|tonal|outlined"`, `checkable/checked`, `icon`, `iconChecked`; área 40.
- `Fab`: `size: "small|regular|large"`, `variant: "primary|secondary|tertiary|surface"` y `extended` (`text` + icono; alto 56; se expande/colapsa con `fastSpatial`).
- `SegmentedButtons`: `model: [{value, text, icon}]`, `multiSelect`, `current`/`selection`; alto 40, borde 1 `m3outline`, seleccionado `m3secondaryContainer` con ✓.

- [ ] **Paso 1: pruebas:** medidas (`Button.implicitHeight == 40`, `IconButton.width == 40`, `Fab` 56/40/96 y extended 56, `SegmentedButtons.height == 40`), colores por tipo contra roles (filled → `m3primary`/`m3onPrimary`; tonal → `m3secondaryContainer`/`m3onSecondaryContainer`; outlined borde 1 `m3outline`; text sin fondo; disabled → 10 %/38 %), `test_press_morphs_corner`, `test_keyboard_activation` (Espacio y Enter emiten `clicked`; Escape no), `test_disabled_not_focusable`, `test_toggle_icon_button_swaps_icon`, `test_extended_fab_collapses`, `test_segmented_single_and_multi`, y captura de cada tipo en claro/oscuro (smoke de píxel no vacío).
- [ ] **Pasos 2–5:** fallan → implementar → pasan → commit `feat(qml): buttons, icon buttons, FABs and segmented buttons`.

### Tarea 8: Indicadores y formas — `Chip`, `Badge`, `Divider`, `LinearProgress`, `CircularProgress`, `ShapeEmblem`

**Archivos:** Crear `apps/qml/WysunM3/controls/Chip.qml`, `feedback/{Badge,LinearProgress,CircularProgress}.qml`, `containers/Divider.qml`, `shapes/{ShapeEmblem,CookieShape}.qml`, `tests/qml/check_indicators.py`.

**Interfaces:**
- `Chip`: `kind: "assist|filter|input|suggestion"`, `text`, `icon`, `selected`, `avatar` (Component, solo input), `signal clicked()`, `signal removed()` (input); alto 32, esquina `small`, borde 1 (seleccionado: sin borde, `m3secondaryContainer`, ✓ a la izquierda con `fastSpatial`).
- `Badge`: `count: int` (0 → punto de 6; >0 → pastilla de 16, `99+`), `m3error`/`m3onError`.
- `Divider`: `inset: "none|start|both"` (16 px), `m3outlineVariant`, 1 px.
- `LinearProgress`: `value` (0–1) o `indeterminate`; alto 4; pista `m3secondaryContainer`, indicador `m3primary`. `CircularProgress`: 48, trazo 4, `indeterminate`.
- `ShapeEmblem`: `shape: "cookie"|"squircle"|"circle"|"flower"`, `size`, `color`, `contentItem`; usa `M3Shapes.MaterialShape` mediante `Loader` (fuente `CookieShape.qml`); si falta M3Shapes, `Rectangle` con `Theme.rounding.extraLarge` (revisión 5); `property bool morphOnHover` (usa `fromShape/toShape`).

- [ ] **Paso 1: pruebas:** medidas, colores por rol, `test_filter_chip_selected_shows_check`, `test_input_chip_remove_emits`, `test_badge_99_plus`, `test_progress_value_fills_proportionally` (píxel a 25/50/100 %), `test_indeterminate_animates_and_stops_when_hidden`, `test_circular_progress_renders_with_shapes` (si `QtQuick.Shapes` no renderiza offscreen, **sustituir por `Canvas`** y anotarlo en el commit), `test_emblem_falls_back_without_m3shapes` (se fuerza con `QML_IMPORT_PATH` sin el runtime de deps), `test_emblem_cookie_with_m3shapes` (si presente).
- [ ] **Pasos 2–5:** fallan → implementar → pasan → commit `feat(qml): chips, badge, divider, progress and expressive shape emblem`.

### Tarea 9: Entradas de texto — `TextField`, `SearchBar`

**Archivos:** Crear `apps/qml/WysunM3/controls/{TextField,SearchBar}.qml`, `tests/qml/check_text_inputs.py`.

**Interfaces:**
- `TextField`: `variant: "outlined|filled"`, `label`, `text`, `placeholder`, `supportingText`, `error`, `errorText`, `leadingIcon`, `trailingIcon`, `echoMode`, `readOnly`, `disabled`, `signal accepted()`, `signal trailingClicked()`; etiqueta flotante (sube al enfocar o con texto, `defaultSpatial`); alto 56; outlined: borde 1 → 2 `m3primary` en foco, `m3error` en error; filled: indicador 1 → 2.
- `SearchBar`: `text`, `placeholder`, `leadingIcon: "search"`, `trailing` (Component), `signal accepted()`, `signal cleared()`; alto 56, full, `m3surfaceContainerHigh`; botón de borrar aparece con texto; `Ctrl+L`/foco programático con `forceFocus()`.

- [ ] **Paso 1: pruebas:** alto 56 y esquinas (`extraSmall` / full), borde 1→2 al enfocar, etiqueta flotante (posición con y sin foco), color de error, deshabilitado (borde 12 %, texto 38 %), `accepted` con Enter, Escape limpia el SearchBar solo si hay texto, selección y pegado funcionan (`insert`), texto largo se recorta (`clip`) sin desbordar, `test_search_clear_button`.
- [ ] **Pasos 2–5:** fallan → implementar → pasan → commit `feat(qml): outlined/filled text fields and search bar`.

### Tarea 10: Contenedores — `ListItem`, `Card`, `EmptyState`, `TopAppBar`

**Archivos:** Crear `apps/qml/WysunM3/containers/{ListItem,Card,EmptyState,TopAppBar}.qml`, `tests/qml/check_containers.py`.

**Interfaces:**
- `ListItem`: `headline`, `supporting`, `overline`, `lines: 1|2|3` (altos 56/72/88), `leading` (Component o `leadingIcon`/`leadingImage`/`leadingAvatar`), `trailingText`, `trailing` (Component), `selected` (`m3secondaryContainer`), `signal clicked()/pressAndHold()`; separador opcional con `Divider`.
- `Card`: `variant: "elevated|filled|outlined"`, `clickable`, contenido por defecto, esquina `medium`.
- `EmptyState`: `emblemShape`, `icon`, `title`, `message`, `actionText`, `signal action()`; el emblema entra con `slowSpatial` (libertad expresiva) y respeta movimiento reducido.
- `TopAppBar`: `variant: "small|centered|medium|large"`, `title`, `leading`, `actions`, `scrollOffset` (colapsa medium 112→64 / large 152→64 con el desplazamiento; `m3surfaceContainer` al desplazar).

- [ ] **Paso 1: pruebas:** altos 56/72/88 y 64/112/152, `test_selected_list_item_uses_secondary_container`, `test_card_variants_surface_and_outline`, `test_empty_state_action_and_reduced_motion`, `test_top_app_bar_collapses_with_scroll_offset`, `test_list_item_long_text_elides` (no cambia la altura), scroll de `ListView` de 10 000 `ListItem` instanciando solo los delegados visibles (conteo de objetos `< 60`).
- [ ] **Pasos 2–5:** fallan → implementar → pasan → commit `feat(qml): list items, cards, empty state and top app bar`.

### Tarea 11: Navegación — `NavigationItem`, `NavigationRail`, `NavigationDrawer`, `AdaptiveNavigation`, `TabBar`

**Archivos:** Crear `apps/qml/WysunM3/navigation/{NavigationItem,NavigationRail,NavigationDrawer,AdaptiveNavigation,TabBar}.qml`, `tests/qml/check_navigation.py`.

**Interfaces:**
- Destino: `{id, icon, activeIcon?, label, badge?, section?}`; separador de sección = `{divider: true}`; encabezado = `{header: "Favoritos"}`.
- `NavigationItem`: `mode: "drawer|rail"`, `destination`, `active`, `signal clicked()`; drawer: alto 56 con indicador 56 `m3secondaryContainer`, icono relleno al activarse (`filled` con `defaultEffects`); rail: indicador 56×32 que crece de 32 a 56 con `fastSpatial`, etiqueta label-medium debajo.
- `NavigationDrawer`: `destinations`, `currentId`, `header` (Component, p. ej. FAB), `variant: "standard|modal"`, `open`, `signal selected(string id)`, `signal closeRequested()`; contenedor `m3surfaceContainerLow`; modal con scrim `m3scrim` 32 %, entra por la izquierda con `fastSpatial`, cierra con Escape/clic en scrim.
- `NavigationRail`: `destinations`, `currentId`, `menuButton`, `fab` (Component), `signal selected(string)`, `signal menuRequested()`; ancho 80.
- `AdaptiveNavigation`: `windowWidth: real`, `destinations`, `currentId`, `default property alias content`, `readonly property string mode` (de `Metrics.windowClass`), `modalOpen`, `header`/`fab` Components; en `modal` muestra un botón de menú que abre el drawer; al pasar a `rail`/`standard` fuerza `modalOpen = false`; la transición de ancho usa `fastSpatial`; `signal destinationSelected(string id)`.
- `TabBar`: `variant: "primary|secondary"`, `tabs: [{id,text,icon?}]`, `currentId`; alto 48, indicador 3/2 con `fastSpatial`; teclas ←/→ cambian de pestaña.

- [ ] **Paso 1: pruebas:** `test_window_class_boundaries` (revisión 2: 0→modal, 599→modal, 600→rail, 839→rail, 840→standard, 3000→standard), `test_mode_does_not_flap_while_resizing`, `test_drawer_dimensions` (ancho 280, item alto 56, indicador 56, esquina `large` en el borde final), `test_rail_dimensions` (80; indicador 56×32 → 56 al activar), `test_selected_uses_secondary_container` (píxel), `test_section_headers_title_small_on_surface_variant`, `test_modal_opens_closes_with_escape_and_scrim` y devuelve el foco, `test_modal_closed_when_growing_to_rail`, `test_keyboard_navigation_in_drawer` (↑/↓, Enter), `test_badge_in_destination`, `test_tabs_indicator_sizes_and_keys`, `test_adaptive_matches_mockup_widths` (capturas a 500/700/1000 px comparadas por regiones con los roles; sin diff de píxeles exacto).
- [ ] **Pasos 2–5:** fallan → implementar → pasan → commit `feat(qml): adaptive navigation (modal/rail/drawer) and tabs`.

### Tarea 12: Superposiciones — `Overlay`, `Menu`, `Dialog`, `Snackbar`, `Tooltip`

**Archivos:** Crear `apps/qml/WysunM3/feedback/{OverlayLayer,Menu,MenuItem,Dialog,Snackbar,SnackbarHost,Tooltip}.qml`, `tests/qml/check_overlays.py`.

**Interfaces:**
- `OverlayLayer` (Item a nivel de ventana, `z: 1000`): `function adopt(item)`; ayuda a anclar menús/diálogos al borde de la ventana sin `QtQuick.Controls`.
- `Menu`: `model: [{id, text, icon, shortcut, divider}]`, `function popup(item, x, y)`, `signal triggered(string id)`; esquina `extraSmall`, `m3surfaceContainer`, elevación 2, items alto 48, ↑/↓/Enter/Escape, se reubica si no cabe, aparece con `fastSpatial` (escala 0,8→1 + `fastEffects`).
- `Dialog`: `title`, `message`, `icon`, `content`, `actions: [{text, id, primary}]`, `modal`, `signal accepted(string id)/rejected()`; ancho 280–560, esquina `extraLarge`, scrim; Escape rechaza, foco atrapado y devuelto.
- `Snackbar`/`SnackbarHost`: `host.show({text, action, duration, longer})`, cola FIFO, alto 48 (68 con dos líneas), `m3inverseSurface`/`m3inverseOnSurface`/acción `m3inversePrimary`.
- `Tooltip`: `text`, `target`, retardo 500 ms de `Theme.anim.durations.normal` + `small` (documentado), plain alto 24; `rich` con título y acciones.

- [ ] **Paso 1: pruebas:** posición y reubicación del menú en los cuatro bordes, `test_menu_keyboard_flow` (revisión 3), Escape cierra y devuelve el foco, `test_dialog_traps_focus_and_escape_rejects`, `test_dialog_width_clamped`, `test_snackbar_queue_order_and_dismiss`, `test_snackbar_action_signal`, `test_tooltip_delay_and_hide_on_leave`, `test_reduced_motion_overlays_appear_instantly`, píxeles de colores de rol.
- [ ] **Pasos 2–5:** fallan → implementar → pasan → commit `feat(qml): menus, dialogs, snackbars and tooltips`.

### Tarea 13: Galería ejecutable y capturas

**Archivos:** Crear `apps/python/wysun_qml/{gallery,__main__}.py`, `apps/qml/gallery/{Gallery.qml,pages/*.qml}`, `tests/qml/check_gallery.py`, `tests/qml/capture_matrix.py`.

**Interfaces:**
- `python3 -m wysun_qml` abre la galería (re-ejecuta en el venv; clase de ventana `wysun-qml-gallery`; título «Wysun · M3 gallery»). Opciones: `--width/--height`, `--page <id>`, `--palette <default|green|orange|blue>`, `--mode <light|dark>` (vista previa vía `ThemeBridge.setPreview`), `--shot RUTA` (captura y sale, también offscreen).
- Galería: `AdaptiveNavigation` con páginas Tema (roles y tipografía), Botones, Chips y formas, Campos y búsqueda, Listas y tarjetas, Navegación, Superposiciones, Movimiento (botones que lanzan FadeThrough/SharedAxis/ContainerTransform y conmutador de movimiento reducido), Estados vacíos. Barra superior con selector de paleta/modo para ver el vivo.
- `capture_matrix.py SALIDA`: renderiza cada página × `STYLES` × paleta × modo offscreen; genera montajes `montage-<palette>.png` (cuadrícula claro/oscuro) y `index.json`; incluye además, si existe, el `scheme.json` vivo del usuario como paleta «wallpaper actual» (solo lectura, **no** forma parte de las pruebas).

- [ ] **Paso 1: pruebas** `check_gallery.py`: la galería carga sin errores QML en cada página (`engine.warnings` vacío), `--shot` produce PNG no vacío para las 8 paletas, `test_gallery_covers_every_exported_component` (cada componente del `qmldir` aparece en alguna página: lista leída del `qmldir`), cambio de página con SharedAxis sin excepciones.
- [ ] **Paso 2:** fallan. **Paso 3:** implementar. **Paso 4:** pasan.
- [ ] **Paso 5: ventana real** (una sola, serializada): `free -g`; `PYTHONPATH=apps/python ~/.cache/wysun-fase1/qml-runtime/bin/python3 -P -m wysun_qml &`; localizar la dirección con `hyprctl clients -j` (clase `wysun-qml-gallery`); `grim -g "<x>,<y> <w>x<h>" ~/.cache/wysun-fase1/shots/<nombre>.png` solo de su región, en anchos ~500/700/1000, claro y oscuro; cerrar **solo** esa ventana con `hyprctl dispatch 'hl.dsp.window.close({window="address:0x…"})'`.
- [ ] **Paso 6: commit** `feat(qml): runnable component gallery and capture matrix`.

### Tarea 14: Documentación

**Archivos:** Crear `docs/qml-base.md`. Modificar `ARCHITECTURE.md` (sección corta «Base QML compartida»: runtime, rutas, `apps/qml`, `qml-runtime`), `docs/themes.md` (adaptador QML en la tabla; nota D1), `AGENTS.md` (una línea: dónde vive la base, cómo probar con el venv).

**Contenido de `docs/qml-base.md`:** qué es y qué no es; arquitectura (runtime, bootstrap, `ThemeBridge`, `ThemeFeed`); **catálogo** de componentes con *cuándo usar cada uno* (y cuándo no) y medidas; tema y roles `m3*`; movimiento (spatial vs effects, patrones y cuál elegir: fade through entre destinos hermanos, shared axis en jerarquía, container transform al abrir un elemento); adaptable (clases de ventana); accesibilidad (foco, estados, teclado, movimiento reducido); libertades expresivas (`ShapeEmblem`, estados vacíos) con criterios; cómo escribir una app nueva (plantilla mínima de `main.py` + `Main.qml`); cómo **extender** (añadir componente: archivo, `qmldir`, `Metrics`, prueba de medidas, entrada en galería, test de pureza); cómo **lo adoptará el shell** (adaptador fino `ThemeFeed` alimentado por `Colours`/`Tokens`, `QML_IMPORT_PATH` en `runtime.sh`, sustitución gradual de `qs.components`); cómo probar (venv, offscreen, capturas, ventana real); límites conocidos (overlays dentro de la ventana, sin `QtQuick.Controls`).

- [ ] **Pasos:** escribir; `python3 tests/check_manifest.py` (sin rutas personales); enlaces válidos; **commit** `docs(qml): shared M3 base guide and architecture notes`.

### Tarea 15: Verificación final, revisión y entrega

- [ ] **Paso 1 (en serie, una a la vez, `free -g` antes de cada una):** `python3 -m unittest discover -s tests -v` (incluye el *runner* QML con el venv), `python3 -m unittest discover -s tests/wysun_app -t tests`, `python3 -m unittest discover -s tests/shell_bridge -t tests`, `QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py`, `python3 tests/check_manifest.py`, `python3 apps/capture/run_tests.py`, `python3 tests/wysun_installed_smoke.py` (medios serializados; bloqueos de sandbox ≠ fallo del producto), y las suites QML directamente con el Python del venv. Registrar resultados.
- [ ] **Paso 2:** `python3 -m unittest tests.test_theme_literals tests.test_python_layout -v`; `git grep -nE "Quickshell|import qs\\.|Wysun\\." apps/qml` sin resultados.
- [ ] **Paso 3:** `capture_matrix.py ~/.cache/wysun-fase1/matrix`; copiar montajes clave y capturas reales de la ventana a `/home/nicolas/.ao/data/artifacts/wysun-shell-2/` (sin datos privados).
- [ ] **Paso 4:** revisión final con un revisor nuevo (`superpowers:requesting-code-review`) sobre `main..qml/fase1-base`; aplicar Críticos e Importantes con `superpowers:receiving-code-review`, repetir las suites afectadas.
- [ ] **Paso 5:** `superpowers:verification-before-completion`; `ao report --done --note "<resumen, suites y resultados, decisiones D1–D5 aplicadas>" --artifact <capturas>`. Sin push ni PR.

## Autorrevisión (hecha)

- **Cobertura de la spec:** (1) runtime/arranque/pruebas con salto → T1, T2; (2) biblioteca pura + Theme en vivo → T3, `check_purity`; (3) muelles y patrones → T5; (4) lista de componentes → T3 (Label/Icon), T6, T7, T8, T9, T10, T11, T12 (drawer/rail/modal, search, text field, botones, chips, listas, tarjetas, menús, diálogos, snackbar, tooltip, progreso, pestañas/segmented, top app bar, divider, badge, estados vacíos, formas, state layers, foco); (5) arreglo Widgets → T4; (6) pruebas offscreen y matriz de paletas/modos → T3 `support.py`, cada tarea, T13; (7) guía → T14; (8) galería → T13; ventana real con `grim -g` → T13/T15.
- **Consistencia de nombres:** `Theme`, `Metrics`, `Motion`, `Anim`/`CAnim`, kinds `fastSpatial…slowEffects` (mapean a `expressive<Kind>`), `ThemeFeed`/`ThemeBridge`, `AdaptiveNavigation.mode` ∈ `modal|rail|standard`, `ShapeEmblem.shape` — iguales en todas las tareas.
- **Proporción:** el plan fija nombres, firmas, medidas y pruebas; los cuerpos de los componentes se dejan al implementador.

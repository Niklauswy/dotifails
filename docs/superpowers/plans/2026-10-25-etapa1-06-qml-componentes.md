# Etapa 1 · Plan 06 — Componentes QML compartidos del shell · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que las ventanas overlay del shell compartan un único `OverlayWindow`, que los controles
repetidos (Toggle, Chip, Segmented, HeroCard, filas de ajustes, campos de búsqueda) tengan una sola
definición en `apps/shell/components/`, y que una prueba impida que vuelvan a duplicarse.

**Architecture:**
- `components/OverlayWindow.qml` es la ventana por pantalla (un `StyledWindow`): recibe la
  pantalla (`modelData`), resuelve su `ScreenState`, se abre y cierra con un indicador de ese estado
  (`surface`, el mismo que conmuta la IPC `wysunShell toggle|open <superficie>` de
  `wysun/WysunBridge.qml`), y aporta la capa Overlay, el foco de teclado `OnDemand`, el
  `HyprlandFocusGrab`, el cierre con Escape y la animación `reveal`. El `Variants { model:
  Quickshell.screens }` se queda en cada usuario: es una línea, y meterlo en el componente
  obligaría a pasar el contenido como `Component` y perder el `id` de la ventana que todos usan.
- Los controles con el mismo nombre que en realidad son controles distintos (por ejemplo, dos
  `HeroCard` sin nada en común) no se fusionan: el compartido sube a `components/` y el otro se
  renombra por lo que es. Las decisiones están en la tabla de abajo.
- Las filas genéricas de Nexus y lo que necesitan (`ConnectedRect`, `RowButton`) pasan a
  `components/rows/` (`import qs.components.rows`). No hay `qmldir`: los imports son por carpeta.
- Una prueba nueva, `tests/shell_bridge/test_shared_components.py`, inspecciona el QML y falla
  mientras quede una duplicación o una ventana sin migrar.

**Tech Stack:** QML / Quickshell 0.x sobre Qt 6.9.3 (runtime privado), Python 3 unittest.

**Spec:** `docs/superpowers/specs/2026-10-24-wysun-limpieza-base-comun-design.md` (§4 "Shell QML").

### Decisiones por control

| Control | Hoy | Resultado |
|---|---|---|
| Overlay | Launcher, EmojiPicker, Cheatsheet, WallpaperPicker (Variants + estado), ColorWindow (una ventana creada a demanda que se destruye al cerrar) | Los cinco usan `OverlayWindow`. ColorWindow con `surface: ""` (siempre abierta mientras existe) y `onDismissed: destroy()` |
| Overlay | ProcessWindow | **Excepción**: es un `FloatingWindow` (ventana normal redimensionable con título y tamaño mínimo), no una capa overlay; no tiene focus grab ni Escape. Se queda igual |
| Toggle | `component Toggle` fila etiqueta+interruptor idéntica en `bar/popouts/Bluetooth.qml` y `Network.qml`; `component Toggle` baldosa de icono en `utilities/cards/Toggles.qml` | `components/controls/SwitchRow.qml` (la fila, copia literal) y `components/controls/ToggleTile.qml` (la baldosa) |
| Chip | `aiusage/Chip.qml` (etiqueta tintada, tokens); inline en `launcher/TranslateCard.qml` (relleno/tintado, pulso, tamaños `24 * scale`, duración `520`) ; inline en `colors/ColorWindow.qml` (un `TextButton` con foco de teclado) | `components/Chip.qml` desde la de aiusage + `filled` y `pulsing` con duración de tokens. TranslateCard lo usa. El de ColorWindow no es un chip sino el tercer envoltorio de botón con foco de teclado junto a `Action`/`IconAction`: se renombra `TextAction` |
| Tabs/Segmented | `dashboard/Tabs.qml` (barra con subrayado, ligada a `dashboardTab`), `component Tab` en `aiusage/Content.qml` (tarjeta de cuenta con medidor y logo), `aiusage/Segmented.qml` (píldora segmentada genérica) | Son tres controles distintos. `Segmented` sube a `components/controls/Segmented.qml`; el `Tab` de aiusage se renombra `AccountTab`; `dashboard/Tabs.qml` (derivado de upstream, ligado al dashboard) se queda |
| HeroCard | `dashboard/performance/HeroCard.qml` (tarjeta de uso CPU/GPU, la usan dashboard **y** processes vía `import qs.modules.dashboard.performance`); `launcher/HeroCard.qml` (arte vacío de los prefijos) | La de rendimiento pasa a `components/widgets/HeroCard.qml`; la del lanzador se renombra `launcher/PrefixHero.qml` |
| Filas | `nexus/common/{ToggleRow,SliderRow,SectionHeader,NavRow}` + dependencias `ConnectedRect`, `RowButton` | Las seis a `components/rows/` |
| Búsqueda | `WallpaperPicker` con `TextInput` crudo; `LauncherPanel` con `TextFieldBase` sin fondo ni iconos | `SearchBar` con una propiedad nueva `bare` (sin fondo, icono ni botón de borrar, padding 0). `lockscreen/LockScene.qml` usa `TextInput` para la contraseña: no es búsqueda, fuera de alcance |

## Global Constraints

- Tocar solo `apps/shell/` (QML/JS, sin `apps/shell/plugin/`), `tests/shell_bridge/` y este plan.
- Colores, radios, espaciado, tipografía y movimiento de `Colours`, `Tokens`, `Appearance`; nada de
  literales nuevos. `tests/test_theme_literals.py` sigue pasando.
- No desplegar (`./instalar.sh`), no reiniciar quickshell ni Hyprland, no cerrar ventanas: el
  coordinador despliega y prueba en vivo después de fusionar.
- `apps/shell/UPSTREAM.json` lista solo archivos existentes (`tests/test_dead_code.py`). Un archivo
  derivado que se mueve conserva su entrada con la ruta nueva y el mismo hash de importación.
- Al mover o renombrar un `.qml`, actualizar cada import y uso; no hay `qmldir` en el shell.
- Estado de partida: commit `6a3f0d84` (= `main`). `qml-lint-conventions.py` da 1305 violaciones.
- Commits en español o inglés como los existentes (`refactor(shell): …`), uno por tarea.

## Review Focus

1. **Escape en el lanzador con un submenú abierto** (menú de acciones, vista previa ampliada o una
   carpeta apilada) debe cerrar solo ese nivel, no el lanzador. `Launcher.qml` fija
   `closeOnEscape: false` y conserva su `handleKey`; lo fija
   `test_launcher_keeps_its_own_escape` (Task 1).
2. **ColorWindow mientras hyprpicker muestrea** está oculta y sin foco: perder el foco no debe
   destruirla. `focusGrab` incluye `!sampling`; lo fija `test_color_window_survives_sampling`
   (Task 1).
3. **Las teclas del carrusel de fondos** (flechas, Inicio/Fin, Enter, Ctrl+R, Escape) deben llegar
   antes que el cursor del campo de texto ahora que es un `SearchBar`. Se conserva
   `Keys.priority: Keys.BeforeItem`; lo fija `test_wallpaper_filter_keeps_carousel_keys` (Task 2).
4. **Un overlay que queda abierto tras recargar el shell** (el estado persiste) vuelve poblado:
   WallpaperPicker conserva su `Component.onCompleted: sync()`; lo cubre la carga en vivo del
   coordinador y la validación offscreen (Task 8).
5. **Un componente movido sin su import** rompe la carga del shell entero ("X is not a type").
   `test_moved_components_are_imported` (Task 7) exige, para cada componente movido, que cada
   archivo que lo instancia importe su carpeta nueva; la Task 8 carga el shell offscreen.

---

### Task 1: `OverlayWindow` y migración de las cinco ventanas overlay

**Files:**
- Create: `apps/shell/components/OverlayWindow.qml`
- Create: `tests/shell_bridge/test_shared_components.py`
- Modify: `apps/shell/modules/launcher/Launcher.qml`, `modules/launcher/EmojiPicker.qml`,
  `modules/cheatsheet/Cheatsheet.qml`, `modules/wallpaperpicker/WallpaperPicker.qml`,
  `modules/colors/ColorWindow.qml`

**Interfaces:**
- Produces `OverlayWindow` (`StyledWindow`, `import qs.components`):
  - `required property ShellScreen modelData`; `readonly property ScreenState state: ShellState.forScreen(modelData)`
  - `property string surface` — indicador de `ScreenState` que la abre; `""` = abierta mientras exista
  - `readonly property bool open` — `surface ? state[surface] : true`
  - `property bool active: open` (el lanzador añade `&& Config.launcher.enabled`)
  - `property real reveal: active ? 1 : 0` con `Behavior` `Anim { type: active ? openAnim : closeAnim }`;
    `property int openAnim: Anim.DefaultSpatial`, `property int closeAnim: Anim.DefaultSpatial`
  - `property bool closeOnEscape: true` — `Shortcut { sequence: "Escape"; enabled: active && closeOnEscape }`
  - `property bool focusGrab: active` — `HyprlandFocusGrab { active: root.focusGrab; windows: [root]; onCleared: root.close() }`
  - `signal dismissed()`; `function close(): void` — `surface ? state[surface] = false : dismissed()`
  - Fija: `name: surface`, `screen: modelData`, `Tokens.screen: modelData.name`,
    `visible: active || reveal > 0.001`, `exclusionMode: ExclusionMode.Ignore`,
    `WlrLayershell.layer: WlrLayer.Overlay`,
    `WlrLayershell.keyboardFocus: active ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None`

- [ ] **Step 1: Escribir las pruebas que fallan**

`test_shared_components.py` con `SHELL = ROOT / 'apps/shell'`, `qml(rel)` que lee un archivo y
`qml_files()` = `SHELL.rglob('*.qml')` sin `plugin/`. Clase `OverlayWindowTests`:

```python
OVERLAYS = ['modules/launcher/Launcher.qml', 'modules/launcher/EmojiPicker.qml',
            'modules/cheatsheet/Cheatsheet.qml', 'modules/wallpaperpicker/WallpaperPicker.qml',
            'modules/colors/ColorWindow.qml']

def test_overlay_window_owns_the_pattern(self):
    text = qml('components/OverlayWindow.qml')
    for needle in ('HyprlandFocusGrab', 'WlrKeyboardFocus.OnDemand', 'WlrLayer.Overlay',
                   'sequence: "Escape"', 'required property ShellScreen modelData', 'ShellState.forScreen'):
        self.assertIn(needle, text)

def test_overlays_use_overlay_window(self):
    for rel in OVERLAYS:
        text = qml(rel)
        self.assertRegex(text, r'\bOverlayWindow\s*\{', rel)
        for copy in ('HyprlandFocusGrab', 'WlrKeyboardFocus.OnDemand', 'WlrLayer.Overlay'):
            self.assertNotIn(copy, text, rel)

def test_no_other_module_copies_the_overlay_pattern(self):
    # Any other layer window that grabs focus should be an OverlayWindow too.
    found = [p for p in qml_files() if 'HyprlandFocusGrab' in p.read_text() and 'WlrKeyboardFocus.OnDemand' in p.read_text()]
    self.assertEqual(sorted(str(p.relative_to(SHELL)) for p in found), ['components/OverlayWindow.qml'])

def test_process_window_is_a_regular_window(self):
    # Documented exception: a resizable toplevel, not an overlay.
    self.assertRegex(qml('modules/processes/ProcessWindow.qml'), r'(?m)^FloatingWindow\s*\{')

def test_launcher_keeps_its_own_escape(self):
    self.assertIn('closeOnEscape: false', qml('modules/launcher/Launcher.qml'))

def test_color_window_survives_sampling(self):
    text = qml('modules/colors/ColorWindow.qml')
    self.assertRegex(text, r'focusGrab:[^\n]*!\s*win\.sampling')
    self.assertIn('closeOnEscape: false', text)
```

Si `test_no_other_module_copies_the_overlay_pattern` encuentra otro archivo (p. ej. un picker o la
sesión), se migra en este mismo paso o se añade a una lista `EXCEPTIONS` con el motivo en un comentario.

- [ ] **Step 2: Ejecutar y ver que fallan**

Run: `python3 -m unittest tests.shell_bridge.test_shared_components -v` (desde la raíz, con `-t tests` no hace falta)
Expected: FAIL — `components/OverlayWindow.qml` no existe y las ventanas contienen `HyprlandFocusGrab`.

- [ ] **Step 3: Crear `OverlayWindow.qml` con la interfaz de arriba**

Comentario de cabecera de una línea, como el resto de `components/`.

- [ ] **Step 4: Migrar las ventanas**

- Cheatsheet: `delegate: OverlayWindow { surface: "cheatsheet"; anchors {…} … }`; quitar el
  `Item { id: keys … Keys.onEscapePressed }` dejando un `Item` con foco si hace falta para el
  teclado (el Escape ya lo da el `Shortcut`); `win.state.cheatsheet = false` → `win.close()`.
- EmojiPicker: `surface: "emoji"`, `openAnim`/`closeAnim` por defecto; quitar
  `Keys.onEscapePressed` del `SearchBar`; `closeTimer` y `pick()` llaman `win.close()`.
- WallpaperPicker: `surface: "wallpapers"`; la rama `Key_Escape` del `Keys.onPressed` se borra.
- Launcher: `surface: "launcher"`, `active: open && Config.launcher.enabled`,
  `openAnim: Anim.DefaultSpatial`, `closeAnim: Anim.FastEffects`, `closeOnEscape: false`; conserva
  `margins`, `mask`, tamaño y `onActiveChanged`.
- ColorWindow: raíz `OverlayWindow { surface: ""; modelData: <la expresión de pantalla de hoy>;
  visible: true; closeOnEscape: false; focusGrab: dismissOnFocusLoss && visible && !win.sampling;
  onDismissed: if (!win.sampling) win.destroy() }`. Conserva su `Shortcut` de Escape en dos pasos y
  sus asignaciones a `visible` del muestreo.

- [ ] **Step 5: Ejecutar las pruebas**

Run: `python3 -m unittest discover -s tests/shell_bridge -t tests -v`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add apps/shell/components/OverlayWindow.qml apps/shell/modules tests/shell_bridge/test_shared_components.py
git commit -m "refactor(shell): one OverlayWindow for the launcher, emoji, cheat sheet, wallpaper and colour overlays"
```

### Task 2: `SearchBar` en todos los campos de búsqueda

**Files:**
- Modify: `apps/shell/components/controls/SearchBar.qml`, `modules/wallpaperpicker/WallpaperPicker.qml`,
  `modules/launcher/LauncherPanel.qml:836-865`
- Test: `tests/shell_bridge/test_shared_components.py`

**Interfaces:**
- Produces: `SearchBar.bare: bool` (por defecto `false`). Con `bare`: `background: null`,
  `searchIcon` y `clearIcon` invisibles, `leftPadding`/`rightPadding` 0. Sin `bare`, igual que hoy.

- [ ] **Step 1: Pruebas que fallan** — clase `SearchFieldTests`:

```python
def test_search_fields_use_search_bar(self):
    for rel in ('modules/wallpaperpicker/WallpaperPicker.qml', 'modules/launcher/LauncherPanel.qml'):
        text = qml(rel)
        self.assertRegex(text, r'\bSearchBar\s*\{', rel)
        self.assertNotRegex(text, r'\b(TextInput|TextFieldBase)\s*\{', rel)

def test_only_the_lock_screen_uses_a_raw_text_field_in_modules(self):
    raw = [str(p.relative_to(SHELL)) for p in qml_files() if str(p.relative_to(SHELL)).startswith('modules/')
           and re.search(r'\b(TextInput|TextFieldBase)\s*\{', p.read_text())]
    self.assertEqual(raw, ['modules/lockscreen/LockScene.qml'])  # password, not search

def test_wallpaper_filter_keeps_carousel_keys(self):
    text = qml('modules/wallpaperpicker/WallpaperPicker.qml')
    block = text[text.index('SearchBar {'):]
    self.assertIn('Keys.priority: Keys.BeforeItem', block)
    self.assertIn('carousel.random()', block)
```

- [ ] **Step 2: Ejecutar y ver que fallan** — Run: `python3 -m unittest tests.shell_bridge.test_shared_components.SearchFieldTests -v`. Expected: FAIL en las tres.
- [ ] **Step 3: Implementar** — `bare` en `SearchBar`. WallpaperPicker: el `Rectangle` + `MaterialIcon` + `TextInput` se sustituyen por un `SearchBar { id: filter; implicitWidth: Tokens.sizes.launcher.itemWidth * 0.6; placeholderText: "Filter wallpapers"; focus: true; Keys.priority…; Keys.onPressed… }` (el `SearchBar` normal ya trae fondo, icono y borrar con tokens). LauncherPanel: `TextFieldBase` → `SearchBar { bare: true; placeholderText: root.placeholders[root.current.id] ?? "" }` y se borra su `StyledText` de placeholder (el `SearchBar` ya lo pinta con `font: root.font`).
- [ ] **Step 4: Ejecutar** — Run: `python3 -m unittest discover -s tests/shell_bridge -t tests -v`. Expected: OK.
- [ ] **Step 5: Commit** — `refactor(shell): search fields use SearchBar, with a bare variant for the launcher`

### Task 3: Toggle

**Files:**
- Create: `apps/shell/components/controls/SwitchRow.qml` (cuerpo del `component Toggle` de Bluetooth), `components/controls/ToggleTile.qml` (el de Toggles)
- Modify: `modules/bar/popouts/Bluetooth.qml`, `modules/bar/popouts/Network.qml`, `modules/utilities/cards/Toggles.qml`
- Test: `tests/shell_bridge/test_shared_components.py`

**Interfaces:** `SwitchRow { label; checked; toggle }` y `ToggleTile` (un `IconButton`), mismas propiedades que hoy.

- [ ] **Step 1: Prueba que falla** — clase `SingleDefinitionTests` con un helper
  `inline(name)` = archivos con `^\s*component\s+<name>\s*:` y `named(name)` = archivos cuyo stem es `name`:

```python
def test_no_inline_toggle(self):
    self.assertEqual(inline('Toggle'), [])
    self.assertEqual(named('SwitchRow'), ['components/controls/SwitchRow.qml'])
    self.assertEqual(named('ToggleTile'), ['components/controls/ToggleTile.qml'])
```

- [ ] **Step 2: Ver que falla** (lista tres archivos con `component Toggle`).
- [ ] **Step 3: Implementar** — usos `Toggle {` → `SwitchRow {` / `ToggleTile {`. Bluetooth y Network son derivados de upstream: su hash en `UPSTREAM.json` no cambia (es el de importación).
- [ ] **Step 4: Ejecutar** la suite `shell_bridge`. Expected: OK.
- [ ] **Step 5: Commit** — `refactor(shell): shared SwitchRow and ToggleTile instead of three inline Toggles`

### Task 4: Chip

**Files:**
- Create: `apps/shell/components/Chip.qml` (desde `modules/aiusage/Chip.qml`, que se borra)
- Modify: `modules/launcher/TranslateCard.qml:177-200,502-555`, `modules/colors/ColorWindow.qml:184,335-338`
- Test: `tests/shell_bridge/test_shared_components.py`

**Interfaces:** `Chip { text; accent: color = m3primary; filled: bool = false; pulsing: bool = false; font (alias) }`.
`filled`: fondo `accent`, texto `onAccent: color` (por defecto `Colours.palette.m3onPrimary`); sin
`filled`: fondo `Qt.alpha(accent, 0.18)`, texto `accent`. `pulsing`: la opacidad del texto oscila
0.45↔1 con `Tokens.anim.durations` (la más cercana a 520 ms) y vuelve a 1 al parar.

- [ ] **Step 1: Prueba que falla**

```python
def test_one_chip(self):
    self.assertEqual(inline('Chip'), [])
    self.assertEqual(named('Chip'), ['components/Chip.qml'])
    self.assertNotRegex(qml('components/Chip.qml'), r'duration:\s*\d')
```

- [ ] **Step 2: Ver que falla.**
- [ ] **Step 3: Implementar** — TranslateCard: `Chip { text: root.sourceName; accent: Colours.palette.m3onTertiaryContainer; pulsing: … }` y el destino `filled: true; accent: Colours.palette.m3tertiary; onAccent: Colours.palette.m3onTertiary`; la fuente escalada se pasa por `font`. ColorWindow: `component Chip` → `component TextAction`, sus tres usos.
- [ ] **Step 4: Ejecutar** la suite `shell_bridge` y `python3 -m unittest tests.test_theme_literals`. Expected: OK.
- [ ] **Step 5: Commit** — `refactor(shell): one token-driven Chip for AI usage and the translate card`

### Task 5: Segmented y pestañas

**Files:**
- Move: `modules/aiusage/Segmented.qml` → `components/controls/Segmented.qml`
- Modify: `modules/aiusage/Content.qml` (`component Tab` → `component AccountTab`), `modules/aiusage/UsageSection.qml` (import `qs.components.controls` si falta)
- Test: `tests/shell_bridge/test_shared_components.py`

- [ ] **Step 1: Prueba que falla**

```python
def test_tabs_are_not_redefined(self):
    self.assertEqual(inline('Tab'), ['modules/dashboard/Tabs.qml'])  # the dashboard's underline tab bar
    self.assertEqual(named('Segmented'), ['components/controls/Segmented.qml'])
```

- [ ] **Step 2: Ver que falla.** — [ ] **Step 3: Implementar** (`git mv`). — [ ] **Step 4: Ejecutar** la suite. — [ ] **Step 5: Commit** — `refactor(shell): Segmented in components; the AI usage tab is AccountTab`

### Task 6: HeroCard

**Files:**
- Move: `modules/dashboard/performance/HeroCard.qml` → `components/widgets/HeroCard.qml`
- Move: `modules/launcher/HeroCard.qml` → `modules/launcher/PrefixHero.qml`
- Modify: `modules/dashboard/Performance.qml`, `modules/processes/ProcessWindow.qml` (deja de importar `qs.modules.dashboard.performance` si ya no usa nada más de ahí), `modules/launcher/ResultRow.qml:173`, `apps/shell/UPSTREAM.json` (clave renombrada, mismo hash)
- Test: `tests/shell_bridge/test_shared_components.py`

- [ ] **Step 1: Prueba que falla**

```python
def test_one_hero_card(self):
    self.assertEqual(inline('HeroCard'), [])
    self.assertEqual(named('HeroCard'), ['components/widgets/HeroCard.qml'])
    self.assertNotIn('qs.modules.dashboard.performance', qml('modules/processes/ProcessWindow.qml'))
```

- [ ] **Step 2: Ver que falla.** — [ ] **Step 3: Implementar.** — [ ] **Step 4: Ejecutar** `shell_bridge` y `python3 -m unittest tests.test_dead_code`. — [ ] **Step 5: Commit** — `refactor(shell): the performance HeroCard is a shared widget; the launcher's is PrefixHero`

### Task 7: Filas genéricas a `components/rows/`

**Files:**
- Move: `modules/nexus/common/{ConnectedRect,RowButton,ToggleRow,SliderRow,SectionHeader,NavRow}.qml` → `components/rows/`
- Modify: cada `.qml` que instancia alguno de ellos (añadir `import qs.components.rows`; quitar `import qs.modules.nexus.common` si ya no usa nada de allí), `apps/shell/UPSTREAM.json` (seis claves renombradas)
- Test: `tests/shell_bridge/test_shared_components.py`

- [ ] **Step 1: Prueba que falla**

```python
MOVED = {'ConnectedRect': 'components/rows', 'RowButton': 'components/rows', 'ToggleRow': 'components/rows',
         'SliderRow': 'components/rows', 'SectionHeader': 'components/rows', 'NavRow': 'components/rows',
         'SwitchRow': 'components/controls', 'ToggleTile': 'components/controls', 'Chip': 'components',
         'Segmented': 'components/controls', 'HeroCard': 'components/widgets', 'OverlayWindow': 'components'}

def test_rows_live_in_components(self):
    for name, folder in MOVED.items():
        self.assertEqual(named(name), [f'{folder}/{name}.qml'], name)

def test_moved_components_are_imported(self):
    for name, folder in MOVED.items():
        module = 'qs.' + folder.replace('/', '.')
        for path in qml_files():
            rel = path.relative_to(SHELL)
            text = path.read_text()
            if str(rel.parent) != folder and re.search(rf'(?<![\w.]){name}\s*\{{', text):
                self.assertRegex(text, rf'(?m)^import {re.escape(module)}\s*$', f'{rel} uses {name}')
```

- [ ] **Step 2: Ver que falla.**
- [ ] **Step 3: Implementar** con `git mv` y un script de una vez para los imports (el import nuevo se inserta junto a los demás `import qs.components*` respetando el orden que exige `qml-lint-conventions.py`).
- [ ] **Step 4: Ejecutar** `shell_bridge`, `tests.test_dead_code` y `python3 apps/shell/scripts/qml-lint-conventions.py | tail -1` (≤ 1305).
- [ ] **Step 5: Commit** — `refactor(shell): settings rows move from nexus/common to components/rows`

### Task 8: Verificación final

- [ ] `python3 -m unittest discover -s tests/shell_bridge -t tests` → OK.
- [ ] `python3 -m unittest discover -s tests` → OK (un fallo ajeno se nombra con su error).
- [ ] `python3 apps/shell/scripts/qml-lint-conventions.py | tail -1` → ≤ 1305 violaciones.
- [ ] Carga offscreen sin tocar la sesión: con `HOME`, `XDG_*` y `XDG_RUNTIME_DIR` temporales, sin
  `WAYLAND_DISPLAY` ni `HYPRLAND_INSTANCE_SIGNATURE`, `QT_QPA_PLATFORM=offscreen`, ejecutar
  `~/.local/share/wysun/runtime/quickshell/bin/quickshell -p apps/shell` con los
  `QML_IMPORT_PATH`/`WYSUN_LIB_DIR` de `runtime.sh`, unos segundos con `timeout`, y comparar sus
  errores QML (`is not a type`, `ReferenceError`, `Cannot assign`) con los de `main` en el mismo
  entorno (worktree temporal de `main`). Si quickshell no arranca sin Wayland, decirlo.
- [ ] `git log --oneline main..HEAD` y `git diff --stat main`.

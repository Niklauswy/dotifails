# Etapa 1 · Plan 01 — Borrar código muerto · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Borrar definitivamente los módulos, la UI, las pruebas y la documentación que ya no usa
nada, y dejar una prueba guardián que impida que vuelva a acumularse código sin uso.

**Architecture:**
- Antes de borrar, una prueba guardián en `tests/test_dead_code.py` escanea los árboles fuente.
  Un módulo Python o un módulo QML del shell está "vivo" si su nombre aparece en algún archivo
  que no sea de prueba ni de documentación: imports, rutas en QML/sh/lua/json o archivos
  `.desktop`.
- La prueba falla hoy con la lista de muertos y pasa al terminar el plan.
- Los borrados son de código puro. No cambia ninguna función visible.

**Tech Stack:** Python 3 (unittest, PySide6), QML/Quickshell, git.

**Spec:** `docs/superpowers/specs/2026-10-24-wysun-limpieza-base-comun-design.md` (§6, paso 2
del orden de trabajo).

Este es el primero de siete planes de la etapa 1; cada paso del orden de trabajo tendrá el suyo:

| Plan | Contenido |
|---|---|
| 01 | este plan, borrar código muerto |
| 02 | `wysun_core` |
| 03 | tokens únicos |
| 04 | carpetas, renombrado y migración |
| 05 | despachador y alias |
| 06 | componentes QML |
| 07 | documentación |

Cada plan se escribe al terminar el anterior, porque depende de cómo quede el código.

## Global Constraints

- No reiniciar Hyprland, no cerrar otras apps, no instalar dependencias del host.
- Las pruebas de medios y compositor van serializadas, con HOME/XDG temporales.
- Despliegue: `./instalar.sh --orbit-only`. Este plan aún no renombra; eso es el plan 04.
  Si termina sin conflictos, ejecutar `~/.local/bin/orbit reload` en la sesión gráfica.
- Tras tocar QML del shell, reiniciar solo el shell con `pkill -x quickshell; setsid wysun-shell &`.
- No se crea ningún alias, shim ni código de compatibilidad.
- Ningún texto del repo puede nombrar el proyecto original del shell fuera de las excepciones
  de `tests/test_branding.py`.
- Estado de partida: commit `e336be92`. La suite principal pasa con 691 pruebas (1 omitida), y
  `wysun_app` (103), `shell_bridge`, `utility_ui` y `check_manifest` están en OK.

## Review Focus

1. **Un módulo que solo se invoca como subproceso** (un backend lanzado desde QML por ruta, o un
   script de `bin/`) **no debe salir como muerto.** La prueba guardián debe buscar el nombre en
   `.qml`, `.js`, `.sh`, `.lua`, `.json`, `.desktop` y en los scripts sin extensión de `bin/`,
   `config/.local/bin/` y `apps/wysun/` (por ejemplo `orbit-client`). Lo cubre
   `test_subprocess_backends_count_as_alive` (Task 1).
2. **Borrar el lock QML viejo no puede romper el lock real** (`modules/lockscreen` vía
   `lock.qml`). Lo cubren `test_real_lock_does_not_import_the_old_one` (Task 3) y la
   verificación en vivo de la Task 5.
3. **`wysun colors` y `wysun color-pick` deben seguir abriendo el panel QML** aunque `orbit.py`
   ya no tenga la ventana Qt. Lo cubre la prueba existente
   `test_launcher_modes_are_not_qt_menus_any_more` (Task 1) y la Task 5 en vivo.
4. **El Recorder debe seguir arrancando y grabando** sin `components.py` ni `materials.py`. Lo
   cubren `python3 apps/capture/run_tests.py` (Task 2) y la Task 5 en vivo.
5. **Un comentario o documento que nombra un archivo borrado como historia** no cuenta como
   referencia viva. La prueba guardián ignora `.md` y `tests/`, y la limpieza de documentación
   es manual (Task 4).

---

### Task 1: Prueba guardián y borrado de módulos Python muertos de `apps/wysun` e `installer`

**Files:**
- Create: `tests/test_dead_code.py`
- Delete en `apps/wysun/`:
  - `utilities.py`, `color_window.py`, `enhanced.py`, `utility_material.py`
  - `desktop_common.py`, `terminal_args.py`
  - `clipboard_data.py`, `energy_data.py`, `files_motion.py`, `files_visuals.py`
  - `link_preview.py`, `screen_lock.py`, `system_panels.py`, `wysun_fonts.py`, `theme_demo.py`
- Delete en `installer/`: `clean_legacy.py`
- Delete la carpeta vacía y sin seguimiento `apps/wysun/tests/`
- Modify: `apps/wysun/orbit.py:75-90`. `show_utility('color')` siempre ejecuta `wysun colors`,
  también en modo prueba, y se elimina la rama `from utilities import ColorWindow`.
  `UTILITIES` queda `('color','music')`.
- Delete estas pruebas, que solo cubren lo borrado:
  - `tests/test_clipboard_library.py`, `tests/test_clipboard_preview.py`
  - `tests/test_screen_lock.py`, `tests/test_wysun_fonts.py`, `tests/test_theme_demo.py`
  - `tests/test_clean_legacy.py`
  - `tests/wysun_app/test_desktop_utilities.py`, `tests/wysun_app/test_preserved_services.py`
  - `tests/wysun_app/test_native_ui.py`
- Modify estas pruebas:
  - `tests/wysun_app/test_refinement.py`: quitar los imports de `desktop_common` y
    `energy_data`, `test_battery_values_and_missing_data` y la clase de pruebas de `Surface`
    (setUp con `Surface('Test')`: `test_rapid_close_reopen_restores_anchor`,
    `test_immediate_hide_cancels_animation_for_focus_handoff`, `test_reduced_motion_and_press`,
    `test_glass_background_alpha`). Se conservan las de `ui_appearance` y `process_data`.
  - `tests/utility_ui.py`: quitar `from utilities import ColorWindow`,
    `test_material_glyphs_and_data_survive_all_presets`,
    `test_color_formats_invalid_input_and_palette` y `test_color_copy`. Se conserva
    `test_theme_switch_refreshes_existing_widgets`.
  - `tests/theme_snapshots.py`: quitar la captura de `ColorWindow` (líneas ~72-73).
  - `tests/test_branding.py`: sacar `installer/clean_legacy.py` y `tests/test_clean_legacy.py`
    de `ALLOWED_FILES`.

**Interfaces:**
- Produces, en `tests/test_dead_code.py`:
  - `corpus_files(root: Path) -> list[tuple[Path, str, bool]]`
  - `references(stem: str, text: str, is_python: bool) -> bool`
  - `alive_names(root: Path) -> str`
  - `dead_python_modules(package_dir: Path) -> list[str]`
  - La clase `DeadCodeTests`. Las Tasks 2 y 3 le añaden métodos.

- [ ] **Step 1: Escribir la prueba guardián**

`tests/test_dead_code.py`:
- `CORPUS_SUFFIXES = {'.py', '.qml', '.js', '.sh', '.lua', '.json', '.desktop', '.toml', ''}`
  (`''` cubre los scripts sin extensión).
- `alive_names(root)` concatena los archivos de `git ls-files --cached --others --exclude-standard`
  con esos sufijos, excepto los que estén bajo `tests/`, `apps/capture/tests/` o `docs/`, los que
  terminen en `.md` y los de `vendor/`.
- `references(stem: str, text: str, is_python: bool) -> bool`. Un script sin extensión con
  shebang de Python cuenta como Python. Esta es la regex validada contra el repo en `e336be92`:

```python
def references(s, t, py):
    if re.search(rf'\b{s}\.py\b|-m\s+[\'"]?(\w+\.)*{s}\b', t):
        return True
    if not py:
        return False
    return bool(re.search(
        rf'^\s*(from\s+\.?(\w+\.)*{s}(\s|\.)|import\s+([\w., ]*,\s*)?(\w+\.)*{s}\b'
        rf'|from\s+[\w.]*\s+import\s+([\w, ]*,\s*)?{s}\b)|[\'"](\w+\.)*{s}[\'"]', t, re.M))
```

  Cubre `from .x import`, `from loomrec.x import`, `'-m', 'loomrec.worker'` y `-m x`. La
  palabra suelta no cuenta: `utilities` aparece en QML y en `self.utilities` sin ser el módulo.
- `MANUAL_ENTRY_POINTS = {'installer/pointer_registration.py'}`. Son scripts que una persona
  ejecuta a mano y que nada invoca; aquí, el registro opcional del helper root del puntero para
  el Recorder. Se tratan como vivos, con un comentario que explica por qué. Integrarlo en el
  instalador o retirarlo es decisión del plan 04, y queda anotado allí.
- `dead_python_modules(package_dir) -> list[str]`, ordenada. Toma los `stem` de
  `package_dir/*.py` (sin subpaquetes y sin `__init__`) y calcula el **cierre transitivo**: un
  módulo está muerto si solo lo referencian archivos de prueba/documentación o módulos que
  también están muertos.

```python
def dead_python_modules(package_dir):
    candidates = {p.stem: p for p in package_dir.glob('*.py') if p.stem != '__init__'}
    files = corpus_files(ROOT)               # [(path, text, is_python)], sin tests/docs/vendor
    dead = set()
    while True:
        live_files = [(p, t, py) for p, t, py in files
                      if not (p.parent == package_dir and p.stem in dead)]
        newly = {s for s, path in candidates.items() if s not in dead and not any(
            p != path and references(s, t, py) for p, t, py in live_files)}
        if not newly:
            return sorted(dead)
        dead |= newly
```

`corpus_files(root)` sustituye a `alive_names`. `alive_names` queda como
`'\n'.join(t for _, t, _ in corpus_files(root))`, para las pruebas que solo necesitan el texto.

```python
class DeadCodeTests(unittest.TestCase):
    def test_every_wysun_module_is_used_outside_tests(self):
        self.assertEqual(dead_python_modules(ROOT / 'apps/wysun'), [])

    def test_every_installer_module_is_used_outside_tests(self):
        self.assertEqual(dead_python_modules(ROOT / 'installer'), [])

    def test_subprocess_backends_count_as_alive(self):
        corpus = alive_names(ROOT)
        for backend in ('launcher_data', 'process_data', 'wysun_scheme', 'code_preview'):
            self.assertRegex(corpus, rf'\b{backend}\b')
```

- [ ] **Step 2: Ejecutar la prueba y comprobar que falla**

Run: `python3 -m unittest tests.test_dead_code -v`

Expected: FAIL. El prototipo, ejecutado contra `e336be92`, dio:
- `test_every_wysun_module_is_used_outside_tests` lista exactamente `clipboard_data`,
  `energy_data`, `files_motion`, `files_visuals`, `link_preview`, `screen_lock`,
  `system_panels`, `terminal_args`, `theme_demo` y `wysun_fonts`.
- Tras editar `orbit.py` (Step 3) se suman `utilities`, `color_window`, `enhanced`,
  `utility_material` y `desktop_common`.
- `test_every_installer_module_is_used_outside_tests` lista `clean_legacy`
  (`pointer_registration` queda fuera por `MANUAL_ENTRY_POINTS`).

Si sale un nombre distinto, se revisa con grep. Si es un falso positivo (un backend invocado de
una forma que `references` no reconoce), se amplía `references`, no `MANUAL_ENTRY_POINTS`.

- [ ] **Step 3: Borrar los módulos y la carpeta vacía, y editar `orbit.py`**

Borrar con `git rm` cada archivo listado en Files y `rmdir apps/wysun/tests`. Editar
`show_utility` en `orbit.py` como se indica arriba.

- [ ] **Step 4: Borrar y editar las pruebas afectadas** según la lista de Files.

- [ ] **Step 5: Ejecutar las suites y comprobar que todo pasa**

Run:
- `python3 -m unittest tests.test_dead_code -v` → los tres tests pasan.
- `python3 -m unittest discover -s tests` → OK.
- `python3 -m unittest discover -s tests/wysun_app -t tests` → OK.
- `QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py` → OK.
- `python3 tests/check_manifest.py` → MANIFEST_OK y TOOLS_OK.

Si alguna falla por un import de un módulo borrado, se corrige esa prueba; no se restaura el
módulo.

- [ ] **Step 6: Commit**

```bash
git add -A apps/wysun installer tests
git commit -m "chore(wysun): delete unused Qt colour window, helpers and dead modules"
```

---

### Task 2: Borrar la UI vieja y el `--pick-color` del Recorder

**Files:**
- Delete: `apps/capture/loomrec/ui/components.py` y `apps/capture/loomrec/ui/materials.py`
- Delete: la carpeta vacía y sin seguimiento `apps/capture/wybieshot/`
- Delete: `apps/capture/loomrec/analysis.py` (análisis de audio y subtítulos) y
  `apps/capture/loomrec/editing.py` (`Editor` transaccional). No están conectados a ninguna UI
  ni flujo; solo los usan sus pruebas.
- Delete: `apps/capture/tests/test_analysis.py` y `apps/capture/tests/test_editing_library.py`
- Modify: `apps/capture/loomrec/ui/material.py`. Se queda solo con `load_fonts()` y
  `symbol_pixmap(name, ink, size)` y sus constantes. Se borran `metric`, `layout_tokens`,
  `Navigation`, `Workspace`, `MediaPreview` y `_Artwork`, después de comprobar con grep en
  `apps/capture` que nadie más las usa (hoy solo `app_kit.metric` es distinta y se queda).
- Modify: `apps/capture/loomrec/__main__.py`, para quitar el argumento `--pick-color` y su rama.
- Modify: `apps/capture/loomrec/portal.py`, para quitar `pick_color()` y la rama `pick-color`
  del `main`, de modo que el mensaje de uso queda "Use screenshot". Antes se comprueba con
  `grep -rn 'pick-color\|pick_color' bin config apps installer` que nada lo invoca.
- Delete: `apps/capture/tests/test_materials.py`
- Modify estas pruebas:
  - `apps/capture/tests/test_visual_contract.py`: quitar el import de `SoftButton`,
    `test_reduced_motion_does_not_start_hover_animation` y
    `test_button_keyboard_activation_and_disabled_guard`.
  - `apps/capture/tests/test_wayland_ui_backend.py`: quitar las pruebas de `materials`.
  - `apps/capture/run_tests.py`: quitar los módulos borrados si los lista.

**Interfaces:**
- Consumes: `dead_python_modules` de la Task 1.

- [ ] **Step 1: Añadir la prueba a `DeadCodeTests`**

```python
    def test_every_recorder_ui_module_is_used_outside_tests(self):
        self.assertEqual(dead_python_modules(ROOT / 'apps/capture/loomrec/ui'), [])

    def test_every_recorder_module_is_used_outside_tests(self):
        self.assertEqual(dead_python_modules(ROOT / 'apps/capture/loomrec'), [])

    def test_recorder_has_no_portal_colour_picker(self):
        source = (ROOT / 'apps/capture/loomrec/__main__.py').read_text()
        self.assertNotIn('--pick-color', source)
```

- [ ] **Step 2: Ejecutar y comprobar que falla**

Run: `python3 -m unittest tests.test_dead_code -v`

Expected: FAIL.
- `test_every_recorder_module_is_used_outside_tests` lista `analysis` y `editing`.
- `test_recorder_has_no_portal_colour_picker` encuentra `--pick-color`.
- `test_every_recorder_ui_module_is_used_outside_tests` **pasa todavía** (prototipo: `[]`),
  porque `material.py` importa `components` en sus clases muertas. `components` y `materials`
  solo aparecen como muertos tras recortar `material.py` en el Step 3. Comprobar que entonces
  la prueba los lista, y luego borrarlos.

- [ ] **Step 3: Borrar y editar** según Files.

- [ ] **Step 4: Ejecutar y comprobar que pasa**

Run (serializado):
- `python3 -m unittest tests.test_dead_code -v` → OK.
- `python3 apps/capture/run_tests.py` → OK.

- [ ] **Step 5: Commit**

```bash
git add -A apps/capture tests/test_dead_code.py
git commit -m "chore(recorder): delete unused legacy UI and portal colour picker"
```

---

### Task 3: Borrar el QML muerto del shell

**Files:**
- Delete:
  - `apps/shell/modules/lock/` (18 archivos);
  - `apps/shell/daemons/Shortcuts.qml`;
  - `apps/shell/modules/nexus/common/TextFieldRow.qml`;
  - la carpeta vacía y sin seguimiento `apps/shell/tests/`.
- Modify: `apps/shell/shell.qml:21`, para quitar `import qs.modules.lock`.
- Modify: `apps/shell/UPSTREAM.json`, para quitar de `imported_files` las claves de los archivos
  borrados (`modules/lock/*`, `daemons/Shortcuts.qml`, `modules/nexus/common/TextFieldRow.qml`).
  Ya que se toca el archivo, quitar también las claves de cualquier archivo que no exista; un
  script de una línea las detecta.
- Modify: `apps/shell/README.md:15` y `ARCHITECTURE.md:48,219`, para quitar las menciones a
  `Shortcuts.qml` y al lock viejo.

**Interfaces:**
- Consumes: `DeadCodeTests` de la Task 1.

- [ ] **Step 1: Añadir las pruebas a `DeadCodeTests`**

```python
    def test_every_shell_module_is_imported(self):
        corpus = alive_names(ROOT)
        modules = sorted(p.name for p in (ROOT / 'apps/shell/modules').iterdir() if p.is_dir())
        unused = [m for m in modules
                  if not re.search(rf'qs\.modules\.{m}\b|modules/{m}\b', corpus)]
        self.assertEqual(unused, [])

    def test_real_lock_does_not_import_the_old_one(self):
        self.assertFalse((ROOT / 'apps/shell/modules/lock').exists())
        self.assertNotIn('qs.modules.lock\n', (ROOT / 'apps/shell/lock.qml').read_text())

    def test_upstream_manifest_lists_only_existing_files(self):
        data = json.loads((ROOT / 'apps/shell/UPSTREAM.json').read_text())
        missing = [f for f in data['imported_files'] if not (ROOT / 'apps/shell' / f).exists()]
        self.assertEqual(missing, [])
```

Nota: `test_every_shell_module_is_imported` debe excluir de su corpus los archivos del propio
módulo. Si no, `modules/lock/center/*.qml`, que hace `import qs.modules.lock`, lo haría parecer
vivo. Por eso el corpus se filtra quitando las rutas `apps/shell/modules/{m}/`.

- [ ] **Step 2: Ejecutar y comprobar que falla**

Run: `python3 -m unittest tests.test_dead_code -v`

Expected: FAIL.
- `test_every_shell_module_is_imported` no debería listar `lock`, porque `shell.qml` lo importa:
  es el caso "importado pero sin usar". Por eso existe la segunda prueba.
- `test_real_lock_does_not_import_the_old_one` falla porque la carpeta existe.
- `test_upstream_manifest_lists_only_existing_files` lista las entradas obsoletas (WallItem,
  ColourSelect, dash/Resources, M3Variants…).

- [ ] **Step 3: Borrar y editar** según Files.

- [ ] **Step 4: Ejecutar y comprobar que pasa**

Run:
- `python3 -m unittest tests.test_dead_code -v` → OK.
- `python3 -m unittest discover -s tests/shell_bridge -t tests` → OK.
- `python3 apps/shell/scripts/qml-lint-conventions.py` → sin errores nuevos respecto a
  `e336be92`. Ejecutarlo antes y después y comparar.
- `python3 tests/check_manifest.py` → OK.

- [ ] **Step 5: Commit**

```bash
git add -A apps/shell ARCHITECTURE.md tests/test_dead_code.py
git commit -m "chore(shell): delete unused legacy lock module, shortcuts daemon and stale upstream entries"
```

---

### Task 4: Documentación y referencias obsoletas

**Files:**
- Modify: `docs/maintenance.md:15`. Quitar `notes_window.py` y `color_window.py`. Color vive en
  `apps/shell/modules/colors/`; los datos, en `utility_data.py`.
- Modify: `docs/themes.md`, para quitar la mención a `theme_demo`.
- Modify: `THIRD_PARTY.md`, para quitar las entradas de `utility_material`, `screen_lock`,
  `wysun_fonts` y cualquier otro archivo borrado en las Tasks 1-3, conservando los créditos de
  lo que sigue existiendo.
- Delete: `docs/multimedia-architecture-plan.md`. Es un plan ya ejecutado cuyo estado final está
  en `ARCHITECTURE.md`; decisión de Claude, por ser historia y no referencia viva. Antes,
  `grep -rn multimedia-architecture-plan` y quitar los enlaces a él.
- `tests/media_benchmark.py:5` se deja como está: menciona `mpv_embed.py` como historia
  explícita ("removed with").

**Interfaces:** ninguna.

- [ ] **Step 1: Añadir la prueba a `DeadCodeTests`**

```python
    DELETED = ('color_window.py', 'utility_material', 'notes_window.py', 'theme_demo',
               'screen_lock', 'wysun_fonts', 'clean_legacy', 'loomrec/ui/components',
               'loomrec/ui/materials', 'modules/lock/', 'Shortcuts.qml',
               'multimedia-architecture-plan')

    def test_docs_do_not_point_to_deleted_files(self):
        docs = [p for p in (ROOT / 'docs').rglob('*.md') if 'superpowers' not in p.parts]
        docs += [ROOT / n for n in ('README.md', 'ARCHITECTURE.md', 'THIRD_PARTY.md', 'AGENTS.md')]
        hits = [f'{p.relative_to(ROOT)}:{name}' for p in docs for name in self.DELETED
                if name in p.read_text()]
        self.assertEqual(hits, [])
```

- [ ] **Step 2: Ejecutar y comprobar que falla**

Run: `python3 -m unittest tests.test_dead_code.DeadCodeTests.test_docs_do_not_point_to_deleted_files -v`

Expected: FAIL. Lista al menos `docs/maintenance.md`, `docs/themes.md` y `THIRD_PARTY.md`.

- [ ] **Step 3: Editar y borrar** según Files.

- [ ] **Step 4: Ejecutar y comprobar que pasa**

Run:
- `python3 -m unittest tests.test_dead_code -v` → OK.
- `python3 -m unittest tests.test_branding -v` → OK.

- [ ] **Step 5: Commit**

```bash
git add -A docs README.md ARCHITECTURE.md THIRD_PARTY.md tests/test_dead_code.py
git commit -m "docs: drop references to deleted modules and the finished multimedia plan"
```

---

### Task 5: Verificación completa, despliegue y prueba en vivo

**Files:** ninguno, salvo que una verificación obligue a corregir algo; en ese caso, commit
aparte.

- [ ] **Step 1: Ejecutar todas las suites requeridas**

Run, en serie:
- `python3 -m unittest discover -s tests -v`
- `python3 -m unittest discover -s tests/wysun_app -t tests`
- `python3 -m unittest discover -s tests/shell_bridge -t tests`
- `QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py`
- `python3 tests/check_manifest.py`
- `python3 apps/capture/run_tests.py`
- `python3 tests/wysun_installed_smoke.py`

Expected: todas OK. Las únicas omisiones aceptadas son las ya existentes; los bloqueos del
sandbox se anotan, no se cuentan como fallo del producto.

- [ ] **Step 2: Desplegar**

Run: `./instalar.sh --orbit-only`, y luego `~/.local/bin/orbit reload`.

Expected: termina sin conflictos.

- [ ] **Step 3: Reiniciar solo el shell**

Run: `pkill -x quickshell; setsid wysun-shell &`

Expected: el log del shell no muestra errores de `import`, `module "qs.modules.lock"` ni
componentes no encontrados.

- [ ] **Step 4: Comprobar en vivo**

Abrir de verdad estas superficies y confirmar que se abren:
- `wysun colors` (y `Super+Shift+C`, que muestrea y abre el panel);
- el lanzador (`wysun`);
- Settings (`wysun settings`);
- `wysun music`;
- `orbit-files`;
- `wysun recorder`.

La pantalla de bloqueo no se activa en automático. Basta con confirmar que `lock.qml` carga:
`wysun-shell` no reporta errores y `test_real_lock_does_not_import_the_old_one` pasa.

- [ ] **Step 5: Informar**

Resumen de lo borrado (líneas eliminadas según `git diff --stat e336be92`), resultado de cada
suite y de cada apertura en vivo.

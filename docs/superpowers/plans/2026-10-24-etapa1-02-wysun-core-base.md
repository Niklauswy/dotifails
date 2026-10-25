# Etapa 1 · Plan 02 — `wysun_core`: rutas, JSON atómico e instancia única · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el paquete compartido `wysun_core` con rutas XDG, escritura y lectura atómica de
JSON y la instancia única. Después, migrar a él las apps Python de Wysun, los backends del shell
y el Recorder, borrar las copias y dejar una prueba guardián que impida que vuelvan.

**Architecture:**
- `apps/wysun/wysun_core/` es un paquete Python. `paths`, `jsonio` e `instance` usan solo la
  biblioteca estándar, para que clientes ligeros como `player_client.py` sigan arrancando sin Qt;
  `qt_instance` añade el puente con Qt.
- El instalador ya copia `apps/wysun` entero a `~/.local/share/orbit/app/`.
- El Recorder recibe el paquete por el enlace `apps/capture/wysun_core → ../wysun/wysun_core`,
  que se copia dentro de cada release (el mismo mecanismo que `wysun_media`). El instalador
  gráfico lo recibe en su `ui_runtime`.
- Los nombres actuales de rutas, sockets y espacios (`orbit`, `wysun`, `loomrec`) **no cambian**
  aquí. Las funciones reciben el espacio como argumento, así el plan 04 los renombra en un solo
  sitio por llamada.

**Tech Stack:** Python 3.13 stdlib (`fcntl`, `socket`, `tempfile`), PySide6 6.8 (`QSocketNotifier`), unittest.

**Spec:** `docs/superpowers/specs/2026-10-24-wysun-limpieza-base-comun-design.md` (§2, paso 3 del
orden de trabajo, primera parte: paths, jsonio, instance). El tema (`wysun_core.theme`) y el kit de
widgets (`wysun_core.ui`) son los planes 02b y 02c.

## Global Constraints

- No reiniciar Hyprland, no cerrar otras apps, no instalar dependencias del host.
- Pruebas de medios y compositor en serie, con HOME/XDG temporales.
- Despliegue con `./instalar.sh --orbit-only --source <checkout limpio>`: el recibo guarda como
  origen `.superpowers/deploy-src`. Tras desplegar, `~/.local/bin/orbit reload`. Si se toca QML,
  reiniciar solo el shell.
- **Sin compatibilidad nueva:** al migrar un consumidor se borra su copia (función, módulo o
  bloque), sin alias ni reexportaciones.
- Fuera de alcance, aunque tengan copias; se anotan en `PENDING` de la prueba guardián con su
  plan dueño:
  - **Plan 02b (tema):** `apps/wysun/theme_core.py`, `apps/capture/loomrec/ui/theme_core.py`,
    `theme_tokens.py`, `ui_appearance.py`, `loomrec/ui/tokens.py`, `loomrec/ui/motion.py` y
    `loomrec/ui/app_kit.py`.
  - **Plan 04 (empaquetado y renombrado):** `installer/*.py`, `apps/tools/**` y
    `apps/shell/modules/aiusage/backend.py` (no importa la app; su `sys.path` se resuelve con el
    `PYTHONPATH` del plan 04).
- `wysun_core` nunca importa módulos de una app (`theme_tokens`, `wysun_music`, `loomrec`…).
- Los archivos privados siguen siendo `0o600` y los directorios que se crean, `0o700`.
- Estado de partida: `main` en `529af187`. Todas las suites requeridas pasan.

## Review Focus

1. **Un archivo que hoy conserva sus permisos al reescribirse** (por ejemplo, un `.lua` del
   usuario reescrito por `settings_data.atomic_write`, o un `0o644`) **debe conservarlos**, y uno
   nuevo nace `0o600`. Lo cubre `test_rewrite_keeps_mode_and_new_file_is_private` (Task 1).
2. **Un JSON corrupto o vacío** en `colors.json`, en `scheme.json` o en las preferencias del
   Recorder **no debe tumbar la app**: `read_json` devuelve el valor por defecto, salvo que el
   llamante pida `strict=True`. Lo cubre `test_invalid_json_returns_default_unless_strict`
   (Task 1).
3. **Dos lanzamientos simultáneos** de Music, Player o Recorder deben acabar en una sola
   instancia, y el segundo debe entregar su petición. Un socket huérfano de un proceso muerto no
   puede bloquear el arranque. Lo cubren `test_second_claim_fails_while_first_holds_lock` y
   `test_stale_socket_is_replaced` (Task 2), además de la apertura doble en vivo (Task 7).
4. **Sin `XDG_RUNTIME_DIR`** (sesión TTY o pruebas), las rutas de runtime deben seguir siendo
   válidas y privadas. Lo cubre `test_runtime_dir_falls_back_to_tempdir` (Task 1).
5. **Una release del Recorder ya instalada** debe seguir funcionando: las releases nuevas llevan
   su propia copia de `wysun_core` y nunca importan la de `orbit/app`. Lo cubre
   `test_capture_release_ships_wysun_core` (Task 1) y la grabación en vivo (Task 7).

---

### Task 1: `wysun_core.paths` y `wysun_core.jsonio`, más su empaquetado

**Files:**
- Create:
  - `apps/wysun/wysun_core/__init__.py` (solo un docstring);
  - `apps/wysun/wysun_core/paths.py`;
  - `apps/wysun/wysun_core/jsonio.py`;
  - el enlace simbólico `apps/capture/wysun_core` → `../wysun/wysun_core`.
- Modify:
  - `installer/capture_distribution.py:58`: la tupla pasa a `('loomrec', 'assets', 'wysun_media', 'wysun_core')`
    y el comentario se actualiza;
  - `installer/ui_support.py`: `package_runtime` copia el árbol `wysun_core/` completo con
    `shutil.copytree` e `ignore_patterns('__pycache__', '*.pyc')`.
- Test: `tests/test_core_paths.py`, `tests/test_core_jsonio.py`, `tests/test_core_packaging.py`.

**Interfaces — Produces:**
```python
# wysun_core/paths.py  (stdlib only; reads the environment on every call)
def home() -> Path
def config_home() -> Path      # $XDG_CONFIG_HOME if set and absolute, else ~/.config
def data_home() -> Path        # $XDG_DATA_HOME  | ~/.local/share
def state_home() -> Path       # $XDG_STATE_HOME | ~/.local/state
def cache_home() -> Path       # $XDG_CACHE_HOME | ~/.cache
def bin_home() -> Path         # ~/.local/bin
def runtime_dir() -> Path      # $XDG_RUNTIME_DIR if set and absolute, else tempfile.gettempdir()
def config(*parts: str) -> Path   # config_home().joinpath(*parts); same for data/state/cache/runtime
def data(*parts: str) -> Path
def state(*parts: str) -> Path
def cache(*parts: str) -> Path
def runtime(*parts: str) -> Path
def private_dir(path: Path) -> Path  # mkdir(parents=True, mode=0o700); RuntimeError if symlink, other owner or group/other bits

# wysun_core/jsonio.py  (stdlib only)
@contextmanager
def atomic_path(path, *, mode: int | None = None) -> Iterator[Path]
    # yields a temp path in path.parent; on clean exit: chmod (mode, else existing file's mode, else 0o600),
    # fsync file, os.replace, fsync dir. On exception: temp removed, target untouched. Parent created 0o700.
def atomic_write_bytes(path, data: bytes, *, mode: int | None = None) -> Path
def atomic_write_text(path, text: str, *, mode: int | None = None) -> Path      # utf-8
def atomic_write_json(path, data, *, mode: int | None = None, indent: int | None = 2) -> Path
    # json.dumps(data, ensure_ascii=False, allow_nan=False, indent=indent) + '\n'
def read_json(path, default=None, *, strict: bool = False)
    # missing → deepcopy(default); invalid UTF-8/JSON → deepcopy(default), or ValueError naming the path if strict
```

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_core_paths.py` (agrega `apps/wysun` a `sys.path`, como el resto de pruebas):
```python
def test_xdg_variables_win_when_absolute(self):
    with patch.dict(os.environ, {'XDG_CONFIG_HOME': '/x/cfg', 'XDG_STATE_HOME': 'relative'}):
        self.assertEqual(paths.config('orbit', 'theme.json'), Path('/x/cfg/orbit/theme.json'))
        self.assertEqual(paths.state_home(), Path.home() / '.local/state')   # relative value is ignored
def test_runtime_dir_falls_back_to_tempdir(self):
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('XDG_RUNTIME_DIR', None)
        self.assertEqual(paths.runtime_dir(), Path(tempfile.gettempdir()))
def test_private_dir_rejects_open_permissions(self):
    # tmp/shared created 0o755 → RuntimeError; tmp/new → created 0o700
```
`tests/test_core_jsonio.py`:
```python
def test_rewrite_keeps_mode_and_new_file_is_private(self):
    # existing file chmod 0o644 → after atomic_write_text stays 0o644; new file → 0o600; parent created 0o700
def test_failure_leaves_target_and_no_temporary(self):
    # with atomic_path(target) as tmp: tmp.write_text('x'); raise RuntimeError → target keeps old text, dir has no extra files
def test_json_round_trip_is_utf8_with_newline(self):
    # atomic_write_json(p, {'nombre': 'canción'}) → p.read_bytes().endswith(b'}\n') and 'canción' in text; read_json(p) == data
def test_invalid_json_returns_default_unless_strict(self):
    # p.write_text('{'); read_json(p, {'a': 1}) == {'a': 1} and is a copy; read_json(p, strict=True) raises ValueError with str(p) in message
def test_missing_file_returns_copy_of_default(self):
    # d = {'k': []}; r = read_json(missing, d); r['k'].append(1); d == {'k': []}
def test_nan_is_rejected(self):
    # atomic_write_json(p, {'x': float('nan')}) raises ValueError; p does not exist
```
`tests/test_core_packaging.py`:
```python
def test_capture_tree_links_wysun_core(self):
    link = ROOT / 'apps/capture/wysun_core'
    self.assertTrue(link.is_symlink()); self.assertEqual(link.resolve(), (ROOT / 'apps/wysun/wysun_core').resolve())
def test_capture_release_ships_wysun_core(self):
    self.assertIn("'wysun_core'", (ROOT / 'installer/capture_distribution.py').read_text())
def test_installer_runtime_copies_wysun_core(self):
    # package_runtime(ROOT, tmp) → (tmp/'wysun_core/jsonio.py').is_file() and no __pycache__ copied
def test_core_imports_no_application_module(self):
    # every wysun_core/*.py: no import of theme_tokens|theme_core|wysun_music|wysun_files|loomrec|orbit|music_material
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `python3 -m unittest tests.test_core_paths tests.test_core_jsonio tests.test_core_packaging -v`

Expected: ERROR `ModuleNotFoundError: No module named 'wysun_core'` en las dos primeras, y FAIL
en las de empaquetado (no hay enlace ni entrada en la tupla).

- [ ] **Step 3: Implementar** `paths.py` y `jsonio.py` con las firmas de arriba, crear el enlace
(`ln -s ../wysun/wysun_core apps/capture/wysun_core`) y editar `capture_distribution.py` y
`ui_support.py`.

- [ ] **Step 4: Ejecutar y comprobar que pasan**

Run: `python3 -m unittest tests.test_core_paths tests.test_core_jsonio tests.test_core_packaging -v` → OK.
Run: `python3 -m unittest tests.test_dead_code` → OK. El cierre transitivo cuenta `wysun_core`
como vivo solo cuando tiene consumidores; si hoy sale como muerto, se acepta hasta la Task 3 y se
anota en el ledger.

- [ ] **Step 5: Commit** — `feat(core): wysun_core paths and atomic JSON, shipped to Recorder releases and the installer runtime`

---

### Task 2: `wysun_core.instance` y `wysun_core.qt_instance`

**Files:**
- Create: `apps/wysun/wysun_core/instance.py` (solo stdlib) y `apps/wysun/wysun_core/qt_instance.py` (PySide6).
- Test: `tests/test_core_instance.py`.

**Interfaces — Produces:**
```python
# wysun_core/instance.py
class SingleInstance:
    def __init__(self, name: str, directory: Path | None = None)
        # endpoint = dir / f'{name}.sock', lock_path = dir / f'{name}.lock'; dir = directory (via paths.private_dir) or paths.runtime_dir()
    endpoint: Path
    lock_path: Path
    def claim(self) -> bool
        # flock(LOCK_EX | LOCK_NB) on lock_path (RuntimeError if it is a symlink); False if held by another process.
        # Then: endpoint exists and is not a socket → RuntimeError; else unlink stale endpoint, bind, chmod 0o600, listen(8), non-blocking.
    def fileno(self) -> int
    def poll(self, handler: Callable[[bytes], bytes | None], *, limit: int = 4096, timeout: float = 3.0) -> None
        # accept all pending clients; read without blocking; for each complete line call handler(line) and
        # send reply + b'\n' when it returns bytes; drop clients over `limit` bytes or older than `timeout` seconds.
    def close(self) -> None   # closes clients and server, unlinks endpoint, releases and closes the lock

def send(endpoint: Path, message: bytes, *, timeout: float = 1.0, reply: bool = False, retry: float = 0.0) -> bool | bytes | None
    # connect, sendall(message + b'\n'). reply=False → True on delivery, False on OSError.
    # reply=True → the first response line without b'\n' (≤ 4096 bytes), or None on OSError.
    # retry > 0 → keeps retrying FileNotFoundError/ConnectionRefusedError until `retry` seconds have passed.

# wysun_core/qt_instance.py
class InstanceNotifier(QObject):
    def __init__(self, instance: SingleInstance, handler: Callable[[bytes], bytes | None], parent=None)
        # QSocketNotifier(instance.fileno(), Read) → instance.poll(handler); plus a 500 ms QTimer that polls while clients are pending
    def close(self) -> None
```

- [ ] **Step 1: Escribir las pruebas que fallan** (directorio temporal privado como `directory`):
```python
def test_second_claim_fails_while_first_holds_lock(self):
    a, b = SingleInstance('t', d), SingleInstance('t', d)
    self.assertTrue(a.claim()); self.assertFalse(b.claim()); a.close(); self.assertTrue(b.claim())
def test_stale_socket_is_replaced(self):
    # bind a socket at d/'t.sock' and close it without unlinking → claim() is True
def test_non_socket_endpoint_is_refused(self):
    # (d/'t.sock').write_text('x') → claim() raises RuntimeError
def test_send_delivers_line_and_reads_reply(self):
    # claimed instance in a thread polling with handler lambda line: b'ok:' + line → send(ep, b'hola', reply=True) == b'ok:hola'
def test_send_without_server_is_false(self):
    self.assertFalse(send(d / 'none.sock', b'x'))
def test_oversized_request_is_dropped_without_reply(self):
    # handler never called for a 5000-byte line; send(..., reply=True) returns b'' or None
def test_endpoint_and_lock_are_private(self):
    # after claim: stat(endpoint).st_mode & 0o777 == 0o600
def test_qt_notifier_dispatches_requests(self):
    # QCoreApplication; InstanceNotifier(instance, handler); send from a thread; process events until handler saw b'present'
```

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_core_instance -v`

Expected: ERROR `ModuleNotFoundError: No module named 'wysun_core.instance'`.

- [ ] **Step 3: Implementar** `instance.py` y `qt_instance.py`.

- [ ] **Step 4: Ejecutar y comprobar que pasan**

Run: `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_core_instance -v` → OK.

- [ ] **Step 5: Commit** — `feat(core): single-instance socket and its Qt notifier`

---

### Task 3: Migrar JSON y rutas de las apps Python de Wysun

**Files — Modify:** cada archivo reemplaza sus escrituras atómicas por `wysun_core.jsonio`, su
lectura de JSON por `read_json` y sus rutas XDG o `~/.config|.local|.cache` por `wysun_core.paths`.

| Archivo | Qué se reemplaza |
|---|---|
| `settings_data.py` | Borrar `atomic_write` (:19) y la escritura de :150; `backup_file` usa `paths.data('orbit', 'settings-backups')` |
| `utility_data.py` | Borrar `atomic` |
| `environment_settings.py` | Borrar `read_json` (:31) y usar `jsonio.read_json(path, {})`; las 4 rutas de `settings-backups` |
| `launcher_data.py` | :149 y :198 pasan a `atomic_write_json`/`atomic_path`; `STATE` y los cachés |
| `music_metadata.py` | :100 `atomic_write_json`; :116 `with atomic_path(path) as tmp: image.save(str(tmp), 'PNG')` |
| `wallpaper_media.py` | :106 y :144, descargas por partes, con `atomic_path`; `cache_dir` |
| `launcher_web.py` | :115 |
| `code_preview.py` | :77 |
| `wysun_media/resume.py` | :60-67 |
| `hypr_settings.py` | `config_dir` |
| `nvim_theme.py`, `settings_runtime.py`, `files_browser.py`, `desktop_backend.py`, `core.py`, `wysun_music/app.py` (`_runtime`) | Lecturas de XDG |

Los usuarios de `settings_data.atomic_write` e `utility_data.atomic` en otros módulos importan
ahora `wysun_core.jsonio` directamente; se localizan con `grep -rn "atomic_write\|import atomic\|\.atomic(" apps/wysun`.
`theme_core.py`, `theme_tokens.py` y `ui_appearance.py` no se tocan (plan 02b).

- [ ] **Step 1: Escribir la prueba guardián que falla.** `tests/test_core_owns_io.py`:
```python
PENDING = {  # path → owning plan; every entry is removed by that plan
    'apps/wysun/theme_core.py': '02b', 'apps/capture/loomrec/ui/theme_core.py': '02b',
    'apps/wysun/theme_tokens.py': '02b', 'apps/wysun/ui_appearance.py': '02b',
    'apps/capture/loomrec/ui/tokens.py': '02b', 'apps/capture/loomrec/ui/motion.py': '02b',
    'apps/capture/loomrec/ui/app_kit.py': '02b',
    'apps/shell/modules/aiusage/backend.py': '04',
}
SCOPES = ('apps/wysun', 'apps/shell', 'apps/capture/loomrec')    # installer/ and apps/tools/ belong to plan 04
ATOMIC = re.compile(r'os\.replace\(|mkstemp\(|\b\w+\.replace\(\s*(self\.)?\w*(path|target|dest|final)\w*\s*\)')
XDG = re.compile(r'XDG_(CONFIG|DATA|STATE|CACHE)_HOME|XDG_RUNTIME_DIR')
def offenders(pattern): # .py files under SCOPES, excluding wysun_core/, vendor/, tests/ and PENDING → ['path:line', ...]
def test_atomic_writes_live_in_wysun_core(self): self.assertEqual(offenders(ATOMIC), [])
def test_xdg_lookups_live_in_wysun_core(self): self.assertEqual(offenders(XDG), [])
def test_pending_entries_still_need_it(self):
    # each PENDING path exists and matches ATOMIC or XDG, so a migrated file must leave the list
```

- [ ] **Step 2: Ejecutar y comprobar que falla**

Run: `python3 -m unittest tests.test_core_owns_io -v`

Expected: FAIL. Lista los archivos de la tabla de arriba, más los del Recorder (Task 5) y los de
los backends del shell (Task 6).

- [ ] **Step 3: Migrar los archivos de la tabla.** Comprobar con `git grep -n "def atomic_write\|def atomic(\|def read_json" apps/wysun`
que no queda ninguna definición propia.

- [ ] **Step 4: Ejecutar las suites**

Run:
- `python3 -m unittest discover -s tests` → OK (salvo `test_core_owns_io`, que solo lista
  Recorder y shell).
- `python3 -m unittest discover -s tests/wysun_app -t tests` → OK.
- Si una prueba compara bytes exactos de un JSON escrito, se actualiza al formato nuevo (con
  salto de línea final) solo si ningún programa externo lee esos bytes.

- [ ] **Step 5: Commit** — `refactor(wysun): use wysun_core for paths and atomic JSON`

---

### Task 4: Migrar la instancia única (Music, Player, residente y Recorder)

**Files:**
- Modify:
  - `apps/wysun/wysun_music/app.py:55-110`: `SingleInstance(f'orbit-music-app-{uid}')`, `send(...)`
    para reenviar e `InstanceNotifier` con un handler que llama a `music.present(line.decode())`.
  - `apps/wysun/player_client.py`: `endpoint()` y `lock_path()` salen de
    `SingleInstance(f'wysun-player-{uid}')`; `forward` usa `send(..., reply=True)` y compara
    con `startswith(b'ok')`. Sigue siendo solo stdlib.
  - `apps/wysun/player_app.py` y `apps/wysun/player_window.py`: el bucle de reclamo de 3 s y el
    servidor usan `SingleInstance` e `InstanceNotifier`.
  - `apps/wysun/orbit.py:15,98-131`: socket `orbit-{uid}`; ahora con lock (gana robustez).
  - `apps/capture/loomrec/ui/instance.py`: `Instance` conserva su API pública (`claim`,
    `request`, `poll`, `close`) como envoltura fina sobre `SingleInstance(f'{name}-{tag}', paths.runtime(f'loomrec-{uid}'))`.
    Las acciones permitidas y el JSON por línea se quedan en el Recorder; `request` usa
    `send(..., reply=True, retry=timeout)`.
- Delete: `apps/wysun/local_ipc.py`.
- Test: las pruebas existentes de cada consumidor, además de una nueva en
  `tests/test_core_instance.py`:
  `test_recorder_instance_keeps_private_directory_and_display_tag`.

- [ ] **Step 1: Escribir la prueba nueva que falla**
```python
def test_recorder_instance_keeps_private_directory_and_display_tag(self):
    # with XDG_RUNTIME_DIR=tmp, WAYLAND_DISPLAY='wayland-9': Instance(name='gui').path.parent == tmp/f'loomrec-{uid}' (mode 0o700)
    # and the path name starts with 'gui-'; Instance('gui').claim() True; a second Instance('gui').claim() False
    # and assert loomrec.ui.instance imports SingleInstance (source contains 'from wysun_core.instance import SingleInstance')
```

- [ ] **Step 2: Ejecutar y comprobar que falla**

Run: `cd apps/capture && python3 -m unittest discover -s ../../tests -p test_core_instance.py`.
Si el import de `loomrec` no resuelve desde `tests/`, la prueba añade `apps/capture` a
`sys.path`.

Expected: FAIL en la aserción del import de `SingleInstance`.

- [ ] **Step 3: Migrar los cinco consumidores y borrar `local_ipc.py`.** Luego,
`git grep -n "fcntl.flock\|AF_UNIX" apps/wysun apps/capture/loomrec` solo puede mostrar
`wysun_core/instance.py` y usos que no sean de instancia única (por ejemplo, el cliente IPC de
Hyprland).

- [ ] **Step 4: Ejecutar las suites, en serie**

Run:
- `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_core_instance tests.test_player_app tests.test_music -v` → OK.
- `python3 -m unittest discover -s tests/wysun_app -t tests` → OK.
- `python3 apps/capture/run_tests.py` → OK.
- `python3 -m unittest tests.test_dead_code` → OK (`local_ipc` ya no existe).

- [ ] **Step 5: Commit** — `refactor: one single-instance implementation for Music, Player, resident and Recorder`

---

### Task 5: Migrar JSON y rutas del Recorder

**Files — Modify** (`apps/capture/loomrec/`):

| Archivo | Qué se reemplaza |
|---|---|
| `schema.py` | Borrar `atomic_json` (:157); los llamantes usan `atomic_write_json(path, data)`. Ya escribía `indent=2`, `ensure_ascii=False` y `allow_nan=False` |
| `consent.py` | :81 y :114 |
| `headless.py` | :143 |
| `portal.py` | :31 |
| `ui/capture_feedback_prefs.py` | :22 (hoy no es atómico de verdad: escribe `.tmp` sin fsync) |
| `library.py`, `videolibrary.py`, `wayland_pointer.py` | Lecturas de XDG con `paths` |

Los usuarios de `schema.atomic_json` se localizan con `grep -rn atomic_json apps/capture`.

- [ ] **Step 1: La prueba guardián de la Task 3 ya falla por estos archivos.** Comprobarlo:

Run: `python3 -m unittest tests.test_core_owns_io -v`

Expected: FAIL. Lista estos archivos.

- [ ] **Step 2: Migrar.**

- [ ] **Step 3: Ejecutar y comprobar que pasa**

Run (serie):
- `python3 apps/capture/run_tests.py` → OK.
- `python3 -m unittest tests.test_core_owns_io -v` → solo quedan los backends del shell.

- [ ] **Step 4: Commit** — `refactor(recorder): use wysun_core for paths and atomic JSON`

---

### Task 6: Backends del shell y cierre de la guardia

**Files — Modify:**
- `apps/shell/modules/colors/backend.py`, `apps/shell/modules/processes/backend.py` y
  `apps/shell/wysun/display_bridge.py`: el bloque que localiza `orbit/app` usa
  `os.environ.get('XDG_DATA_HOME')`, que es justo lo que la guardia prohíbe. Se reemplaza por
  `Path(__file__)` (fuente) o, en su defecto, `Path.home() / '.local/share/orbit/app'`, la ruta
  instalada fija.

  Esto es temporal y está documentado: el plan 04 elimina estos bloques con `PYTHONPATH`. La
  instalación siempre está en `~/.local/share`, porque el instalador despliega con rutas fijas
  relativas a HOME (`installer/main.py:210`).

  Decisión de Claude: el backend no puede importar `wysun_core` antes de encontrar la app.
- `apps/shell/wysun/backend.py`: sus lecturas de XDG pasan a `wysun_core.paths` (importa la app
  después de localizarla).

- [ ] **Step 1:** Run: `python3 -m unittest tests.test_core_owns_io -v`. Expected: FAIL, solo con
  estos archivos.
- [ ] **Step 2: Migrar.**
- [ ] **Step 3:** Run:
  - `python3 -m unittest tests.test_core_owns_io -v` → OK;
  - `python3 -m unittest discover -s tests/shell_bridge -t tests` → OK.
- [ ] **Step 4: Commit** — `refactor(shell): backends resolve paths through wysun_core`

---

### Task 7: Verificación completa, despliegue y prueba en vivo

- [ ] **Step 1: Ejecutar todas las suites requeridas** en un worktree limpio del commit:
  - `python3 -m unittest discover -s tests -v`
  - `python3 -m unittest discover -s tests/wysun_app -t tests`
  - `python3 -m unittest discover -s tests/shell_bridge -t tests`
  - `QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py`
  - `python3 tests/check_manifest.py`
  - `python3 apps/capture/run_tests.py`
  - `python3 tests/wysun_installed_smoke.py`

  Expected: todas OK.
- [ ] **Step 2: Desplegar.**
  1. `git -C .superpowers/deploy-src checkout --detach main`.
  2. `./instalar.sh --orbit-only --source "$PWD"` desde ese worktree. Expected: rc 0 y sin
     conflictos.
  3. `~/.local/bin/orbit reload`.
  4. Reiniciar solo el shell.
- [ ] **Step 3: Comprobar en vivo**, cerrando solo las ventanas abiertas para la prueba:
  - `wysun music` dos veces seguidas: una sola ventana `orbit-music`, que vuelve al frente.
  - `wysun player <imagen>` dos veces a la vez: una sola instancia, con las dos peticiones
    servidas.
  - `wysun colors`: aparece la capa `wysun-colors` y los favoritos se guardan (`colors.json`
    sigue siendo válido).
  - `wysun recorder` dos veces: una sola ventana.
  - Una grabación breve de 3 s de una región con `wysun-shell record start`, detenida después;
    el proyecto queda en la biblioteca.
  - Settings: cambiar y restaurar un ajuste para comprobar que se escribe la copia de respaldo en
    `settings-backups`.
- [ ] **Step 4: Informar** las líneas eliminadas (`git diff --stat 529af187`), cada suite y cada
  comprobación en vivo.

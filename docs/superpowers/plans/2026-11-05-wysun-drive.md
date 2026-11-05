# Wysun Drive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `wysun drive` sube archivos y carpetas al Nextcloud del usuario y da el link público, desde terminal (CLI + selector TUI), Files, la captura y la barra.

**Architecture:** Paquete stdlib `wysun_drive` (cliente WebDAV/OCS sobre `http.client`, planificador de subidas, historial, archivo de estado para la barra, CLI y TUI sobre `wysun_core.tui`). El shell lee el estado como LANShare; Files y la captura lanzan el CLI con `--notificar`.

**Tech Stack:** Python 3 stdlib, `wysun_core` (paths, jsonio, launch, tui), QML (Quickshell), PySide6/QML de Files.

**Spec:** `docs/superpowers/specs/2026-11-05-wysun-drive-design.md`

## Global Constraints

- Solo biblioteca estándar; paquete `apps/python/wysun_drive`; `MODULES['drive'] = ('app', 'wysun_drive', [])`.
- Cuenta `~/.local/share/wysun/drive/account.json` (0700/0600); historial `~/.local/share/wysun/drive/history.json` (≤200); ajustes `~/.config/wysun/drive.json`.
- Servidor por defecto `https://cloud.wysun.store`; carpeta por defecto `Wysun`.
- HTTPS obligatorio salvo `127.0.0.1`/`localhost`; sin seguir redirecciones; la contraseña de aplicación nunca en salidas, errores, estado ni historial.
- Trozos: archivos ≥ 64 MiB en trozos de 16 MiB, 3 reintentos por trozo.
- Estado de barra `$XDG_RUNTIME_DIR/wysun-drive/<pid>.json`, latido 10 s, vivo si < 30 s.
- Salida: 0 bien, 1 fallo, 2 uso, 3 sin sesión. Textos en español.
- UI con tokens (`Tokens.*`, `Colours.*`, `Palette`), sin colores literales.

## Review Focus

- Nombre con espacios, acentos, `#`, `%` o `?`: la ruta WebDAV debe ir codificada (prueba en Task 1).
- Archivo remoto ya existente: `nombre (2).ext`, nunca reemplazar (Task 2).
- Contraseña revocada en Nextcloud (401): mensaje «La sesión ya no es válida: wysun drive login», salida 3 (Task 1/4).
- Enlace simbólico o ruta inexistente en la lista: se informa y el resto sigue (Task 2).
- Servidor que exige contraseña en links (OCS 403/400): error en español con el mensaje del servidor (Task 1).

---

### Task 1: Cliente Nextcloud y cuenta

**Files:** Create `apps/python/wysun_drive/{__init__,account,client,login}.py`; Test `tests/drive/test_client.py` (servidor HTTP falso en 127.0.0.1 que implementa PROPFIND/MKCOL/PUT/MOVE/OCS/login v2).

**Interfaces — Produces:**
- `account.Account(server, user, password)`; `account.load() -> Account|None`, `account.save(acc)`, `account.forget()`, `account.settings() -> {'server','folder'}`.
- `client.DriveError(message, code=1)`; `client.AuthError(DriveError)` (code 3).
- `client.Client(acc)`: `exists(remote) -> bool`, `mkdirs(remote)`, `put(remote, path, progress=None)`, `share(remote, password=None, expire_days=None) -> {'id','url'}`, `unshare(id)`.
- `login.start(server) -> (login_url, poll)`; `login.wait(poll, timeout=1200, interval=2) -> Account`.

- [ ] Tests: subir pequeño y grande (umbral reducido por parámetro) llegan íntegros; ruta con `á #%?` codificada; 401 → `AuthError`; OCS error → `DriveError` con el mensaje del servidor; `http://` a host no local rechazado; la contraseña sintética no aparece en `str()` de ningún error; account.json con modo 0600; redirección 302 no se sigue.
- [ ] Implementar; pasar pruebas; commit.

### Task 2: Planificador y subida

**Files:** Create `apps/python/wysun_drive/{upload,history,status,api}.py`; Test `tests/drive/test_upload.py`.

**Interfaces — Produces:**
- `upload.Item(local, remote, size, is_dir)`; `upload.plan(client, paths, folder, name=None) -> (items, problems)` (resuelve conflictos de primer nivel con `(2)`…).
- `upload.run(client, items, on_progress(name, done, total), cancelled=lambda: False) -> list[Result]`, `Result(local, remote, size, is_dir, link=None, password=None, error=None)`.
- `history.add(results)`, `history.load() -> list[dict]`, `history.set_link(remote, url, id)`.
- `status.StatusFile(pid, title)` `.update(items)`, `.remove()`; `status.stop(pid) -> bool`.
- `api.upload(paths, link=False, folder=None, name=None, password=None, expire_days=None, on_progress=None) -> list[Result]`.

- [ ] Tests: carpeta con subcarpetas crea MKCOL y PUT; existente → `(2)`; inexistente/enlace → `problems`; historial ≤200 sin credenciales; status atómico 0600; `stop` rechaza pid ajeno.
- [ ] Implementar; pasar; commit.

### Task 3: CLI y registro

**Files:** Create `apps/python/wysun_drive/{__main__,cli}.py`; Modify `bin/wysun` (MODULES + ayuda), `tests/test_python_layout.py` (PACKAGES), `tests/shell_bridge/test_dispatcher.py`; Test `tests/drive/test_cli.py`.

- [ ] Tests: `up --link --json` imprime JSON por línea con `url`; sin cuenta → salida 3 y mensaje; `--nombre` con 2 rutas → 2; `--clave` genera 10 caracteres; `recientes --json`; dispatcher `drive up x` → módulo `wysun_drive`.
- [ ] Implementar (portapapeles `wl-copy`, notificación `notify-send -a "Wysun Drive"`, `--terminal`, `--detener`); pasar; commit.

### Task 4: Selector TUI

**Files:** Create `apps/python/wysun_drive/ui/{__init__,app}.py`; Test `tests/drive/test_tui.py` (VirtualTerminal).

- [ ] Tests: lista la carpeta, `espacio` marca, `u` sube en un hilo y muestra links, `Tab` → Recientes, `c` copia; sin cuenta muestra el panel de login.
- [ ] Implementar; pasar; commit.

### Task 5: Barra, Files y captura

**Files:** Create `apps/shell/services/{Drive.qml,DriveLogic.js}`, `apps/shell/modules/bar/popouts/DrivePopout.qml`; Modify `StatusIcons.qml`, `popouts/Content.qml`, `apps/qml/files/parts/FilesMenus.qml`, `apps/python/wysun_files/quick/operations.py`, `apps/shell/modules/areapicker/{ActionBar,Session,AreaPicker o Picker}.qml`; Test `tests/shell_bridge/test_drive_logic.py`, prueba de operations.

- [ ] Implementar, pasar suites de shell/Files/temas; commit.

### Task 6: Docs, prueba real y despliegue

- [ ] `docs/utilities.md` (sección Wysun Drive + contrato para otras herramientas), `ARCHITECTURE.md` fila de utilidades.
- [ ] Suites completas; `wysun update`; `wysun reload`; reiniciar shell; probar login real con el usuario y una subida real.

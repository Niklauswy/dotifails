# Fase 3 — Wysun Files en QML: plan de implementación

> **Para workers agénticos:** SUB-SKILL REQUERIDA: superpowers:executing-plans (ejecución nativa, elegida por Nicolas). Casillas `- [ ]`. Una suite a la vez; `TMPDIR` y venvs en `~/.cache`.

**Estado (2026-10-26):** maquetas aprobadas («Sí, ya hazlo»). Tarea 1 hecha y en `main`. Tarea 2 empezada en el worktree
`~/orca/workspaces/wysun-shell/qml-fase3-files` (`quick/folder.py`, `quick/thumbs.py` sin commit ni pruebas). Tareas 3-8 pendientes.

**Meta:** Wysun Files reescrita en QML sobre `WysunM3` con el rediseño aprobado (`docs/design/qml-migration/files-*.html`, 2026-10-26: «Sí, ya hazlo»), paridad F-01…F-71 (`docs/superpowers/specs/2026-10-26-qml-paridad-music-files.md`), y el selector de archivos, el portal `org.freedesktop.impl.portal.FileChooser` y `org.freedesktop.FileManager1` funcionando sobre la nueva UI.

**Arquitectura:** se conservan `ops.py` (operaciones seguras), `kinds.py`, `markdown.py`, `highlight.py`, `browser.py`, el protocolo de `picker.py` y la lógica de filtros/validación de `chooser.py` (se extrae a un módulo sin Widgets). `wysun_files/quick/` expone a QML: `FolderModel` (sobre `QFileSystemModel` de QtGui + proxy de orden/filtro/tipo/ocultos/filtros del portal), `Places` (favoritos, marcadores, dispositivos, papelera), `Operations` (hilo, una a la vez, portapapeles, papelera con deshacer), `Preview` (texto, código resaltado, Markdown, resúmenes), un proveedor de miniaturas `image://thumb/` con los límites actuales (32 MB, 16 Mpx, 160 px, 2 hilos). La UI vive en `apps/qml/files/`; el modo selector es la misma ventana con `chooser: true`. Vídeo y audio del inspector con `QtMultimedia` (QML, del runtime); «Seguir en Wysun Player» y abrir medios lanzan Wysun Player como hoy.

**Spec:** diseño de la migración, lista de paridad, maquetas `files-folder/details/dialogs/chooser.html`, `docs/qml-base.md`.

## Restricciones globales

- Las de la fase 2 (tokens, datos privados, pruebas offscreen con datos temporales, `QtQuick.Effects`/`QtMultimedia` solo en la app).
- `ops.py` no cambia de garantías: nunca sobrescribe, `O_EXCL`, `renameat2`, sin borrar definitivamente.
- El selector no escribe archivos; el portal solo atiende al dueño de `org.freedesktop.portal.Desktop`; handles duplicados se rechazan.
- `wysun files` con varios argumentos abre una pestaña por ruta; un archivo abre su carpeta y lo selecciona.
- Nuevo aprobado: «Deshacer» tras enviar a la papelera (restaura desde `~/.local/share/Trash` con su `.trashinfo`).

## Review Focus

1. **Carpetas enormes o que cambian en marcha** (10 000 archivos, archivos que aparecen/desaparecen): scroll fluido, selección estable → Tarea 2/3.
2. **Selector ante un archivo que desaparece, sin permisos, nombre con «/», carpeta como destino de guardar** → Tarea 7.
3. **Operación larga y cerrar la ventana** (espera; no se pierde nada) → Tarea 5.
4. **Medios del inspector**: un solo reproductor activo, se detiene al cambiar de archivo o cerrar → Tarea 6.
5. **Portal**: emisor no autorizado, `Close` del Request, cierre ordenado del servicio con diálogos abiertos → Tarea 7.

## Tareas

### Tarea 1: Núcleo sin Widgets ✅
`wysun_files/core/{filters.py, places.py}`: filtros glob/MIME del portal y validación del selector extraídos de `chooser.py`; favoritos/marcadores/dispositivos de `sidebar.py`; `model.py` a `QtGui.QFileSystemModel`. Pruebas unitarias con el Python del sistema. Commit `refactor(files): Widgets-free core for filters, places and the model`.

### Tarea 2: Puente de carpeta (en curso)
`quick/folder.py` (`FolderModel`: roles path, name, isDir, kind, icon, role, label, sizeText, modifiedText, ext, thumb; `setRoot`, `sort(key, desc)`, `setFilter(text)`, `setKindFilter(kind)`, `showHidden`, `summary`), `quick/thumbs.py` (proveedor asíncrono). Pruebas `check_files_folder.py`. Commit `feat(files): QML folder model and thumbnails`.

### Tarea 3: Ventana, pestañas y navegación
`apps/qml/files/Main.qml` + `parts/` (FileIcon según la maqueta, FileGrid, FileList, PathBar, TabStrip, StatusLine, FolderHero, FilterRow), `quick/window.py`, `app.py` (instancia por ventana, argumentos, re-exec al venv). Historial por pestaña, Alt+↑/Retroceso con reselección, Ctrl+L, Ctrl+T/W/Tab, Ctrl+1/2, Ctrl+H, Ctrl+F y escribir para filtrar, Esc en cascada, selección múltiple y barra flotante. Pruebas `check_files_window.py`. Commit `feat(files): QML window, tabs and navigation`.

### Tarea 4: Lugares
Drawer/rail/modal con Favoritos, Marcadores (añadir/quitar), Dispositivos (uso refrescado cada 20 s, expulsar), Papelera; lugar más específico resaltado. Pruebas. Commit `feat(files): places`.

### Tarea 5: Operaciones
`quick/operations.py`: portapapeles (`text/uri-list` + `x-special/gnome-copied-files` + texto; cortados atenuados), copiar/mover/pegar en hilo, una a la vez, progreso en la barra de estado, papelera con confirmación y Deshacer, nueva carpeta/archivo, renombrar, propiedades, abrir (Player/PDF/sistema, máx. 10), terminal aquí, copiar ruta, arrastrar hacia otras apps, cierre que espera. Pruebas con carpetas temporales. Commit `feat(files): operations, clipboard and dialogs`.

### Tarea 6: Vista previa
Inspector automático ≥ 1000 px (Ctrl+I), imagen con zoom, texto/código resaltado, Markdown ⇄ fuente con enlaces que navegan, audio/vídeo con un solo reproductor, PDF, resúmenes de carpeta y selección, vista ampliada (Espacio), pantalla completa (F), «Seguir en Wysun Player», archivo dañado. Pruebas. Commit `feat(files): preview inspector and expanded preview`.

### Tarea 7: Selector, portal y FileManager1
Modo selector en la ventana (abrir/guardar/guardar varios, carpeta, múltiple, filtros, choices, reemplazar, nombres únicos, códigos de retorno), `picker.py` y `service.py` sobre QML (servicio en el venv). Pruebas: el protocolo JSON del picker, el portal en un bus privado (OpenFile/SaveFile/Close/emisor no autorizado), ShowItems selecciona. Commit `feat(files): QML file chooser, portal and FileManager1`.

### Tarea 8: Medidas, retirada y despliegue
Medidas antes/después (carpeta de 10 000 archivos), paridad fila a fila, retirar la UI Widgets y sus pruebas, documentación, suites, revisión, fusión, despliegue y prueba en vivo (Files, selector desde el PDF, «Mostrar en la carpeta» desde Music).

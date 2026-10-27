# Fase 2 — Wysun Music en QML: plan de implementación

> **Para workers agénticos:** SUB-SKILL REQUERIDA: superpowers:executing-plans (ejecución nativa, elegida por Nicolas: «continúa tú»). Casillas `- [ ]`. Una compilación/suite a la vez; `TMPDIR` y venvs en `~/.cache`.

**Meta:** Wysun Music reescrita en QML sobre `WysunM3` con el rediseño aprobado (`docs/design/qml-migration/music-*.html`) y paridad completa con la versión Widgets (filas M-01…M-76 de `docs/superpowers/specs/2026-10-26-qml-paridad-music-files.md`), más los atajos «nuevos» D1/D3/D4 (aprobados por Nicolas el 2026-10-26).

**Arquitectura:** el backend no cambia (`Library`, `Player`+mpv, `PlayQueue`, `CoverStore`, `Metadata`, `data`, `mpris`, `store`). Un paquete `wysun_music/quick/` lo expone a QML con modelos `QAbstractListModel` y objetos puente; la UI vive en `apps/qml/music/` (se despliega con `apps/qml` a `~/.local/share/wysun/qml/music`). `python3 -m wysun_music` comprueba la instancia única con el Python del sistema y, si hay que arrancar, se re-ejecuta en el venv `qml-runtime`.

**Tecnología:** PySide6 6.9.3 (bindings) sobre el Qt del shell, `QGuiApplication`, `WysunM3`, `QtQuick.Effects` solo en la app (máscara de portadas; nunca en la biblioteca), mpv por IPC.

**Spec:** `docs/superpowers/specs/2026-10-26-wysun-qml-music-files-design.md` (Fase 2), lista de paridad, maquetas, `docs/qml-base.md`.

## Restricciones globales

- Nada literal: colores `Theme.m3*`, medidas `Metrics.*`/tokens; excepción declarada: tono/arte de las portadas del usuario (`theme-exception`).
- Datos privados en `wysun_core.paths`/`WYSUN_MUSIC_HOME`; las pruebas usan `WYSUN_MUSIC_HOME`/`WYSUN_MUSIC_LIBRARY` temporales en `~/.cache` y audio sintético (`ffmpeg sine`), mpv con `--ao=null`.
- La versión Widgets sigue siendo la predeterminada hasta la Tarea 12 (`WYSUN_MUSIC_UI=qml` activa la nueva durante el desarrollo); el cambio es de una vez.
- Rutas de navegación (persistidas en `store['ui']['route']`): `home`, `search[:texto]`, `downloads`, `library:<albums|artists|songs|lists>`, `collection:<id>`.
- Destinos: drawer = Escuchar (Inicio, Explorar, Añadir música) · Biblioteca (Canciones→`library:songs`, Artistas, Álbumes, Recientes→`collection:recent`, Tus me gusta→`collection:favorites`) · Playlists (portada, ecualizador si suena, «+» Ctrl+N, menú contextual); rail = Inicio, Explorar, Biblioteca, Listas (`library:lists`), Añadir.
- Atajos (M-30 + nuevos): Espacio/M fuera de campos de texto; Ctrl+←/→, Ctrl+↑/↓ ±5, Ctrl+Espacio y Media Play, Ctrl+S, Ctrl+R, Ctrl+Shift+F, Ctrl+F/Ctrl+K, Alt+←/→, Ctrl+L, Ctrl+Q, Ctrl+P, Ctrl+N, Ctrl+O, F1, Esc; **nuevos** Alt+1…5 (Inicio, Tus me gusta, Artistas, Añadir música, importar), Ctrl+J (enfocar contenido), Ctrl+Enter en resultados de descarga (descargar selección), ↑/↓/Enter en la letra.

## Review Focus

1. **Biblioteca vacía o que cambia en marcha** (`library.json` reemplazado por el worker de descargas): ninguna página queda con delegados de claves inexistentes; la ruta huérfana muestra «Esta lista ya no existe.» → Tarea 4 (`test_models_follow_library_reload`), Tarea 6 (`test_orphan_route`).
2. **mpv ausente o que se cae**: la app abre igual y avisa con un snackbar; el reproductor se recupera → Tarea 5 (`test_engine_failure_is_a_snackbar`).
3. **Sin red** (portadas, letras, fotos de artista): placeholders de forma, nunca imágenes rotas; letras «No disponible» → Tareas 4 y 8.
4. **Segunda instancia y `--background`** con la ventana oculta o cerrándose → Tarea 2 (`test_second_launch_presents`).
5. **Teclado en campos de texto**: Espacio/M escriben en la búsqueda y el filtro, no reproducen → Tarea 5 (`test_space_types_in_text_fields`).

## Estructura de archivos

| Ruta | Responsabilidad |
|---|---|
| `apps/python/wysun_music/app.py` (mod.) | `main()`: instancia única con Python del sistema → re-exec al venv; `build(ui)` |
| `apps/python/wysun_music/quick/window.py` | `QmlMusicWindow`: motor, `Main.qml`, `present()`, `save_ui()`, ocultar al cerrar |
| `apps/python/wysun_music/quick/covers.py` | `CoverUrls`: `url(key)`, `collection(id)` (1 o 4 URLs), `revision` |
| `apps/python/wysun_music/quick/models.py` | `TrackListModel`, `CardListModel`, `QueueModel`, `DownloadModel` |
| `apps/python/wysun_music/quick/controller.py` | `MusicController`: datos de páginas y acciones (playlists, favoritos, menús, mostrar en carpeta, Spotify) |
| `apps/python/wysun_music/quick/playback.py` | `PlayerBridge` (propiedades del reproductor) y `LyricsBridge` |
| `apps/python/wysun_music/quick/addmusic.py` | `AddMusic`: búsqueda YouTube (QProcess), importación Spotify, importar archivos/carpeta con el selector de Files, cola de descargas |
| `apps/python/wysun_files/picker.py` (mod.) | peticiones `kind: "audio"` (múltiple) y `directory` |
| `apps/qml/music/` | `Main.qml`, `Shortcuts.qml`, `PlayerCapsule.qml`, `NowPlaying.qml`, `LyricsView.qml`, `QueueList.qml`, `pages/{Home,Library,Collection,Search,AddMusic}Page.qml`, `parts/{Cover,TrackRow,TrackList,AlbumCard,ArtistCard,BentoTile,Shelf,ChartRow,SelectionBar,MusicMenus,PlaylistDialogs,ShortcutSheet}.qml` |
| `apps/qml/WysunM3/navigation/*` (mod.) | destino con `image`, `trailingIcon`; cabecera con acción; menú contextual |
| `tests/qml/check_music_*.py`, `tests/qml/music_fixture.py` | pruebas offscreen con biblioteca sintética |

---

### Tarea 1: Selector de Files para audio y carpetas

**Archivos:** `apps/python/wysun_files/picker.py`, `tests/test_files_picker_audio.py` (o ampliar la prueba existente del picker).

**Interfaces:** request JSON `{title, kind: "audio"|"document", multiple: bool, directory: bool, initial}`; respuesta `{code, uris:[…]}` (sin cambios). `suffix` sigue valiendo para PDF/MD.

- [ ] Pruebas: `make_selector({'kind':'audio','multiple':True})` → `FileChooser` con `multiple`, filtro «Audio» con `*.m4a *.opus *.mp3 *.flac *.ogg *.wav *.aac`; `directory: True` → `chooser.directory`; `kind` desconocido → `ValueError`; las peticiones PDF anteriores no cambian.
- [ ] Implementar; pasar las pruebas del picker y `tests/test_pdf*` que lo usan. Commit `feat(files): picker requests for audio files and folders`.

### Tarea 2: Arranque, ventana QML y navegación

**Archivos:** `wysun_music/app.py`, `wysun_music/quick/{__init__,window}.py`, `apps/qml/music/Main.qml`, `tests/qml/music_fixture.py`, `tests/qml/check_music_window.py`, `tests/test_python_layout.py` si hace falta.

**Interfaces:** `QmlMusicWindow(library, covers, player, test=False)` con `present()`, `save_ui()`, `hide()`; contexto QML: `music` (controller), `player`, `lyrics`, `addMusic`, `bridge`. `Main.qml`: `property string route`, `function navigate(route, remember=true)`, `goBack()`, `goForward()`, historial de 50, `AdaptiveNavigation` con los destinos de «Restricciones», barra superior (ocultar, atrás, adelante, `SearchBar` Ctrl+K, atajos F1), contenido con `FadeThrough` entre destinos y `SharedAxis` al entrar en una colección. `music_fixture.library(tmp)` crea 3 pistas sintéticas importadas y devuelve el `build(test=True, ui='qml')`.

- [ ] Pruebas: la ventana carga sin avisos QML; `navigate('collection:favorites')` cambia la página y el destino activo; atrás/adelante; la ruta se guarda y se restaura; cerrar la ventana la oculta y el reproductor sigue (`player.playing` sin cambios); `test_second_launch_presents` (`main()` con un dueño ya vivo envía `present`); `test_reexec_happens_after_the_instance_check` (con `send` parcheado a True no se llama a `ensure_runtime_python`).
- [ ] Implementar `main()`: `send` → si no hay dueño, `bootstrap.ensure_runtime_python('wysun_music')` → `require_qt()` → `QGuiApplication` (`wysun-music`, `setDesktopFileName`), `build(ui=os.environ.get('WYSUN_MUSIC_UI','widgets'))`.
- [ ] Commit `feat(music): QML window, navigation and launch on the qml-runtime`.

### Tarea 3: Base — destinos con imagen, acciones de cabecera y menú contextual

**Archivos:** `apps/qml/WysunM3/navigation/{NavigationItem,NavigationDrawer,NavigationRail,AdaptiveNavigation}.qml`, `tests/qml/check_navigation.py`, `docs/qml-base.md`, galería.

**Interfaces:** destino `{image: url, trailingIcon: string}`; cabecera `{header, action: icon, actionId}`; señales `headerAction(string actionId)` y `contextRequested(string id, real x, real y)` en drawer y `AdaptiveNavigation`.

- [ ] Pruebas: imagen 24 px redondeada en lugar del icono; `trailingIcon` visible; clic en la acción emite `headerAction`; clic derecho emite `contextRequested` con coordenadas de ventana. Implementar, galería, commit `feat(qml): navigation destinations with artwork, header actions and context menus`.

### Tarea 4: Modelos y datos de páginas

**Archivos:** `wysun_music/quick/{covers,models,controller}.py`, `tests/qml/check_music_models.py`.

**Interfaces:**
- `CoverUrls(covers)`: `@Slot(str, result=str) url(key)` (`file://…` o `""`), `@Slot(str, result='QVariantList') collection(id)` (propia, o hasta 4 de sus pistas), `revision: int` (sube con `covers.updated`).
- `TrackListModel` roles `key, title, artist, artists, album, duration, durationText, favorite, cover, current, playing`; `setKeys(list)`; se refresca con `favorites_changed`, `track_changed`, `revision`.
- `CardListModel` roles `id, title, subtitle, kind, count, covers, round, playing`; `setCollections(list[Collection])`.
- `MusicController`: `@Slot(str, result='QVariantMap') page(route)` → para `home`: `{greeting, date, bento:[3], recent, playlists, chart, albums, artists}` (listas de ids o claves); `library:*` → modelo y recuento; `collection:<id>` → `{exists, title, kind, label, byline, meta, editable, source, count}` + `collectionTracks` (TrackListModel) con `@Slot(str) setFilter`, `@Slot(str) setSort(custom|title|artist|album|duration)`; `search` → `{top, songs(5), songCount, artists, lists}`; `explore`.
- Reglas copiadas de la versión Widgets: saludo por hora (5-12, 12-20, resto), fecha «lunes 26 de octubre», bento (sonando/sigue escuchando/empieza por aquí · Tus me gusta · Mezcla), «Lo que más escuchas» = 9 más reproducidas disponibles, artistas por nº de canciones, `lead_artist` («Varios artistas»), byline por tipo, meta «N canciones · duración larga [· Actualizado fecha]», filtro visible con > 8 canciones.
- [ ] Pruebas con biblioteca sintética: cada página devuelve los datos esperados; `test_models_follow_library_reload` (borrar una pista del `library.json` y recargar quita su fila); filtro/orden; búsqueda con acentos; ruta huérfana `exists: false`; sin red las URLs son `""`.
- [ ] Commit `feat(music): models and page data for the QML UI`.

### Tarea 5: Reproductor, cápsula y atajos

**Archivos:** `wysun_music/quick/playback.py` (`PlayerBridge`), `apps/qml/music/{PlayerCapsule,Shortcuts}.qml`, `parts/Cover.qml`, `tests/qml/check_music_player.py`.

**Interfaces:** `PlayerBridge` propiedades `currentKey, title, artist, artists, album, coverUrl, paused, playing, position, duration, volume, muted, shuffle, repeat (off|all|one), canNext, canPrevious, quality, favorite, contextId`; slots `toggle, next, previous, seek(s), seekBy(s), setVolume(v), changeVolume(d), toggleMute, setShuffle(b), cycleRepeat, toggleFavorite, play(key, contextKeys, contextId), playCollection(id, startKey, shuffle), toggleCollection(id), addToQueue(keys), playNext(keys), removeUpcoming(i), jumpTo(i)`; señal `message(str)` → `SnackbarHost`. `Cover.qml`: imagen enmascarada en una forma (`MultiEffect` + `ShapeEmblem` como máscara; con renderizador software, rectángulo redondeado), gira lentamente mientras suena (respeta movimiento reducido).
- [ ] Pruebas con mpv real (`--ao=null`): play/pausa desde la cápsula y con Espacio; Ctrl+→; M silencia; `test_space_types_in_text_fields`; Ctrl+R cicla; barra de posición: flechas ±5 s, Home/End; `test_engine_failure_is_a_snackbar` (PATH sin mpv).
- [ ] Commit `feat(music): player capsule, transport and keyboard shortcuts`.

### Tarea 6: Inicio y Biblioteca

**Archivos:** `pages/HomePage.qml`, `pages/LibraryPage.qml`, `parts/{BentoTile,Shelf,ChartRow,AlbumCard,ArtistCard}.qml`, `tests/qml/check_music_pages.py`.

- [ ] Inicio según la maqueta: fecha y saludo, bento adaptable (fila de 3 ≥ 780 px, si no 2+1), estanterías horizontales con «Ver todo», ranking, artistas en cookie; Biblioteca con `TabBar` (Álbumes, Artistas, Canciones, Listas), rejillas adaptables (`GridView`) y estado vacío; tarjetas con Enter/Espacio abre, Ctrl+Enter reproduce, botón de reproducir; `test_orphan_route`.
- [ ] Pruebas: secciones presentes con datos sintéticos; rejilla de 1 000 álbumes sintéticos solo crea los visibles; teclado en tarjetas. Commit `feat(music): home and library pages`.

### Tarea 7: Colección, lista de canciones, selección, menús y diálogos

**Archivos:** `pages/CollectionPage.qml`, `parts/{TrackRow,TrackList,SelectionBar,MusicMenus,PlaylistDialogs}.qml`, `tests/qml/check_music_collection.py`.

- [ ] Cabecera con portada en forma por tipo (álbum squircle, artista cookie con foto o iniciales, Tus me gusta sunny, Recientes burst), velo del arte, se compacta al desplazar; Reproducir/Pausar, Aleatorio, Más; filtro y orden; artista: estantería de álbumes + canciones.
- [ ] Lista: columnas #/portada/título/artista/álbum/duración (álbum oculto en álbumes y < 840 px), corazón, «más», clic en artista; selección múltiple (Ctrl/Mayús+clic, pulsación larga) con barra contextual; teclas Enter, Ctrl+Enter (artista), F, tecla Menú; doble clic reproduce.
- [ ] Menús M-35/M-37 exactos (incluido «Añadir a playlist» con submenú → menú secundario, «Ir al artista» con varios artistas, «Mostrar en la carpeta» por FileManager1 `ShowItems` y, si falla, abrir la carpeta), diálogos de nueva playlist (nombre sugerido «Mi playlist n.º N»), renombrar y borrar con confirmación.
- [ ] Pruebas de cada acción contra el backend. Commit `feat(music): collection page, track list, selection, menus and playlist dialogs`.

### Tarea 8: Búsqueda y Explorar

**Archivos:** `pages/SearchPage.qml`, `tests/qml/check_music_search.py`.

- [ ] Escribir en la barra navega a `search:` y refina la misma entrada del historial; rebote de 140 ms; Explorar con búsqueda vacía; resultado principal (artista o canción), 5 canciones + «Ver las N canciones» (`collection:search:<q>`), artistas, listas; ↓/Enter bajan a los resultados; Esc limpia; sin resultados → estado vacío. Commit `feat(music): search and explore`.

### Tarea 9: Ahora suena, letra y cola

**Archivos:** `wysun_music/quick/playback.py` (`LyricsBridge`, `QueueModel`), `apps/qml/music/{NowPlaying,LyricsView,QueueList}.qml`, `tests/qml/check_music_nowplaying.py`.

**Interfaces:** `LyricsBridge`: `state (idle|loading|synced|plain|instrumental|missing)`, `lines: [{time, text}]`, `currentIndex`, `offset`, `source`, `@Slot(int) seekLine`, `@Slot(float) nudge(±0.5)` (persistido en `offset:<key>`), clave de caché `key:duración`.
- [ ] Panel que cubre la ventana con container transform desde la portada; portada grande en cookie, calidad «OPUS · 160 kb/s», controles grandes; pestañas Letra / A continuación (Ctrl+L, Ctrl+Q, Ctrl+P; la misma tecla cierra); sin letra y sin pestaña elegida → muestra la cola con la nota; letra con seguimiento suave y pausa de 3,5 s tras la rueda; clic o ↑/↓+Enter saltan; cola con origen, saltar, quitar, menú.
- [ ] Pruebas con letras sintéticas inyectadas en `Metadata.ready`: línea actual sigue la posición con el desfase; `nudge` persiste; estados; cola. Commit `feat(music): now playing, synced lyrics and queue`.

### Tarea 10: Añadir música

**Archivos:** `wysun_music/quick/addmusic.py`, `pages/AddMusicPage.qml`, `tests/qml/check_music_addmusic.py`.

- [ ] Paridad M-62…M-67 (búsqueda yt-dlp con tiempo límite 90 s, enlaces válidos, Spotify, «Descargar selección» y Ctrl+Enter, importar archivos/carpeta con el selector de Files (Tarea 1), abrir carpeta de música, cola con Continuar/Pausar/Reintentar y estados con tono). Pruebas con `ytdlp` y `import_link` falsos. Commit `feat(music): add music page`.

### Tarea 11: Integración y modo en segundo plano

- [ ] MPRIS sin cambios sobre `QGuiApplication` (`Raise` → `present`), `--background`, `music-mini`, «Abrir en Spotify», hoja de atajos (F1) como diálogo con la lista de «Restricciones». Prueba MPRIS con bus propio si hay `dbus-daemon` (si no, se salta). Commit `feat(music): desktop integration on the QML window`.

### Tarea 12: Medidas, cambio y retirada de Widgets

- [ ] Medir antes (Widgets) y después (QML) con la misma biblioteca sintética de 3 000 pistas: arranque hasta ventana con datos (caliente y frío), scroll de «Canciones», RSS/PSS. QML no puede ser perceptiblemente peor; resultados en `docs/superpowers/specs/2026-10-26-qml-medidas-music.md`.
- [ ] Recorrer la lista de paridad fila a fila (marcar ✓ o la prueba que lo cubre) y comprobar en ventana real.
- [ ] Hacer QML la UI predeterminada, borrar `wysun_music/ui/` y las pruebas que solo cubrían widgets (sustituidas por `tests/qml/check_music_*`), actualizar `ARCHITECTURE.md`/`apps/python/README.md`. Suites en serie, revisión final, fusión y despliegue con verificación en vivo.

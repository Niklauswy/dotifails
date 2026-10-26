# Lista de paridad: Wysun Music y Wysun Files (Widgets → QML)

Fecha: 2026-10-26. Rama `qml/paridad-maquetas`. Es el contrato de «ninguna función se pierde» de
`2026-10-26-wysun-qml-music-files-design.md`: cada fila es una función del código Widgets actual, dónde
vive (`archivo:línea`, relativo a `apps/python/` salvo que se indique), cómo comprobar que la versión QML
la conserva y en qué maqueta (`docs/design/qml-migration/`) tiene sitio visible.

Cómo usarla: al migrar, se recorre la tabla fila a fila; una fila solo se da por hecha si su columna
**Verificación** pasa con la versión QML. La columna **Maqueta** la rellenan los puntos 3 y 4 del encargo
(`music-*.html`, `files-*.html`); «nueva» marca lo que la maqueta propone y hoy no existe (no es paridad,
es rediseño).

Las líneas se tomaron del árbol en `4298fac4`. Las pruebas citadas se ejecutan con los comandos de
`AGENTS.md`; «manual» = comprobación en ventana real (Hyprland), sin prueba automática hoy.

## Discrepancias entre documentación y código (decidir antes de migrar)

El README (`apps/python/README.md:226-244`) describe cosas que el código **no** tiene. Hay que decidir si
la migración las implementa, las descarta o corrige el README; **no** cuentan como paridad hasta entonces.

| # | Dice el README | Realidad en el código | Propuesta |
|---|---|---|---|
| D1 | `Alt+1…5` abren biblioteca, favoritos, artistas, descargas y añadir música; `Ctrl+J` enfoca el contenido (README:234) | No existen: `ui/window.py:143-158` solo registra los atajos de M-30. Alt+1…5 no aparece en `wysun_music/` | Implementarlos en QML (barato y útil) o borrar del README. Las maquetas los muestran como «nueva» |
| D2 | Mini reproductor propio, `Ctrl+Enter` lo abre completo (README:226, 234) | Music ya no tiene mini ventana: `Super+Shift+M` ejecuta `wysun music-mini`, que arranca Music oculto (`--background`) y abre el widget de media del shell (`bin/wysun:90-95`, `config/.config/wysun/hyprland.lua:48`) | La maqueta mantiene el «minirreproductor» como tarjeta dentro de la app (cápsula inferior) y deja el widget del shell como está |
| D3 | `Ctrl+Enter` en resultados de descarga guarda la selección (README:234) | `ui/downloads.py` no maneja teclas (sin `keyPressEvent`/atajos) | Igual que D1 |
| D4 | En la letra, las flechas recorren líneas y `Enter` salta (README:230) | `ui/nowplaying.py:34-200` (`LyricsView`) solo tiene rueda (129), clic (159) y hover (147); no hay `keyPressEvent` | Igual que D1; el salto por clic sí existe (M-52) |
| D5 | Las flechas de la barra de tiempo mueven 5 s (README:230) | Cierto: `Slider.keyPressEvent` (`wysun_core/ui/widgets.py:361`, `step=5/300` en `playerbar.py:90`) | Conservar; no es discrepancia |
| D6 | `F1` ventana de atajos | `SHORTCUTS` (`window.py:26`) lista `Ctrl+↑/↓`, `M`, `Ctrl+S`, `Ctrl+R`, `Ctrl+Q`… que el README omite | La hoja de atajos de la maqueta usa la lista del código (M-30) |

---

## Wysun Music

### A. Proceso, ventana y sesión

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| M-01 | Instancia única por usuario (`wysun-music-<uid>`); un segundo `wysun music` entrega «present» a la primera, con reintento si pierde la reclamación | `wysun_music/app.py:55-70`; `wysun_core/instance.py` | `tests/test_music_instance.py:12`; `tests/music_ui.py` (instancia única) | n/a (proceso) |
| M-02 | `--background`: arranca el reproductor sin mostrar ventana (widget de media del shell) | `wysun_music/app.py:26-27,57`; `bin/wysun:90-95` | manual: `wysun music-mini` con Music cerrado → proceso vivo, sin ventana, MPRIS presente | n/a |
| M-03 | Cerrar la ventana = ocultarla; el audio sigue. `Esc` final oculta; `quitOnLastWindowClosed=False` | `ui/window.py:320-324`, `wysun_music/app.py:71`, `ui/window.py:284-290` | `tests/music_ui.py`; manual: cerrar y comprobar `playerctl status` | `music-player.html` (botón ocultar) |
| M-04 | Salida limpia: guarda UI, cierra mpv y la base al terminar (SIGTERM/SIGINT) | `wysun_music/app.py:30-35,72-90` | manual: `kill -TERM` → `player.sqlite3` íntegro | n/a |
| M-05 | Restaura ruta de UI, canción, posición, volumen y cola (en pausa) al abrir | `ui/window.py:60-64,326-328`; `player.py:229-247` | `tests/test_music_player.py:25`; `tests/music_ui.py` | n/a (estado) |
| M-06 | Ventana sin marco, translúcida, movimiento de entrada/salida, redimensión, tamaño mínimo 900×600, centrada en la pantalla del cursor | `ui/window.py:38-50,303-318,345` | manual en Hyprland (flotante y mosaico) | los tres anchos en cada `music-*.html` |
| M-07 | Tema en vivo: repinta ventana, reproductor completo y etiquetas al cambiar modo/wallpaper/estilo | `ui/window.py:59,335-342`; `wysun_core/qt_theme.py` | `tests/test_music_material.py:12`; manual cambiando modo claro/oscuro | claro/oscuro y 2+ paletas en todas |

### B. Navegación y búsqueda

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| M-10 | Barra lateral: «Escuchar» (Inicio, Explorar, Añadir música) y «Biblioteca» (Canciones, Artistas, Álbumes, Recientes, Tus me gusta) con ítem activo | `ui/sidebar.py:17-23,76-90,118-127` | `tests/test_music_material.py:12`; manual | `music-library.html` (drawer/rail/modal) |
| M-11 | Playlists del usuario y colecciones guardadas en la barra, con su portada; indicador de la que suena; botón «+» nueva playlist (`Ctrl+N`) | `ui/sidebar.py:26-48,84-86,100-129` | `tests/test_music_core.py:70`, manual | `music-library.html` |
| M-12 | Menú contextual de colección en la barra (clic derecho en una playlist) | `ui/sidebar.py:112` → `ui/actions.py:81-93` | manual | `music-library.html` (menú) |
| M-13 | Historial de navegación atrás/adelante (50 entradas), botones y `Alt+←/→`; escribir en la búsqueda refina la misma entrada | `ui/window.py:25,153,165-218,220-228` | `tests/music_ui.py`; manual | `music-library.html` (barra superior) |
| M-14 | Rutas: `home`, `search`, `downloads`, `artists`, `albums`, `collection:<id>`; ruta huérfana → «Esta lista ya no existe.» | `ui/window.py:189-204,123` | manual: borrar playlist abierta | `music-library.html` (estado vacío) |
| M-15 | Búsqueda global con acentos/mayúsculas: canciones, artistas, playlists y álbumes; escribir navega a la página de búsqueda; limpiar al salir | `ui/window.py:220-235`; `ui/sidebar.py:63`; `library.py:134-140`; `ui/search.py:168-250`; `store.py` (`normalize`) | `tests/test_music_core.py:108`, `tests/test_music_player.py:36`; `tests/music_ui.py:76-77` | `music-search.html` |
| M-16 | Página Explorar (búsqueda vacía): mosaicos «Explorar» de colecciones | `ui/search.py:15-62,114,187-198` | manual | `music-search.html` |
| M-17 | Resultados: «Resultado principal» (artista), «Canciones» + «Ver todas», «Artistas», «Playlists y álbumes» | `ui/search.py:64-100,126-160,199-250` | `tests/music_ui.py` | `music-search.html` |
| M-18 | `Ctrl+F`/`Ctrl+K` enfoca la búsqueda; `↓`/`Enter` en la búsqueda baja a los resultados; `Enter` en la lista reproduce | `ui/window.py:152,230-235,254-260,277-282`; `ui/tracks.py:251-258` | `tests/music_ui.py:76-77` | `music-search.html` |
| M-19 | Inicio: saludo por hora, bento (Sonando ahora/Sigue escuchando · Tus me gusta · Mezcla), «Escuchado recientemente», «Tus playlists», «Lo que más escuchas» (ranking), «Álbumes», «Tus artistas» | `ui/home.py:24,32-80,82-245` | `tests/test_music_bento.py:25`; manual | `music-library.html` (Inicio) |
| M-20 | Cuadrículas de Artistas (ordenados por canciones, retratos en cookie) y Álbumes (por título) con contador y estado vacío; reconstrucción diferida 150 ms | `ui/browse.py:13-77` | manual con biblioteca vacía y con datos | `music-library.html` (pestañas) |
| M-21 | Tarjetas navegables por teclado: `Enter`/`Espacio` abre, `Ctrl+Enter` reproduce; botón de reproducir en la tarjeta | `ui/cards.py:19-147` (`Tile`), `149-190` (`Card`) | manual con Tab/Enter | `music-library.html` |
| M-22 | Hoja de atajos (F1) | `ui/window.py:26-35,296-298` | manual | `music-search.html` (diálogo de atajos) |

### C. Colecciones (álbum, playlist, artista, favoritos, recientes)

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| M-25 | Cabecera con portada, tipo, título grande, subtítulo (artista del álbum / «Tu playlist» / «Guardadas por ti»…), meta (n.º canciones · duración · «Actualizado»); se compacta al hacer scroll | `ui/collection.py:34-158,239-271` | manual; `tests/test_music_material.py:12` | `music-album.html` |
| M-26 | Retrato del artista en cookie con foto (MusicBrainz→Wikidata→Commons) o iniciales | `ui/collection.py:86-108`; `metadata.py:152-176`; `covers.py` | manual con red y sin red | `music-album.html` (artista) |
| M-27 | Velo difuminado de la portada bajo la cabecera | `ui/collection.py:278-302` | manual | `music-album.html` |
| M-28 | Botones Reproducir/Pausar (alterna con su contexto), Aleatorio, «Más opciones» | `ui/collection.py:176-182,272-277,304-315`; `ui/actions.py:21-40` | `tests/music_ui.py` | `music-album.html` |
| M-29 | Filtro de texto «Buscar en la lista» (solo visible con > 8 canciones) y orden: personalizado, título, artista, álbum, duración | `ui/collection.py:21-22,183-192,239-252,316-326` | manual | `music-album.html` |
| M-30 | Atajos globales de la app: `Ctrl+←/→` anterior/siguiente, `Ctrl+↑/↓` volumen ±5, `Ctrl+Espacio` y tecla `Media Play` reproducir/pausar, `Ctrl+S` aleatorio, `Ctrl+R` repetir, `Ctrl+Shift+F` favorita, `Ctrl+F`/`Ctrl+K`, `Alt+←/→`, `Ctrl+L` letra, `Ctrl+Q` cola, `Ctrl+P` Ahora suena, `Ctrl+N`, `Ctrl+O`, `F1`, `Esc` | `ui/window.py:143-163` | `tests/music_ui.py`; manual (Ctrl+Space no choca con el IME) | `music-search.html` (atajos) y tooltips en `music-player.html` |
| M-31 | `Espacio` reproduce/pausa y `M` silencia en cualquier punto de la ventana, salvo escribiendo o con un botón con foco | `ui/window.py:262-275` | manual | `music-player.html` |
| M-32 | Tabla de canciones: columnas #/portada/título/artista/álbum/duración, filas alternadas, reproducción en la fila, corazón, «más», clic en artista | `ui/tracks.py:23-163,226-249` | `tests/music_ui.py` | `music-album.html` |
| M-33 | Selección múltiple (`ExtendedSelection`) con menú sobre el conjunto | `ui/tracks.py:182,218-224` | manual (Ctrl/Shift+clic) | `music-album.html` (barra de selección, «nueva») |
| M-34 | Teclas en la tabla: `Enter` reproduce, `Ctrl+Enter` abre el artista, `F` favorita, tecla Menú abre el menú; doble clic reproduce | `ui/tracks.py:184-185,251-267` | `tests/music_ui.py` | `music-album.html` |
| M-35 | Menú de canción: Reproducir, Reproducir a continuación, Añadir a la cola, Añadir a playlist (+ Nueva playlist…), Quitar de esta playlist, Guardar/Quitar de Tus me gusta, Ir al artista (varios artistas → submenú), Mostrar en la carpeta | `ui/actions.py:45-79` | manual; `tests/test_music_core.py:70` | `music-album.html` (menú) |
| M-36 | «Mostrar en la carpeta»: abre la carpeta del archivo (`QDesktopServices`, no usa FileManager1) | `ui/actions.py:121-124` | manual; **ojo**: al migrar conviene llamar a `org.freedesktop.FileManager1.ShowItems` (F-70) para seleccionar el archivo | `music-album.html` (menú) |
| M-37 | Menú de colección: Reproducir, Reproducir en aleatorio, Añadir a la cola, Cambiar nombre…, Eliminar playlist (con confirmación), Abrir en Spotify | `ui/actions.py:81-93,109-119` | manual | `music-album.html` |
| M-38 | Playlists: crear (nombre sugerido «Mi playlist n.º N», con canciones o vacía), renombrar, eliminar, añadir/quitar canciones | `ui/actions.py:101-119`; `library.py:194-215`; `store.py:151-183` | `tests/test_music_core.py:70`, `tests/test_music_player.py:41` | `music-album.html` (diálogos) |
| M-39 | Favoritos: corazón en tabla, barra, reproductor completo y `Ctrl+Shift+F`; colección «Tus me gusta» | `library.py:189-192`; `ui/playerbar.py:62,191-194`; `ui/nowplaying.py:341,649-651` | `tests/test_music_player.py:25` | `music-player.html`, `music-album.html` |
| M-40 | Recientes y más escuchadas (registro de reproducciones) | `library.py:217-220`; `store.py:184-194` | `tests/test_music_core.py:70` | `music-library.html` |

### D. Reproducción y cola

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| M-45 | Cápsula inferior: portada (abre Ahora suena), título, artista (enlace), corazón, aleatorio, anterior, play/pausa, siguiente, repetir (off/lista/una), barra de progreso ondulada con tiempos, letra, cola, silencio, volumen | `ui/playerbar.py:20-200` | `tests/music_ui.py` | `music-player.html` (minirreproductor) |
| M-46 | Barra de posición: clic/arrastre con vista previa del tiempo, flechas ±5 s, `Home`/`End`; se pausa la ondulación en pausa | `ui/playerbar.py:90-95,183-192`; `wysun_core/ui/widgets.py:247-370` | `tests/music_ui.py`; manual | `music-player.html` |
| M-47 | Volumen (slider, ±5 con atajo, silencio con `M`) con iconos según nivel | `ui/playerbar.py:117-125,157-174` | manual | `music-player.html` |
| M-48 | Cola estable independiente de la vista; aleatorio reversible; repetir off→lista→una; «a continuación» antes del contexto; saltar canciones no disponibles | `queue.py:12-99`; `store.py:24-76`; `player.py:76-190` | `tests/test_music_core.py:24-55`, `tests/test_music_player.py:11-25` | `music-player.html` (cola) |
| M-49 | Panel «Ahora suena» a pantalla completa: portada grande con halo que respira, fondo difuminado, título, artista (enlace), álbum, calidad (códec · kb/s), controles grandes, entrada animada; `Esc`/botón lo cierra | `ui/nowplaying.py:270-640` | `tests/music_ui.py` | `music-player.html` (reproductor completo) |
| M-50 | Pestañas del panel: «Letra» y «A continuación» (cola); `Ctrl+L`, `Ctrl+Q`, `Ctrl+P` alternan | `ui/nowplaying.py:30,437-449`; `ui/window.py:154-155,237-258` | `tests/music_ui.py` | `music-player.html` |
| M-51 | Cola: «Sonando ahora», «A continuación» con origen («De <colección>»), saltar a una pista, quitar de la cola, «Más opciones…» | `ui/nowplaying.py:202-268`; `player.py:170-190` | `tests/test_music_core.py:24-43` | `music-player.html` |
| M-52 | Letra: líneas sincronizadas con seguimiento suave y pausa de 3,5 s tras rueda manual; clic salta al instante; sin sincronizar si no coinciden título/artista/duración (±2 s); mensajes «Buscando…», «Instrumental», «No disponible» | `ui/nowplaying.py:31-200,660-715`; `metadata.py:127-150` | `tests/test_music_player.py:36`; `tests/music_ui.py` (letras sincronizadas) | `music-player.html` |
| M-53 | Desfase de letra ±0,5 s por canción, persistido (`offset:<key>`), con etiqueta de fuente («Sincronizada · LRCLIB») | `ui/nowplaying.py:400-411,675-720` | `tests/music_ui.py` | `music-player.html` |
| M-54 | Motor mpv por IPC (`--input-ipc-server`), eventos de pausa/posición/duración/silencio, reinicio ante caída; audio local en `~/Music/Wysun` | `engine.py:19-224`; `player.py:191-228` | `tests/music_ui.py` (mpv real, `--ao=null`) | n/a |
| M-55 | Toasts de mensajes del reproductor | `ui/window.py:130,57,299-300`; `wysun_core/ui/toast.py` | manual | `music-player.html` (snackbar) |

### E. Biblioteca, importación y descargas

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| M-60 | Biblioteca en `library.json` con recarga al cambiar el directorio (el worker lo reemplaza atómicamente); solo muestra archivos disponibles | `library.py:50-100`; `data.py:23-47` | `tests/test_music_core.py:108` | n/a |
| M-61 | Portadas: embebidas → Spotify oEmbed → mosaico → tono; caché de pixmaps redondeados | `covers.py:23-195`; `spotify.py` | manual; `tests/test_music_spotify.py` | `music-album.html` (carátulas y mosaicos) |
| M-62 | Página «Añadir música»: buscador (nombre, enlace de YouTube, enlace público de Spotify), resultados, «Descargar selección», estado | `ui/downloads.py:86-130,170-240` | `tests/test_music.py:24-80`, `tests/test_music_spotify.py:9-16` | `music-search.html` (Añadir música) |
| M-63 | Importar Spotify (lista/álbum/canción públicos): lee metadata, indica cuántas canciones se publicaron, deduplica por ID/título/duración (±2 s) | `ui/downloads.py:242-272`; `spotify.py:8-43`; `data.py:52-90` | `tests/test_music_spotify.py:16`; `tests/test_music.py:34,72` | `music-search.html` |
| M-64 | Desde este equipo: Importar archivos (`Ctrl+O`), Importar carpeta, Abrir carpeta de música; lee etiquetas embebidas en un hilo | `ui/downloads.py:22-37,130-139,273-300`; `data.py:269-305` | `tests/test_music_core.py:131` | `music-search.html` |
| M-65 | Cola de descargas: Continuar, Pausar cola, Reintentar errores; estados En cola / Descargando / Error / Revisar versión; progreso por pista | `ui/downloads.py:17,140-160,301-334`; `data.py:91-103,183-262` | `tests/test_music.py:42,54-80` | `music-search.html` |
| M-66 | yt-dlp con versión/SHA fijada, 2 trabajadores, validación de duración; variantes de audio sin cambiar el archivo en reproducción; pistas compartidas reutilizan archivo | `data.py:104-262`; `store.py:135-150` | `tests/test_music.py:24,72,80` | n/a (backend) |
| M-67 | Selector de archivos del sistema para importar (`QFileDialog`) | `ui/downloads.py:273-280` | manual; al migrar: usar el portal/selector Wysun (F-60) | `music-search.html` |

### F. Integración con el escritorio

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| M-70 | MPRIS `org.mpris.MediaPlayer2.wysun_music[.instanceN]`: Play/Pause/Next/Previous/Seek/SetPosition/OpenUri, Shuffle/Loop/Volume, metadatos con carátula, `Raise`/`Quit` | `mpris.py:93-244` | `tests/music_ui.py:140-159` (`playerctl`, con bus de sesión) | n/a (backend) |
| M-71 | Wysun Player pausa Music por MPRIS al empezar un sonido | `wysun_media/integration.py:7-30,64` | `tests/test_media_integration.py` | n/a |
| M-72 | Lanzador: entradas «Wysun Music» y «Wysun Music · widget» | `apps/shell/modules/launcher/services/Catalog.js:46-47` | manual (Super+D) | n/a |
| M-73 | CLI `wysun music`, `wysun music-mini`; `.desktop` con `StartupWMClass=wysun-music`; icono `musika` | `bin/wysun:19,40,116-117`; `config/.local/share/applications/wysun-music.desktop` | `tests/test_wysun_distribution.py:232-239` | n/a |
| M-74 | Atajo `Super+Shift+M` (widget de media) y regla de ventana flotante/centrada para `wysun-music` | `config/.config/wysun/hyprland.lua:25,48` | manual | n/a |
| M-75 | Modo teclado del dashboard del shell para el widget de Music (Esc cierra, teclas multimedia) | `apps/shell/modules/dashboard/Wrapper.qml:37`; `apps/shell/wysun/WysunBridge.qml:63` | manual | n/a |
| M-76 | Persistencia privada: `~/.local/share/wysun/music/` (library.json, `player.sqlite3` favoritos/sesión/referencias/variantes/desfases, `metadata/`), fuera del código instalado | `data.py:23`, `store.py:78-210`, `metadata.py:60-104` | `tests/test_music_player.py:25` | n/a |

---

## Wysun Files

### G. Proceso, CLI y persistencia

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| F-01 | CLI `wysun files [CARPETA\|file://…]…`: abre una pestaña por ruta (un archivo abre su carpeta); rechaza esquemas no locales y rutas inexistentes con aviso | `wysun_files/app.py:9-21,24-44`; `bin/wysun:19` | `tests/files_ui.py:74` (`test_file_url_and_remote_rejection`); `tests/test_wysun_distribution.py:239` | n/a |
| F-02 | `.desktop` con `MimeType=inode/directory`; `inode/directory` por defecto en `mimeapps.list` conservando alternativas | `config/.local/share/applications/wysun-files.desktop`; `installer/main.py:192-198` | `tests/test_file_integration.py` | n/a |
| F-03 | Atajos de sesión `Super+Alt+F` y `Super+E` → `wysun files`; regla flotante para el selector | `config/.config/wysun/hyprland.lua:28,46,172` | manual | n/a |
| F-04 | Persistencia `QSettings('Wysun','Files')`: modo de vista, archivos ocultos, vista previa automática, marcadores | `wysun_files/window.py:59-65,332,346-348,418-419,588-605` | `tests/files_ui.py` (modo/ocultos); manual reabriendo | n/a |
| F-05 | Cierre protegido: espera a que termine una operación en curso; detiene vista previa/medios antes de cerrar | `window.py:883-895` | `tests/files_ui.py:285-300` (medios); manual con copia larga | `files-dialogs.html` (progreso) |
| F-06 | Una ventana por proceso `wysun files`; varias ventanas permitidas; `Ctrl+Q` cierra | `app.py:24-44`; `window.py:808` | manual | n/a |
| F-07 | Entradas de integración con el lanzador/shell («Files») y la hoja de atajos del shell | `apps/shell/modules/cheatsheet/backend.py:25`; `apps/python/wysun_services/launcher_data.py:17` (búsqueda de archivos del lanzador, distinta de la app) | manual | n/a |

### H. Navegación

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| F-10 | Barra lateral: Favoritos (Inicio, Escritorio, Documentos, Descargas…), Marcadores, Dispositivos (Sistema y volúmenes montados/extraíbles con uso de disco refrescado cada 20 s), Papelera; se resalta el lugar más específico que contiene la carpeta; indicador deslizante | `sidebar.py:17,153-253` | `tests/files_ui.py:71,138` | `files-adaptive-nav.html` (aprobada), `files-folder.html` |
| F-11 | Marcadores: añadir (menú «Más acciones»), quitar (menú contextual del marcador), persistidos | `window.py:587-605`; `sidebar.py:197-203` | manual | `files-folder.html` (menú) |
| F-12 | Barra de ruta con segmentos navegables, edición con `Ctrl+L` (`Esc` cancela), copiar ruta sin navegar | `pathbar.py:14-173`; `window.py:774-775` | `tests/files_ui.py:61,69` | `files-folder.html` |
| F-13 | Pestañas: nueva (`Ctrl+T`, botón +), cerrar (`Ctrl+W`), ciclar (`Ctrl+Tab`, `Ctrl+Shift+Tab`, `Ctrl+PgUp/PgDn`), «Abrir en nueva pestaña», historial por pestaña | `chrome.py:24-160`; `window.py:213-253,817-820`; `tab.py:72-115` | `tests/files_ui.py:54` | `files-folder.html` |
| F-14 | Atrás/adelante (`Alt+←/→`), Carpeta superior (`Alt+↑`, Retroceso, `←` en lista), `Alt+Inicio` a la carpeta personal; al subir se reselecciona la carpeta de la que se venía | `window.py:255-262,805-811`; `fileview.py:373-384`; `tab.py:94-115` | `tests/files_ui.py:54,122` | `files-folder.html` |
| F-15 | Seguir enlaces de la vista previa (Markdown) hacia otras rutas | `window.py:263-272` | `tests/files_ui.py:238` | `files-details.html` |
| F-16 | Título de ventana «<carpeta> · Wysun Archivos»; carpeta «Cargando carpeta…» | `window.py:301-302`; `tab.py:145-160` | `tests/files_ui.py:166` | `files-folder.html` |

### I. Vista de carpeta

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| F-20 | Rejilla y lista (`Ctrl+1`/`Ctrl+2`, conmutador segmentado) con miniaturas de imágenes (hilo, caché, límites 32 MB / 16 Mpx), iconos por tipo/color de categoría; entrada animada | `window.py:150-153,329-336`; `fileview.py:227-300`; `thumbnails.py:1-101`; `kinds.py:23-75` | `tests/files_ui.py:132,146,189,196` | `files-folder.html` |
| F-21 | Carpeta grande fluida (virtual, `ScrollPerPixel`, tamaños uniformes) | `fileview.py:244-270` | `tests/files_ui.py:141` (`test_large_folder_stays_responsive`); medidas base punto 2 | `files-folder.html` |
| F-22 | Encabezado de columnas de la lista (Nombre/Fecha/Tamaño/Tipo), clic alterna dirección | `fileview.py:457-523` | `tests/files_ui.py:186` | `files-folder.html` (lista) |
| F-23 | Ordenar: nombre, fecha, tamaño, tipo, ascendente/descendente (menú) | `window.py:351-363` | `tests/files_ui.py:178` | `files-folder.html` |
| F-24 | Filtro por nombre (`Ctrl+F`, o escribir en la vista), que se ensancha; filtros por tipo (Todo, Carpetas, Imágenes, Vídeos, Audio, Documentos, Código) que mantienen las carpetas | `window.py:337-344,769-773,853-882`; `chrome.py:361-375`; `model.py:12,35-58` | `tests/files_ui.py:125,160` | `files-folder.html` |
| F-25 | Archivos ocultos (`Ctrl+H`) | `window.py:345-350` | `tests/files_ui.py:160` | `files-folder.html` (menú) |
| F-26 | Cabecera (Hero): título del lugar, resumen «N carpetas · N archivos · tamaño», glifo/emblema | `chrome.py:355-435`; `window.py:296-300,304-328` | manual | `files-adaptive-nav.html` (emblema cookie) y `files-folder.html` |
| F-27 | Barra de estado: «N elementos · M seleccionados», espacio libre, indicador de operación en curso | `chrome.py:243-289`; `window.py:304-328` | `tests/files_ui.py:166` | `files-folder.html` |
| F-28 | Estados vacíos: «Esta carpeta está vacía.», «Nada coincide con el filtro.», «Cargando carpeta…» | `tab.py:145-158`; `fileview.py:409-455` | `tests/files_ui.py:166` | `files-folder.html` (vacíos) |
| F-29 | Selección múltiple (Ctrl/Shift, `Ctrl+A`), «pop» al seleccionar, barra flotante de selección (Abrir, Copiar, Renombrar, Papelera, Opciones, Quitar selección) | `fileview.py:253,345-365`; `chrome.py:164-241`; `window.py:538-542,522-537` | `tests/files_ui.py:108,132` | `files-folder.html` (selección) |
| F-30 | Teclado en la vista: escribir inicia el filtro; `Enter` abre; `Espacio` vista previa; `Supr` papelera; `F2` renombrar; `Esc` en cascada (sheet → pantalla completa → ruta → filtro → expandida → selección) | `fileview.py:373-384`; `window.py:781-800,822-830` | `tests/files_ui.py:112` | `files-folder.html` |
| F-31 | Menú contextual (clic derecho / `Alt+K` anclado al elemento): Abrir, Abrir en nueva pestaña, Vista previa ampliada, Copiar, Cortar, Pegar aquí, Cambiar nombre, Enviar a la papelera, Copiar ruta, Nueva carpeta, Terminal aquí, Propiedades — con estados habilitado/deshabilitado | `window.py:731-768`; `menu.py:1-232` | `tests/files_ui.py:112` | `files-folder.html` (menús) |
| F-32 | Menús «Nuevo» (Carpeta, Archivo vacío) y «Más acciones» (Nueva pestaña, Carpeta superior, Añadir a marcadores, Terminal aquí, Archivos ocultos, Copiar ruta, Propiedades) | `window.py:364-382` | manual | `files-folder.html` (menús) |
| F-33 | Arrastrar: sacar archivos de la vista hacia otras apps (`DragOnly`; **no** hay soltar dentro de Files) | `fileview.py:256-257` | manual (arrastrar a un navegador o gestor); `Chooser` lo desactiva (`chooser.py:182`) | `files-folder.html` (nota; soltar es «nueva») |

### J. Operaciones de archivos

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| F-40 | Copiar/Cortar/Pegar vía portapapeles (`text/uri-list` + `x-special/gnome-copied-files` + texto); las cortadas se atenúan hasta pegar y el portapapeles se limpia tras mover | `window.py:611-639,682-712`; `fileview.py:308-315` | `tests/files_ui.py:79,88` | `files-dialogs.html` |
| F-41 | Operaciones fuera del hilo de la GUI, una a la vez («Espera a que termine la operación actual»), con aviso final y error | `window.py:43-55,682-712`; `ops.py:101-169` | `tests/test_files_ops.py:16-115` | `files-dialogs.html` (progreso) |
| F-42 | Garantías de `ops`: nunca sobrescribe, copia exclusiva (`O_EXCL`), `renameat2` sin sobrescribir, mover entre dispositivos copia y luego borra, no copia una carpeta dentro de sí misma, selecciones anidadas rechazadas, enlaces simbólicos preservados, limpieza solo de lo creado | `ops.py:34-100,101-169` | `tests/test_files_ops.py:26-115` | n/a (backend; el rediseño de conflictos de la maqueta es «nueva» y debe conservarlas) |
| F-43 | Conflictos de nombre **hoy**: la operación entera falla con «Ya existe: …» (no hay diálogo reemplazar/omitir/conservar ambos) | `ops.py:34-40`; `window.py:695-701` | `tests/test_files_ops.py:26,66` | `files-dialogs.html` (diálogo de conflicto = «nueva») |
| F-44 | Nueva carpeta (`Ctrl+Shift+N`) y archivo vacío, con validación de nombre (sin `/`, no `.`/`..`) y sufijo seleccionado solo hasta la extensión | `window.py:640-660`; `sheet.py` | `tests/files_ui.py:92,95` | `files-dialogs.html` |
| F-45 | Cambiar nombre (`F2`) con hoja modal que preselecciona el nombre sin extensión | `window.py:661-671`; `sheet.py` | `tests/files_ui.py:100` | `files-dialogs.html` |
| F-46 | Papelera con confirmación (`gio trash`; nunca borra definitivamente) | `window.py:672-681`; `ops.py:127-137` | `tests/files_ui.py:105`; `tests/test_files_ops.py:81` | `files-dialogs.html` |
| F-47 | Propiedades (nombre, ruta, tipo, tamaño, permisos, fecha, destino del enlace) para la selección o la carpeta | `window.py:713-730` | `tests/files_ui.py:156` | `files-details.html` |
| F-48 | Abrir: carpeta navega; imagen/vídeo/audio → Wysun Player (varios en una sola ventana, en orden); PDF → navegador predeterminado vía `gio launch`; resto → aplicación del sistema; máx. 10 a la vez | `window.py:543-568`; `browser.py:7-17`; `wysun_player/client.py` | `tests/files_ui.py:273,314,322` | `files-folder.html` |
| F-49 | Terminal aquí (ghostty → x-terminal-emulator → alacritty → kitty → xterm) | `window.py:578-586` | manual | `files-folder.html` (menú) |

### K. Vista previa / inspector

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| F-50 | Inspector lateral automático (372 px, ≥ 1000 px de ancho, un solo archivo con vista previa; botón y `Ctrl+I`) con animación de deslizamiento | `window.py:384-440,807`; `preview.py:239-350` | `tests/files_ui.py:205` | `files-details.html` |
| F-51 | Vista previa de imagen (paginada, zoom con rueda/`+`/`-`/`0`, arrastre, doble clic restablece), texto literal con margen de números (512 KB), Markdown renderizado ⇄ fuente, código resaltado, audio/vídeo con un solo reproductor reutilizado | `preview.py:24-624`; `zoom.py:7-58`; `markdown.py`; `highlight.py`; `textview.py` | `tests/files_ui.py:217-262,285-305`; `tests/test_files_text.py`; `tests/test_files_wrap.py` | `files-details.html` |
| F-52 | Resumen de carpeta y de selección múltiple en el inspector; etiquetas de metadatos (dimensiones, duración, códec…) | `preview.py:155-238,367-428,492-515` | `tests/files_ui.py:245,300` | `files-details.html` |
| F-53 | Ampliar la vista previa (`Espacio`/botón) ocupando la ventana; pantalla completa de vídeo (`F`); continuar en Wysun Player en el mismo instante | `window.py:441-521,569-577`; `preview.py:515-527` | `tests/files_ui.py:256,305` | `files-details.html` |
| F-54 | Archivo no decodificable: se selecciona e informa sin romper | `preview.py:528-547` | `tests/files_ui.py:335` | `files-details.html` (estado de error) |
| F-55 | Copiar ruta desde el inspector y desde la barra de ruta (ruta absoluta) | `window.py:607-610`; `preview.py:613-618` | `tests/files_ui.py:69` | `files-details.html` |

### L. Selector de archivos y D-Bus (no negociable)

| ID | Función | Dónde | Verificación | Maqueta |
|---|---|---|---|---|
| F-60 | `wysun_files.picker`: selector de un disparo con JSON por stdin/stdout `{title, save, initial, suffix(pdf\|md)}` → `{code, uris, current_filter…}`; arranca desde la carpeta existente más cercana; en guardar propone nombre (`documento.<ext>`) y sufijo | `wysun_files/picker.py:11-45` | `tests/files_chooser_ui.py`; `tests/pdf/` (PDF); manual desde PDF | `files-chooser.html` (modo PDF) |
| F-61 | Cliente PDF: `pick_file` lanza el picker como subproceso, deshabilita la ventana padre, un selector por ventana, cancelable (`cancel_picker`) | `wysun_pdf/file_picker.py:8-70`; usos en `wysun_pdf/window.py:367,498,612,919` | `tests/pdf/` | `files-chooser.html` (modo PDF) |
| F-62 | `FileChooser` (reutiliza `FilesWindow` sin edición ni atajos destructivos): modos abrir / guardar / guardar varios; carpeta o archivo; múltiple; modal o no; título «… — Wysun Selector» | `chooser.py:144-195` | `tests/files_chooser_ui.py:39-66` | `files-chooser.html` |
| F-63 | Filtros del portal: glob (tipo 0) y MIME (tipo 1, con herencia y comodines) intersectados con el filtro de nombre, sin ocultar carpetas; selector de filtro; filtro actual devuelto | `chooser.py:28-80,106-141,196-242` | `tests/files_chooser_ui.py:42` | `files-chooser.html` |
| F-64 | Opciones («choices») del portal: combos y casillas devueltos con su valor | `chooser.py:228-242,347-358` | `tests/files_chooser_ui.py:66` | `files-chooser.html` |
| F-65 | Guardar: nombre sin escapes de ruta, sufijo por defecto, error si es carpeta o sin permiso de escritura, **confirmación «Reemplazar archivo»**; no escribe el archivo | `chooser.py:286-310` | `tests/files_chooser_ui.py:55,61` | `files-chooser.html` (reemplazo) |
| F-66 | Guardar varios: nombres únicos `nombre (1).ext` sin escribir | `chooser.py:312-324` | `tests/files_chooser_ui.py:63` | `files-chooser.html` |
| F-67 | Abrir: valida existencia, tipo (carpeta/archivo), lectura; selección que desaparece → error; URIs UTF-8; `Ctrl+A` solo en múltiple; `Enter` entra en carpeta o acepta; cancelar devuelve código 1 sin archivos | `chooser.py:262-345,347-358` | `tests/files_chooser_ui.py:39,49,51,53` | `files-chooser.html` |
| F-68 | Portal `org.freedesktop.impl.portal.FileChooser` v4 (`OpenFile`, `SaveFile`, `SaveFiles`) en `org.freedesktop.impl.portal.desktop.wysun`; solo acepta al dueño de `org.freedesktop.portal.Desktop`; handles duplicados rechazados; `Request.Close` solo del emisor; resultados tipados | `service.py:15-60,93-101` | `tests/files_portal_dbus.py:51-61`: `dbus-run-session -- env QT_QPA_PLATFORM=offscreen python3 tests/files_portal_dbus.py` | `files-chooser.html` (modo portal) |
| F-69 | Registro del backend: `wysun.portal`, `portals.conf` (`FileChooser=wysun;gtk`), servicio D-Bus y `wysun-files-integration.service` | `installer/main.py:217-225`; `installer/wayland.py:89`; `docs/files-integration.md` | `tests/test_file_integration.py`; `tests/test_wayland_install.py` | n/a |
| F-70 | `org.freedesktop.FileManager1` (`ShowItems`, `ShowFolders`, `ShowItemProperties`): abre la carpeta, selecciona los elementos (espera a la carga), abre Propiedades; si otro gestor tiene el nombre sin permitir reemplazo, solo queda el selector | `service.py:62-91,98-101` | `tests/files_portal_dbus.py:65`; `wysun_media/player.py:557` (cliente: «mostrar en carpeta» del Player) | `files-folder.html` (selección resaltada al abrir desde otra app), `files-details.html` (propiedades) |
| F-71 | Cierre ordenado del servicio (SIGTERM/SIGINT) con diálogos/ventanas abiertos; bucle GLib integrado en Qt | `service.py:102-117` | `tests/files_portal_dbus.py` | n/a |

---

## Resumen de cobertura prevista

- Music: 62 funciones (M-01…M-76) → 4 maquetas (`music-library`, `music-album`, `music-player`, `music-search`).
- Files: 56 funciones (F-01…F-71) → 5 maquetas (`files-adaptive-nav` aprobada, `files-folder`, `files-details`,
  `files-dialogs`, `files-chooser`).
- Lo que no es visible (proceso, D-Bus, instalador, persistencia) se verifica solo por prueba; la columna
  Maqueta dice «n/a».
- Cada punto del encargo 3 y 4 sustituye las rutas de la columna **Maqueta** por anclas concretas
  (`archivo.html#sección`) al terminar las maquetas.

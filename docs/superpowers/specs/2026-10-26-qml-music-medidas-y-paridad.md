# Wysun Music en QML — medidas y paridad verificada

Fecha: 2026-10-26. Rama `qml/fase2-music`. Plan: `docs/superpowers/plans/2026-10-26-qml-fase2-music.md`.

## Medidas (antes: Widgets; después: QML)

`tests/perf/music_compare.py`: sesión Hyprland real, Intel UHD 620 (OpenGL por hardware), biblioteca sintética de
3 000 pistas y 300 álbumes en datos y `XDG_RUNTIME_DIR` propios (la instancia de Music del usuario no se toca).
Arranque = desde `python3 -m wysun_music` hasta que la ventana aparece en `hyprctl clients` (incluye la
re-ejecución en el venv `qml-runtime`). Memoria a los 3 s, en reposo.

| | Widgets (Qt 6.8.2 del sistema) | QML (Qt 6.9.3 del shell) |
|---|---|---|
| Ventana con datos | 1,30 – 1,85 s | 0,86 – 1,35 s (primera tanda), 1,6 – 1,7 s con el equipo cargado |
| RSS en reposo | 125 MB | 213 MB |
| PSS en reposo | 84 MB | 141 MB |
| Desplazamiento de 10 000 filas | — | 60 fps, 0 frames > 25 ms (banco de la galería, mismo `ListView`/`ListItem`) |

Desglose del PSS de QML: memoria anónima y montón 68 MB (motor JS, grafo de escena, modelos), driver OpenGL de Mesa
(`libLLVM` + `gallium`) 22 MB que el shell también tiene mapeado, bibliotecas Qt 18 MB. La diferencia con Widgets
(+57 MB de PSS) es el coste fijo de Qt Quick + OpenGL que ya midió la fase 0 (85–99 MB para una app mínima);
«Ahora suena» y la hoja de atajos se crean al abrirse por primera vez (−9 MB). Arranque igual o mejor.

## Paridad (lista `2026-10-26-qml-paridad-music-files.md`)

Todas las filas M-01…M-76 tienen sitio y prueba en la versión QML. Pruebas en `tests/qml/check_music_*.py`
(offscreen, biblioteca sintética, mpv real con `--ao=null`):

| Filas | Cómo se verifica |
|---|---|
| M-01, M-02, M-04 | `check_music_window` (segunda instancia sin re-ejecutar, orden de re-ejecución), `check_music_integration` (`--background`) |
| M-03, M-05, M-06, M-07 | `check_music_window` (cerrar oculta y sigue sonando, ruta guardada), tema en vivo por `ThemeBridge` (fase 1) |
| M-10…M-14 | `check_music_window` (destinos, historial de 50, ruta huérfana), `check_navigation` (portadas, «+», menú contextual de playlists) |
| M-15…M-18, M-22 | `check_music_search` (Ctrl+K, refina el historial, ↓/Enter, Esc), `ShortcutSheet` (F1) |
| M-19…M-21 | `check_music_pages` (Inicio, Biblioteca, teclado de tarjetas) |
| M-25…M-40 | `check_music_collection`, `check_music_pages`, `check_music_models` (cabecera, filtro > 8, orden, menús M-35/M-37, playlists, favoritos, selección múltiple, teclas de la lista) |
| M-36 | mejorado: `FileManager1.ShowItems` selecciona el archivo; si no hay gestor, abre la carpeta (`check_music_collection`) |
| M-45…M-55 | `check_music_player` (cápsula, Espacio/M, Ctrl+…, posición ±5 s, Inicio/Fin, mensajes), `check_music_nowplaying` (letra, desfase, saltos, cola) |
| M-60…M-67 | `check_music_models` (recarga de la biblioteca), `check_music_addmusic` (YouTube, Spotify, selector de Files, cola de descargas) |
| M-70…M-76 | `check_music_integration` (MPRIS con `playerctl` en un bus privado, Raise); lanzador, `.desktop`, atajo y regla de ventana sin cambios (clase `wysun-music`) |
| D1, D3, D4 (nuevos) | Alt+1…5 y Ctrl+J (`Main.qml`), Ctrl+Enter en resultados (`check_music_addmusic`), ↑/↓+Enter en la letra (`check_music_nowplaying`) |

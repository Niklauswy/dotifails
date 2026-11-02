# Wysun Player en QML — plan de implementación

> Ejecución: nativa (el coordinador implementa cada tarea en esta sesión) y una revisión de toda la rama al final.

**Meta:** Wysun Player pasa de Qt Widgets a QML sobre WysunM3 con las mismas funciones y atajos.

**Arquitectura:** `wysun_player/app.py` (sin Qt) se re-ejecuta en el venv QML cuando debe servir;
`wysun_player/quick/` contiene el proceso, un `PlayerController` por ventana (la lógica de `MediaPlayer` sin widgets)
y los ítems de video libmpv; `apps/qml/player/` la interfaz. `wysun_media` queda como motor sin interfaz.

**Spec:** `docs/superpowers/specs/2026-11-02-qml-player-design.md`.

## Restricciones globales

- Tokens del tema, sin literales (`tests/test_theme_literals.py`); excepción declarada: lienzo negro del video.
- `QSG_RENDER_LOOP=basic` en el proceso Player (render de Python y GIL; ver spec).
- `app_id`/clase de ventana `wysun-player` (`StartupWMClass` del `.desktop`).
- Cliente (`wysun_player.client`) solo biblioteca estándar; formato del socket sin cambios.
- Pruebas QML con el Python del venv (`tests/qml/check_player_*.py`, registradas en `tests/test_qml_runtime.py`);
  medios sintéticos generados con ffmpeg en directorios temporales; `WYSUN_MPV_OPTIONS=ao=null`.
- Nada de builds ni suites en paralelo.

## Foco de revisión

1. Cerrar una ventana con un video reproduciéndose: sin cuelgue, el núcleo mpv liberado, MPRIS retirado.
2. Redimensionar/pasar a pantalla completa con video en marcha: sin congelarse, imagen al tamaño nuevo (HiDPI).
3. Abrir una imagen y luego un video en la misma ventana (y al revés): una sola superficie visible, audio parado.
4. Un archivo roto o borrado en medio de la colección: aviso, sin excepción, siguiente/anterior siguen.
5. Cambiar de modo claro/oscuro con la ventana abierta: el HUD y el aviso cambian en vivo.

---

### Tarea 1: Ítems de video libmpv para QML

**Archivos:** crear `apps/python/wysun_player/quick/__init__.py`, `apps/python/wysun_player/quick/video.py`;
prueba `tests/qml/check_player_video.py`.

**Interfaces producidas:**
- `MpvVideoItem(QQuickFramebufferObject)`: propiedad `controller` (objeto con `.session: MediaSession`); señal
  `failed(str)`; render a `fbo.size()` (ítem × dpr), `render_hook` de la sesión → `update()`; el renderer libera el
  contexto mpv en su destructor y llama `session.set_surface_ready(False)`; al crearlo, `True`.
- `MpvSoftwareItem(QQuickPaintedItem)`: mismo contrato; hilo de render por software (lógica de
  `wysun_media.video.SoftwareVideoView`), `release()` lo une.
- `renderer_name() -> 'opengl'|'software'` según `WYSUN_PLAYER_RENDERER` y la API del grafo de escena.
- `register()` registra ambos en `Wysun.Player 1.0` (`MpvVideo`, `MpvSoftwareVideo`).

**Pruebas:** con un clip `testsrc` 320×180 de 2 s: el ítem por software, en una ventana offscreen, recibe fotogramas
y la captura tiene píxeles no negros; `release()` deja el hilo terminado; `renderer_name()` respeta la variable.

### Tarea 2: PlayerController

**Archivos:** crear `apps/python/wysun_player/quick/controller.py`; modificar `apps/python/wysun_media/mpris.py`
(ventana QWindow: `requestActivate`, `visibility()`); prueba `tests/qml/check_player_controller.py`.

**Interfaces producidas** (`PlayerController(QObject)`, uno por ventana):
- Propiedades notificables: `kind`, `title`, `state`, `position`, `duration`, `volume`, `muted`, `speed`, `looping`,
  `abLoop` (lista de 0–2), `chapters`, `audioTracks`, `subtitleTracks`, `subDelay`, `count`, `hasPrevious`, `hasNext`,
  `source` (URL), `coverUrl`, `audioTitle`, `audioDetail`, `error` (texto del aviso, vacío si no hay), `fullscreen`,
  `info` (lista de pares etiqueta/valor), `renderer`.
- Slots: `open(path, start, paused, browse)`, `openMany(list, paused, start)`, `toggle()`, `skip(s)`,
  `seek(s)`, `scrub(s)`, `seekFraction(f)`, `toggleMute()`, `setVolume(p)`, `nudgeVolume(d)`, `setSpeed(s)`,
  `nudgeSpeed(dir)`, `step(frames)`, `markLoop()`, `toggleLoop()`, `cycleSubtitles()`, `cycleAudio()`,
  `selectSubtitle(id|-1)`, `selectAudio(id)`, `shiftSubtitles(s)`, `addSubtitle(path)`, `saveFrame()`, `copyPath()`,
  `copyImage()`, `reveal()`, `trash()`, `stepCollection(n)`, `setFullscreen(bool)`, `drop(urls)`, `shutdown()`.
- Señales: `toast(str text, str icon)`, `fullscreenRequested(bool)`, `imageZoom(...)` no: el zoom de imagen vive en QML.
- Integración: `window()`, `isVisible()`, `mode == 'full'`, `activated`, `collection`, `session`, `source`,
  `close_media()` para `wysun_media.integration`/`mpris`.

**Pruebas:** abrir video/audio/imagen sintéticos fija `kind`/`title`; colección de carpeta y `stepCollection` en los
extremos («No hay más archivos»); archivo borrado → `error`; `nudgeVolume` acota 0–150 y emite toast; `nudgeSpeed`
recorre `SPEEDS`; `cycleSubtitles` sin pistas → toast; `trash` con `gio` falso abre el vecino; posición recordada.

### Tarea 3: Proceso, ventanas y arranque

**Archivos:** crear `apps/python/wysun_player/quick/process.py`; modificar `apps/python/wysun_player/app.py`
(`serve` → `bootstrap.ensure_runtime_python` antes de reclamar), `client.py` (comentario/intérprete),
`apps/python/wysun_files/picker.py` (petición `kind: "media"`); crear `apps/qml/player/Main.qml` mínimo;
prueba `tests/qml/check_player_process.py`.

**Interfaces producidas:** `Process(quit, owner, window_factory)` con `show(payload)`, `windows`, gracia de 400 ms,
límite 24; `RequestServer` igual que hoy; `PlayerWindow` (QML `Main.qml` + `PlayerController` + ajuste al primer
video + pantalla completa); `run(first, owner)`; abrir sin archivos lanza el selector de Files `kind: media`.

**Pruebas:** `RequestServer.parse` (como hoy); `show` crea ventana, reutiliza la última al llegar al límite; la última
ventana cerrada sale tras la gracia; una petición durante la gracia la cancela; `QSG_RENDER_LOOP` es `basic`;
`picker.request_options({'kind': 'media'})` permite varios archivos con filtros de video/audio/imagen.

### Tarea 4: Interfaz QML

**Archivos:** `apps/qml/player/` `Main.qml`, `VideoStage.qml`, `ImageStage.qml`, `AudioStage.qml`, `ControlBar.qml`,
`SeekBar.qml`, `PlayMorph.qml`, `PlayerMenus.qml`, `Toast.qml`, `Note.qml`; prueba `tests/qml/check_player_ui.py`.

Barra: capsula HUD centrada abajo, ancho ≤ 46 unidades, compacta < 26; botones según `kind` y `count` (tabla de
`wysun_media/bar.py`); seek con capítulos, rango A‑B y burbuja; ocultar barra y cursor a los 2,5 s mientras se
reproduce video o se ve una imagen, salvo con menú abierto o el puntero encima. Imagen: `Image`/`AnimatedImage`,
ajustar/tamaño real/zoom anclado a cursor, pellizco, arrastre, giro, `sourceSize` acotado. Audio: carátula en
`CookieShape` que gira mientras suena, título y artista·álbum. Atajos de la spec con `Keys.onPressed`.

**Pruebas:** cargar `Main.qml` offscreen con un controlador falso: botones visibles por tipo y modo compacto; cada
atajo llama al slot correcto; Esc sale de pantalla completa; la barra se oculta tras la inactividad con video en
reproducción; ninguna advertencia QML al cargar.

### Tarea 5: Retirar Widgets y desplegar

**Archivos:** borrar `wysun_media/{player,controls,bar,menus,audio,image,video,shape,symbols,host}.py`,
`wysun_player/{window,host}.py` y sus pruebas/arneses (`test_media_{player,controls,image,shape}.py`,
`media_support.py`, `media_benchmark.py`, `media_latency.py`, `wayland_media_case.py`); adaptar
`test_media_session.py`, `test_media_integration.py`, `test_player_app.py`; actualizar `ARCHITECTURE.md`,
`docs/qml-base.md`, la spec general, el manifiesto del instalador si nombra archivos.

**Verificación:** las suites de `AGENTS.md` en serie; `./instalar.sh --wysun-only`; prueba en vivo de la lista de la
spec; captura de la ventana con video, audio e imagen en claro y oscuro.

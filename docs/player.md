# Wysun Player

Wysun Player es el visor de **imágenes, video y audio** de Wysun, una app QML sobre la base compartida WysunM3
(`apps/qml/player`, `docs/qml-base.md`). Todo lo que abre un archivo multimedia para verlo o escucharlo usa Wysun Player;
el motor (`wysun_media`: libmpv, sesión, colección, MPRIS) es común con el Recorder, que todavía embebe su reproductor de
Widgets hasta su propia migración.

| Contexto | Comportamiento |
|---|---|
| Files: doble clic, Enter, «Abrir» | Abre Wysun Player directamente, sin pasar por `xdg-open`. Varios medios seleccionados abren **una** ventana con la selección en orden. |
| Files: panel de detalles | Vista previa propia de Files (QML); «Abrir en Wysun Player» abre el archivo en el reproductor. |
| Recorder | Su página de reproducción embebe el reproductor de Widgets de `wysun_media` (hasta la migración del Recorder). |
| Capturas del shell | «Guardar y ver» (`V`) guarda el PNG y lo abre; solo lo abre cuando el archivo ya existe. |
| Otras aplicaciones y `xdg-open` | La instalación completa fija Wysun Player como aplicación predeterminada de sus imágenes, video y audio (§ Instalación). |
| Wysun Music | Sigue siendo la app de biblioteca. Un audio suelto abierto desde Files se reproduce en Wysun Player. |

## Uso

```
wysun player [--paused] [--fullscreen] [--start SEGUNDOS] [--] ARCHIVO...
```

Hay **un solo proceso por usuario** mientras haya ventanas abiertas. Una segunda llamada entrega sus archivos a ese proceso
(socket `$XDG_RUNTIME_DIR/wysun-player-<uid>.sock`, una línea JSON que el servidor confirma con `ok`) y termina; cada petición abre una
ventana nueva con su propia sesión. El proceso termina cuando se cierra la última ventana (400 ms de gracia por si ya viene otra
petición): no queda nada residente. Si dos llamadas coinciden al arrancar, una toma el bloqueo y la otra reintenta hasta 3 s.

Un archivo se abre con su carpeta como colección (orden natural, sin recursión, sin vuelta circular); varios archivos conservan el orden
dado. Imágenes se navegan entre imágenes; video y audio entre video y audio.

### Teclado

| Video y audio | | Imágenes | |
|---|---|---|---|
| `Espacio` / `K` | reproducir · pausar | `←` `→` · `PgUp` `PgDn` | anterior · siguiente |
| `←` `→` | −5 s · +5 s (`Shift` 1 s, `Ctrl` 60 s) | `+` `−` · rueda | acercar · alejar (anclado al cursor) |
| `↑` `↓` · rueda | volumen ±5 % (hasta 150 %) | `0` · `1` | ajustar · tamaño real (1 píxel de imagen = 1 de pantalla) |
| `0`–`9` | saltar al 0–90 % | doble clic | alterna ajustar / tamaño real |
| `Inicio` `Fin` | principio · final | `R` · `Shift+R` | girar (solo presentación; el original no cambia) |
| `.` `,` | fotograma siguiente · anterior (en pausa) | `Espacio` | animación GIF/WebP: reproducir · pausar |
| `[` `]` · `Retroceso` | velocidad 0.25×–4× · normal | | |
| `M` | silencio | **Todos** | |
| `L` · `Shift+L` | bucle A-B · bucle del archivo | `F` / `F11` · `Esc` | pantalla completa |
| `C` · `A` | siguiente subtítulo · pista de audio | `I` | información |
| `S` | guardar el fotograma en Imágenes | `Ctrl+C` | copiar imagen (o la ruta en video y audio) |
| `N` `P` | siguiente · anterior archivo | `Supr` | mover a la papelera (recuperable; solo en la ventana) |
| | | `O` / `Ctrl+O` | abrir archivos (selector de Wysun Files) |
| | | `Ctrl+Q` / `Ctrl+W` | cerrar la ventana |

Un clic sobre el video pausa y un doble clic pasa a pantalla completa; la rueda cambia el volumen. Arrastrar archivos sobre la ventana los abre; un `.srt/.ass/.vtt` soltado sobre un video se carga como subtítulos. La barra de controles
flota sobre el contenido y se oculta tras 2,5 s sin actividad mientras un video suena o se ve una imagen (no con un menú abierto ni con
el puntero encima); reaparece al mover el ratón o pulsar una tecla, y el cursor se oculta con ella sobre el video. Las posiciones de
archivos de más de 5 minutos se recuerdan (`~/.local/state/wysun/player/positions.json`, claves por hash, sin rutas).

## Arquitectura

```text
apps/python/
  wysun_player/
    app.py         línea de órdenes e instancia, sin Qt; se re-ejecuta en el venv QML solo si debe servir
    client.py      entrega a la instancia en marcha o la inicia (biblioteca estándar)
    quick/process.py     proceso QML: RequestServer, una ventana (Main.qml + controlador) por petición, salida tras la última
    quick/controller.py  PlayerController: la lógica de una ventana (abrir, colección, posiciones, acciones, información)
    quick/video.py       MpvVideo (QQuickFramebufferObject + render API OpenGL) y MpvSoftwareVideo (respaldo)
  wysun_media/                  motor común (sin interfaz salvo el reproductor de Widgets que aún usa el Recorder)
    source.py      validación y clasificación de archivos locales; errors.py: vocabulario de errores
    mpv.py         binding ctypes mínimo de libmpv (comandos asíncronos, propiedades observadas, render GL/SW)
    session.py     MediaSession: un archivo a la vez sobre un único núcleo mpv reutilizado
    software.py    render por software de mpv en un hilo, sin toolkit
    collection.py  carpeta o lista explícita, anterior/siguiente   resume.py: posiciones recordadas
    cover.py       carátula incrustada de un audio (ffmpeg en segundo plano)
    mpris.py, integration.py  MPRIS, pista de pantalla encendida y pausa de Music
    player.py, controls.py, bar.py, menus.py, image.py, audio.py, video.py, shape.py, symbols.py, host.py
                   reproductor de Widgets del Recorder (se retira con su migración)
apps/qml/player/   Main.qml (ventana, atajos, menús, información, avisos), ControlBar, SeekBar, ImageStage, AudioStage,
                   PlayerMenus; la carátula es el Cover de Music (`apps/qml/music/parts`)
apps/recorder/wysun_media        enlace al mismo paquete (desarrollo); cada release de Recorder lleva su copia
```

Decisiones:

- **libmpv**, no Qt Multimedia ni GStreamer: reproducción, sincronía, subtítulos y pistas son de mpv. Opciones fijas: sin configuración de
  usuario, scripts, ytdl, descubrimiento de subtítulos o audio externos, listas de reproducción inseguras y con los protocolos de FFmpeg
  limitados a `file`. Solo se aceptan rutas locales y URLs `file:`; se rechazan dispositivos, FIFOs, sockets y manifiestos.
- **Nada bloquea la interfaz.** Los comandos se envían con `mpv_command_async` y las respuestas llegan como eventos que se vacían al
  despertar un `pipe` (los hilos de mpv solo escriben un byte; Qt nunca se llama desde ellos). El cierre del núcleo (`mpv_terminate_destroy`)
  corre en su propio hilo.
- **Generaciones.** Cada `open()` abre una generación; los eventos del archivo reemplazado se reconocen por su `playlist_entry_id` y se
  descartan, y los resultados de decodificación de imágenes se descartan por token.
- **GPU:** mpv dibuja con su render API de OpenGL en el framebuffer de un `QQuickFramebufferObject`, bajo los controles QML, con
  `hwdec=auto-copy` (decodificación por hardware con copia de vuelta). El proceso usa el bucle de render **básico**
  (`QSG_RENDER_LOOP=basic`): el render se llama desde Python, y con el bucle con hilo el hilo de render necesitaría el GIL mientras el
  hilo GUI lo retiene esperándolo (bloqueo al capturar o redimensionar). Antes de cerrar el núcleo, la ventana libera el contexto de
  mpv con el contexto GL de la escena activo (mpv bloquea al destruir un núcleo con contexto vivo). Sin OpenGL, o si falla al iniciar, se
  usa el render por software (`wysun_media/software.py`) pintado por un `QQuickPaintedItem`.
- **Imágenes:** `Image`/`AnimatedImage` de QML con `autoTransform` y decodificación asíncrona acotada al tamaño de la ventana (el tamaño
  real se lee de la cabecera); al acercar, se decodifica más detalle tras una pausa breve, sin parpadeo (`retainWhileLoading`). La
  anterior y la siguiente se decodifican de antemano con la misma clave, así que aparecen al instante.
- **Forma y color (Material 3):** la barra es una barra de herramientas flotante M3 (`surfaceContainer`, nivel 2, esquina `extraLarge`)
  con los componentes de WysunM3, en el modo claro u oscuro del tema y en vivo; el video va sobre `scrim`. El botón de reproducir es un
  botón de icono relleno que pasa de círculo (pausa) a cuadrado redondeado (reproduciendo). El audio muestra la carátula en una galleta
  que gira despacio mientras suena.
- **Escritorio:** MPRIS por reproductor activado (ventana del reproductor; vista previa embebida desde que se pulsa reproducir; nunca imágenes
  ni vistas previas pasivas), con un nombre `org.mpris.MediaPlayer2.wysun_player.instance<pid>_<n>` y una conexión privada cada uno. La clave
  `wysun:visibleVideo` de los metadatos hace que el shell mantenga la pantalla encendida mientras un video visible se reproduce
  (`daemons/IdleInhibit.qml`), sin tocar el interruptor manual. Al empezar un sonido, Music se pausa por MPRIS si estaba sonando (una vez
  por inicio; no se reanuda solo; con tiempo de espera de 1 s y sin bloquear nunca).

## Dependencias y diagnóstico

Requiere `libmpv2`, FFmpeg (ya instalados con mpv) y el runtime QML de Wysun (venv `qml-runtime` sobre el Qt del shell), que instala
`./instalar.sh --wysun-only`. Variables (solo diagnóstico):

| Variable | Efecto |
|---|---|
| `WYSUN_PLAYER_RENDERER=software` | Fuerza el render por software. |
| `WYSUN_MPV_OPTIONS=ao=null,hwdec=no` | Opciones de mpv permitidas: `ao`, `hwdec`, `audio-device`, `volume`. |
| `WYSUN_LIBMPV=/ruta/libmpv.so.2` | Otra copia de libmpv. |

El diálogo «Información» (`I`) muestra decodificador, renderizador y fotogramas perdidos.

### Instalación y asociaciones

`./instalar.sh --wysun-only` actualiza el código y la entrada `.desktop` (`Exec=wysun player -- %F`), y **no** toca asociaciones. La instalación
completa añade a `~/.config/mimeapps.list` Wysun Player como predeterminado de los tipos de su `.desktop` (imágenes, video y audio; no SVG);
lo que era predeterminado queda como alternativa en «Abrir con». El respaldo del instalador guarda el archivo anterior y
`wysun-install restore ID` lo recupera, rescatando en `changes-before-restore/` lo que se haya editado después.

## Pruebas

```sh
python3 -m unittest tests.test_qml_runtime -v                    # incluye tests/qml/check_player_*.py (ventana, controlador, proceso,
                                                                 #   video, MPRIS) en el venv QML, offscreen y con D-Bus privado
python3 -m unittest discover -s tests -p 'test_media_*.py'      # motor: sesión, fuentes, colección, posiciones; widgets del Recorder
python3 -m unittest discover -s tests -p 'test_player_*.py'     # cliente, instancia única con procesos reales, escritorio e instalador
python3 apps/recorder/run_tests.py                               # incluye la página de reproducción de Recorder
WYSUN_TEST_GL=1 QT_QPA_PLATFORM=wayland <venv>/bin/python3 -m unittest qml.check_player_video   # OpenGL en la sesión real
python3 tests/wayland_media_case.py                             # reproductor de Widgets del Recorder en el compositor real
python3 tests/media_benchmark.py                                # CPU, memoria, primer fotograma y fotogramas perdidos
```

Los medios son sintéticos (`tests/media_fixtures.py`: H.264, VP9, HEVC, AV1, audio en seis formatos con y sin carátula, JPEG con las ocho
orientaciones EXIF, PNG con alfa, BMP, TIFF, WebP, GIF animado y archivos dañados); las de `tests/qml` generan los suyos con ffmpeg.
Las pruebas offscreen usan el render por software; la ruta OpenGL se valida en la sesión real. Cada proceso de
pruebas usa un bus D-Bus propio y desechable. `WYSUN_PYSIDE_EXTRA=<carpeta>` permite probar los módulos OpenGL de PySide6 extraídos de sus
paquetes sin instalarlos.

## Rendimiento

Objetivos (mediciones en serie y con medios sintéticos):

| Escenario | Objetivo |
|---|---|
| Abrir archivo con la instancia en marcha | Primer fotograma o imagen visible: p95 < 300 ms |
| Arranque en frío de Wysun Player | Primer fotograma o imagen visible: p95 < 1 s |
| Salto en archivo local indexado | p95 < 300 ms |
| Siguiente/anterior imagen precargada | Visible en < 50 ms |
| 1080p60 H.264 en el Intel de referencia | < 1 % de fotogramas perdidos |
| En pausa u oculto | Sin bucle de repintado; CPU casi en reposo |
| Hilo de UI | Ningún bloqueo de medios > 50 ms |
| Abrir y cerrar 100 veces | Sin procesos, hilos ni descriptores que crezcan |

Cada medición registra códec, resolución, decodificador, renderizador, versiones y hardware; no se exige AV1 por hardware donde no exista
ni se afirma compatibilidad general de GPU a partir de una sola máquina.

Última medición (2026-10-24, Intel i7-8565U, Hyprland, PySide6 6.8.2, mpv 0.40): con OpenGL + `vaapi-copy` un 1080p60 H.264 usa 77–152 %
de CPU (el render por software, 199–293 %) sin fotogramas perdidos. Cumplen el arranque en frío (<1 s), abrir una imagen con el proceso en
marcha (16–83 ms), los saltos (p95 172–317 ms), la pausa sin repintados y los 100 ciclos de apertura. **No cumplen** abrir un video con el
proceso en marcha (0,28–0,92 s, mediana ≈400 ms: ventana y contexto GL nuevos) ni, siempre, la imagen precargada (24–130 ms). Una ejecución
aislada tardó 51 s en mostrar el primer fotograma y no se ha reproducido; no está descartado un bloqueo intermitente.

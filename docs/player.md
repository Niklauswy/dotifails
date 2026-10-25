# Wysun Player

Wysun Player es el visor de **imágenes, video y audio** de Wysun. Todo lo que abre un archivo multimedia para verlo o
escucharlo usa Wysun Player o su componente embebido, `wysun_media`; no hay visores paralelos.

| Contexto | Comportamiento |
|---|---|
| Files: doble clic, Enter, «Abrir» | Abre Wysun Player directamente, sin pasar por `xdg-open`. Varios medios seleccionados abren **una** ventana con la selección en orden. |
| Files: panel de detalles | Componente embebido, en pausa (el video muestra su primer fotograma; el audio, su carátula). El botón «Abrir en Wysun Player» continúa en la misma posición. |
| Recorder | La página de reproducción embebe el mismo componente, con las mismas funciones de transporte. |
| Capturas del shell | «Guardar y ver» (`V`) guarda el PNG y lo abre; solo lo abre cuando el archivo ya existe. |
| Otras aplicaciones y `xdg-open` | La instalación completa fija Wysun Player como aplicación predeterminada de sus imágenes, video y audio (§ Instalación). |
| Wysun Music | Sigue siendo la app de biblioteca. Un audio suelto abierto desde Files se reproduce en Wysun Player. |

## Uso

```
wysun player [--paused] [--fullscreen] [--start SEGUNDOS] [--] ARCHIVO...      # alias: wysun image
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
| | | `O` / `Ctrl+O` | abrir archivos (ventana del reproductor) |

Arrastrar archivos sobre la ventana los abre; un `.srt/.ass/.vtt` soltado sobre un video se carga como subtítulos. La barra de controles
flota sobre el contenido y se oculta tras 2,5 s sin actividad mientras un video suena; reaparece al mover el ratón. Las posiciones de
archivos de más de 5 minutos se recuerdan (`~/.local/state/wysun/player/positions.json`, claves por hash, sin rutas).

## Arquitectura

```text
apps/wysun/
  wysun_media/                  componente reutilizable (sin dependencias de Files, Music ni Recorder)
    host.py        Host: lo que el anfitrión presta (colores, tokens, tipografía, símbolos, movimiento reducido)
    source.py      validación y clasificación de archivos locales; errors.py: vocabulario de errores
    mpv.py         binding ctypes mínimo de libmpv (comandos asíncronos, propiedades observadas, render GL/SW)
    session.py     MediaSession: un archivo a la vez sobre un único núcleo mpv reutilizado
    video.py       GLVideoView (QOpenGLWidget + render API de OpenGL) y SoftwareVideoView (respaldo acotado)
    image.py       decodificación en segundo plano, caché acotada y ImageView (zoom, paneo, giro, animación)
    collection.py  carpeta o lista explícita, anterior/siguiente   resume.py: posiciones recordadas
    shape.py       escala de esquinas M3 como rutas y morph      controls.py, bar.py, menus.py: controles pintados
    audio.py, cover.py        escenario de audio (carátula en «cookie»)   player.py: MediaPlayer, el widget que lo une todo
    mpris.py, integration.py  MPRIS, pista de pantalla encendida y pausa de Music
  player_app.py / player_client.py / player_window.py     línea de órdenes, cliente sin Qt y ventanas del proceso
  media_host.py                 adaptador al tema de Wysun
apps/capture/wysun_media        enlace al mismo paquete (desarrollo); cada release de Recorder lleva su copia
apps/capture/loomrec/ui/media_host.py    adaptador al tema de Recorder
```

Uso desde cualquier anfitrión:

```python
import media_host; media_host.install()                      # o loomrec.ui.media_host en Recorder
from wysun_media.player import MediaPlayer
player = MediaPlayer(mode='embedded', backdrop='surface')   # 'full' para una ventana propia
player.enable_integration()                                  # MPRIS, pantalla encendida y pausa de Music
player.open(path, paused=True, browse='folder')             # imagen, audio o video
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
- **GPU:** OpenGL con `hwdec=auto-copy` (decodificación por hardware con copia de vuelta, **no** cero copias: PySide6 6.8 no expone el display
  de Wayland para la interop directa). Si OpenGL no está disponible o falla al iniciar, se usa el render por software. Si el contexto GL se
  recrea (p. ej. al cambiar la ventana de pantalla), se vuelve a crear el contexto de mpv y se reselecciona la pista de video.
- **Imágenes:** `QImageReader` en un pool propio de 2 hilos; JPEG y WebP se decodifican directamente al tamaño de la ventana; el resto en
  completo si cabe en 128 MiB (si no, se muestra un error claro, nunca una asignación sin límite). Caché de 128 MiB por proceso;
  precarga de la anterior y la siguiente; más detalle cuando el zoom se estabiliza.
- **Forma (Material 3):** la escala `corner_none … corner_full` vive en los tokens (cada estilo da sus valores). El botón de reproducir es la
  única pieza animada: círculo en pausa, cuadrado redondeado al reproducir. Las esquinas de lo que no se puede recortar (la superficie GL)
  se redondean con una capa que pinta los recortes en el color de fondo. Los controles flotantes usan los tokens `hud*`, definidos en
  todas las variantes para superficies sobre video.
- **Escritorio:** MPRIS por reproductor activado (ventana del reproductor; vista previa embebida desde que se pulsa reproducir; nunca imágenes
  ni vistas previas pasivas), con un nombre `org.mpris.MediaPlayer2.wysun_player.instance<pid>_<n>` y una conexión privada cada uno. La clave
  `wysun:visibleVideo` de los metadatos hace que el shell mantenga la pantalla encendida mientras un video visible se reproduce
  (`daemons/IdleInhibit.qml`), sin tocar el interruptor manual. Al empezar un sonido, Music se pausa por MPRIS si estaba sonando (una vez
  por inicio; no se reanuda solo; con tiempo de espera de 1 s y sin bloquear nunca).

## Dependencias y diagnóstico

Requiere `libmpv2` y FFmpeg (ya instalados con mpv). La ruta de GPU necesita `python3-pyside6.qtopengl` y
`python3-pyside6.qtopenglwidgets`, que la instalación completa añade; `--orbit-only` no instala dependencias y, si faltan, el reproductor
funciona con el render por software y `dotifails doctor` lo avisa. Variables (solo diagnóstico):

| Variable | Efecto |
|---|---|
| `WYSUN_PLAYER_RENDERER=software` | Fuerza el render por software. |
| `WYSUN_MPV_OPTIONS=ao=null,hwdec=no` | Opciones de mpv permitidas: `ao`, `hwdec`, `audio-device`, `volume`. |
| `WYSUN_LIBMPV=/ruta/libmpv.so.2` | Otra copia de libmpv. |

`wysun_media.capabilities()` devuelve la versión de libmpv y si OpenGL está disponible; el menú «Información» (`I`) muestra decodificador,
renderizador y fotogramas perdidos.

### Instalación y asociaciones

`./instalar.sh --orbit-only` actualiza el código, instala `wysun-player` y su entrada `.desktop`, y **no** toca asociaciones. La instalación
completa añade a `~/.config/mimeapps.list` Wysun Player como predeterminado de los tipos de su `.desktop` (imágenes, video y audio; no SVG);
lo que era predeterminado queda como alternativa en «Abrir con». El respaldo del instalador guarda el archivo anterior y
`dotifails restore ID` lo recupera, rescatando en `changes-before-restore/` lo que se haya editado después.

## Pruebas

```sh
python3 -m unittest discover -s tests -p 'test_media_*.py'      # sesión, imágenes, controles, widget, tema, integración (D-Bus privado)
python3 -m unittest discover -s tests -p 'test_player_*.py'     # proceso (instancia única con procesos reales), escritorio e instalador
python3 apps/capture/run_tests.py                               # incluye la página de reproducción de Recorder
python3 tests/wayland_media_case.py                             # física: OpenGL, ocultar/mostrar, pérdida de contexto, fugas
python3 tests/media_benchmark.py                                # CPU, memoria, primer fotograma y fotogramas perdidos
```

Los medios son sintéticos (`tests/media_fixtures.py`: H.264, VP9, HEVC, AV1, audio en seis formatos con y sin carátula, JPEG con las ocho
orientaciones EXIF, PNG con alfa, BMP, TIFF, WebP, GIF animado y archivos dañados). Las pruebas offscreen usan el render por software
(`QOpenGLWidget` no existe en esa plataforma): la ruta OpenGL se valida con `wayland_media_case.py` en la sesión real. Cada proceso de
pruebas usa un bus D-Bus propio y desechable. `WYSUN_PYSIDE_EXTRA=<carpeta>` permite probar los módulos OpenGL de PySide6 extraídos de sus
paquetes sin instalarlos.

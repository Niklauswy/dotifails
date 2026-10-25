# Wysun Player — plan de arquitectura e implementación

**Estado: implementado (2026-10-24).** Este documento conserva el plan y sus decisiones; el estado actual, los atajos y el diagnóstico están en `docs/player.md`. Las diferencias entre el plan y lo construido están en la sección 10.

Fecha: 2026-10-24. Sustituye la propuesta del 2026-10-22, que mezclaba el componente con toda la integración del ecosistema. Este plan reduce el alcance inicial y conserva sus decisiones técnicas válidas.

## 1. Objetivo y decisiones

**Wysun Player es el visor único de Wysun para imágenes, video y audio.** Todo lo que en Wysun abre un archivo multimedia para verlo o escucharlo usa Wysun Player o su componente embebido. No existen visores paralelos.

| Contexto | Comportamiento |
|---|---|
| Files: activar un archivo (doble clic, Enter, «Abrir») | Abre Wysun Player directamente, sin pasar por `xdg-open` |
| Files: panel de vista previa | Componente embebido, primer fotograma sin reproducción automática; «Expandir» abre Wysun Player en la misma posición |
| Escritorio (otras apps, `xdg-open`) | Wysun Player es la aplicación predeterminada para `image/*`, `video/*` y `audio/*` |
| Wysun Recorder | La página de reproducción embebe el mismo componente, con las mismas funciones de transporte |
| Capturas del shell | La acción «Ver» abre Wysun Player cuando la captura ya está guardada |
| Wysun Music | Sigue siendo la aplicación de biblioteca de música y conserva su motor. Abrir un audio suelto desde Files usa Wysun Player |

Principios:

- **Un componente, muchos anfitriones.** `wysun_media` es una biblioteca de widgets Qt sin dependencias de Files, Music ni Recorder. La app Wysun Player es una capa delgada encima.
- **Pequeño y bien hecho.** Pocas piezas con contratos claros. Nada de interfaces especulativas ni de caminos de código sin un consumidor real.
- **Rápido por diseño.** El hilo de UI nunca espera a un decodificador, a un proceso ni a disco. El render es por GPU, y una sola sesión se reutiliza entre archivos.
- **Material 3 Shape** como lenguaje de forma (§4), con todos los valores tomados de los tokens del tema.

## 2. Punto de partida (verificado en `4d4d6405`)

| Área | Estado actual | Consecuencia |
|---|---|---|
| Files | `wysun_files/player.py` + `mpv_embed.py`: render por software a `QImage`, sin decodificación por hardware, sondeo IPC cada 120 ms; `_probe_media()` llama a ffprobe en el hilo de UI | Se reemplaza por el componente |
| Files, apertura | `wysun_files/window.py:open_path` usa `QDesktopServices.openUrl` | Se enruta a Wysun Player para tipos multimedia |
| Recorder | `loomrec/ui/player.py`: superficie libmpv duplicada (Wayland) y proceso mpv hijo (X11) | Se reemplaza por el componente |
| Imágenes | Decodificación, EXIF, zoom y paneo existentes en Files (`file_media.py`, `files_zoom.py`) | Se extraen y se mejoran |
| Instancia única | Music usa `local_ipc.LocalSettingsServer` con un socket en `$XDG_RUNTIME_DIR` | Wysun Player reutiliza el mismo patrón |
| Runtime | Apps con PySide6 6.8 del sistema y shell con Qt 6.9.3 privado. Faltan `QtOpenGL` y `QtOpenGLWidgets` | Dependencia nueva en el instalador completo y respaldo por software sin ella |
| Host | mpv 0.40, libmpv API 2.5, FFmpeg 7.1. Sin HEIF/AVIF en Qt | La disponibilidad real de formatos se consulta, no se supone |

## 3. Tecnología

- **Video y audio: libmpv** mediante ctypes, con la render API de OpenGL en `QOpenGLWidget`. La reproducción, la sincronización, los subtítulos y las pistas son de mpv. No hay reproductor propio sobre libav*, ni GStreamer, ni Qt Multimedia en las apps; Qt Multimedia queda solo para los fondos del shell.
- **Decodificación por hardware: `hwdec=auto-copy`.** PySide6 6.8 no expone el display nativo de Wayland para la interop directa. Con copia de vuelta se obtiene decodificación por hardware y presentación por GPU sin acceso privado a Qt. No es cero copias y no se anuncia así. Si falla, mpv cae solo a decodificación por software, y eso no requiere código.
- **Respaldo sin OpenGL:** render por software de libmpv, que ya existe en `mpv_embed.py`, consolidado dentro del componente. Hay dos caminos, no tres.
- **Imágenes: `QImageReader`** en `QThreadPool`. Las animaciones GIF/WebP usan `QMovie`. No se añaden Pillow ni libvips.
- **Metadatos de medios:** los da mpv (`duration`, `track-list`, `chapter-list`, `video-params`). El reproductor no usa ffprobe; Files lo conserva para sus miniaturas.

## 4. Forma y estilo (Material 3 Shape)

La forma comunica jerarquía y estado, no decoración. Referencia: <https://m3.material.io/styles/shape/overview-principles>.

**Escala de forma en tokens.** Se añade a `shape` en `apps/wysun/wysun_theme.json` y en su copia `apps/capture/loomrec/ui/` (lo comprueba `tests/test_theme_tokens.py`):

| Token | Uso en el reproductor |
|---|---|
| `corner_none` | Superficie de video a pantalla completa |
| `corner_xs` | Marcadores de capítulo y miniatura al arrastrar |
| `corner_s` | Menús emergentes y tooltips |
| `corner_m` | Panel de información y lista de pistas |
| `corner_l` | Barra de controles flotante |
| `corner_xl` | Contenedor del reproductor embebido |
| `corner_full` | Botones de icono, pista del deslizador y píldoras de velocidad y volumen |

Cada estilo define sus valores. Al implementarlo, el tema pasó a un único estilo (Material You) que usa la escala de M3 (0/4/8/12/16/28/completo); si vuelve a haber varios, cada uno puede dar sus números. Los radios actuales (`radius_s`…`radius_l`) se mantienen como alias mientras el resto de la UI migra.

**`wysun_media/shape.py`:** genera un `QPainterPath` a partir de un token de esquina e interpola entre dos formas (morph) para los cambios de estado. Las apps no tienen Qt Quick, así que no pueden usar el M3Shapes del shell; el dibujo se hace con QPainter.

**Una pieza animada central.** El botón reproducir/pausar cambia de círculo (`corner_full`) a cuadrado redondeado (`corner_l`) al reproducir, con el movimiento de los tokens del tema. El resto de controles cambia solo de color o de opacidad. Con movimiento reducido el cambio es instantáneo.

**Reglas de tema:** todo color, radio, espacio, tipografía, icono y movimiento sale de los tokens. Excepción declarada (`theme-exception: contenido de video`): el fondo de las bandas laterales del video es negro. El fondo de transparencia de las imágenes usa tokens. Se prueba en Space Black (`space-black`, `tokyo`, `severance`) y Fluent (`light`, `dark`), con cambio de tema en vivo.

**Controles:** la barra se oculta tras 2 s sin actividad junto con el cursor, y reaparece al mover el ratón o pulsar una tecla. Muestra pocos controles; lo avanzado vive en un menú.

## 5. Funciones

### Video y audio

| Función | Detalle |
|---|---|
| Transporte | Reproducir/pausar, reiniciar al final (`keep-open`), barra de progreso con tiempo transcurrido y restante (clic alterna) |
| Avance | ←/→ ±5 s (Shift 1 s, Ctrl 60 s), `0`–`9` saltan al 0–90 %, rueda sobre la barra, clic para saltar. Al arrastrar se agrupan las peticiones (un salto por fotograma clave cada 33 ms) y se hace un salto exacto al soltar |
| Fotograma a fotograma | `.` / `,` en pausa, útil para revisar grabaciones de Recorder |
| Velocidad | 0.25×–4× en pasos (`[` / `]`, Retroceso restablece), con corrección de tono (`scaletempo2` de mpv). La velocidad actual aparece como píldora |
| Volumen | 0–150 %, silencio (`m`), ↑/↓ y rueda sobre el video |
| Capítulos | Marcadores en la barra, capítulo anterior y siguiente |
| Bucle | Archivo en bucle y bucle A-B (`l`) |
| Pistas | Selección de pista de audio; subtítulos incrustados y externos (SRT/ASS/VTT por menú o arrastrando el archivo); retardo de subtítulos |
| Presentación | Pantalla completa (`f`, doble clic), ajustar/llenar, rotación de los metadatos aplicada por mpv |
| Captura de fotograma | `s` guarda el fotograma actual en la carpeta de imágenes del usuario |
| Reanudar | Recuerda la posición de los archivos de más de 5 min. Se guarda en `~/.local/state/wysun/player/positions.json` con un límite de entradas y clave por ruta, tamaño y fecha |
| Audio suelto | Vista compacta con la carátula incrustada (o una nota) en una «cookie» que gira despacio mientras suena. No se crea superficie de video |
| Información | Códec, resolución, decodificador real (hardware o software), renderizador y fotogramas perdidos |
| Colección | Anterior/siguiente dentro de la carpeta (orden natural, sin recursión) o de la lista de archivos pasada en la línea de órdenes |

### Imágenes

| Función | Detalle |
|---|---|
| Vista | Ajustar, 100 % real (teniendo en cuenta el device pixel ratio), zoom con rueda anclado al cursor, gesto de pellizco, paneo, doble clic alterna ajustar/100 % |
| Navegación | ←/→ dentro de la carpeta, sin vuelta circular; los archivos borrados se saltan |
| Velocidad | Decodificación al tamaño del viewport y más detalle cuando el zoom se estabiliza. Precarga de la imagen anterior y la siguiente. Caché limitada (por omisión 128 MiB) |
| Animación | GIF/WebP con `QMovie`, en pausa si la ventana no se ve. Con movimiento reducido arranca detenida |
| Orientación | EXIF aplicado una sola vez; giro de 90° solo de presentación, sin modificar el original |
| Acciones | Copiar imagen, copiar ruta, mostrar en Files, abrir con otra app, mover a la papelera (`gio trash`, reversible) |
| Información | Nombre, dimensiones, formato, tamaño y fecha |
| Límites | Una imagen que excede el presupuesto de memoria muestra sus dimensiones y un error claro; nunca se reintenta sin límite |

### Fuera de esta versión

Streaming y URLs remotas, discos, DRM, casting, edición, descarga de subtítulos, listas persistentes, picture-in-picture, salida HDR (las fuentes HDR se presentan en SDR), HEIF/AVIF/RAW salvo que Qt los soporte, imágenes gigapíxel en mosaico, y reanudación automática de Music.

## 6. Arquitectura

### Componente `apps/wysun/wysun_media/`

```text
wysun_media/
  mpv.py         binding ctypes mínimo: cliente, render context GL/SW, opciones fijas
  session.py     MediaSession(QObject): estado, propiedades observadas, comandos
  video.py       VideoView(QOpenGLWidget) y respaldo por software
  image.py       ImageLoader (QThreadPool) e ImageView (zoom, paneo, animación)
  collection.py  lista de la carpeta en segundo plano, anterior/siguiente
  shape.py       escala de forma M3 y morph con QPainterPath
  controls.py    barra de transporte, deslizador con capítulos, menús de velocidad/volumen/pistas
  player.py      MediaPlayer(QWidget): combina todo; modos `embedded` y `full`
  resume.py      posiciones recordadas
```

El tamaño previsto es de unas 1.800 líneas. Si una pieza crece mucho más, primero se revisa el diseño.

Uso desde cualquier anfitrión:

```python
player = MediaPlayer(theme=host_theme, mode='embedded')
player.open(path, start=0.0, paused=True)   # imagen, audio o video
player.session.stateChanged.connect(on_state)
player.expandRequested.connect(lambda: launch_player(path, player.session.position))
```

**`MediaSession`**
- Estados: `idle`, `loading`, `playing`, `paused`, `ended`, `error`, más el indicador `seeking`. Derivan de propiedades de mpv (`idle-active`, `pause`, `eof-reached`, `seeking`) y no se mantienen a mano.
- Propiedades expuestas como señales Qt: posición, duración, velocidad, volumen, pistas, capítulos y decodificador.
- Cada `open()` incrementa una generación. Se descartan los eventos y resultados de generaciones anteriores. Los errores distinguen operación (carga, salto o pista) y causa.
- La API pública son métodos tipados. No se exponen comandos arbitrarios de mpv.
- Una sola sesión por reproductor, reutilizada entre archivos. La superficie de video no existe en modo audio.

**Hilos y render (libmpv)**
- libmpv es thread-safe. Los comandos se envían con `mpv_command_async` / `mpv_set_property_async` desde el hilo de UI y nunca bloquean. No hay hilo de control propio.
- El callback de wakeup de mpv solo despierta (señal en cola o `QSocketNotifier` sobre un pipe). Los eventos se drenan en el hilo de UI y sus datos se copian antes de que expire su memoria nativa.
- El callback de actualización del render llama a `update()` mediante señal en cola. El render va a `defaultFramebufferObject()` en píxeles físicos.
- Orden: crear el handle, crear el render context con el contexto GL activo, cargar. Al cerrar se libera el render context antes del handle. Los callbacks y sus buffers se retienen hasta terminar. El cierre es asíncrono y nunca hace `join` desde la UI.
- Se pausa el repintado cuando la vista se oculta. El reproductor completo sigue sonando minimizado.
- `LC_NUMERIC=C` antes de inicializar mpv. Se conserva la protección de fotogramas opacos que ya cubren los tests de Recorder.

**Opciones fijas de mpv (seguridad y previsibilidad):** sin configuración de usuario (`config=no`), sin scripts, sin ytdl, sin atajos ni OSC propios, sin carga automática de subtítulos ni audio externo, sin listas de reproducción inseguras, y protocolos de FFmpeg limitados a archivos locales. Solo se aceptan rutas locales y URLs `file:`. Se rechazan dispositivos, FIFOs, sockets y manifiestos. Las rutas se pasan como argumentos, nunca interpoladas. Los códecs corren en el proceso: esto reduce la superficie expuesta, pero no es un sandbox.

**`ImageView`**
- `QImageReader` en workers con `setScaledSize` al viewport, `setAutoTransform` y límite de asignación. Devuelve `QImage`; el `QPixmap` se crea solo en el hilo de UI.
- Las peticiones canceladas pueden terminar, pero no publican si su generación es antigua.
- Se reutiliza el zoom anclado al cursor de `files_zoom.py`. Las dimensiones originales y las del preview decodificado se guardan por separado.

### Aplicación Wysun Player

- **Entrada:** `wysun player [--paused] [--fullscreen] [--start SEG] -- ARCHIVO...` y `wysun-player.desktop`. El alias `wysun image` abre lo mismo.
- **Instancia única por usuario mientras haya ventanas abiertas.** Socket en `$XDG_RUNTIME_DIR/wysun-player-{uid}.sock` con `local_ipc.LocalSettingsServer`, como Music. Una segunda llamada envía una línea JSON con los archivos y opciones (JSON para admitir rutas con saltos de línea), y la instancia existente abre una ventana nueva y la enfoca. Así se evitan el arranque de Python y PySide en cada apertura, y cada ventana tiene su propia sesión.
- Al cerrar la última ventana el proceso termina; no queda nada residente. Si la medición del arranque en frío supera el objetivo, se evaluará mantener el proceso vivo sin ventanas.
- El proceso es independiente de Files y del shell: un fallo del decodificador no los cierra.
- Usa el runtime de tema existente (`theme_tokens.watch_theme`) y aplica en vivo los cambios de estilo y variante.

### Integración

**Files**
- `open_path` envía imágenes, video y audio a `wysun player -- RUTA` antes de `QDesktopServices`, sin depender de que Wysun Player sea el predeterminado del sistema, lo que evita recursión.
- El panel de vista previa usa `MediaPlayer(mode='embedded')` en pausa (mpv muestra el primer fotograma). Al cambiar la selección carga en la misma sesión. «Expandir» abre Wysun Player con `--start` en la posición actual y pausa la vista previa.
- `_probe_media()` desaparece: los metadatos llegan de la sesión.
- «Abrir con…» elige una aplicación del escritorio excluyendo Wysun Player.

**Recorder**
- `PlayerPage` embebe `MediaPlayer(mode='embedded')` con el adaptador de tema de Recorder. Tiene las mismas funciones (velocidad, fotograma a fotograma, avance) y una acción «Abrir en Wysun Player».
- Las releases de Recorder son inmutables, así que `installer/capture_distribution.py` copia `wysun_media` dentro de cada release y lo incluye en el hash. Recorder nunca importa de `~/.local/share/orbit/app/`.
- Se mantiene el contrato de grabación: solo se reproduce una salida finalizada (`ready` y el archivo existe), no se generan exportaciones extra, y cerrar el reproductor no detiene la captura ni la finalización.
- `wysun recorder --show RUTA` sigue aceptando videos como hoy.

**Escritorio y aplicación predeterminada**
- El instalador completo registra `wysun-player.desktop` y lo fija como predeterminado para `image/*`, `video/*` y `audio/*` en `~/.config/mimeapps.list`. Antes guarda los valores previos en el journal, y el rollback los restaura sin pisar cambios posteriores del usuario.
- `--orbit-only` no modifica `mimeapps.list` ni instala dependencias. Igual que los atajos, la migración en el escritorio activo se hace con respaldo y comprobando conflictos.

**Shell, Music y sistema (fase 4)**
- **MPRIS** para Wysun Player y para la reproducción activada explícitamente en Files o Recorder; las vistas previas pasivas no se registran. Así funcionan las teclas multimedia y los controles del shell.
- **Inhibición de reposo** mientras haya video visible reproduciéndose. Se publica como metadato MPRIS que el shell lee, sin tocar su interruptor manual. El mecanismo concreto se verifica en la fase 4.
- **Music:** al empezar un video con sonido, Wysun Player llama a `Pause` por MPRIS sobre Music si está reproduciendo. No hay reanudación automática en esta versión.
- **Capturas:** la acción «Ver» del shell espera a que el PNG esté publicado. Hoy `Session.qml.keep()` devuelve el destino antes de terminar de guardar, así que se le añade un resultado de completado o error, y solo después se lanza `wysun player -- RUTA`.

## 7. Fases

Cada fase requiere instrucción expresa para comenzar. Cada una termina con sus pruebas y con verificación real en el escritorio.

| Fase (todas implementadas) | Trabajo | Criterio de aceptación |
|---|---|---|
| **0. Línea base** | Fixtures sintéticos (MP4/MKV/WebM/MOV con H.264/VP9/HEVC/AV1, audios comunes, JPEG/PNG/WebP/GIF/TIFF con EXIF y alfa) y un script de medición: CPU, RSS, fotogramas perdidos, tiempo hasta el primer fotograma. Se reemplaza `tests/wayland_preview_case.py`, que está obsoleto | Medición reproducible del reproductor actual de Files y de Recorder |
| **1. Componente** | `wysun_media` completo, tokens de forma en ambos JSON y dependencias OpenGL declaradas | Video, audio e imagen en una ventana de prueba. Sin rutas de fotogramas GL por `QImage`. Respaldo por software sin OpenGL. Mejora medible frente a la fase 0; si no la hay, se revisa el plan antes de seguir |
| **2. Wysun Player y Files** | App, instancia única, `bin/wysun` y desktop file. Vista previa y apertura de Files. Predeterminado MIME en el instalador completo | Abrir desde Files, desde `xdg-open` y con una segunda llamada concurrente. La vista previa no reproduce sola. Las rutas no multimedia de Files siguen igual |
| **3. Recorder** | `PlayerPage` sobre el componente y empaquetado en releases | Recorder funciona desde su release. Las grabaciones activas no se ven afectadas. Releases anteriores siguen funcionando tras actualizar |
| **4. Sistema** | MPRIS, inhibición de reposo, pausa de Music, «Ver» en capturas | Teclas multimedia, inhibición y pausa de Music en el escritorio real. Un guardado fallido nunca abre un archivo inexistente |
| **5. Limpieza** | Eliminar `mpv_embed.py`, `wysun_files/player.py` y `loomrec/ui/player.py` cuando nada los use. Actualizar `ARCHITECTURE.md`, `docs/themes.md` y créditos | Todas las suites requeridas pasan y la revisión visual en las cinco variantes está hecha |

Los puntos de entrada antiguos se mantienen como envoltorios hasta que su sustituto pase las pruebas instaladas.

## 8. Rendimiento, objetivos y pruebas

Objetivos medidos contra la fase 0:

| Escenario | Objetivo |
|---|---|
| Abrir archivo con la instancia en marcha | Primer fotograma o imagen visible: p95 < 300 ms |
| Arranque en frío de Wysun Player | Primer fotograma o imagen visible: p95 < 1 s |
| Salto en archivo local indexado | p95 < 300 ms |
| Siguiente/anterior imagen precargada | Visible en < 50 ms |
| 1080p60 H.264 en el Intel de referencia | < 1 % de fotogramas perdidos y menos CPU que la superficie actual |
| En pausa u oculto | Sin bucle de repintado; CPU casi en reposo |
| Hilo de UI | Ningún bloqueo de medios > 50 ms |
| Abrir y cerrar 100 veces | Sin procesos, hilos ni descriptores que crezcan |

Cada medición registra códec, resolución, decodificador, renderizador, versiones y hardware. No se exige AV1 por hardware donde no exista, ni se afirma compatibilidad general de GPU a partir de una sola máquina.

**Pruebas principales**
- **Sesión:** rutas inválidas, Unicode, nombres que empiezan por guion, archivos borrados o sustituidos; cambios rápidos A→B→C; ráfagas de saltos; cierre durante la carga; EOF frente a error; duración desconocida; falta de libmpv o de OpenGL.
- **Imagen:** las ocho orientaciones EXIF, alfa, ICC, 100 % en HiDPI, JPEG grande con decodificación escalada frente a PNG completo, cabeceras corruptas, dimensiones excesivas, navegación mientras cambia la carpeta.
- **App:** instancia única con llamadas concurrentes, socket huérfano, rutas con saltos de línea, posiciones recordadas.
- **Tema:** cada variante que defina el tema (las pruebas las recorren, sin nombrarlas), cambio en vivo, movimiento reducido, `tests/test_theme_literals.py` sin literales nuevos.
- **Integración:** apertura desde Files sin recursión, releases de Recorder, MIME con journal y rollback, MPRIS y Music (fase 4).

Se ejecutan las comprobaciones de `AGENTS.md` (unidad, `wysun_app`, `shell_bridge`, `utility_ui`, manifiesto, `apps/capture/run_tests.py` y `wysun_installed_smoke.py`). Las pruebas de medios y compositor se ejecutan en serie con HOME/XDG temporales. El éxito en offscreen no sustituye la verificación en Wayland real.

## 9. Riesgos aceptados

- **Copia de vuelta en la decodificación por hardware:** hay coste de transferencia. La interop directa se revisará si las mediciones lo justifican y PySide expone el display de Wayland.
- **Códecs en proceso:** un fallo nativo cierra la ventana del anfitrión (Files o Recorder en modo embebido, o Wysun Player), pero no el shell.
- **Cancelación de imágenes cooperativa:** los límites de memoria y de cola acotan el coste, pero no aíslan el decodificador.
- **Copias de `wysun_media` en Recorder:** hay duplicación instalada a cambio de releases reproducibles.
- **QML:** el shell no embebe el componente. Lanza Wysun Player o lo controla por MPRIS. Un renderizador QML solo se construiría ante un requisito real y para el runtime Qt 6.9.3 del shell.

## 10. Resultado de la implementación

Medido el 2026-10-24 en la máquina de referencia (Intel i7-8565U, Parrot 7, Hyprland sobre Wayland nativo, PySide6 6.8.2, libmpv API 2.5,
mpv 0.40, FFmpeg 7.1) con medios sintéticos. La superficie OpenGL se probó con los módulos de PySide6 extraídos de los paquetes
`python3-pyside6.qtopengl` y `qtopenglwidgets` **sin instalarlos**; en el sistema siguen sin instalarse hasta que la instalación completa (o el
usuario con `apt`) los añada, y mientras tanto el reproductor usa el render por software.

| Escenario (1080p60 H.264 en ventana de 960×540, 3–4 s, `ao=null`) | CPU | Primer fotograma | Memoria | Perdidos |
|---|---|---|---|---|
| Superficie anterior (software, `mpv_embed.py`, ya eliminada) | 216–240 % | 98 ms | 185 MiB | 0 |
| Nueva, OpenGL + `vaapi-copy` | 77–152 % | 18–77 ms | 256–260 MiB | 0 |
| Nueva, software | 199–293 % | 45–123 ms | 245–269 MiB | 0 |

La variación entre tandas refleja la carga del equipo (se midió con el escritorio en uso). OpenGL ahorra entre un tercio y dos tercios de CPU y
no pierde fotogramas, a costa de unos 70 MiB más de memoria (contexto GL y controladores). El render por software no mejora al anterior: es solo
el respaldo.

| Objetivo | Medido (`tests/media_latency.py`, 9 ejecuciones) | |
|---|---|---|
| Arranque en frío hasta la primera imagen | ≈0,25–0,45 s de importaciones y aplicación + 31–56 ms | cumple (<1 s) |
| Abrir una imagen con el proceso en marcha | 16–83 ms | cumple (<300 ms) |
| Abrir un video con el proceso en marcha (ventana y contexto GL nuevos) | 0,28–0,92 s (25 aperturas seguidas: 164–531 ms, mediana ≈400 ms) | **no cumple** el objetivo de 300 ms; sí el de 1 s |
| Salto en un archivo indexado (1080p60, GOP de 1 s) | mediana 91–179 ms; p95 172–317 ms | cumple en 8 de 9 (una tanda 317 ms) |
| Siguiente imagen precargada | 24–130 ms (mediana ≈95) | **no cumple** siempre el objetivo de 50 ms: un JPEG de 1600×1200 tarda en pintarse en la ventana de prueba |
| En pausa u oculto | 0 repintados (`wayland_media_case.py`) | cumple |
| Abrir y cerrar 8 veces | sin descriptores, hilos ni procesos que crezcan | cumple |

Una ejecución de 11 registró 51 s hasta el primer fotograma de un video: no se reprodujo en 8 ejecuciones posteriores ni en 25 aperturas
seguidas con un vigilante de hilo, y coincidió con el escritorio en uso (se descarta un bloqueo del reproductor, pero no se demostró la causa).

### Diferencias entre el plan y lo construido

- ↑/↓ cambian el volumen (como en VLC y mpv) y Ctrl+←/→ salta 60 s; el plan asignaba ↑/↓ a ±60 s.
- Audio suelto: carátula incrustada o una nota en una «cookie» animada; no se implementó forma de onda.
- El cierre del núcleo de mpv se hace en un hilo propio (`mpv_terminate_destroy` bloquea hasta que terminan los hilos de audio y video).
- La reselección de la pista de video (`vid no` → `vid auto`) tras recrear el contexto GL es necesaria: mpv descarta la pista de video al liberar su
  contexto de render, y `video-reload` no la recupera.
- `exit_on_disconnect` de libdbus está desactivado en todas las conexiones del reproductor: por omisión cierra el proceso si el bus cae.
- Los medios de Files se abren con `player_client.launch` (no con `xdg-open`), así que Files no depende de que Wysun Player sea el
  predeterminado del sistema; la asociación predeterminada solo la hace la instalación completa.
- No se tocó `file_media.preview_file`/`probe_media`: las usa la vista previa del lanzador del shell y siguen necesitando ffprobe.
- Las ediciones QML del shell (`Session.qml`, `ActionBar.qml`, `Picker.qml`, `IdleInhibit.qml`) se cubren con comprobaciones estáticas de su
  contrato (`tests/test_screenshot_view.py`), porque las pruebas unitarias no cargan Quickshell. En la sesión real se comprobó que cargan sin
  errores (se abrió el selector de capturas) y que, con un video visible reproduciéndose, `idleInhibitor isInhibiting` pasa a `true` y vuelve a
  `false` al pausar. El flujo completo «Guardar y ver» (seleccionar una región con el ratón) no se automatizó.
- En la sesión real: `wysun player` abre una ventana nativa de Wayland (no XWayland), publica MPRIS (`playerctl` pausa, reanuda y salta), una
  segunda llamada entrega su archivo en 0,17 s al proceso existente (una ventana más, un solo proceso) y cerrar las ventanas termina el proceso,
  borra el socket y libera los nombres MPRIS.

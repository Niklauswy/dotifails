# Wysun Player en QML (fase 4 de la migración)

Fecha: 2026-11-02. Estado: decidido por el coordinador por delegación de Nicolas («seguirías con el plan grande de
migrar las apps de widgets a qml»), sobre el diseño general `2026-10-26-wysun-qml-music-files-design.md`.

## Intención

Wysun Player es el visor de cada imagen, video y audio que se abre desde Files, la terminal o el portal. Es la última
app de uso diario que sigue en Qt Widgets: pinta a mano sus controles (`wysun_media/controls.py`, `bar.py`, `menus.py`,
`image.py`, `audio.py`) con un sistema de diseño paralelo al de WysunM3. Pasa a QML sobre la base compartida, con las
mismas funciones y atajos, y deja `wysun_media` como un motor sin interfaz.

## Metas

1. **Mismas funciones y atajos** que hoy (lista completa abajo); nada se recorta.
2. **El diseño actual, en WysunM3**: capsula flotante en material HUD con barra de progreso (capítulos, rango A‑B,
   burbuja de tiempo), botón de reproducir que se transforma de círculo a cuadrado redondeado, píldora de velocidad,
   menús, avisos breves, carátula en galleta que gira despacio para audio. No es un rediseño (**decisión del
   coordinador**: ese diseño ya es M3 Expressive y Nicolas lo aprobó al hacerlo); cambia el material: componentes de
   `apps/qml/WysunM3` (`IconButton`, `Slider`, `Menu`, `CookieShape`, `Tooltip`, `Dialog`…) y tokens del tema.
3. **Un proceso, varias ventanas** como hoy: `wysun player ARCHIVO…` entrega los archivos a la instancia que corre o la
   inicia; el proceso termina con su última ventana. El cliente sigue siendo solo biblioteca estándar.
4. **Video con libmpv dentro de la escena QML**, con superposición de controles QML, y respaldo por software cuando no
   hay OpenGL.
5. **`wysun_media` sin Widgets**: lo que no es interfaz (`mpv`, `session`, `source`, `collection`, `resume`, `mpris`,
   `integration`, `cover`, `errors`) se conserva; lo pintado a mano se retira.

## No-metas

- Cambiar el motor (libmpv por ctypes, `MediaSession`), el formato del socket de instancia, la memoria de posiciones,
  MPRIS ni la pausa de Music al reproducir.
- Migrar el Recorder o el instalador (fase siguiente / se queda en Widgets).
- Funciones nuevas. Las que surjan en la ronda de pulido van aparte.

## Anti-metas

- Perder una función, un atajo o el comportamiento de una ventana (ajustarse al tamaño del primer video, pantalla
  completa, arrastrar y soltar, `--paused/--fullscreen/--start`).
- Peor fluidez de video: el video debe ir a su velocidad en 1080p60 sin fotogramas perdidos en reposo de la UI.
- Que el video se congele o el proceso se bloquee al redimensionar, capturar o cerrar ventanas.
- Colores, radios, medidas o duraciones literales (excepción declarada: el lienzo negro del video).
- Romper a quien abre el Player: Files (`wysun_player.client.launch`), `bin/wysun`, el `.desktop` (`StartupWMClass`),
  el portal y MPRIS (`playerctl`, widget del shell).

## Inventario de funciones (todas se conservan)

**Tipos:** video, audio, imagen (estática y animada: GIF/WebP/APNG). Colección: una lista explícita o la carpeta del
archivo (imágenes entre imágenes; video con audio), orden natural, sin vuelta al final, archivos borrados se saltan,
prelectura de la imagen vecina.

**Controles video/audio:** reproducir/pausa, ±10 s, anterior/siguiente (si hay colección), silencio + volumen 0–150 %
(rueda sobre el video: ±5), velocidad (0,25×–4×; menú), subtítulos (pistas, desactivar, cargar archivo, desfase
±0,1 s), pista de audio (si hay más de una), más (información, bucle de archivo, bucle A‑B, fotograma ±1 en pausa,
guardar fotograma), pantalla completa (no en audio), copiar ruta, mostrar en Files, mover a la papelera. Barra
compacta bajo 26 unidades: volumen, velocidad, pistas y ±10 s pasan a «más».

**Controles imagen:** alejar, zoom % (clic: ajustar ↔ tamaño real), acercar, girar; reproducir/pausar animación;
información (formato, dimensiones, detalle cargado), girar izq./der., copiar imagen.

**Atajos:** Espacio/K, ←/→ (5 s; Mayús 1 s; Ctrl 60 s), ↑/↓ volumen, Inicio/Fin, 0–9 (décimas), `.`/`,` fotograma
en pausa, `]`/`[` velocidad, Retroceso velocidad 1×, M, L (A‑B), Mayús+L (bucle), C, A, S, F/F11, Esc, I, Ctrl+C
(imagen o ruta), Supr (papelera), Re Pág/N y Av Pág/P (siguiente/anterior; ←/→ en imágenes), O/Ctrl+O (abrir),
Ctrl+Q/Ctrl+W (cerrar). Imagen: +/=/↑, −/↓, 0 ajustar, 1 tamaño real, R/Mayús+R girar. Doble clic en video:
pantalla completa; clic: pausa.

**Ventana:** título «nombre · Wysun Player»; la primera vez se ajusta al tamaño del video (80 % de la pantalla como
máximo, nunca en mosaico ni pantalla completa); los controles y el cursor se ocultan tras inactividad mientras se
reproduce video; arrastrar archivos los abre y arrastrar subtítulos los añade; posiciones recordadas en archivos
largos; aviso «no se pudo abrir» a pantalla completa para archivos rotos.

## Arquitectura

```
wysun_player/app.py      CLI + instancia (sin Qt). Si debe servir, se re-ejecuta en el venv QML (bootstrap).
wysun_player/client.py   sin cambios salvo el intérprete del hijo: el sistema; el propio app se re-ejecuta.
wysun_player/quick/      (nuevo) proceso QML:
  process.py             QGuiApplication, RequestServer (de window.py), ventanas, salida al cerrar la última.
  controller.py          PlayerController(QObject) por ventana: el «MediaPlayer» sin widgets. Propiedades para QML,
                         slots para cada acción; posee MediaSession, Collection, Positions, Integration, CoverJob.
  video.py               MpvVideoItem(QQuickFramebufferObject) y MpvSoftwareItem(QQuickPaintedItem).
  images.py              ImageProvider de carátulas (image://cover/<generación>).
apps/qml/player/         Main.qml (ventana), Stage*.qml (video, imagen, audio), ControlBar.qml, SeekBar.qml,
                         PlayMorph.qml, menús, Toast, NoteView, InfoDialog.
```

**Render (decisión del coordinador, verificada con un prototipo):** `QQuickFramebufferObject` con el render API de
libmpv dibuja a 29–30 fps reales en un clip de 30 fps con controles QML encima, orientación correcta sin espejo. El
Player fuerza `QSG_RENDER_LOOP=basic`: con el bucle con hilo, el render de Python en el hilo de render y el GIL
bloquean el proceso cuando el hilo GUI espera al de render (`grabWindow`, y potencialmente redimensionar). Con el bucle
básico, render y GUI van en el mismo hilo y las llamadas a libmpv (ctypes) sueltan el GIL. mpv avisa por el pipe de la
sesión (`render_hook`) y el ítem llama a `update()`; nunca se toca Qt desde hilos de mpv. Sin OpenGL (`QSG_RHI_BACKEND`
distinto o `WYSUN_PLAYER_RENDERER=software`) se usa el render por software de `video.py` actual en un hilo, pintado
por un `QQuickPaintedItem`.

**Imágenes:** `Image` de QML (`asynchronous`, `autoTransform`, `sourceSize` acotado al tamaño de la vista y subido al
hacer zoom, `cache: false` para no duplicar con la prelectura) y `AnimatedImage` para animaciones. Zoom anclado al
cursor con la rueda, pellizco (`PinchHandler`), arrastre para desplazar, giro en pasos de 90°. Sustituye a
`wysun_media/image.py` (`ImageView`, `Jobs`, `Cache`).

**Tema:** `ThemeBridge` y `Theme` de WysunM3 como Music/Files. La barra es una barra de herramientas flotante M3
(`surfaceContainer`, nivel 2) en el modo del tema (**decisión del coordinador**, revisada al implementar: un HUD siempre
oscuro no es posible con los controles de WysunM3, cuyos colores siguen el modo; con la barra M3 todos los controles
tienen el contraste correcto en claro y oscuro). El video va sobre `scrim`; todo cambia en vivo.

## Lo que se retira

`wysun_player/window.py` y `wysun_player/host.py`. El reproductor de Widgets de `wysun_media` (`player.py`,
`controls.py`, `bar.py`, `menus.py`, `audio.py`, `image.py`, `video.py`, `shape.py`, `symbols.py`, `host.py`) **se
queda** hasta la migración del Recorder: su página de reproducción lo embebe y cada release lo lleva consigo (hallado al
implementar). El render por software pasa a `wysun_media/software.py`, sin toolkit, y lo comparten ambos.

## Riesgos

- **GIL y render**: mitigado con el bucle básico; probar redimensionar, capturar y cerrar con video en marcha.
- **Pérdida del contexto GL** (cambio de pantalla): liberar el contexto de mpv al destruirse el renderer y
  `set_surface_ready(False)`; al recrearse, `True` (la sesión re-selecciona la pista de video).
- **HiDPI**: el FBO debe medir el tamaño del ítem × `devicePixelRatio`.
- **Imágenes enormes**: `sourceSize` acotado; probar una de 12000 px y un GIF largo.

## Verificación

Pruebas `tests/qml/check_player_*.py` (controlador, atajos, cliente/instancia, render offscreen por software),
pruebas del motor existentes, y prueba en vivo: video 1080p60, audio con carátula, carpeta de fotos, GIF, subtítulos,
claro/oscuro, ventana en mosaico y flotante, pantalla completa, abrir desde Files.

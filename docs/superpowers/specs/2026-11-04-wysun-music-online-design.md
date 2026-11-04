# Wysun Music: escuchar sin descargar, descargas sin fricción y ventana normal

Fecha: 2026-11-04. Estado: borrador para aprobación.

## Por qué

- La ventana de Music se abre flotante (regla `wysun-panels` en `config/.config/wysun/hyprland.lua`); el usuario la
  quiere en mosaico, como cualquier ventana.
- «Añadir música» se ve fea y expone la mecánica interna: estados «Revisar versión», «Esperando turno», «requieren
  atención», y una playlist de Spotify se encola completa sin poder elegir canciones.
- El usuario no quiere llenarse de descargas: quiere escuchar en el momento lo que no tiene, descubrir música nueva
  (novedades, tops, recomendaciones «tipo Spotify») y descargar solo lo que de verdad le gusta.

## Principio: no hay «modo online»

No existe pestaña, interruptor ni distinción explícita. La app es la misma; **con internet, aparece más**:

- Sin conexión: la app se comporta exactamente como hoy, solo con lo descargado. Ningún error ni aviso insistente.
- Con conexión: Inicio y Buscar se amplían con contenido en streaming, y las playlists de Spotify se pueden escuchar
  sin descargarlas.

Antiobjetivo: que el usuario tenga que pensar en «modos», o que la falta de red rompa o ensucie la experiencia local.

## Objetivos

1. **Ventana normal.** `wysun-music` deja de flotar (sale de la regla `wysun-panels`; Recorder sigue flotante).
   Comprobar que `requestHide`/el widget de la barra y `wysun music-mini` siguen funcionando con la ventana en mosaico.
2. **Streaming.** Cualquier canción que no está en el disco se puede reproducir: se resuelve en YouTube (misma
   puntuación `candidate_score`/`find_video` que la descarga) y mpv reproduce el audio por red. Nunca se escribe audio
   en disco.
3. **Local primero.** Si una canción está descargada (por id de Spotify, por `equivalent_track`, o por id de YouTube),
   siempre suena el archivo local.
4. **Buscar unificado.** En la búsqueda: primero resultados de la biblioteca (como hoy), debajo «En YouTube» con
   resultados en streaming (búsqueda `ytsearch` de yt-dlp, con debounce; no en cada tecla). Sin red, solo la biblioteca.
5. **Inicio ampliado.** Con red, nuevas estanterías debajo de las actuales:
   - «Para ti» (ver Recomendaciones).
   - «Novedades», «Top México», «Top Global», «Virales» y unas pocas editoriales por género: playlists públicas de
     Spotify leídas por su embed (`spotify.import_link` ya lo hace). La lista de playlists es una constante en código.
   Al abrirlas se ve la misma vista de colección (`CollectionPage`) con portada y canciones, reproducible sin descargar.
6. **Enlaces de Spotify/YouTube.** Pegar un enlace (en Buscar o en «Añadir música») abre la lista para escucharla;
   descargarla es una acción aparte.
7. **Me gusta / añadir a playlist ⇒ descarga.** Dar «me gusta» a una canción en streaming o añadirla a una playlist
   propia la marca y la encola para descargar. Mientras baja se sigue escuchando por streaming.
8. **Marca discreta.** Las canciones que no están en disco llevan un pequeño icono de nube (token de icono del tema).
   Es la única señal de «online».
9. **Cola mixta.** La cola admite canciones locales y en streaming. Si se pierde la red, las de streaming que no se
   puedan resolver se saltan sin diálogo y siguen las locales. La siguiente canción en streaming se resuelve por
   adelantado mientras suena la actual para no tener silencio entre canciones.
10. **Rediseño de «Añadir música».**
    - Pegar un enlace de playlist/álbum muestra la lista completa con portada y casillas, todas marcadas; atajos
      «Solo las que no tengo» y «Ninguna»; botón «Descargar N». Las que ya están en la biblioteca aparecen marcadas
      como tales y no se vuelven a descargar.
    - Desaparece «Revisar versión» como estado visible: si la duración no coincide con la versión de álbum, se acepta
      el mejor resultado sin preguntar. Si no se encuentra nada, la canción queda como «No encontrada», con la acción
      «Elegir otra versión» (lista de resultados de YouTube para escoger).
    - El progreso se muestra por lote (playlist/álbum o «Canciones sueltas»): «Lo-fi 2024 · 12 de 30», barra de
      progreso, pausar y cancelar. Los fallos se pliegan en «3 no se pudieron descargar · Reintentar».
    - Importar archivos/carpeta y «Abrir carpeta» se mantienen como acciones secundarias, discretas.
    - Diseño con los tokens del tema y componentes de `WysunM3` (sin literales), probado en claro y oscuro.

## Recomendaciones («Para ti»)

Todo se calcula en el equipo, sin cuentas:

- **Tops cruzados:** se juntan las canciones de las playlists públicas (tops y novedades). Una canción sube si aparece en
  varias listas, si su artista está en la biblioteca o en el historial de Wysun (`history`, `most_played`), y baja si ya
  está descargada o se escuchó hace poco.
- **Mixes:** a partir de las canciones/artistas más escuchados en Wysun, se piden los mixes de YouTube de esas
  canciones (`https://www.youtube.com/watch?v=<id>&list=RD<id>`, `--flat-playlist`) y se mezclan.
- Resultado: una estantería «Para ti» de unas 20–30 canciones y, si hay material, uno o dos mixes «Mix de <artista>».
- Se recalcula como mucho una vez al día o a petición (refrescar), cacheado en el directorio de datos privado.

## Datos y privacidad

- Solo se piden páginas públicas: embed de Spotify y YouTube vía yt-dlp. Sin login, tokens, credenciales ni cookies.
- Se guardan solo datos ligeros fuera del repositorio, en `~/.local/share/wysun/...` de Music (junto a
  `player.sqlite3`): las playlists públicas leídas (con fecha, refresco ~diario), las resoluciones canción→vídeo de
  YouTube (para no buscar dos veces) y el historial de reproducción, que ya existe. Las URLs de audio de YouTube
  caducan: se resuelven justo antes de reproducir y no se guardan.
- Las portadas siguen el caché de portadas actual.

## Restricciones

- Respetar AGENTS.md: paquetes en `apps/python`, tokens del tema, pruebas con HOME temporal, nada de editar la copia
  instalada, desplegar con `wysun update`.
- No hay dependencias nuevas del sistema: yt-dlp (el privado de `data.ytdlp()`) y mpv ya están. mpv corre con
  `--no-config`; la app resuelve la URL de audio con su propio yt-dlp (`-f bestaudio -g`) y le pasa a mpv la URL
  directa, en vez de depender del hook ytdl de mpv.
- Detección de red: no hace falta un sondeo dedicado; basta con que las peticiones fallen rápido y la UI oculte lo que
  no llegó. Se puede usar `QNetworkInformation` si está disponible.
- MPRIS, letra, «Ahora suena» y el widget de la barra funcionan igual con canciones en streaming (título, artista,
  portada, duración).
- La reproducción y la cola deben dejar de suponer que toda clave es una pista de `library.json`: hoy
  `Player._load` exige `track['path']`. Las canciones en streaming necesitan un catálogo propio en memoria/caché
  (id → título, artista, duración, portada, url de YouTube si ya se resolvió).

## Decisiones tomadas tras la revisión (llamadas del diseñador, no del usuario)

- **Claves de canciones en streaming.** El id de Spotify cuando existe (igual que las pistas importadas hoy); si no,
  `yt-<id de vídeo>`. Favoritos, playlists propias e historial en `player.sqlite3` aceptan claves sin archivo en disco.
  Al terminar la descarga, la pista entra en `library.json` con la misma clave, así que no hay migración ni fusión.
- **Me gusta que no se puede descargar.** El «me gusta» o la entrada de playlist se conserva y la canción sigue sonando
  por streaming, con su nube. El fallo aparece en el resumen plegado de «Añadir música» con «Reintentar».
- **Historial.** Las reproducciones en streaming cuentan en `history` y alimentan «Para ti» y «Lo más escuchado».
- **Barra y mini reproductor.** El widget de media del shell lee MPRIS (`apps/shell/services/Players.qml`), y
  `music-mini` solo abre ese widget. Basta con que `mpris.py` publique título, artista, duración y portada (`artUrl`
  hacia un archivo de caché o una URL https) de las canciones en streaming. No cambia nada en `apps/shell`.
- **Si Spotify cambia el embed.** Las estanterías que dependen de él se ocultan en silencio y se registra el error en el
  log de la app. No hay fuente alternativa en esta versión. Buscar, los mixes de YouTube y la biblioteca siguen
  funcionando.
- **Pausar descargas.** La canción en curso termina y no empieza ninguna más. La cola ya vive en `library.json`, así que
  sobrevive a reinicios. «Cancelar» quita del lote las canciones que no han empezado y detiene la actual.

## Lo que decide quien construye

- Estructura exacta de módulos (p. ej. un `online.py`/`catalog.py` y un resolvedor en hilo), nombres y modelo de datos
  del catálogo en streaming.
- Ids concretos de las playlists públicas de Spotify y número de estanterías por género.
- Cómo se pinta el lote de descargas y el diálogo «Elegir otra versión», dentro del lenguaje visual actual.
- Pesos exactos de la recomendación.
- Migración de las pistas que hoy están en estado `review`: tratarlas como listas (si tienen archivo) o «No encontrada».

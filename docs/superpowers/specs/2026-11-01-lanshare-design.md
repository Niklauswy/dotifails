# Wysun LANShare — rediseño (interfaz, arranque e indicador en la barra)

Fecha: 2026-11-01. Paquete: `apps/python/wysun_lanshare` (ya existe: servidor `server.py` + `static/`), orden `wysun lanshare`.

## Para qué es

Compartir cosas **rápido** dentro de la misma red, más rápido que mandarlas por Discord. Dos usos reales:

1. **Yo con mi celular:** ver en el celular lo que tengo en el PC (videos, fotos, documentos).
2. **Con otra persona en la red:** que alguien baje un archivo o una carpeta que le paso, o que me suba algo.

También se usa fuera de casa (redes ajenas), donde antes se hacía con `python3 -m http.server`. Quien abre la página puede estar en un **celular o en una computadora**.

Hoy funciona, pero la interfaz es mala, arrastra cosas de otro proyecto («yurai/share», filtros por «canal» que interpretan nombres `canal__fecha.mp4`) y no hay control de acceso: escucha en la red sin contraseña y con subidas siempre activas.

## Objetivos

- Interfaz nueva con **la calidad y el estilo del shell de Wysun, en tema claro**.
- Arranque con opciones claras: **subidas apagadas por defecto**, **contraseña opcional**, compartir **un archivo suelto** sin moverlo a una carpeta.
- **Se apaga solo** tras 1 hora sin uso.
- Mientras comparte, **un indicador en la barra** de Wysun con un panel para ver el estado y detenerlo.
- Dejar listo lo que necesitará Wysun Files para un «Compartir en la red» en el clic derecho (sin tocar Files ahora).

## No objetivos

- Código QR (el usuario lo descartó).
- HTTPS, cuentas de usuario, permisos por persona, compartir por internet.
- Integración en Wysun Files en esta etapa: hay otro agente migrándolo a QML (worktree `~/orca/workspaces/wysun-shell/qml-fase3-files`). No se toca `apps/python/wysun_files` ni ese worktree.
- Tema oscuro en la página web.

## Anti-objetivos (sería un fracaso aunque funcione)

- Que se vea genérico o «hecho a la rápida»; que no parezca parte de Wysun.
- Que quede algo de yurai (marca, canales, textos).
- Que alguien pueda subir archivos sin que el dueño lo haya permitido al arrancar.
- Que se apague mientras alguien está viendo un video o descargando.
- Que obligue a dictar más de lo necesario: la dirección debe salir clara al arrancar y en el panel de la barra.

## Arranque (decidido con el usuario)

```sh
wysun lanshare                              # carpeta actual, solo ver y descargar
wysun lanshare informe.pdf                  # comparte solo ese archivo
wysun lanshare ~/Videos --subidas           # permite subir archivos (y crear carpetas)
wysun lanshare ~/Videos --clave             # genera una contraseña corta y la muestra
wysun lanshare ~/Videos --clave gato123     # contraseña elegida
wysun lanshare --puerto 9000
wysun lanshare ~/Videos --inactivo 3h       # cambia el apagado automático
wysun lanshare ~/Videos --sin-limite        # nunca se apaga solo
wysun lanshare --detener PID                # lo usa el panel de la barra
```

- **Rutas:** una carpeta → se navega esa carpeta. Uno o más archivos (o mezcla) → *(decisión mía)* la página muestra solo esos elementos como una lista virtual; no se ve nada más de su carpeta. Las carpetas incluidas en una mezcla **se pueden abrir y recorrer**: cada elemento es una raíz propia con nombre virtual (su nombre; si dos coinciden, se añade un sufijo `(2)`), y el confinamiento de rutas se aplica por raíz. «Descargar todo» baja la lista virtual entera como un `.zip`. Sin ruta → carpeta actual.
- **`--subidas`:** por defecto **no**. Sin la opción no hay botón Subir, ni arrastrar para subir, ni crear carpetas, y el servidor rechaza esas peticiones (403). *(Decisión mía)* Solo se admite cuando se comparte una sola carpeta; con archivos sueltos da un error claro.
- **`--clave [CLAVE]`:** sin valor genera una contraseña corta y fácil de dictar *(mía: 6 caracteres en minúscula y dígitos, sin ambiguos como l/1/o/0)*. Quien entra la escribe una vez en una pantalla sencilla y queda dentro (cookie de sesión `HttpOnly`, aleatoria, válida mientras el servidor vive). Limitar intentos fallidos por IP.
- **Puerto:** por defecto 8000; si está ocupado prueba los siguientes y usa el primero libre *(mía: hasta +20)*, y lo dice. `--port`/`-p` y `--readonly` se aceptan como alias antiguos *(mía)*.
- **Apagado automático:** tras **1 hora sin uso**. «Sin uso» *(interpretación mía, aceptada)*: ninguna petición en ese tiempo **y** ninguna transferencia en curso (un video reproduciéndose o una descarga larga cuentan como uso). *(Mía)* Con `--clave` solo cuenta el tráfico de quien ya entró: la pantalla de contraseña, los intentos fallidos o un escáner de la red no mantienen el servidor encendido ni cuentan como «personas conectadas». `--inactivo DURACIÓN` (`30m`, `2h`) y `--sin-limite` lo cambian.
- **Al arrancar** imprime qué comparte, si hay subidas, la contraseña si la hay, y las direcciones: la **dirección fácil** `http://NOMBRE-PC.local:PUERTO` solo cuando la red la permita (p. ej. avahi activo; si no se puede saber, no se muestra), y **siempre la IP** (todas las interfaces LAN, con su nombre si hay varias). Ctrl+C detiene.
- **Lanzado sin terminal** (en el futuro, desde Files) funciona igual: la barra es su interfaz. *(Mía)* La barra **no inicia** servidores: solo muestra los activos y los detiene; empezar a compartir es desde la terminal o, después, desde Files.

## Interfaz web (decidida con mockups; quedan en `.superpowers/brainstorm/`)

Estilo Wysun, **siempre tema claro**: Material You con colores **sacados del wallpaper actual en modo claro** (`wysun_services.scheme.generate_dynamic(..., mode='light')`; si falla, `palettes.light.scheme` de `tokens.json`). Radios, espaciado, tipografía y movimiento de `wysun_core/tokens.json`. Fuentes empaquetadas servidas por el propio servidor (Google Sans Flex y Material Symbols Rounded, en `wysun_core/fonts`): no depender de internet. El CSS usa solo variables que el servidor genera desde los tokens; excepciones (velo oscuro sobre video, color de tipo de archivo) marcadas como en `docs/themes.md`.

**Celular (lista, opción B):**
- Arriba: nombre del PC con un punto de «en línea», búsqueda en píldora, botón para cambiar a cuadrícula.
- Ruta (migas) bajo la búsqueda.
- Filas: miniatura pequeña (video con duración, foto, icono por tipo para el resto), nombre, datos (tamaño · calidad · fecha), botón de descarga directa. Carpetas primero, con flecha.
- Botón flotante «Subir» **solo con `--subidas`**.

**Computadora (lista + panel, opción 1):**
- Cabecera: marca (nombre del PC), búsqueda, lista/cuadrícula, «Descargar carpeta» (.zip), «Subir» (solo con subidas).
- Lista en columnas: Nombre · Tamaño · Duración · Fecha · acción. Fila seleccionada resaltada.
- Panel derecho: vista previa del elemento seleccionado (video reproducible, foto, PDF, texto, audio), sus datos y botones **Abrir** (pantalla completa) y **Descargar**.
- Doble clic o Abrir → visor a pantalla completa con flechas anterior/siguiente.

**En ambas:**
- Vista previa del video al pasar el ratón/dedo por la miniatura (los *sprites* actuales) se conserva.
- Ordenar (fecha, nombre, tamaño), buscar con `/`.
- Arrastrar archivos a la página para subir (solo con subidas), con progreso por archivo.
- Pantalla de contraseña cuando hay `--clave`.
- Modo archivo suelto: misma lista con solo lo compartido.
- Se retira todo lo de yurai: marca, título, `describe()`/canales/chips.
- Accesible con teclado; sin desplazamiento horizontal en celular.

## Lógica del servidor que se conserva

Streaming con Range (Safari/iPhone), miniaturas y *sprites* con ffmpeg en `~/.cache/wysun/lanshare`, metadatos con ffprobe, `.zip` de carpetas al vuelo, rutas confinadas a lo compartido (sin `..` ni enlaces que escapen; ocultos fuera), escritura atómica de subidas (`wysun_core.jsonio.atomic_path`), solo biblioteca estándar más `wysun_core`/`wysun_services`.

## Indicador en la barra (Quickshell)

- Solo muestra y detiene (no inicia). Mientras haya al menos un LANShare activo, un icono de compartir en la barra vertical (junto a los demás indicadores, con el mismo patrón que `AiUsageIndicator.qml`: `StateLayer` que abre su panel).
- Panel: qué se comparte, dirección(es) y contraseña con botón **copiar**, si hay subidas, personas conectadas y qué se está descargando, cuánto falta para el apagado automático, y **«Dejar de compartir»**.
- Notificación del sistema cuando alguien sube un archivo (nombre y carpeta). *(Mía)* La envía **el servidor** con `notify-send` (si existe) al terminar cada subida, así el JSON de estado no necesita registro de eventos y avisa aunque el shell no esté corriendo.
- **Contrato servidor → shell** *(mío)*: cada servidor escribe `$XDG_RUNTIME_DIR/wysun-lanshare/<pid>.json` (escritura atómica, actualizado al cambiar, como mucho ~1 vez por segundo) con: rutas compartidas, direcciones, puerto, contraseña (el directorio es privado del usuario), subidas sí/no, clientes recientes, transferencias en curso, momento previsto de apagado. Lo borra al salir; el shell ignora archivos de procesos muertos. Varios servidores a la vez son posibles: el panel los lista, cada uno con su botón de detener.
- «Dejar de compartir» ejecuta `wysun lanshare --detener PID`, que comprueba que ese PID es un LANShare del usuario antes de enviarle SIGTERM.
- Colores, radios y movimiento del shell (`Colours`, `Tokens`), como el resto de paneles.

## Para Wysun Files (después de la migración)

Nota a entregar (en `docs/utilities.md` y aquí): en el clic derecho de un archivo, varios archivos o una carpeta, «Compartir en la red» abre un diálogo pequeño (subidas sí/no —solo para una carpeta—, contraseña sí/no) y lanza `wysun lanshare RUTA… [--subidas] [--clave]` desacoplado. Todo lo demás (estado, detener) lo hace la barra. No se hace en esta etapa.

## Restricciones

- Reglas de `AGENTS.md`: un paquete, orden en `MODULES` de `bin/wysun`, nada suelto; datos fuera del repo; tokens del tema; pruebas en HOME/XDG temporales; despliegue con `./instalar.sh --wysun-only` y reinicio solo del shell; comprobar la apertura real del panel.
- No compilar en paralelo (memoria: una compilación a la vez).

## Lo que queda al constructor

Estructura interna del servidor y del JS (puede reescribirse entero), cómo se sirven los tokens al navegador, el detalle de la pantalla de contraseña, el visor a pantalla completa, la animación, cómo detectar si `.local` funciona, el formato exacto del JSON de estado, el lugar exacto del icono en la barra y las pruebas.

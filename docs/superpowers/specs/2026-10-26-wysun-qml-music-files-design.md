# Wysun — Music y Files en QML sobre una base Material 3 Expressive

Fecha: 2026-10-26. Estado: aprobado por Nicolas para empezar («ya empieza la migración»).
Las decisiones marcadas **(decisión del coordinador)** las tomé yo porque Nicolas me las delegó
(«como decidas»); el resto son suyas.

## Intención

Las apps Qt Widgets de Wysun no se ven ni se mueven como Material 3, y no es un detalle de una
pieza: es la base. Una auditoría contra los tokens oficiales (`material-web`,
`tokens/versions/v0_192`) encontró:

- **Color:** `wysun_core.theme` traduce el esquema M3 a ~25 nombres propios (`canvas`, `well`,
  `accent`, `nav_selected`…) y pierde roles (`primaryContainer`, `secondaryContainer`,
  `tertiaryContainer`); `tertiary` se llama `warning`. Sin `secondaryContainer` no existe el indicador
  activo M3.
- **Componentes:** `wysun_core.ui` tiene ~15 piezas; no hay navigation drawer/rail, search bar, text
  field, menú, diálogo, lista, tarjeta, pestañas ni top app bar. Resultado: 4 `Sidebar`, 2 `Rail`,
  2 `Hero`, 2 `SelectionBar`, menús propios por app.
- **Barra lateral:** filas de 36 px (M3: 56), títulos en MAYÚSCULAS espaciadas (M3: title-small en
  `onSurfaceVariant`), selección gris (M3: `secondaryContainer`/`onSecondaryContainer`), sin
  contenedor (M3: `surfaceContainerLow`, esquina grande), hover ~5 % (M3: 8 %, focus/pressed 12 %).
- **Búsqueda:** píldora de 36 px con texto pequeño (M3 search bar: 56 px, `surfaceContainerHigh`,
  body-large, iconos `onSurface`). Los campos de texto no siguen el outlined text field (56 px,
  esquina 4, etiqueta flotante, foco 2 px `primary`).
- **Chips:** píldoras completas (M3 filter chip: 32 px, esquina 8, seleccionado `secondaryContainer`
  con ✓).
- **Movimiento:** duraciones de tokens, pero 15 `OutCubic`; sin patrones de transición M3.

El shell (QML) ya tiene componentes M3 de verdad. En lugar de reconstruir un kit Qt Widgets que luego
se tiraría, Music y Files pasan a QML y estrenan una base compartida.

## Metas

1. **Wysun Music** y **Wysun Files** reescritas en QML y **rediseñadas** (no traducción fiel) en
   Material 3 Expressive, con **todas** las funciones actuales (nada se elimina en esta fase).
2. **Navegación adaptable al ancho de ventana** (decisión de Nicolas), con las clases de ventana M3:
   - < 600 px: navigation drawer **modal** desde el botón de menú;
   - 600–839 px: **navigation rail** (80 px; indicador 56×32 `corner-full`; etiqueta label-medium);
   - ≥ 840 px: navigation **drawer estándar** dentro de su contenedor `surfaceContainerLow`
     (indicador 56 px de alto, `secondaryContainer`/`onSecondaryContainer`, icono relleno al activarse,
     títulos de sección title-small `onSurfaceVariant`, divisores `outlineVariant`).
   Maqueta aprobada: `docs/design/qml-migration/files-adaptive-nav.html`.
3. **Libertad creativa expresiva** (Nicolas: «añade libertades creativas como estas, en más partes»):
   el emblema con forma (cookie/squircle) junto al título y resumen de la carpeta es el ejemplo de
   referencia. Usar formas M3 Expressive, color de los roles y movimiento con muelles en más sitios
   (cabeceras, estados vacíos, carátulas, reproductor, selección, transiciones), sin sacrificar
   legibilidad ni densidad útil.
4. **Base compartida reutilizable** (biblioteca de componentes QML + tema + movimiento) que las demás
   apps (PDF, Player, Recorder, instalador) adoptarán después, y documentación de qué ofrece y cómo
   usarla («que las apps sepan qué deben y pueden implementar»).
5. Movimiento según el sistema M3: muelles espaciales/efectos (fast/default/slow) de
   `tokens.json` (`anim.curves.expressive*`, `anim.durations.expressive*`), y patrones de transición
   M3 (fade through entre destinos, shared axis en navegación jerárquica, container transform al
   abrir un elemento), respetando movimiento reducido.

## No-metas

- Migrar PDF, Player, Recorder o el instalador (después, sobre la misma base).
- Cambiar el modelo de datos, la biblioteca de Music, mpv, SQLite, las operaciones de archivos ni
  las rutas privadas: la lógica Python se conserva y se expone a QML.
- Recortar funciones (se decidirá en otra fase qué sobra).

## Anti-metas (fallaría aunque funcione)

- Perder cualquier función o atajo actual de Music o Files.
- Más lento o más pesado que ahora de forma perceptible (arranque, scroll de carpetas grandes y de la
  biblioteca, memoria residente). Medir antes y después.
- Romper el **selector de archivos** (`wysun_files.chooser`, usado por el PDF y por el portal
  `org.freedesktop.impl.portal.FileChooser`) o `org.freedesktop.FileManager1` / «mostrar en carpeta».
- Colores, radios, medidas o duraciones literales (regla de `AGENTS.md`/`docs/themes.md`).
- Dejar dos sistemas de diseño divergentes para siempre: la base nueva debe poder adoptarla el shell.
- Un Material 3 «de manual» sin carácter: debe sentirse de la familia del shell.

## Restricciones

- `AGENTS.md`: tokens del tema, sin literales; probar claro/oscuro y wallpapers de colores distintos;
  datos privados fuera del repo; no reiniciar Hyprland; desplegar con `./instalar.sh --wysun-only`.
- **No instalar dependencias del host sin autorización expresa de Nicolas.** Debian trae PySide6
  6.8.2 **sin QtQuick**; el shell usa un Qt privado 6.9.3 (`~/.local/share/wysun/runtime`).
- **Recursos (este equipo ya sufrió un OOM):** una sola compilación a la vez, `--jobs 3`, suites en
  serie, nada grande en `/tmp` (tmpfs).
- La versión Widgets actual sigue instalada y funcionando hasta que la nueva tenga todas las
  funciones; el cambio de cada app se hace de una vez (decisión del coordinador).

## Cómo (lo decidido)

### Fase 0 — prueba técnica del runtime QML (desechable)

Decide cómo corre QML para las apps. Candidatos:

1. **PySide6 con QtQuick en un runtime privado** (venv como `pdf-runtime`, PySide6 de la misma
   versión que el Qt privado 6.9.3), cargando o no el plugin `Wysun.*`.
2. **Biblioteca QML pura** (sin Quickshell ni C++) usada por apps PySide6 y, más adelante, por el
   shell.
3. **Apps sobre el runtime del shell** (Quickshell), con la lógica Python como backend por IPC (como
   ya hace Ajustes).

Criterios: un solo Qt por proceso; arranque < 1 s en frío para una ventana con lista; scroll fluido de
10 000 elementos; memoria; que el tema y los muelles M3 funcionen; que se pueda probar offscreen; que
no requiera paquetes del host sin permiso; que el shell pueda compartir los componentes. El resultado
(con números) se escribe en este documento antes de seguir. **(decisión del coordinador:** la elección
final la toma el coordinador con esos datos; si exige instalar algo en el host, se pregunta a Nicolas.)

### Fase 1 — base compartida

- Tema: roles **M3 directos** (`primary`, `primaryContainer`, `secondaryContainer`,
  `surfaceContainer*`, `outlineVariant`…) desde `~/.local/state/wysun/scheme.json` y
  `wysun_core/tokens.json`, en vivo al cambiar modo o wallpaper.
- Componentes mínimos para Music y Files, con las medidas de los tokens M3 oficiales: navigation
  drawer/rail/modal adaptable, search bar, text field (outlined/filled), botones (filled, tonal,
  outlined, text, icon, FAB/extended FAB), chips (assist, filter, input), listas y elementos de lista,
  tarjetas, menús, diálogos, snackbar, tooltip, progress (linear/circular), pestañas/segmented,
  top app bar, divider, badge, estados vacíos, formas expresivas, state layers (8/12/12/16 %),
  foco accesible.
- Movimiento: muelles y patrones de transición como componentes reutilizables.
- **Arreglo inmediato en Widgets** (decisión del coordinador, barato y útil pase lo que pase): que
  `wysun_core.theme` exponga también los roles M3 directos, para que las apps que siguen en Widgets
  puedan usarlos.
- Documento de uso de la base (qué componentes hay, cuándo usar cada uno, cómo extenderla).

### Fase 2 — Music (primero: más pequeña y con menos integración de sistema; decisión del coordinador)

### Fase 3 — Files (incluye el selector de archivos y la integración D-Bus/portal)

Cada fase: diseño de pantallas → plan → TDD → revisión → capturas claro/oscuro con 3 paletas →
prueba en ventana real → despliegue.

## Lo que se deja al constructor

- La estructura de carpetas de la biblioteca QML y los nombres de componentes.
- El patrón exacto Python↔QML (modelos `QAbstractListModel`, objetos de contexto, señales).
- Dónde aplicar las libertades expresivas en cada pantalla (proponerlas con capturas).
- Cómo partir los commits.

## Resultado de la fase 0

Prueba desechable en `spike/` (rama `qml-spike`, no se fusiona). Misma mini-app en todos los casos:
biblioteca QML pura `spike/qml/SpikeM3` (solo `import QtQuick`) con navegación adaptable (drawer
modal < 600, rail 600–839, drawer estándar ≥ 840), search bar, `ListView`/`GridView` de 10 000
elementos, roles M3 directos de `scheme.json` (`m3primaryContainer`, `m3secondaryContainer`…), muelle
`anim.curves.expressive*` de `tokens.json` (`Spring.qml`) y medidor de frames (`Bench.qml`).
Arnés: `spike/measure.py`; tema en vivo: `spike/theme_live.py`; datos en bruto: `spike/results/`;
capturas: `spike/shots/`.

### Hallazgo clave

El Qt de la rueda `PySide6_Essentials 6.9.3` de PyPI **es binario idéntico** al Qt 6.9.3 privado del
shell (aqtinstall): 66 de las bibliotecas comunes tienen el mismo `md5` (solo difiere ICU, y la rueda
trae además Timeline y WaylandCompositor). Por eso los bindings de PySide6 pueden correr **sobre el Qt
del runtime del shell**: se precargan sus `libQt6*.so.6` por ruta absoluta antes de `import PySide6`
(el enlazador reutiliza el soname ya cargado) y se apuntan plugins e imports QML al runtime. Comprobado
con el `PySide6/Qt/` de la rueda **renombrado**: arranca, pinta y carga `Wysun.Config` y `M3Shapes`.

### Candidatos medidos

- **1-rueda**: PySide6 6.9.3 de pip con su propio Qt (`--qt wheel`).
- **1+2 runtime**: bindings PySide6 6.9.3 sobre el Qt del shell + biblioteca QML pura
  (`--qt runtime`); variante `+plugin` importando además `Wysun.Config` del plugin del shell.
- **3 Quickshell**: instancia aparte de `quickshell -p spike/quickshell/shell.qml` con la misma
  biblioteca y Python como proceso hijo (JSON por tubería → `ListModel`).
- **3 con componentes del shell** (`spike/quickshell/app-in-shell.qml`, entrada junto a `shell.qml`
  en una copia de `apps/shell`, importando `qs.components`/`qs.services`).

Sesión Hyprland real, monitor 1920×1080 a 60 Hz, ventana en mosaico de 941×1056. Arranque = desde
`Popen` hasta el primer `frameSwapped`. «Frío» = tras expulsar de la caché de páginas (sin root,
`posix_fadvise DONTNEED`) el venv, el runtime, la stdlib y el spike; las páginas que el shell en marcha
tiene mapeadas (su Qt) no se pueden expulsar, igual que en uso real. Scroll = animación lineal de
`contentY` registrando cada `frameSwapped`: *fling* 20 000 px en 4 s, lista completa
(720 000 px en 8 s, ~33 delegados nuevos por frame) y rejilla completa; 2–5 repeticiones.

| | 1-rueda | 1+2 runtime | 1+2 runtime +plugin | 3 Quickshell |
|---|---|---|---|---|
| Primer frame, caliente (mediana de 5) | 264 ms | 277 ms | 318 ms | 164 ms vacío; datos a ~230 ms |
| Primer frame, frío (mediana de 3) | 284 ms | 261 ms | 312 ms | 132 ms vacío; datos a ~216 ms |
| RSS estable (reposo) | 156 MB | 156 MB | 174 MB | 155 MB (quickshell 140 + backend 15) |
| PSS estable (reposo) | 99 MB | 85 MB | 95 MB | 77 MB |
| RSS / PSS tras el scroll | 158 / 100 MB | 158 / 85 MB | 177 / 97 MB | 127–138 / 65–68 MB |
| Scroll: fps (lista y rejilla) | 60 | 60 | 60 | 58–60 |
| Scroll: p50 / p95 del frame | 17 / 18–21 ms | 17 / 18–21 ms | 17 / 18–22 ms | 17 / 18–20 ms |
| Scroll: peor frame; frames > 25 ms de 480 | 20–59 ms; 0–5 | 19–56 ms; 0–4 | 20–51 ms; 0–5 | 18–44 ms; 0–3, y un tirón de 340 ms en 1 de 5 pasadas |
| Qt en `/proc/<pid>/maps` | uno, **el de la rueda** (copia aparte) | uno, **el del shell**; plugins y QML del runtime | uno, el del shell | uno, el del shell |
| Plugin `Wysun.*` | no probado (dos copias del mismo Qt) | posible | **carga** (`Tokens` → 350) | sí |
| Componentes del shell (`qs.*`) | no | no | no | solo dentro del árbol del shell, arrastrando todo `qs.services` |
| Offscreen + `grabToImage` | sí | sí | sí | sí con la biblioteca pura; **no** con `qs.services` («No PanelWindow backend loaded») |
| Tema en vivo (cambio de `scheme.json`) | sí (`QFileSystemWatcher`) | sí | sí | sí (`FileView`) |
| Modelo | `QAbstractListModel` de Python | idem | idem | JSON por tubería + `ListModel` JS (10 000 filas: `append` 16 ms) |
| Disco a desplegar | venv 272 MB (Qt duplicado 172 MB) | venv ~21 MB (bindings sin `Qt/`) | idem | nada nuevo |

El muelle de tokens (`Easing.BezierSpline` con los puntos de `anim.curves.expressive*`, que se salen de
[0, 1]) funciona igual en los tres; el modo claro/oscuro y tres semillas distintas (verde claro,
naranja oscuro, azul claro, generadas con `wysun_services.scheme.gen_scheme` en un `XDG_STATE_HOME`
temporal) se repintan en vivo en PySide6 y en Quickshell (`spike/shots/montage-theme.png`).
`spike/shots/wayland-runtime+plugin.png` y `wayland-qs.png` son las ventanas reales (solo su región, con
grim). Las cifras de scroll están limitadas por los 60 Hz del monitor: los tres candidatos van
holgados con 10 000 elementos, y la llamada a `data()` en Python por delegado no se nota.

### Recomendación: candidato 1 + 2 sobre el runtime del shell

**PySide6 6.9.3 solo como bindings, sobre el Qt privado del shell, con la UI en una biblioteca QML pura
compartida** (sin `Quickshell`, sin `qs.*` y sin depender del plugin `Wysun.*`).

- **Un solo Qt, y es el del shell.** No hay un segundo Qt en disco ni en memoria. Las páginas de
  `libQt6*` se comparten con el shell en marcha: PSS de 85 MB frente a 99 MB con el Qt de la rueda, y
  sin 172 MB duplicados.
- **Conserva la lógica Python en proceso**, que es lo que pide el diseño. `QAbstractListModel` sobre
  SQLite, mpv y las operaciones de archivos, y sobre todo el selector `wysun_files.chooser`, que usan
  el PDF y el portal, y los servicios D-Bus (`dbus`/`gi` del sistema, accesibles con un venv
  `--system-site-packages` donde el PySide6 6.9.3 del venv tapa al 6.8.2 de Debian; comprobado).
  Quickshell obligaría a convertir todo eso en un protocolo IPC.
- **Arranque < 1 s con margen**: 260–280 ms hasta la ventana con datos, frente a ~220–230 ms de
  Quickshell con datos. Además hay margen de mejora con `qmlcachegen`/caché de disco de QML.
- **Pruebas offscreen** con `QT_QPA_PLATFORM=offscreen` y `grabToImage`, con el Python del venv, sin
  sesión.
- **Compartible con el shell**: la biblioteca pura carga igual en Quickshell, con el mismo aspecto
  pixel a pixel (`off-qs.png` y `off-runtime-1000.png`). Los componentes actuales del shell no se
  pueden reutilizar tal cual fuera de él: 58 de 69 importan `qs.*`, que solo existe dentro de la
  configuración del shell y arrastra todos sus servicios. La convergencia va al revés: la base nueva
  nace pura y el shell la adopta.
- **No usar `Wysun.Config` en las apps**, aunque cargue. Cuesta +40 ms y +18 MB, y arrastra
  `libqalculate` y el resto de `libwysun-core`. Los tokens y el esquema se leen como JSON (ya lo hace
  `wysun_core`). `M3Shapes` (formas expresivas, en `runtime/deps`) sí carga en el proceso PySide6 y
  puede usarse.

Descartados: **1-rueda** (funciona, pero duplica Qt y no comparte memoria ni plugin con el shell);
**3** (el más ligero en RSS/PSS y en primer frame, pero sin modelos Python en proceso, con todo el
backend por IPC, sin reutilización real de componentes, y con un tirón de 340 ms sin explicar en una de
cinco pasadas que habría que investigar).

### Consecuencias

- **Instalación** (sin paquetes del host): un paso del instalador crea
  `~/.local/share/wysun/qml-runtime` con `python3 -m venv --system-site-packages` y hace
  `pip install --no-deps PySide6_Essentials==X shiboken6==X`, con `X` igual a `qt.version` de
  `RUNTIME.json` (hoy 6.9.3). Después borra `PySide6/Qt/` y las herramientas (`designer`, `qmlls`…),
  y queda en ~21 MB. Descarga una vez ~97 MB de PyPI, como ya hace `pdf-runtime` con PyMuPDF.
  **Versión en lockstep**: si `runtime_build.py` sube Qt, hay que subir PySide6 a la misma versión,
  porque `libpyside6qml` usa API privada de QtQml. El sello del venv guarda la versión, y el arranque
  comprueba `qVersion() == PySide6.__version__`; si no coinciden, avisa.
- **Arranque de la app**: el lanzador (`wysun music`/`wysun files`) re-ejecuta con el Python de ese
  venv, como hace el PDF con `pdf-runtime`. Antes de importar PySide6 precarga las `libQt6*` del
  runtime con `ctypes.CDLL(..., RTLD_GLOBAL)`, o, más limpio, se cambia una vez en la instalación el
  RPATH de los `.abi3.so`/`libpyside6*` al runtime. Luego fija `QCoreApplication.setLibraryPaths`
  (plugins del runtime) y añade al motor los imports `runtime/qt/.../qml`, `runtime/deps/lib/qt6/qml`
  y la biblioteca base. No exporta `LD_LIBRARY_PATH`, así que los hijos (mpv…) no heredan nada.
- **Empaquetado**: la biblioteca QML (p. ej. `apps/qml/<Módulo>/` con `qmldir`) viaja como fuente
  dentro de `app/` y no se compila. `qmlcachegen` es opcional más adelante. El Recorder no se toca en
  esta fase.
- **Pruebas**: suites offscreen con el Python del venv (capturas claro/oscuro con 3 semillas como en
  `theme_live.py`). Se saltan con un aviso si falta el runtime o el venv, y van en serie.
- **Compartir con el shell**: la biblioteca solo importa `QtQuick` (y opcionalmente `M3Shapes`), y su
  `Theme` recibe esquema y tokens del anfitrión. En las apps se los da Python. En el shell, un
  adaptador fino alimenta `Theme` desde `Colours`/`Tokens`, y `runtime.sh` añade la ruta de la
  biblioteca a `QML_IMPORT_PATH`. Nombrar los roles `m3*` (como el shell): en QML una propiedad
  `onSurface` se toma por manejador de señal y no pinta.
- **Permisos**: no hace falta instalar nada en el host. La única novedad es la descarga de PyPI en el
  instalador para un venv privado, que conviene que Nicolas confirme como hizo con `pdf-runtime`.
  Para recrear el venv de la prueba: `python3 -m venv --system-site-packages
  ~/.cache/wysun-qml-spike/venv && ~/.cache/wysun-qml-spike/venv/bin/pip install
  PySide6_Essentials==6.9.3 shiboken6==6.9.3`.

### Aprobación (2026-10-26)

Nicolas aprobó que el instalador cree el venv privado `~/.local/share/wysun/qml-runtime` y descargue
una vez de PyPI `PySide6_Essentials` y `shiboken6` de la misma versión que el Qt del runtime
(hoy 6.9.3, ~97 MB). No se instalan paquetes del host.

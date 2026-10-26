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

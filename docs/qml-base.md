# Base QML compartida (WysunM3)

`apps/qml/WysunM3` es la biblioteca de componentes Material 3 Expressive sobre la que se escriben las apps QML de
Wysun (Music, Files, Player y los ajustes del Recorder; el instalador se queda en Widgets). Este documento explica qué ofrece, cuándo
usar cada pieza y cómo ampliarla. Diseño de origen: `docs/superpowers/specs/2026-10-26-wysun-qml-music-files-design.md`.

## Qué es y qué no es

- **Es** una biblioteca QML pura: solo importa `QtQuick`, `QtQuick.Shapes` y, de forma opcional, `M3Shapes`
  (decisión D3). No conoce Python, el shell ni el plugin `Wysun.*`. `tests/qml/check_purity.py` lo hace cumplir, y
  también la ausencia de colores y duraciones literales.
- **Es** Material 3 con las medidas de los tokens oficiales (`material-web`, `tokens/versions/v0_192`). Cada medida
  de componente vive una sola vez en `Metrics.qml`, con el token del que sale.
- **No es** `QtQuick.Controls`: no hay `Popup` ni estilos de Qt. Menús, diálogos, tooltips y snackbars se dibujan
  dentro de la ventana, en un `OverlayLayer`.
- **No es** todavía la base del shell: el shell sigue con `apps/shell/components`; la convergencia está descrita al
  final.

## Arquitectura

```
app (python3 -m wysun_<app>)
  └─ wysun_qml.bootstrap  re-ejecuta con el Python del venv qml-runtime, precarga libQt6* del runtime del shell,
  │                      fija plugins e imports QML (sin LD_LIBRARY_PATH)
  └─ wysun_qml.engine     QGuiApplication + QQmlApplicationEngine, fuentes empaquetadas, rutas de import
  └─ wysun_qml.theme_bridge.ThemeBridge   scheme.json + theme.json + tokens.json + appearance.json, en vivo
        │  (propiedades scheme, tokens, reducedMotion; setPreview() para galerías y pruebas)
        ▼
  ThemeFeed { scheme: bridge.scheme; tokens: bridge.tokens; reducedMotion: bridge.reducedMotion }
        ▼
  Theme (singleton)   roles m3*, rounding/spacing/padding/font/anim, typeFont(), duration(), curve()
  Metrics (singleton) medidas de componente M3, windowClass(ancho)
  Motion (singleton)  ms(kind), bezier(kind), reduced
```

- **Runtime**: PySide6 en el venv `~/.local/share/wysun/qml-runtime` (`installer/qml_runtime.py`), solo los bindings,
  a la misma versión que el Qt del runtime del shell (`RUNTIME.json`). Un único Qt por proceso, compartido con el
  shell en memoria. Si las versiones no coinciden, el arranque avisa y sigue.
- **Rutas**: la biblioteca se despliega en `~/.local/share/wysun/qml/WysunM3` (y la galería en
  `~/.local/share/wysun/qml/gallery`). `WYSUN_QML_LIB` la sustituye (las pruebas la fijan al árbol del repositorio).
- **Tema en vivo**: `ThemeBridge` vigila los archivos como `wysun_core.qt_theme.watch_theme`. Un `scheme.json` ausente,
  incompleto o roto conserva el último bueno; un rol que falta se toma de la paleta base del modo en `tokens.json`.

## Plantilla mínima de una app

```python
# apps/python/wysun_ejemplo/__main__.py
import sys
from wysun_qml import bootstrap

def main():
    bootstrap.ensure_runtime_python('wysun_ejemplo')   # re-ejecuta en el venv si hace falta
    bootstrap.preload_qt()                             # antes de cualquier import de PySide6
    from PySide6.QtCore import QUrl
    from wysun_qml import engine, theme_bridge
    app, qml = engine.create_engine('wysun-ejemplo')
    app.setDesktopFileName('wysun-ejemplo')            # app_id de Wayland = clase en hyprctl
    bridge = theme_bridge.ThemeBridge(parent=qml)
    qml.rootContext().setContextProperty('bridge', bridge)
    qml.load(QUrl.fromLocalFile('…/Main.qml'))
    return app.exec()

raise SystemExit(main())
```

```qml
// Main.qml
import QtQuick
import WysunM3

Window {
    visible: true
    color: Theme.m3surface

    Item {
        anchors.fill: parent

        ThemeFeed { scheme: bridge.scheme; tokens: bridge.tokens; reducedMotion: bridge.reducedMotion }

        AdaptiveNavigation {
            anchors.fill: parent
            destinations: [{id: "home", icon: "home", label: "Inicio"}]
            currentId: "home"
            // contenido de la página
        }

        SnackbarHost { id: snackbars; anchors.fill: parent }
        OverlayLayer { id: overlay }          // host de menús, diálogos y tooltips
    }
}
```

La lógica (modelos, mpv, SQLite, operaciones de archivos) se queda en Python y se expone con `QAbstractListModel`
y objetos con propiedades y señales. QML solo presenta.

## Tema

- Color: **solo** `Theme.m3<rol>` (`m3primary`, `m3onSurfaceVariant`, `m3secondaryContainer`,
  `m3surfaceContainerLow`…, más `m3success*`). Se llaman `m3*` porque una propiedad `onSurface` sería un manejador
  de señal en QML. La lista coincide con `wysun_core.theme.MATERIAL_ROLE_NAMES` (prueba de paridad).
- Forma, espacio y tipo: `Theme.rounding.*`, `Theme.spacing.*`, `Theme.padding.*`, `Label { role: "title.medium" }`
  (o `Theme.typeFont(rol)`). Un radio de píldora es `Theme.fullRadius(alto)`.
- Medidas de componente: `Metrics.*` (56 del elemento de drawer, 40 del botón, 80 del rail…). Una medida nueva va a
  `Metrics.qml` con el nombre del token M3 en el comentario, nunca como número suelto en un componente.
- Iconos: `Icon { name: "folder"; filled: activo }` (Material Symbols Rounded). Sin la fuente no se dibuja nada: el
  nombre de la ligadura nunca aparece como texto.

## Catálogo

| Componente | Cuándo usarlo | Cuándo no | Medidas |
|---|---|---|---|
| `Button` | Acciones con texto. `filled` la principal de una vista, `tonal` secundaria con peso, `outlined` media, `elevated` sobre fondos con color, `text` la menor (diálogos, tarjetas). `checkable` para un conmutador con texto | Acciones de barra con solo icono (`IconButton`) | alto 40, icono 18 |
| `IconButton` | Acciones compactas: barras, filas, reproductor. `checkable` + `iconChecked` para favoritos, aleatorio… | La acción principal de la pantalla (`Fab`) | 40, icono 24 |
| `Fab` | La acción principal y constructiva de la pantalla (nueva carpeta, reproducir). `extended` con texto; `expanded: false` lo pliega al desplazar | Más de uno por pantalla; acciones destructivas | 40/56/96; extendido 56 |
| `SegmentedButtons` | Elegir 2-5 opciones relacionadas (modo de vista, filtros excluyentes o múltiples) | Navegación entre destinos (`TabBar`) | alto 40 |
| `Slider` | Un valor continuo: posición de una canción (`wavy`, `waveMoving`), volumen; ←/→, RePág/AvPág, Inicio/Fin | Elegir entre pocas opciones (`SegmentedButtons`) | pista 4, asa 20, objetivo 40 |
| `Chip` | `filter` para acotar contenido, `assist` acciones contextuales, `input` valores introducidos (con quitar), `suggestion` propuestas | Acciones principales | alto 32 |
| `Switch` | Un ajuste de sí o no que se aplica al instante; clic, Espacio o Enter; el halo rodea el asa | Elegir entre varias opciones (`SegmentedButtons`, `Dropdown`) | pista 52×32, asa 16/24/28 |
| `Dropdown` | Elegir una opción entre varias (`model: [{value, text}]`, `current`, `activated(value)`); abre un `Menu` bajo el campo, ↑/↓ abren | Pocas opciones excluyentes (`SegmentedButtons`) | alto 56 |
| `Badge` | Novedad (punto) o un recuento sobre un icono | Texto largo | 6 / 16 |
| `Divider` | Separar grupos en listas y paneles (`inset`) | Separar cada fila (el espacio basta) | 1 px |
| `LinearProgress`, `CircularProgress` | Progreso determinado (`value`) o indeterminado | Esperas de < 1 s | 4; circular 48 |
| `ShapeEmblem` | La libertad expresiva de Wysun: un icono o carátula en una forma M3 (cookie, flor, sol…) junto a un título, en estados vacíos o cabeceras | Iconos de lista o de botones | 56 por defecto |
| `TextField` | Entrada de texto: `outlined` por defecto, `filled` en formularios densos o sobre superficies con color | Búsqueda (`SearchBar`) | alto 56 |
| `SearchBar` | La búsqueda de una app o vista (Ctrl+L, Escape borra) | Filtros de una lista corta (`TextField`) | alto 56, píldora |
| `ListItem` | Filas de 1-3 líneas con icono, avatar, imagen o elemento propio; `selected`, `highlighted` para el actual del teclado; `contextRequested` para menús | Rejillas de carátulas (`Card`) | 56/72/88 |
| `Card` | Un objeto con entidad propia (álbum, vista previa, resumen) | Envolver secciones enteras | esquina `medium` |
| `EmptyState` | Vistas sin contenido o primer uso, con una acción | Errores bloqueantes (`Dialog`) | emblema 112 |
| `TopAppBar` | Cabecera de una vista; `medium`/`large` se pliegan con `scrollOffset` | Barras flotantes sobre contenido | 64/112/152 |
| `AdaptiveNavigation` | La navegación de una app según la clase de ventana (modal < 600, rail 600-839, drawer ≥ 840) | — | — |
| `NavigationDrawer`, `NavigationRail`, `NavigationItem` | Piezas sueltas (las usa `AdaptiveNavigation`) | Cambiar de vista dentro de un destino (`TabBar`) | drawer 280 (D2), item 56; rail 80, indicador 56×32 |
| `TabBar` | `primary` para vistas hermanas de un destino, `secondary` dentro de una vista | Navegación principal | alto 48 (64 con iconos) |
| `Menu`, `MenuItem` | Opciones contextuales (clic derecho, botón «más») | Más de ~10 opciones o formularios | filas 48, ancho 112-280 |
| `Dialog` | Decisiones que interrumpen (confirmar borrado, conflictos) | Avisos que no requieren respuesta (`SnackbarHost`) | 280-560, esquina `extraLarge` |
| `SnackbarHost`, `Snackbar` | Confirmaciones breves con «Deshacer» opcional | Errores que exigen acción | alto 48 / 68 |
| `Tooltip` | Nombrar un `IconButton` o explicar algo (`rich`) | Información imprescindible | alto 24 |
| `Surface` | Contenedor con rol, elevación (sombra y tinte tonal), borde y estado deshabilitado | — | niveles 0-5 |
| `StateLayer`, `FocusRing` | Hacer interactivo un elemento propio: capa 8/12/12/16 %, onda y anillo de foco de teclado | Componentes que ya los traen | anillo 3 px a 2 px |
| `OverlayLayer` | El host de las superposiciones; uno al final del elemento raíz | — | — |
| `RollingNumber` | Cifras en vivo que cambian a menudo (CPU, memoria, recuentos): los dígitos ruedan con el muelle | Texto estático | rol de tipo |
| `LiveChart` | Series temporales del último minuto; desplazamiento continuo, guía al pasar el cursor (`scrub`), marcas de picos | Comparar categorías | — |
| `StateShape` | El estado de un proceso o elemento vivo como forma M3 que se transforma (trabajando, en espera, pausado…) | Iconos de lista | 56 por defecto |

La galería (`python3 -m wysun_qml`) muestra cada componente con sus variantes y estados; es la referencia visual.

## Movimiento

- **Muelles M3 Expressive** (`anim.curves.expressive*` y `anim.durations.expressive*` de `tokens.json`):
  `SpringBehavior on x { kind: "fastSpatial" }`, `Anim { kind: "defaultSpatial" }`, `CAnim { kind: "fastEffects" }`.
  *Spatial* (posición, tamaño, forma; puede rebotar) para lo que se mueve; *effects* (color, opacidad; sin rebote) para
  lo que cambia de aspecto. `fast` para piezas pequeñas (botones, chips), `default` para paneles, `slow` para
  entradas grandes (estados vacíos, pantallas).
- **Patrones de transición** (todos sobre `TransitionHost`):
  - `FadeThrough`: entre destinos sin relación jerárquica (elementos de navegación, pestañas).
  - `SharedAxis` (`axis: "x"|"y"|"z"`): navegación con relación espacial o jerárquica (entrar en una carpeta, pasos).
  - `ContainerTransform`: abrir un elemento en su detalle (una tarjeta de álbum en la vista del álbum).
- **Movimiento reducido** (`appearance.json`, o `WYSUN_REDUCED_MOTION=1`): todas las duraciones pasan a 0 y una
  animación en curso termina en su destino. Los indicadores indeterminados se quedan quietos. No hace falta
  comprobarlo en cada app si se usan estas piezas.

### Destinos de navegación

`{id, icon, label}` y, opcionales: `activeIcon`, `badge` (número o punto), `trailing` (texto) o `trailingIcon`
(p. ej. «sonando»), `image` (portada en lugar del icono en los drawers), `rail: false` (solo drawers),
`drawer: false` (solo rail), `railLabel`/`railIcon`/`railOrder` (el rail es más corto y puede ordenar distinto).
Separadores `{divider: true}`; cabeceras `{header, action, actionId, actionLabel}` (la acción emite
`headerAction(actionId)`). El clic derecho en un destino emite `contextRequested(id, x, y)` en coordenadas de ventana.

## Adaptable

`Metrics.windowClass(ancho)` devuelve `"modal"` (< 600), `"rail"` (600-839) o `"standard"` (≥ 840).
`AdaptiveNavigation` coloca el contenido y, en modal, expone `menuButtonVisible` y `openModal()` para el botón de menú
de la barra superior. Al crecer fuera de modal, el drawer modal se cierra y devuelve el foco. Las apps adaptan su
contenido con el mismo `windowClass` (p. ej. rejilla de 2, 3 o 5 columnas).

## Accesibilidad y teclado

- Los controles toman foco solo con teclado (`Qt.TabFocus`): el ratón no deja anillos de foco. Tab recorre, Espacio y
  Enter activan, los deshabilitados no toman foco.
- Navegación: ↑/↓ y Enter en el drawer; ←/→ en las pestañas; Escape cierra el drawer modal, menús y diálogos y
  devuelve el foco a donde estaba. El diálogo atrapa el foco.
- Contraste: los pares rol/`on`-rol de M3 cumplen WCAG con cualquier semilla; no mezclar un rol con el `on` de otro.

## Libertades expresivas (criterios)

El carácter de Wysun sale de **formas, color de rol y muelles**, no de decoración:

- Un `ShapeEmblem` por vista como mucho (junto al título, en el estado vacío o en la carátula del reproductor), con
  `primaryContainer`/`secondaryContainer`/`tertiaryContainer` y su `on*`.
- Esquinas que cambian al pulsar o seleccionar (como `ButtonBase` del shell), indicadores que crecen con
  `fastSpatial`, entradas con `slowSpatial`.
- Nunca a costa de densidad útil en listas y rejillas grandes, ni de legibilidad.

## Correspondencia con el shell

| Base (`WysunM3`) | Shell (`apps/shell/components`) |
|---|---|
| `Theme.m3*` (de `ThemeFeed`) | `Colours.palette.m3*` |
| `Theme.rounding/spacing/padding/font/anim` | `Tokens.*` (plugin `Wysun.Config`) |
| `Anim`, `CAnim`, `SpringBehavior` (`kind`) | `Anim`/`CAnim` (`type: Anim.FastSpatial…`) |
| `StateLayer` | `StateLayer` |
| `controls/ButtonBase` (interno), `Button`, `IconButton` | `ButtonBase`, `TextButton`, `IconButton` |
| `Chip`, `SegmentedButtons` | `Chip`, `Segmented` |
| `Icon` | `MaterialIcon` |
| `ShapeEmblem` | `MaterialShape` de `M3Shapes` (`CoverArt`, `LoadingIndicator`) |

Mismo ritmo: los morfos de esquina, las duraciones y las curvas salen de los mismos tokens.

## Cómo extender

1. Crear el archivo en la subcarpeta que corresponda (`controls/`, `containers/`, `navigation/`, `feedback/`,
   `motion/`, `shapes/`) con `import QtQuick` e `import WysunM3`, y una cabecera que diga para qué es y cuándo usarlo.
2. Registrarlo en `qmldir` (`Nombre 1.0 carpeta/Nombre.qml`; `internal` si es una pieza auxiliar).
3. Medidas nuevas en `Metrics.qml` citando el token M3; colores solo de `Theme.m3*`; duraciones solo con `Motion`.
4. Pruebas en `tests/qml/check_<grupo>.py`: medidas, colores por rol (píxel), estados, teclado, movimiento reducido.
5. Un ejemplo en la galería (`apps/qml/gallery/pages/`): `check_gallery.py` falla si un componente exportado no
   aparece.
6. `check_purity.py` y `tests/test_theme_literals.py` pasan.

## Cómo lo adoptará el shell

1. Un adaptador fino en el shell: un `ThemeFeed` alimentado desde `Colours.palette` y `Tokens` (convertidos a la
   forma de `tokens.json`) y `reducedMotion` desde la apariencia.
2. `apps/shell/wysun/runtime.sh` añade `~/.local/share/wysun/qml` a `QML_IMPORT_PATH`.
3. Sustitución gradual de `qs.components` por `WysunM3` pieza a pieza, empezando por las que no dependen de servicios
   del shell (botones, chips, listas), comprobando cada cambio en la sesión real.

## Cómo probar

```sh
python3 installer/qml_runtime.py --prefix ~/.cache/wysun-fase1/qml-runtime   # venv de desarrollo (una vez)
python3 -m unittest tests.test_qml_runtime -v                                 # instalador + suites QML con el venv
<venv>/bin/python3 -m unittest discover -s tests/qml -t tests -p 'check_*.py' # solo las suites QML (offscreen)
<venv>/bin/python3 tests/qml/capture_matrix.py ~/.cache/wysun-fase1/matrix    # capturas: páginas × paletas × modos
python3 -m wysun_qml [--page lists] [--palette green --mode dark] [--shot x.png] [--bench]
```

Las suites usan `QT_QPA_PLATFORM=offscreen` (renderizador software) con `grabToImage`; `support.Harness` crea las
vistas, envía teclado y ratón y compara píxeles con los roles de las paletas de prueba (la base del wallpaper por
defecto y tres semillas sintéticas, en claro y oscuro). La ventana real se comprueba con la galería y `grim` sobre su
región.

## Límites conocidos

- Las superposiciones viven dentro de la ventana: un menú no puede salir de ella.
- `M3Shapes` no pinta con el renderizador software (pruebas offscreen); ahí `ShapeEmblem` usa su forma de respaldo.
- Sin `QtQuick.Controls`: no hay `ScrollBar` todavía (`Switch` y `Dropdown` ya existen); se añadirá como componente
  de la base cuando una app lo necesite.

## Hilos de Python en una app QML

Una app con hilos de Python llama a `wysun_qml.engine.collect_on_gui_thread()`: la recolección automática de ciclos corre
en el hilo que reserva memoria y podría destruir allí objetos Qt del hilo de la interfaz, con un fallo al azar. Además, un
`QMimeData` creado en Python no debe seguir en el portapapeles al apagarse el intérprete (véase
`wysun_files/quick/operations.py`).

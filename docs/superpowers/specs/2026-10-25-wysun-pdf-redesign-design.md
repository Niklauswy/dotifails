# Wysun PDF: rediseño técnico y de interfaz

Fecha: 2026-10-25 · Rama: `Niklauswy/wysun-pdf-redesign` · Brief: tarea `task_1adab435ff0b` del coordinador Orca.

El usuario pidió un rediseño técnico y visual del lector ("es muy básico"). No se pudo hacer la
sesión de brainstorming (el usuario dormía): el brief del coordinador es el documento aprobado y
todas las decisiones que no fija el brief las tomé yo. Cada una va marcada **[Decisión propia]**.

## 1. Punto de partida

- Una página a la vez, zoom con un combo ("Ajustar", 75…200 %, donde 100 % eran 800 px fijos).
- Raster PNG en base64 dentro de JSON: codificar el PNG cuesta ~220 ms por página de 1400 px
  (medido con PyMuPDF 1.26.7). Además, cada cambio de zoom vuelve a extraer el texto.
- Riel izquierdo + panel lateral pesado con miniaturas grandes, búsqueda y notas; barra inferior de
  estado; la paginación es una cápsula inferior.
- `pdf_material.py` es un segundo kit (`ReaderTheme`, `Metrics/M`, `Panel`, `Text`, `Action`, delegados,
  `Emblem`, `NoteDialog`). Duplica `wysun_core.ui`, y `ReaderTheme` es un segundo sistema de tema con
  roles propios.
- No tiene enlaces, vista de dos páginas ni memoria de posición. Las notas listadas son solo las de la página actual.

## 2. Objetivos

Los del brief: desplazamiento continuo virtualizado, zoom fluido anclado al cursor, vista de una y
de dos páginas, enlaces, búsqueda con resaltado y lista con contexto, selección entre líneas,
memoria de posición. Todo lo que ya funciona se conserva. La interfaz se rehace sobre `wysun_core.ui`.

Fuera de alcance: impresión, formularios, firmas, OCR, mosaicos (tiles) para zoom extremo, recoloreado
nocturno del papel.

## 3. Arquitectura

```
pdf_app.py        arranque (sin cambios de contrato: `wysun pdf [archivos]`, una ventana por documento)
pdf_engine.py     proceso aislado, MuPDF (protocolo ampliado, respuestas binarias)
pdf_worker.py     transporte asíncrono: cola con prioridad, claves, cancelación, tramas binarias
pdf_layout.py     geometría pura (sin Qt): rectángulos de página, visibles, ajustes de zoom, anclaje, raster máximo
pdf_cache.py      caché LRU de rasters acotada por bytes (sin Qt)
pdf_source.py     puente ventana↔motor: rasters e info de página, revisiones, cancelación (Qt, sin widgets)
pdf_view.py       DocumentView (QAbstractScrollArea): pinta solo lo visible, selección, enlaces, coincidencias
pdf_chrome.py     piezas propias del lector sobre el kit: grupos de controles, zoom, indicador de página,
                  barra contextual de anotación, emblema, diálogo de nota
pdf_sidebar.py    panel lateral plegable: Páginas, Índice, Notas, Resultados
pdf_state.py      memoria por documento y preferencias del lector (privadas, fuera del repo)
pdf_theme.py      capa fina sobre qt_theme: modo fijado del lector (sol/luna)
pdf_window.py     ventana: composición, atajos, flujo de apertura/guardado/anotación/búsqueda
```

`pdf_material.py` desaparece.

### 3.1 Motor y protocolo

- `open` devuelve también `sizes`: ancho y alto de cada página ya rotada, en puntos. Así la vista
  conoce toda la geometría sin renderizar nada. Cargar las páginas cuesta ~0,16 ms cada una.
  **[Decisión propia]**: se calcula al abrir; un documento de 10 000 páginas tarda ~1,6 s.
- `render(page, width)` devuelve solo el raster: cabecera `{page, width, height, stride}` y una
  **trama binaria** RGB888 tras la línea JSON (`"blob": n` bytes). **[Decisión propia]**: ~13 ms en
  lugar de ~220 ms del PNG, y la interfaz crea el `QImage` sin decodificar nada. Se mantiene el
  límite por raster: 8 MP y 2800 px de ancho (`pdf_layout.raster_width`, compartido con el cliente
  para que nunca pida más de lo que el motor entrega).
- `page_info(page)` devuelve palabras (con `block/line`), enlaces y anotaciones de la página. Se pide
  una vez por página y se cachea aparte del raster: el zoom no vuelve a extraer texto.
  - Enlaces: `{'rect', 'page', 'y'}` internos (incluye destinos con nombre que resuelve MuPDF), `{'rect','uri'}` externos.
- `search(page, text)` devuelve `hits` y, por cada coincidencia, `context`: la línea donde aparece,
  recortada alrededor del término.
- `annotations()` lista las anotaciones de todo el documento: página, xref, tipo, texto, rect.
- `thumbnail(page)` también usa trama binaria.
- `annotate/update_note/delete/save` no cambian, salvo que reciben la página explícita.

### 3.2 Transporte (`pdf_worker.py`)

- Una petición lleva `op`, `args`, `callback`, `priority` y `key` opcional.
- Cola estable por prioridad: 0 = interactivo (vista, ediciones, guardar, abrir), 1 = miniaturas,
  2 = búsqueda. Dentro de una misma prioridad se respeta el orden (las ediciones conservan su orden).
- `key`: la misma clave en la cola sustituye a la anterior (sin duplicados). `cancel(predicate)`
  quita de la cola las peticiones que ya no interesan. Lo que ya se está procesando en el motor
  termina, pero la fuente descarta su respuesta.
- Lectura en dos fases: primero la línea JSON y, si trae `blob`, después exactamente `n` bytes.
- Errores y caída del proceso como hoy.

### 3.3 Fuente de páginas (`pdf_source.py`) y virtualización

- `PageSource(worker)` guarda `RenderCache` (LRU por bytes, **[Decisión propia]**: 192 MiB,
  ~6 rasters de 8 MP; además ≤ 2 anchos por página) e `InfoCache` (LRU de 96 páginas de texto/enlaces).
- `want(pages_with_widths)`: la vista lo llama al hacer scroll, zoom o redimensionar con la lista
  ordenada de lo visible (primero) más el margen. Hace tres cosas:
  1. cancela las peticiones `render:*` encoladas que no estén en la lista (renders obsoletos);
  2. pide lo que falta en orden: visibles primero;
  3. pide `page_info` de las páginas visibles.
- Margen de precarga: **[Decisión propia]** media altura de ventana por arriba y por abajo.
- `image(page)` devuelve el raster exacto o, mientras llega, el más cercano de esa página escalado.
  Si no hay ninguno, la vista pinta el papel vacío.
- Ancho pedido: `round(ancho_en_pantalla × devicePixelRatio)`, cuantizado a 8 px y limitado por `raster_width`.
- Revisión por página: una edición la incrementa, invalida el raster y la info, y descarta las
  respuestas en vuelo de la revisión anterior. La generación de documento sigue descartando todo lo del documento anterior.
- Durante un zoom continuo (Ctrl+rueda) la vista escala lo que ya tiene y pide los rasters nuevos
  tras **120 ms** sin cambios **[Decisión propia]**.

### 3.4 Geometría (`pdf_layout.py`)

- Zoom = píxeles lógicos por punto PDF; **100 % = tamaño real a 96 ppp** (1 pt = 4/3 px)
  **[Decisión propia]**, sustituye los 800 px fijos. Rango 10 %–800 %.
- Modos `single` (una columna continua) y `spread` (dos páginas por fila: 1-2, 3-4…; **[Decisión propia]**:
  sin portada aislada). Las páginas de una fila se centran verticalmente; las filas, horizontalmente.
- Separación entre páginas y margen = tokens de espaciado (`space_l`, `space_xl`) leídos vía
  `wysun_core.ui.style.metric`.
- `fit_width` (fila más ancha) y `fit_page` (la fila actual cabe entera). El ajuste se recalcula al
  redimensionar mientras el modo de zoom sea `width`/`page`.
- `visible(top, bottom)` por búsqueda binaria sobre filas; `page_at(point)`.
- Anclaje: antes del zoom se toma (página, fracción x, fracción y) bajo el cursor. Después del
  zoom se recoloca el scroll para que ese punto quede bajo el mismo píxel. Con el teclado, el ancla es el centro de la ventana.

### 3.5 Vista (`pdf_view.py`)

- `DocumentView(QAbstractScrollArea)`; el viewport se pinta a mano. Solo recorre las filas visibles.
- Papel: rect blanco del raster. Debajo, una sombra sutil con el token `shadow`. El papel vacío usa `well`.
- Superposiciones en coordenadas de página: coincidencias (`accent`/60), la coincidencia actual
  (`accent`/110 con borde `focus`), la selección (`text_selection`).
- Selección: pulsar sobre texto fija el ancla (palabra más cercana, orden de lectura del motor).
  Arrastrar extiende el rango de palabras **dentro de la misma página**, entre líneas. Doble clic selecciona
  una palabra. Ctrl+C copia; las líneas se separan con salto de línea (usa `block/line`).
- Enlaces: el cursor cambia a mano y el tooltip muestra el destino. El clic sin arrastre activa el enlace.
- Teclado: flechas, AvPág/RePág, Espacio/Shift+Espacio, Inicio/Fin. Ctrl+rueda, Ctrl++/Ctrl+−, Ctrl+0 (ajustar al ancho).
- Señales: `pageChanged`, `zoomChanged`, `selectionChanged`, `selectionFinished`, `linkActivated`, `noteRequested`.
- Accesibilidad: nombre accesible con página y total; foco visible (anillo `focus` en el borde del área).

### 3.6 Memoria por documento (`pdf_state.py`)

- `$XDG_STATE_HOME/wysun/pdf-reader/positions.json` (`paths.state`, `jsonio.atomic_write_json`, 0600).
- Clave: SHA-256 de la ruta resuelta. **[Decisión propia]**: no se guardan nombres de archivo en claro.
  Valor: `{page, fx, fy, zoom_mode, zoom, view, t}`. Máximo 200 documentos; al pasarse se eliminan los más antiguos.
- Se guarda con retardo de 1 s al desplazarse y al cerrar. Al abrir se restaura cuando llega la geometría.
- Preferencias del lector en `$XDG_CONFIG_HOME/wysun/pdf-reader.json` (archivo existente): `mode`
  (sol/luna), `sidebar` (visible y pestaña) e `ink` (último color de anotación). Se conservan las claves desconocidas.

## 4. Tema

- `ReaderTheme` y sus roles desaparecen. Todo se pinta con `qt_theme.color()` y los tokens del kit.
- **Botón sol/luna** (se conserva porque leer en oscuro con el escritorio en claro, o al revés, tiene
  sentido). Pasa a ser un menú «Apariencia del lector»: *Como el escritorio* / *Claro* / *Oscuro*.
  **[Decisión propia]**: se añade «Como el escritorio», que antes no se podía recuperar.
  `pdf_theme.ReaderMode` es una capa fina. Si el modo fijado difiere del del escritorio, pone
  `WYSUN_THEME` en el entorno **del proceso del lector**, que es el mecanismo existente de paleta base,
  y llama a `qt_theme.refresh_widgets()`. Si coincide o sigue al escritorio, restaura el entorno
  original y se ven los colores del wallpaper. Escucha `on_theme_changed` para reevaluarlo. El modo
  contrario usa la paleta base, como hasta ahora. `xdg-open` recibe el entorno original.
- Tipografía, radios, espaciado y movimiento: `metric()`, `text_font()`, `tokens()` del kit. No se usan
  nombres de token sueltos fuera de esas funciones donde se pueda evitar: el plan 03 los renombra.
- Colores de anotación: el primero es el acento actual y los otros cuatro son clásicos de
  marcador (amarillo, verde, rosa, azul), declarados `theme-exception: muestra de color del usuario` porque se
  escriben en el PDF. «Otro…» abre el selector.

## 5. Interfaz

Lenguaje: el de Files y Music (M3 Expressive pintado). Ventana sin bordes (`FramelessResize` +
`WindowMotion`, material `paint_surface`). Contenido sobre un `Panel` elevado y controles del kit
(`IconButton`, `PillButton`, `SearchField`, `ElidedLabel`, `Toast`, `apply_kit_style`).

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ✕  ⊟  muestra.pdf •                 [🔍 Buscar en el documento   2/14 ˄ ˅]           │
│       6 páginas                          [− 125 % +] [▤|▥]  ✎  [💾 Guardar]  ⋮       │
├───────────────┬──────────────────────────────────────────────────────────────────────┤
│ ▦ ☰ ✎ 🔍      │                                                                      │
│ Páginas       │                ┌──────────── papel ────────────┐                     │
│ ┌──┐ ┌──┐     │                │   ▔▔▔▔ selección ▔▔▔▔         │                     │
│ │1 │ │2 │     │                │  ( ▮ ▁ ⧉ ● )  barra contextual│                     │
│ └──┘ └──┘     │                └───────────────────────────────┘                     │
│               │                          ( 3 / 6 )                                   │
└───────────────┴──────────────────────────────────────────────────────────────────────┘
```

- **Barra superior compacta** (una fila de 56 px que también arrastra la ventana): cerrar,
  mostrar/ocultar panel (F9), título con punto de cambios y subtítulo (páginas · solo lectura).
  Después, la búsqueda (campo `SearchField` que se ensancha con el foco, contador `n/m` y anterior/siguiente),
  el zoom (− / porcentaje con menú de ajustes y porcentajes / +), el modo de vista (grupo de dos
  conmutadores), la herramienta Nota, Guardar (`PillButton` relleno, activo solo con cambios) y el menú ⋮
  (Abrir, Guardar copia, Apariencia del lector, Atajos de teclado).
- **Panel lateral plegable** (244 px, mismo ancho que Files): cuatro pestañas de icono (Páginas,
  Índice, Notas, Resultados) con el nombre de la sección debajo.
  - Páginas: miniaturas ligeras (≤ 120 px), número debajo y anillo de acento en la página actual.
    Se piden solo las visibles, con caché de 48.
  - Índice: árbol sangrado del PDF. Clic o Enter salta.
  - Notas: **todas** las anotaciones del documento por página **[Decisión propia]**. Clic salta;
    Enter o doble clic edita la nota; Supr o botón Eliminar.
  - Resultados: una fila por coincidencia con la página y el contexto; el término va en negrita.
- **Indicador flotante de página** (cápsula inferior centrada): «3 / 6». Clic o Ctrl+G lo convierte en campo para saltar.
- **Barra contextual de anotación**: una cápsula flotante sobre la selección con Resaltar,
  Subrayar, Copiar y el color. Solo aparece si hay selección; en documentos de solo lectura queda solo Copiar.
- **Mensajes**: `Toast` del kit en lugar de la línea de estado.
- **Vacío**: emblema cookie M3 con el glifo de libro, «Abre un PDF», botón relleno y la pista
  «o arrastra un archivo aquí».
- **Accesibilidad**: todo control tiene nombre accesible y tooltip con su atajo, y foco visible.
  Los atajos documentados se mantienen.

### Atajos

Ctrl+O abrir · Ctrl+S guardar · Ctrl+Shift+S guardar copia · Ctrl+F buscar · Enter/Shift+Enter
siguiente/anterior coincidencia (en el campo; F3/Shift+F3 en cualquier sitio) · Esc limpia la selección o la búsqueda ·
Ctrl+C copiar · Ctrl+H resaltar · Ctrl+U subrayar · Ctrl+G ir a página · Alt+←/→ o AvPág/RePág página
anterior/siguiente · Inicio/Fin · Ctrl+rueda, Ctrl++, Ctrl+− zoom · Ctrl+0 ajustar al ancho ·
Ctrl+9 ajustar a la página **[Decisión propia]** · Ctrl+2 alterna una/dos páginas **[Decisión propia]** · F9 panel · Ctrl+Q / Ctrl+W cerrar.

## 6. Enlaces externos

Antes de abrir un enlace externo se pide confirmación mostrando la URL completa. Solo se admiten
`http`, `https` y `mailto` **[Decisión propia]**. Otros esquemas (`file:`, `javascript:`, lanzadores)
se rechazan con un aviso. Se abren con `xdg-open` mediante `QProcess.startDetached`, con el entorno original.

## 7. Seguridad y guardado

Sin cambios de semántica: escritura atómica de `wysun_core.jsonio.atomic_path`, huella contra
cambios externos, cifrado conservado, confirmación de descarte al cerrar o abrir otro documento,
una ventana por documento, arrastrar y soltar.

## 8. Pruebas

- `tests/pdf/test_layout.py`: geometría, visibles, ajustes, anclaje, modo dos páginas, `raster_width`.
- `tests/pdf/test_cache.py`: presupuesto en bytes, LRU y mejor raster.
- `tests/pdf/test_engine.py`: tamaños, raster binario, `page_info` con enlaces internos y externos,
  contexto de búsqueda, lista de anotaciones y los casos existentes.
- `tests/pdf/test_worker.py`: tramas binarias, prioridad y cancelación con el motor real.
- `tests/pdf/test_state.py`: memoria por documento, límite y permisos.
- `tests/pdf/test_window.py`: flujo real con widgets.
  - Virtualización: en un documento de 60 páginas, ningún render fuera de visibles ± margen.
  - Zoom que conserva el punto, modo dos páginas, enlace interno, enlace externo con confirmación simulada.
  - Búsqueda con resaltado y Enter/Shift+Enter, recordar la posición.
  - Anotar, guardar y reabrir.
  - Capturas con `WYSUN_PDF_SCREENSHOTS`.
- `tests/test_pdf_theme.py` (sin PyMuPDF): modo fijado vía capa fina, persistencia, glifos del lector presentes en la fuente.

## 9. Riesgos

- Zoom > ~2800 px de raster: la imagen se escala (algo borrosa). Sin mosaicos en esta versión.
- `WYSUN_THEME` en el entorno del proceso afecta a los hijos: el motor lo ignora y `xdg-open` recibe el entorno original.
- Plan 03 (renombrado de tokens) en paralelo: se usan los accesores del kit para minimizar el choque y se rebasa al final.

## 10. Capturas y comparación

`pdf-shots/` (1280 × 860, offscreen, `tests/pdf/shots.py`): `before-dark.png` es el lector anterior.
`base-{light,dark}-{reader,search,spread,empty}.png` usan las paletas base; `teal-*` y `amber-*` usan
esquemas generados con `wysun_scheme.generate_dynamic` a partir de dos fondos sintéticos.

| Antes (`before-dark.png`) | Ahora (`base-dark-reader.png`, `base-*-search.png`, `base-*-spread.png`) |
|---|---|
| Riel de 80 px, panel lateral con miniaturas grandes y cabecera alta con emblema: menos de la mitad del ancho es documento | Barra superior de una fila, panel plegable de 244 px y escenario con el documento: la página ocupa el ~75 % del ancho |
| Una página a la vez, flechas abajo y combo «Ajustar» | Desplazamiento continuo, indicador flotante «1 / 6» que salta de página y zoom −/%/+ con menú de ajustes |
| Barra de herramientas de anotación siempre visible y modal (seleccionar/resaltar/subrayar/nota) | Barra contextual sobre la selección; la herramienta Nota está en la barra superior |
| Búsqueda en una pestaña del riel con lista «Página N · k coincidencias» | Campo en la barra superior con contador y ↑/↓; resultados con la línea de contexto y el término destacado; coincidencias resaltadas en el papel |
| Línea de estado fija abajo | Toast del kit |

## 11. Revisión final y pendientes

La revisión final (2026-10-25) encontró dos fallos que se corrigieron con su prueba: los mensajes de
MuPDF salían por el stdout del protocolo y desfasaban las respuestas con PDFs dañados, y las miniaturas
no arrancaban al abrir otro documento en la misma ventana. También se corrigieron Esc en la búsqueda,
el retardo de 120 ms del zoom y la lista de atajos de `docs/pdf-reader.md`.

Pendientes menores, para el rediseño sobre la nueva base de componentes:

- Cerrar la ventana se rechaza mientras `busy` también al abrir o editar; con un motor colgado no se
  puede cerrar. Bloquear solo durante `save` o pedir confirmación y matar el worker.
- Un error del motor en la búsqueda abre un `QMessageBox` por página y corta la búsqueda sin marcarla
  como terminada. Usar un toast y continuar.
- Si el motor se cae, `PdfWorker.failed` puede emitirse dos veces (`errorOccurred` y `finished`).
- `pdf_state.clamp` no tolera valores no numéricos en `positions.json`; un archivo corrupto rompe la
  apertura. Envolver en `try/except (TypeError, ValueError)` y no restaurar.
- Medidas literales fuera de tokens: `CONTROL = 38`, botones de 34/40 px, alturas 44/40, búsqueda de
  280 px, `WIDTH = 244`, celdas de miniatura 104×168 y 112×172, desplazamientos 4/6/22/26/9 px, trazos
  de 2 y 3 px, `Toast(duration=3200, bottom=112)`. Derivarlas de `metric()` o de métricas de componente
  cuando exista la nueva base.
- No verificado sin ejecución: coordenadas en páginas rotadas fuera de las pruebas, `PDF_ENCRYPT_KEEP`
  en el guardado de PDFs con contraseña y el valor real de `QProcess.startDetached` (las pruebas lo simulan).
- Pendiente del plan: rebase sobre `main` (adoptar los tokens renombrados si llegó el plan 03) y repetir
  todas las suites.

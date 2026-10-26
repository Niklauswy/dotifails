# Wysun PDF

Lector local de Linux en `apps/python/wysun_pdf/`, construido sobre el kit compartido `wysun_core.ui`
(controles, paneles, toasts, ventana sin bordes) y los tokens del tema, como Files y Music. Sigue en vivo el modo y los colores del
wallpaper. Se abre con `wysun pdf [archivo.pdf ...]`, desde la entrada **Wysun PDF** de aplicaciones o
arrastrando un PDF a la ventana. Cada documento abre su propia ventana. No registra una asociación
predeterminada sin pedirla.

## Biblioteca y espacio de estudio

Sin argumentos, la aplicación abre la biblioteca: continuar la última lectura, buscar por título,
abrir un PDF y volver a los documentos recientes. Alt+Home vuelve a ella sin cerrar el documento que
estabas leyendo. Las aperturas nuevas crean el historial; las rutas no pueden reconstruirse desde los
hashes del almacén antiguo de posiciones. Ajustes permite desactivar o limpiar los recientes sin borrar
los originales ni las notas.

La cabecera agrupa zoom, una/dos páginas y nota PDF bajo **Lectura**. La búsqueda se abre con Ctrl+F
(o la lupa). **Guardar PDF** aparece cuando hay anotaciones pendientes. A la derecha están Cuaderno
y Sesión. El panel de páginas/índice/anotaciones PDF/resultados sigue disponible mediante F9.
Un solo panel auxiliar se muestra a la vez. En ventanas estrechas el panel de estudio ocupa el área
central; al cerrarlo vuelve el documento, evitando reducir el texto a una columna ilegible.

La selección ofrece resaltar, subrayar, copiar, color, **Nota** y **Consultar**. Las dos últimas acciones
abren el cuaderno y la consulta lateral. El contenido PDF y sus colores originales se conservan.

### Cuaderno

Ctrl+Shift+N o Nota guarda una reflexión/pregunta junto a la cita, página y posición del pasaje.
El botón **Guardar nota** escribe en la biblioteca local; no modifica el PDF. Todavía no hay autosave:
los cambios pendientes se pueden guardar, descartar o conservar al cancelar una navegación/cierre.
Las ediciones concurrentes no se sobrescriben: si otra ventana cambió la nota, el editor conserva tu
texto y ofrece guardarlo como una entrada nueva. El cuaderno se exporta a Markdown con página y fuente.

Los datos viven en `$XDG_DATA_HOME/wysun/pdf-reader/study.sqlite3` (0600). Esta base contiene rutas
para permitir reabrir recientes, a diferencia de `positions.json`. Quitar un reciente conserva sus notas.
Guardar una copia del PDF abre un cuaderno distinto. Si el archivo cambió desde que se guardó una cita,
volver al pasaje pide confirmar un salto aproximado a la página; no afirma haber reconciliado el texto.

### Traducción y referencias

Consultar permite elegir **Traducir** o **Concepto** y alternar EN/ES. Abrir el panel o seleccionar texto
no inicia ninguna petición. Al pulsar Buscar por primera vez para cada proveedor, se muestra exactamente
el fragmento que se enviará y se pide consentimiento; se revoca en Ajustes → Consultas online.

- Traducción: MyMemory, un fragmento de hasta 500 bytes UTF-8, un párrafo. El servicio tiene cuota
  gratuita limitada; un fallo/cuota agotada se muestra sin bloquear la lectura.
- Concepto: búsqueda de hasta tres referencias de Wikipedia en el idioma elegido, con fragmento,
  título, URL y atribución. Son resultados de búsqueda, no una explicación generada ni un consenso.
- Abrir fuente utiliza el navegador externo. Guardar en cuaderno conserva fuente, URL, idioma,
  fecha y el ancla del pasaje desde el que se abrió la consulta, aunque luego cambie la página visible.

La consulta usa un proceso auxiliar `wysun_pdf.lookup_worker` y la biblioteca estándar HTTPS de Python:
no necesita `PySide6.QtNetwork`, WebEngine ni paquetes adicionales. Tiene timeout global de 15 segundos,
respuesta HTTP máxima de 64 KiB y cancelación al cambiar consulta/documento/panel. Los redirects se rechazan.
Los resultados se muestran como texto, sin ejecutar HTML remoto. No se envían el archivo PDF ni el cuaderno.

Documentación de proveedores: [API MyMemory](https://mymemory.translated.net/doc/spec.php),
[límites](https://mymemory.translated.net/doc/usagelimits.php),
[condiciones](https://mymemory.translated.net/terms-and-conditions) y
[MediaWiki REST](https://www.mediawiki.org/wiki/API:REST_API/Reference/en).

### Sesiones de concentración

Sesión abre un temporizador de estudio (25 minutos por defecto) y descanso (5), ajustables, con objetivo
opcional. Permite empezar, pausar, reanudar, terminar y anotar lo aprendido. El reloj queda en la cabecera
al cerrar el panel. No inicia automáticamente al abrir un libro ni impide seguir leyendo al terminar.

El estado se guarda en `$XDG_STATE_HOME/wysun/pdf-reader/focus.json`. Las ventanas del proceso comparten
una sesión; un bloqueo impide propietarios simultáneos en procesos diferentes. Cerrar la última ventana
pausa la sesión. Tras suspensión/interrupción se recupera pausada, sin atribuir tiempo no observado al
estudio. No hay aún historial de sesiones ni ciclo automático de cuatro bloques/descanso largo.

### Movimiento y validación visual

La navegación biblioteca/lector anima una captura temporal de la vista saliente; no vuelve a renderizar
el PDF en cada fotograma. Los paneles usan transiciones de opacidad, y la ilustración de biblioteca tiene
movimiento finito al hover. Todo usa tokens del kit y respeta `WYSUN_REDUCED_MOTION`/ajustes del escritorio.
Las capturas de `docs/design/pdf-study-shots/` se generan con PDFs y fondos sintéticos; las de consulta
identifican explícitamente los resultados simulados. No son evidencia de despliegue en el escritorio.

Pendientes del diseño completo: colecciones, cuaderno global, repaso pregunta/respuesta, borradores
recuperables, relocalización de archivos movidos y métricas/historial de estudio. No se presentan como
funciones disponibles en esta versión.

## Lectura

- **Desplazamiento continuo** de todo el documento, en una columna o en dos páginas por fila
  (1-2, 3-4…; Ctrl+2 alterna).
- **Zoom** del 10 % al 800 %. El 100 % es el tamaño real a 96 ppp. Ajustar al ancho (Ctrl+0, por
  defecto) o a la página (Ctrl+9). Ctrl+rueda, Ctrl++ y Ctrl+− conservan el punto bajo el cursor o el centro.
- **Enlaces**: los internos saltan a su destino. Los externos (`http`, `https`, `mailto`) piden
  confirmación mostrando la dirección completa y se abren con `xdg-open`. Se rechazan los demás esquemas
  (`file:`, `javascript:`…).
- **Búsqueda** (Ctrl+F) mientras escribes, en todo el documento: resalta las coincidencias en las páginas,
  marca la actual y salta a la primera desde la página donde estás. Enter / Shift+Enter (o F3 / Shift+F3)
  pasan a la siguiente o la anterior; Esc limpia.
- **Selección** arrastrando sobre el texto, entre líneas dentro de una página; un doble clic selecciona una
  palabra. Ctrl+C copia, con saltos de línea.
- **Memoria por documento**: página, posición, zoom y modo de vista se restauran al reabrir.
  Se guardan en `$XDG_STATE_HOME/wysun/pdf-reader/positions.json` (0600) con la ruta resumida en SHA-256,
  sin nombres de archivo, y como máximo 200 documentos.

## Anotaciones y guardado

- Resaltado (Ctrl+H) y subrayado (Ctrl+U) de la selección; sin selección, el siguiente arrastre se anota.
  Las notas se colocan con la herramienta Nota y un clic en la página.
- Ctrl+S guarda; Ctrl+Shift+S guarda una copia y sigue trabajando sobre ella (como «Guardar como»). Las anotaciones son objetos PDF nativos, legibles en otros
  lectores; no se almacenan en archivos auxiliares. El color de una anotación se fija al crearla.

## Apariencia del lector (antiguo botón sol/luna)

Menú ⋮ → *Apariencia del lector*: *Como el escritorio* (por defecto), *Claro* u *Oscuro*. Se guarda en
`$XDG_CONFIG_HOME/wysun/pdf-reader.json` junto con el panel lateral y el último color de anotación.
`wysun_pdf.theme.ReaderMode` es una capa fina sobre `qt_theme`, no un segundo tema. Un modo distinto al del escritorio activa
la paleta base de ese modo (`WYSUN_THEME`) solo en el proceso del lector, sin los colores del wallpaper.
Fijar el mismo modo que el escritorio conserva esos colores. Los programas que abre el lector (`xdg-open`)
reciben el entorno original. El papel y el contenido del PDF conservan los colores del documento.

### Atajos

Ctrl+O abrir · Ctrl+S guardar · Ctrl+Shift+S copia · Ctrl+F buscar · Enter/Shift+Enter, F3/Shift+F3
coincidencias · Esc limpiar · Ctrl+C copiar · Ctrl+H resaltar · Ctrl+U subrayar · Ctrl+G ir a página ·
Alt+←/→ página anterior/siguiente · RePág/AvPág, Espacio/Shift+Espacio desplazan una pantalla · Inicio/Fin ·
Ctrl+rueda, Ctrl++/− zoom · Ctrl+0 ancho · Ctrl+9 página · Ctrl+2 una/dos páginas · F9 panel · F1 atajos ·
Ctrl+Shift+N reflexión · Alt+Home biblioteca · Ctrl+W / Ctrl+Q cerrar.

La selección usa el orden de lectura del motor y coordenadas de palabras, compensando la rotación de la
página. Los PDFs escaneados sin capa de texto se pueden leer y anotar con notas, pero no buscar ni subrayar;
no hay OCR integrado. No hay impresión, formularios ni firmas digitales.

## Motor, virtualización y seguridad de guardado

`wysun_pdf.worker` mantiene un único proceso `wysun_pdf.engine` por ventana. MuPDF se usa exclusivamente allí:
apertura, extracción, renderizado, búsqueda y escritura no ejecutan trabajo PDF en el hilo de interfaz.

- **Protocolo**: una línea JSON por respuesta. Los rasters (RGB888) siguen como trama binaria de `blob`
  bytes, sin PNG ni base64: unos 13 ms frente a ~220 ms por página de 1400 px. `open` devuelve el tamaño
  de todas las páginas, así la vista distribuye el documento sin renderizarlo. `page_info` (palabras,
  enlaces, anotaciones) se pide una vez por página y no se repite al cambiar el zoom.
- **Cola**: estable por prioridad (interactivo, miniaturas, búsqueda), con claves que evitan duplicados
  y cancelación de lo encolado que ya no sirve.
- **Virtualización** (`wysun_pdf.source`, `wysun_pdf.view`): solo se piden las páginas visibles, primero, y
  media ventana por encima y por debajo. Al desplazarse o hacer zoom se cancelan los renders encolados
  de páginas que ya no interesan, y se descartan las respuestas de otro documento o de una página editada
  desde entonces. Durante el zoom se escala lo que ya hay y se piden rasters nítidos tras 120 ms. El ancho
  pedido tiene en cuenta `devicePixelRatio`.
- **Límites de memoria**: cada raster tiene como máximo 8 megapíxeles y 2800 px de ancho (`wysun_pdf.layout.raster_width`;
  por encima se escala). La caché de rasters ocupa como máximo 192 MiB y guarda hasta dos anchos por página.
  Se guarda el texto de 96 páginas y 48 miniaturas de hasta 120 px de ancho.

El guardado usa la escritura atómica de `wysun_core` (temporal en el directorio del destino,
sincronizado y sustituido de golpe, conservando los permisos del archivo). La huella de dispositivo, inode, tamaño y mtime
permite rechazar modificaciones externas habituales; no es un bloqueo contra
escrituras concurrentes de otros programas. Se conserva el cifrado. Ante un error
se mantiene el documento abierto y su estado sin guardar. Cerrar o abrir otro PDF
pide confirmar el descarte cuando hay cambios. Un fallo del proceso desactiva el lector y lo avisa:
no existe recuperación automática de anotaciones sin guardar.

## Dependencia y distribución

PySide6 ya forma parte de Wysun. El motor adicional es **PyMuPDF**, paquete Debian
`python3-fitz`, declarado en los componentes desktop y wayland del manifiesto.
`--wysun-only` despliega código y entrada de aplicaciones, pero no instala esta
dependencia. Si falta, el lector lo comunica antes de arrancar. Si el paquete del sistema no está disponible, el lector también admite un venv
con PyMuPDF en `$XDG_DATA_HOME/wysun/pdf-runtime`: lo selecciona al arrancar. Se crea sin tocar
el sistema:

```sh
python3 -m venv --system-site-packages ~/.local/share/wysun/pdf-runtime
~/.local/share/wysun/pdf-runtime/bin/pip install PyMuPDF==1.26.7
```

No se instala ninguna dependencia automáticamente al abrir un PDF.

Verificación sin modificar paquetes del host:

```sh
python3 -m venv --system-site-packages /tmp/wysun-pdf-venv
/tmp/wysun-pdf-venv/bin/pip install PyMuPDF==1.26.7
PYTHONPATH=apps/python /tmp/wysun-pdf-venv/bin/python -P -m wysun_pdf
QT_QPA_PLATFORM=offscreen /tmp/wysun-pdf-venv/bin/python -m unittest discover -s tests/pdf -v
```

Usar HOME/XDG temporales para las pruebas. `WYSUN_PDF_SCREENSHOTS=/tmp/pdf-screens`
exporta capturas de los dos modos durante la prueba de interfaz. `tests/pdf` cubre el motor (tramas
binarias, enlaces, contexto de búsqueda, rotaciones, contraseña, permisos, conflictos externos), el
transporte (prioridad, claves, cancelación), la geometría, la caché, la memoria por documento, la vista
(virtualización, zoom anclado, dos páginas, selección, enlaces) y la ventana real (anotar y guardar,
búsqueda con Enter/Shift+Enter, enlaces con confirmación, posición recordada, caída del motor).
`tests/test_pdf_theme.py` (sin PyMuPDF) comprueba la capa de apariencia y los widgets del lector en
claro y oscuro.

## Evidencia

- Rediseño de 2026-10-25: diseño en `docs/superpowers/specs/2026-10-25-wysun-pdf-redesign-design.md`,
  capturas en `docs/superpowers/specs/pdf-shots/`.
- Medición del motor anterior en proceso nuevo, PyMuPDF 1.26.7, PDF sintético de 500 páginas
  de texto: apertura 1,3 ms; búsqueda de todas las páginas 2,90 s; RSS máximo del proceso 66,7 MiB.
  Con el protocolo binario, un raster de 1400 px tarda ~40 ms en rasterizar y ~13 ms en copiarse, frente
  a ~220 ms del PNG. Calcular los tamaños de 500 páginas al abrir cuesta ~80 ms. No es una garantía
  para documentos escaneados o complejos ni incluye la memoria de Qt.
- Las pruebas del lector se omiten sin PyMuPDF (`tests/pdf` exige `fitz`): ejecútalas con el venv de arriba.

## Integración en el escritorio

La orden `wysun pdf` y la entrada
`wysun-pdf.desktop` ya están conectados en el instalador. El lanzador del shell
indexa esa entrada como cualquier aplicación; no requiere plugin QML/C++ nuevo.

1. Instalar `python3-fitz` con el gestor de paquetes, con autorización explícita
   para modificar dependencias del host. No lo hace `--wysun-only`.
2. Desde este checkout, ejecutar `./instalar.sh --wysun-only` y revisar que no
   haya conflictos. El instalador crea los respaldos correspondientes.
3. Ejecutar `wysun reload` en la sesión gráfica.
4. Abrir **Wysun PDF** desde el lanzador y probar `wysun pdf /ruta/documento.pdf`;
   crear una anotación, guardar una copia y reabrirla.

La asociación predeterminada es opcional. Tras decidir usar este lector para
los PDFs: `xdg-mime default wysun-pdf.desktop application/pdf`.
No se han modificado los atajos ni se ha cambiado esa asociación automáticamente.

La guía visual es la de las apps hermanas (M3 Expressive pintado): controles totalmente redondeados,
superficies tonales y la forma expresiva (cookie) reservada para la identidad. Los controles se pintan con
el kit `wysun_core.ui` para que el estilo nativo del host no cambie su forma ni su contraste.

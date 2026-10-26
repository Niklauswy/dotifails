# Wysun PDF

Lector local de Linux en `apps/python/pdf_*`, construido sobre el kit compartido `wysun_core.ui`
(controles, paneles, toasts, ventana sin bordes) y los tokens del tema, como Files y Music. Sigue en vivo el modo y los colores del
wallpaper. Se abre con `wysun pdf [archivo.pdf ...]`, desde la entrada **Wysun PDF** de aplicaciones o
arrastrando un PDF a la ventana. Cada documento abre su propia ventana. No registra una asociación
predeterminada sin pedirla.

## Interfaz

- **Barra superior compacta** (también arrastra la ventana): cerrar, panel lateral, título con punto de
  cambios y número de páginas. Le siguen la búsqueda con contador y anterior/siguiente, el zoom
  (− / porcentaje con menú de ajustes y porcentajes / +), el modo de vista (una página continua o dos
  páginas), la herramienta Nota, Guardar (activo solo con cambios) y el menú ⋮ (Abrir, Guardar una copia,
  Apariencia del lector, Atajos).
- **Panel lateral plegable** (F9, se recuerda) con cuatro pestañas: *Páginas* (miniaturas
  bajo demanda), *Índice* (el del PDF), *Notas* (todas las anotaciones del documento: clic salta,
  Enter o doble clic edita, Supr o Eliminar borra) y *Resultados* (cada coincidencia con su página y la
  línea donde aparece, con el término destacado).
- **Indicador flotante de página** («3 / 40»): clic o Ctrl+G para escribir la página.
- **Barra contextual** sobre la selección: Resaltar, Subrayar, Copiar y el color de la anotación
  (acento del tema o cuatro colores de marcador; «Otro color…» abre el selector). En documentos de solo
  lectura solo queda Copiar.
- Los mensajes salen en el toast del kit. Sin documento se muestra un estado vacío con «Abrir un PDF».

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
`pdf_theme.ReaderMode` es una capa fina sobre `qt_theme`, no un segundo tema. Un modo distinto al del escritorio activa
la paleta base de ese modo (`WYSUN_THEME`) solo en el proceso del lector, sin los colores del wallpaper.
Fijar el mismo modo que el escritorio conserva esos colores. Los programas que abre el lector (`xdg-open`)
reciben el entorno original. El papel y el contenido del PDF conservan los colores del documento.

### Atajos

Ctrl+O abrir · Ctrl+S guardar · Ctrl+Shift+S copia · Ctrl+F buscar · Enter/Shift+Enter, F3/Shift+F3
coincidencias · Esc limpiar · Ctrl+C copiar · Ctrl+H resaltar · Ctrl+U subrayar · Ctrl+G ir a página ·
Alt+←/→ página anterior/siguiente · RePág/AvPág, Espacio/Shift+Espacio desplazan una pantalla · Inicio/Fin ·
Ctrl+rueda, Ctrl++/− zoom · Ctrl+0 ancho · Ctrl+9 página · Ctrl+2 una/dos páginas · F9 panel · F1 atajos ·
Ctrl+W / Ctrl+Q cerrar.

La selección usa el orden de lectura del motor y coordenadas de palabras, compensando la rotación de la
página. Los PDFs escaneados sin capa de texto se pueden leer y anotar con notas, pero no buscar ni subrayar;
no hay OCR integrado. No hay impresión, formularios ni firmas digitales.

## Motor, virtualización y seguridad de guardado

`pdf_worker.py` mantiene un único proceso `pdf_engine.py` por ventana. MuPDF se usa exclusivamente allí:
apertura, extracción, renderizado, búsqueda y escritura no ejecutan trabajo PDF en el hilo de interfaz.

- **Protocolo**: una línea JSON por respuesta. Los rasters (RGB888) siguen como trama binaria de `blob`
  bytes, sin PNG ni base64: unos 13 ms frente a ~220 ms por página de 1400 px. `open` devuelve el tamaño
  de todas las páginas, así la vista distribuye el documento sin renderizarlo. `page_info` (palabras,
  enlaces, anotaciones) se pide una vez por página y no se repite al cambiar el zoom.
- **Cola**: estable por prioridad (interactivo, miniaturas, búsqueda), con claves que evitan duplicados
  y cancelación de lo encolado que ya no sirve.
- **Virtualización** (`pdf_source.py`, `pdf_view.py`): solo se piden las páginas visibles, primero, y
  media ventana por encima y por debajo. Al desplazarse o hacer zoom se cancelan los renders encolados
  de páginas que ya no interesan, y se descartan las respuestas de otro documento o de una página editada
  desde entonces. Durante el zoom se escala lo que ya hay y se piden rasters nítidos tras 120 ms. El ancho
  pedido tiene en cuenta `devicePixelRatio`.
- **Límites de memoria**: cada raster tiene como máximo 8 megapíxeles y 2800 px de ancho (`pdf_layout.raster_width`;
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
/tmp/wysun-pdf-venv/bin/python bin/wysun pdf
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

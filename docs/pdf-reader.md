# Wysun PDF

Lector local de Linux en `apps/wysun/pdf_*`, con controles y superficies Material 3 Expressive.
Colores, formas, espaciado, tipografía y movimiento son los tokens compartidos de Wysun (`wysun_core`):
el lector sigue en vivo el modo y los colores del wallpaper, como el resto de las apps. Solo el botón de
sol/luna le da una elección propia (ver abajo). Se abre con `wysun pdf [archivo.pdf ...]`, desde la entrada
**Wysun PDF** de aplicaciones, o arrastrando un PDF a la ventana. Cada documento
abre su propia ventana. No registra una asociación predeterminada sin pedirla.

## Lectura y anotaciones

- Miniaturas de páginas bajo demanda, índice del PDF, zoom y ajuste al ancho.
- Búsqueda progresiva en todo el documento, con resultados por página.
- Arrastrar sobre texto para seleccionarlo; Ctrl+C copia la selección.
- Resaltado (Ctrl+H), subrayado (Ctrl+U) y notas colocadas con un clic.
- Selector de color para las anotaciones y panel de notas de la página actual,
  con edición y eliminación.
- Ctrl+S guarda; Ctrl+Shift+S guarda una copia. Las anotaciones son objetos PDF
  nativos, legibles en otros lectores; no se almacenan en archivos auxiliares.
- Ctrl+O abre, Ctrl+F busca, Alt+←/→ cambia de página, F9 oculta la navegación.
- Mientras no se use el botón de sol/luna, el lector sigue el modo del escritorio. Al pulsarlo fija claro u oscuro
  solo para el lector, en vivo, y lo guarda en `$XDG_CONFIG_HOME/wysun/pdf-reader.json`. El modo contrario al del
  escritorio usa la paleta base, sin los colores del wallpaper. El contenido y el papel del PDF
  conservan los colores del documento; el color de una anotación se fija al crearla.

La selección usa el orden de lectura del motor y coordenadas de palabras,
compensando la rotación de la página. El texto inclinado dentro de una página
puede tener cajas de selección más amplias. Los PDFs escaneados sin capa de texto
se pueden leer y anotar con notas, pero no buscar ni subrayar como texto; no hay OCR
integrado. Esta versión usa navegación de una página a la vez, sin impresión,
formularios, firmas digitales ni seguimiento de enlaces.

## Motor y seguridad de guardado

`pdf_worker.py` mantiene un único proceso `pdf_engine.py` por ventana. MuPDF se
usa exclusivamente allí; apertura, extracción, renderizado, búsqueda y escritura
no ejecutan trabajo PDF en el hilo de interfaz. Las solicitudes se serializan y
los renders pendientes se sustituyen por el último. La búsqueda avanza página a
página, cediendo entre solicitudes. La ventana descarta respuestas de renders
anteriores. No hay precarga del documento completo: se conserva un raster actual,
limitado a 8 megapíxeles y 2800 píxeles de ancho, más el texto de esa página.
Las miniaturas se solicitan según la zona visible, una a la vez, con una caché
limitada a 48 imágenes de hasta 160 × 210 píxeles.

El guardado usa la escritura atómica de `wysun_core` (temporal en el directorio del destino,
sincronizado y sustituido de golpe, conservando los permisos del archivo). La huella de dispositivo, inode, tamaño y mtime
permite rechazar modificaciones externas habituales; no es un bloqueo contra
escrituras concurrentes de otros programas. Se conserva el cifrado. Ante un error
se mantiene el documento abierto y su estado sin guardar. Cerrar o abrir otro PDF
pide confirmar el descarte cuando hay cambios. Un fallo del proceso muestra un
error: no existe recuperación automática de anotaciones sin guardar.

## Dependencia y distribución

PySide6 ya forma parte de Wysun. El motor adicional es **PyMuPDF**, paquete Debian
`python3-fitz`, declarado en los componentes desktop y wayland del manifiesto.
`--orbit-only` despliega código y entrada de aplicaciones, pero no instala esta
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
exporta capturas de los dos modos durante la prueba de interfaz. Los tests
cubren anotaciones y guardado real, rotaciones, contraseña, permisos, conflictos
externos y el flujo asíncrono de selección/búsqueda/guardado/cambio de tema.

## Evidencia

- Las ocho pruebas del lector (`tests/pdf`) pasan con el venv de PyMuPDF y HOME/XDG temporales; incluyen
  interacción real de widgets con un PDF sintético, guardado y reapertura, rotaciones, contraseña, permisos,
  conflictos externos y el cambio de modo en vivo. Se revisaron capturas en claro y oscuro.
- Sobre el árbol integrado con `main` pasan la suite general, `tests/wysun_app`, `tests/shell_bridge`,
  `tests/utility_ui.py` y `tests/check_manifest.py`, incluidas las guardas de tema (`test_theme_literals`)
  y de IO (`test_core_owns_io`).
- Medición del motor en proceso nuevo, PyMuPDF 1.26.7, PDF sintético de 500 páginas
  de texto: apertura 1,3 ms; primer raster de 1400 px 141,5 ms; búsqueda de todas
  las páginas 2,90 s; RSS máximo del proceso 66,7 MiB. No es una garantía para
  documentos escaneados o complejos ni incluye la memoria de Qt.
- Las pruebas del lector se omiten sin PyMuPDF (`tests/pdf` exige `fitz`): ejecútalas con el venv de arriba.

## Integración en el escritorio

La ruta pública `wysun pdf`, el wrapper `wysun-pdf` y la entrada
`wysun-pdf.desktop` ya están conectados en el instalador. El lanzador del shell
indexa esa entrada como cualquier aplicación; no requiere plugin QML/C++ nuevo.

1. Instalar `python3-fitz` con el gestor de paquetes, con autorización explícita
   para modificar dependencias del host. No lo hace `--orbit-only`.
2. Desde este checkout, ejecutar `./instalar.sh --orbit-only` y revisar que no
   haya conflictos. El instalador crea los respaldos correspondientes.
3. Ejecutar `~/.local/bin/orbit reload` en la sesión gráfica.
4. Abrir **Wysun PDF** desde el lanzador y probar `wysun pdf /ruta/documento.pdf`;
   crear una anotación, guardar una copia y reabrirla.

La asociación predeterminada es opcional. Tras decidir usar este lector para
los PDFs: `xdg-mime default wysun-pdf.desktop application/pdf`.
No se han modificado los atajos ni se ha cambiado esa asociación automáticamente.

La guía visual usada es https://m3.material.io/styles/shape/overview-principles:
formas con jerarquía, controles totalmente redondeados, superficies tonales y
énfasis expresivo reservado para la identidad. `pdf_material.py` pinta los controles
para evitar que el estilo nativo del host cambie su forma o contraste.

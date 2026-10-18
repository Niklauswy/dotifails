# Historial integrado de Wysun

El historial forma parte del lanzador existente: misma ventana de 860 × 550
(adaptada al espacio disponible), tema, búsqueda, botones, animación y navegación
inferior. `orbit clipboard` y Alt+2 abren esa página, sin una ventana independiente.
Alt+1 vuelve a Inicio; Esc limpia la búsqueda o vuelve a Inicio antes de cerrar.

La lista usa el mismo delegado de filas del lanzador y muestra el detalle a la
derecha. Conserva búsqueda por texto reconocido, imágenes con zoom, texto
seleccionable, colores HEX/RGB/HSL/CMYK, archivos, favoritos, colecciones y grupos
combinados. Los datos, límites y capturador residente se mantienen separados de
la interfaz. No se vuelve a crear ni se vacía la base de datos.

Los enlaces conservan portada, título, descripción y dirección original. La
consulta se hace en segundo plano al seleccionar el enlace, con caché local,
límites de tamaño y redirecciones, sin JavaScript ni servicios de previsualización
externos. Sin metadatos o sin conexión sigue disponible Abrir en el navegador.

El OCR usa Tesseract local español/inglés, un trabajo y un hilo de CPU a la vez.
La resolución del ejecutable funciona aunque el PATH gráfico no incluya binarios
personales. Se conserva la recuperación de intentos antiguos y la preparación de
imágenes pequeñas u oscuras. Texto alterna entre imagen y reconocimiento; Copiar
texto copia el contenido visible como texto, y volver a Imagen restaura la copia
de imagen. Las actualizaciones conservan selección, lectura y zoom.

## Teclado

- Flecha abajo desde búsqueda lleva a resultados; las flechas recorren la lista.
- Ctrl+C copia y conserva la ventana; Enter copia y cierra.
- Ctrl+Enter intenta pegar en la aplicación de origen si conserva el foco esperado.
- Ctrl+Shift+C abre Copiar como; flechas y Enter eligen un formato.
- Ctrl+Alt+1–4 copia HEX, RGB, HSL y CMYK, reservando Alt+1–5 para el lanzador.
- Ctrl+I alterna imagen/texto; Ctrl+O abre el archivo o enlace.
- Ctrl+P fija o desfija; Ctrl+G combina una selección múltiple; Supr elimina con
  confirmación. Ctrl+clic y Shift+flechas seleccionan varios elementos.
- Ctrl+F busca; Ctrl+Shift+F abre filtros; F1 muestra las acciones con sus atajos.

Las colecciones referencian clips existentes. Los grupos guardan copias de sus
elementos y sobreviven a la eliminación de los originales: hasta 20 elementos y
16 MB por grupo, con un límite conjunto de 64 MB para imágenes de grupos.
Eliminar una colección conserva sus clips y eliminar un grupo solo elimina sus
copias. Los formatos pegados dependen de lo que acepte la aplicación destino.

Comprobaciones: `tests/clipboard_ui.py` prueba la integración dentro de la misma
ventana, cambios de página, teclado, colores completos, OCR, portada web, grupos y
copia. `tests/test_clipboard_library.py` y `tests/test_clipboard_preview.py` prueban
datos, OCR real, metadatos y límites de red con bases e imágenes temporales.

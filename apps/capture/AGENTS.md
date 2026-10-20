# Wysun Recorder y Wysun Screenshot

- Esta carpeta es la fuente de desarrollo integrada en `dotifails`. No modificar las copias instaladas ni la copia histórica del repositorio `loom`.
- El instalador común distribuye ambos paquetes en versiones inmutables. Actualizar con `./instalar.sh --orbit-only`; no usar los instaladores históricos de `scripts/` para el escritorio integrado.
- Conservar los nombres técnicos `loomrec` y `wybieshot`, sus sockets, rutas de datos y formatos de proyecto. Wysun es la identidad visible. No copiar bibliotecas, grabaciones, capturas, preferencias ni otros datos privados al repositorio.
- El controlador de captura no depende de la GUI; los trabajadores deben poder finalizar una grabación aunque se cierre la ventana. No reiniciar ni terminar una grabación para actualizar el código.
- FFmpeg usa un origen temporal compartido para pantalla, audio y cámara. No reiniciar los timestamps de cada flujo por separado.
- En X11 se mantiene x11grab/píxeles visibles. En Wayland se usan los portales XDG: ScreenCast/PipeWire para vídeo y capturas con cursor, y Screenshot para imágenes sin cursor; nunca recurrir a XWayland ni presentar un crop de monitor como ventana independiente. La existencia del backend o una prueba mocked no demuestra una sesión nativa real. Ventanas ocultas/minimizadas dependen del portal/compositor; no prometer su captura.
- Las fuentes multimedia son inmutables. Exportar a archivos temporales y publicar sin sobrescribir originales.
- Ejecutar las pruebas de medios en serie: `python3 run_tests.py` desde esta carpeta. El ejecutor aísla HOME y XDG en directorios temporales; no usar preferencias personales al probar. Las pruebas físicas usan solo ventanas opacas sintéticas propias; nunca capturar pantallas privadas, micrófono o cámara como prueba automática.
- No descargar modelos ni usar servicios externos silenciosamente. Mantener las operaciones largas fuera del hilo de la interfaz.

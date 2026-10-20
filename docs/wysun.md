# Wysun · una familia de aplicaciones

Wysun es el nombre público del escritorio y del lanzador antes llamado Órbita. Las aplicaciones se presentan como Wysun Music, Wysun Files, Wysun Recorder, Wysun Screenshot, Wysun Notes, Wysun Ajustes, Wysun Conexiones, Wysun Clipboard, Wysun Processes, Wysun Colors y Wysun Tools. Los textos de ayuda y las acciones continúan en español.

## Fuente y distribución

- `apps/wysun/`: lanzador, música, archivos y paneles Python/PySide6.
- `apps/capture/loomrec/`: Recorder, editor, biblioteca y trabajadores FFmpeg.
- `apps/capture/wybieshot/`: Screenshot, selección, anotación y biblioteca editable.
- `installer/main.py` y `installer/capture_distribution.py`: instalación común, respaldos, conflictos y recuperación.
- `bin/wysun`: punto de entrada público. `wysun --help` enumera sus modos.

`./instalar.sh --wysun-only` y `./instalar.sh --orbit-only` actualizan toda la familia usando el mismo procedimiento que la instalación completa. No instalan dependencias, no modifican atajos y no reinician el escritorio. La instalación completa incluye las dependencias de captura en los componentes de escritorio y sesión: PySide6, FFmpeg, mpv, portal Wayland, audio y Tesseract.

El código de captura se publica en `.local/share/wysun/capture/releases/<hash>/`. Cada actualización conserva las versiones anteriores para no cambiar los módulos de un trabajador en ejecución. Actualizar no detiene una grabación ni cierra sus ventanas. Una ventana que ya está abierta conservará su versión y su título hasta cerrarla normalmente.

## Compatibilidad y datos

El cambio de nombre no mueve ni borra archivos personales. Se conservan:

| Uso | Identidad o ubicación conservada |
| --- | --- |
| Código del lanzador instalado | `~/.local/share/orbit/app/` |
| Datos y preferencias del lanzador | `~/.local/share/orbit/`, `~/.config/orbit/` |
| Música y biblioteca | `~/Music/Orbita`, `~/.local/share/orbit/music/` |
| Proyectos de Recorder | `~/.local/share/loomrec/recordings/` o la biblioteca elegida |
| Preferencias de Recorder | `~/.config/loomrec/` |
| Sesiones editables de Screenshot | `~/.local/share/wybie-screenshot/` |
| Exportaciones | Las carpetas elegidas en cada aplicación |
| Comandos anteriores | `orbit`, `musika`, `musica`, `orbit-files`, `loomrec`, `wybie-screenshot` |
| Paquetes, sockets, nombres de escritorio y clases de ventana | Identidades técnicas existentes para conservar compatibilidad |

Recorder y Screenshot se incorporan sin depender del repositorio original `loom`. Sus lanzadores antiguos solo se adoptan automáticamente si su contenido coincide con el manifiesto del instalador anterior. Los archivos personalizados se conservan y la versión propuesta queda en `incoming/` dentro del respaldo de dotifails. Los instaladores independientes antiguos quedan como herramientas históricas de compatibilidad; no deben usarse para administrar la nueva distribución.

Los accesos del menú conservan sus IDs existentes y cambian su nombre visible; no se crean entradas duplicadas para el mismo producto. Los atajos activos que invocan los comandos antiguos siguen funcionando. La configuración distribuida usa `wysun screenshot` y `wysun recorder --quick-record`; una migración de atajos activos debe respaldar el archivo y preservar las demás asignaciones.

## Alcance

Esta integración cambia la distribución y los nombres públicos. Conserva las interfaces, motores, formatos y funciones existentes. La sesión Wysun / Hyprland se prepara con el componente `wayland`, activo por defecto; consulta [instalación y recuperación](wayland.md). Las funciones de captura usan los portales XDG (Screenshot y ScreenCast/PipeWire) y no XWayland.

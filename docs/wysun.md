# Wysun · una familia de aplicaciones

Wysun es el nombre público del escritorio y del lanzador antes llamado Órbita. Las aplicaciones se presentan como Wysun Music, Wysun Files, Wysun Recorder, Wysun Player, Wysun Notes, Wysun Ajustes, Wysun Conexiones, Wysun Clipboard, Wysun Processes, Wysun Colors y Wysun Tools. Los textos de ayuda y las acciones continúan en español.

## Fuente y distribución

- `apps/wysun/`: lanzador, música, archivos y paneles Python/PySide6.
- `apps/wysun/wysun_media/`, `player_app.py`: Wysun Player (visor de imágenes, video y audio) y el componente reutilizable que también usan Files y Recorder; ver `docs/player.md`.
- `apps/capture/loomrec/`: Recorder, editor, biblioteca y trabajadores FFmpeg.
- `apps/shell/modules/areapicker/`: captura de pantalla del shell (selección, anotación y OCR); sustituye a la app Wysun Screenshot.
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
| Sesiones de la antigua app Screenshot (se conservan, ya no se usan) | `~/.local/share/wybie-screenshot/` |
| Exportaciones | Las carpetas elegidas en cada aplicación |
| Comandos anteriores | `orbit`, `orbit-files`, `loomrec`, `wybie-screenshot` (los alias `musica`/`musika` se retiraron: usa `wysun music`) |
| Paquetes, sockets, nombres de escritorio y clases de ventana | Identidades técnicas existentes para conservar compatibilidad |

Recorder se incorpora sin depender del repositorio original `loom`; los lanzadores antiguos de Screenshot se adoptan como redirecciones a la captura del shell. Sus lanzadores antiguos solo se adoptan automáticamente si su contenido coincide con el manifiesto del instalador anterior. Los archivos personalizados se conservan y la versión propuesta queda en `incoming/` dentro del respaldo de dotifails. Los instaladores independientes antiguos quedan como herramientas históricas de compatibilidad; no deben usarse para administrar la nueva distribución.

Los accesos del menú conservan sus IDs existentes y cambian su nombre visible; no se crean entradas duplicadas para el mismo producto. Los atajos activos que invocan los comandos antiguos siguen funcionando. La configuración distribuida usa `wysun-shell screenshot` y `wysun recorder --quick-record`; una migración de atajos activos debe respaldar el archivo y preservar las demás asignaciones.

## Alcance

Esta integración cambia la distribución y los nombres públicos. Conserva las interfaces, motores, formatos y funciones existentes. La sesión Wysun / Hyprland se prepara con el componente `wayland`, activo por defecto; consulta [instalación y recuperación](wayland.md). Las funciones de captura usan los portales XDG (Screenshot y ScreenCast/PipeWire) y no XWayland.

## Temas

Un solo estilo, Material You, con el color del wallpaper y el modo claro/oscuro/automático, se aplica en vivo a todas las superficies de Wysun. Los tokens viven en `apps/wysun/wysun_theme.json`; la guía, los valores de contraste y cómo crear un widget que obedezca el tema están en [themes.md](themes.md).

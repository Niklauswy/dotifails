# Wysun · una familia de aplicaciones

Wysun es el nombre público del escritorio y del lanzador antes llamado Órbita. Las aplicaciones se presentan como Wysun Music, Wysun Files, Wysun Recorder, Wysun Player, Wysun Notes, Wysun Ajustes, Wysun Conexiones, Wysun Clipboard, Wysun Processes, Wysun Colors y Wysun LANShare. Los textos de ayuda y las acciones continúan en español.

## Fuente y distribución

- `apps/python/`: lanzador, música, archivos y paneles Python/PySide6.
- `apps/python/wysun_player/` y `apps/qml/player`: Wysun Player (visor de imágenes, video y audio) sobre el motor sin interfaz `apps/python/wysun_media/`; ver `docs/player.md`.
- `apps/recorder/wysun_recorder/`: Recorder: trabajadores de captura FFmpeg y la ventana de ajustes en QML.
- `apps/shell/modules/areapicker/`: captura de pantalla del shell (selección, anotación y OCR); sustituye a la app Wysun Screenshot.
- `installer/main.py` y `installer/capture_distribution.py`: instalación común, respaldos, conflictos y recuperación.
- `bin/wysun`: punto de entrada público. `wysun --help` enumera sus modos.

`./instalar.sh --wysun-only` actualiza toda la familia usando el mismo procedimiento que la instalación completa. No instala dependencias, no modifica atajos y no reinicia el escritorio. La instalación completa incluye las dependencias de captura en los componentes de escritorio y sesión: PySide6, FFmpeg, mpv, portal Wayland, audio y Tesseract.

El código de captura se publica en `.local/share/wysun/capture/releases/<hash>/`. Cada actualización conserva las versiones anteriores para no cambiar los módulos de un trabajador en ejecución. Actualizar no detiene una grabación ni cierra sus ventanas. Una ventana que ya está abierta conservará su versión y su título hasta cerrarla normalmente.

## Compatibilidad y datos

El cambio de nombre no mueve ni borra archivos personales. Se conservan:

| Uso | Identidad o ubicación conservada |
| --- | --- |
| Código del lanzador instalado | `~/.local/share/wysun/app/` |
| Datos y preferencias del lanzador | `~/.local/share/wysun/`, `~/.config/wysun/` |
| Música y biblioteca | `~/Music/Wysun`, `~/.local/share/wysun/music/` |
| Proyectos de Recorder | `~/.local/share/wysun/recorder/recordings/` o la carpeta de videos elegida |
| Preferencias de Recorder | `~/.config/wysun/recorder/` |
| Sesiones de la antigua app Screenshot (se conservan, ya no se usan) | `~/.local/share/wybie-screenshot/` |
| Exportaciones | Las carpetas elegidas en cada aplicación |
| Paquetes, sockets, nombres de escritorio y clases de ventana | `wysun_*`, `wysun-*` (ver `ARCHITECTURE.md` §7) |

Recorder se incorpora sin depender del repositorio original `loom`. `wysun` es el único lanzador: una actualización retira los lanzadores anteriores que escribió el instalador (`wysun-screenshot`, `wybie-screenshot`, `wysun-player`, `wysun-tools`…) si no se modificaron; uno modificado pasa a ser tuyo y se conserva, y uno que tu `~/.config/wysun/*.lua` sigue llamando se conserva hasta que cambies esa llamada por su orden de `wysun`. Los instaladores independientes antiguos no deben usarse para administrar esta distribución.

Los accesos del menú conservan sus IDs existentes y cambian su nombre visible; no se crean entradas duplicadas para el mismo producto. La configuración distribuida usa `wysun-shell screenshot` y `wysun-shell record`; un atajo propio que llame a un comando retirado debe cambiarse a su orden de `wysun` (respaldando el archivo y preservando las demás asignaciones).

## Alcance

Esta integración cambia la distribución y los nombres públicos. Conserva las interfaces, motores, formatos y funciones existentes. La sesión Wysun / Hyprland se prepara con el componente `wayland`, activo por defecto; consulta [instalación y recuperación](wayland.md). Las funciones de captura usan los portales XDG (Screenshot y ScreenCast/PipeWire) y no XWayland.

## Temas

Un solo estilo, Material You, con el color del wallpaper y el modo claro/oscuro/automático, se aplica en vivo a todas las superficies de Wysun. Los tokens viven en `apps/python/wysun_core/tokens.json`; la guía, los valores de contraste y cómo crear un widget que obedezca el tema están en [themes.md](themes.md).

## Modo estudio

Sesiones pomodoro para estudiar sin distracciones. `Super + N` (o `wysun study`) abre el panel de preparación: duración (de 30 min a 3 h: más horas seguidas rinden menos), ritmo (25/5, 50/10 o 90/20), apps bloqueadas (por defecto solo Brave; todo lo demás sigue disponible) y «Ocultar el tiempo». Al empezar, una entrada a pantalla completa se recoge en una píldora arriba en el centro, en la capa overlay, visible sobre apps en pantalla completa. La píldora no muestra minutos salvo que se pidan.

- Las apps bloqueadas se cierran al empezar (petición normal de cierre, para que dejen de consumir recursos) y se vuelven a cerrar si se abren durante la sesión; la píldora lo avisa. Las apps de Wysun, los portales y polkit nunca se bloquean.
- Estado de la sesión en `~/.local/state/wysun/study.json` (un reinicio del shell la retoma), historial en `~/.local/state/wysun/study/sessions.jsonl` y preferencias del panel en `~/.config/wysun/study.json`.
- Teclado: en el panel, ↑/↓ o Tab cambian de fila, ←/→ cambian el valor, Espacio marca e Intro empieza. Durante la sesión, `Super + N` despliega la píldora con el teclado: Espacio pausa, → salta al descanso, X pregunta si terminar (mantén Intro para salir) y Esc cierra.
- Desde terminal: `wysun shell pomodoro status|start|pause|skip|stop`. `stop` termina sin la pulsación larga y sirve de salida de emergencia.
- Código: `apps/shell/services/Study.qml`, `StudyBlocker.qml`, `StudyPlan.js`, `StudyApps.js` y `apps/shell/modules/study/`. Diseño: `docs/superpowers/specs/2026-10-31-modo-estudio-design.md`.

# Validación · 25 de septiembre de 2026

Pruebas realizadas sobre la versión portable, sin reemplazar la sesión del equipo de origen.

| Comprobación | Resultado |
| --- | --- |
| Instalador y datos de utilidades: 10 pruebas | Correcto |
| Interfaz de notas, colores y procesos: 3 pruebas Qt | Correcto |
| Órbita: 71 pruebas de cálculo, portapapeles, OCR real, medios, conexiones, ajustes y barra | Correcto en Debian y Parrot |
| Manifiesto original: un único fondo, versiones coherentes, atajos sin colisiones, sin rutas personales ni enlaces rotos | Correcto |
| Gitleaks sobre el árbol distribuido, salida redactada | Sin secretos detectados |
| Instalación completa y repetición en Debian 13 x86_64 | Correcto |
| Instalación completa y repetición en Parrot 7.3 x86_64 | Correcto |
| Doctor: Qt, BSPWM, Picom, Neovim, Node, Ghostty, OCR, FFmpeg y mpv | Correcto en ambas |
| Neovim: 11 comprobaciones de LSP, diagnósticos, formato, fuzzy, tareas e interfaces | Correcto en ambas |
| Depuración real: breakpoints, lectura de variables y avance en JS, Python y C++ | Correcto en ambas; CodeLLDB admite un arranque más lento |
| X11 aislado en Debian: BSPWM, SXHKD, Picom, Polybar, Ghostty, utilidades y ocultación/restauración de barra en fullscreen | Correcto |
| X11 aislado en Parrot: terminal, barra, fullscreen y utilidades | Correcto |

La prueba usa contenedores oficiales y Xvfb con D-Bus, no máquinas virtuales completas. Se revisó visualmente una captura del escritorio instalado. No prueba el arranque desde LightDM en una máquina física, GPU propietaria, conexiones reales Wi-Fi/Bluetooth, bloqueo/suspensión ni monitores físicos múltiples. Las aplicaciones opcionales Flatpak no se instalaron durante estas pruebas.

Fallos corregidos durante la validación: paquete Polkit retirado de Debian, extracción AppImage con un enlace a AppDir, preparación de plugins y tema de NvChad antes del primer arranque, búsqueda de iconos de usuario, PATH en las pruebas y espera a que BSPWM gestione la ventana antes de probar fullscreen.

La carpeta original y las configuraciones activas se respaldaron fuera del repositorio antes de la limpieza. Los fondos descartados permanecen en el respaldo y el historial Git.

La actualización de perfiles añade azul y morado. Su validación específica se realiza con instalación aislada de configuraciones, selección de perfil, recursos, caché de Bat y manifiesto; las pruebas completas anteriores de Debian/Parrot no equivalen a repetir una instalación completa de esta revisión.

Revisión de los perfiles: 13 pruebas del instalador/almacenamiento/selección y 21 pruebas de Ajustes correctas. Instalación aislada azul, cambio a morado y repetición sin reescrituras verificados; recursos del tema, ambos fondos y caché Tokyo de Bat comprobados. El archivo azul coincide byte a byte con el original seleccionado.

## Gestor de procesos · 26 de septiembre de 2026

- `python3 -m unittest discover -s tests -v`: 17 pruebas correctas, incluidas señales reales sobre procesos desechables y rechazo de un PID cuya identidad no coincide.
- `QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py`: 5 pruebas correctas de utilidades.
- `QT_QPA_PLATFORM=offscreen python3 tests/process_ui.py`: 6 pruebas correctas de ordenación numérica, selección múltiple estable, árbol y filtros, reemplazo de PID, congelación, confirmación/cancelación y navegación con teclado/acciones.
- `python3 tests/check_manifest.py` y `git diff --check`: correctos.
- Despliegue mediante `--orbit-only`, con respaldo y sin conflictos. Recarga del residente y apertura real mediante Super + Shift + K en X11; búsqueda, selección con flecha abajo, inspector y menú Alt K revisados visualmente. La lectura de unos 312 procesos tomó aproximadamente 0,10 segundos en este equipo, en un hilo de trabajo; no es una garantía de rendimiento para otros equipos.

Esta revisión no repite la instalación completa en Debian/Parrot ni las pruebas de hardware. Las pruebas de pausa y cierre solo afectaron procesos temporales creados por las propias pruebas.

## Mise · 26 de septiembre de 2026

Mise 2026.9.14 instalado en el usuario tras verificar el SHA-256 del archivo oficial. Integración Zsh comprobada con Node 20.19.5 y 24.19.0 ya existentes: cambio por carpeta, restauración del valor global y ejecución de npm correctos. `mise doctor` informa activación y shims disponibles, sin problemas. La configuración activa de Zsh se respaldó y se conservaron sus personalizaciones.

18 pruebas del instalador y datos correctas, incluida una regresión para conservar el nombre del comando al ejecutar los shims de mise. Manifiesto y sintaxis Zsh correctos. Se añadió mise al instalador portable; no se repitió la instalación completa en contenedores para esta revisión.

## Teclado del menú de sesión · 26 de septiembre de 2026

Se reprodujo que Enter no activaba los botones de Sesión antes de la corrección. `tests/power_ui.py`: 3 pruebas Qt correctas (Enter normal/numérico para las cinco acciones, foco y flechas, cancelación simulada y supresión de repetición automática). Dos pruebas de integración de `test_v3.UITests` verifican confirmación/cancelación y despacho del comando con ejecución sustituida por un mock. Las 18 pruebas del instalador/datos y el manifiesto siguen correctos. Tras desplegar y recargar Órbita, Super + X → flecha derecha → Enter abrió «Suspender» en la sesión X11 real; Esc canceló y devolvió al menú. No se ejecutaron suspensión, apagado ni cierre de sesión durante la verificación.

El panel incorpora hora local, fecha en español y tiempo desde el arranque obtenido con `CLOCK_BOOTTIME` (incluye suspensión). Mantiene cinco acciones en 460 × 370 px, con fondos sutiles y foco visible. Cinco pruebas de `tests/power_ui.py` y las dos de integración anteriores pasan, incluida la representación del tiempo en días/horas/minutos y la detención del temporizador al ocultar el panel. Manifiesto correcto. Instalación `--orbit-only` sin conflictos, recarga y captura del menú real revisada en X11; apertura y cancelación de «Suspender» con el teclado verificadas de nuevo sin suspender el equipo.

## Recuperación de monitores · 26 de septiembre de 2026

Se sustituyó el reinicio posicional de escritorios (`bspc monitor -d`) por traslados mediante IDs que conservan árboles y ventanas. Las recargas de BSPWM omiten la restauración posicional de nombres guardados. Se activan `remove_disabled_monitors` y `remove_unplugged_monitors`; la transferencia nativa está documentada en el [código de BSPWM](https://github.com/baskerville/bspwm/blob/master/src/monitor.c). La reconciliación rescata también monitores obsoletos, conserva nombres personalizados, limpia duplicados numéricos vacíos y distingue los ocupados como «recuperado».

- 23 pruebas del instalador/datos correctas, incluyendo cinco sobre distribución de escritorios y rechazo sin destino activo; manifiesto y sintaxis del arranque correctos.
- 21 pruebas de Ajustes correctas fuera del sandbox (dentro, una prueba de socket estaba bloqueada por permisos).
- `XVFB_BIN=/ruta/a/Xvfb python3 tests/monitor_x11.py`: BSPWM real en X11 aislado, monitores virtuales 3 → 1 → 2 → 3, recargas repetidas y duplicados heredados. Conservación de IDs de escritorios ocupados y ventanas reales comprobada; escritorios personalizados conservados. Esta prueba simula la lista de salidas disponibles, no la señal eléctrica de un cable físico.
- Código desplegado con `--orbit-only`. Configuración activa de BSPWM migrada con respaldo, conservando ajustes de entrada y arranque. Activación sin reiniciar el WM y verificación de que los IDs de escritorios ocupados y todas las ventanas de la sesión real permanecen intactos.

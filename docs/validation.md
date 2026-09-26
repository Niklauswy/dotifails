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

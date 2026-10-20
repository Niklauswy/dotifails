# Validación · 19 de octubre de 2026

## Migración a Wysun / Hyprland

Esta revisión completa la migración del escritorio a **Wysun / Hyprland sobre Wayland**. El escritorio X11 anterior (BSPWM, SXHKD, Polybar y Picom) se retiró del repositorio, del instalador y de la configuración activa. Se conservan XWayland y las bibliotecas X11 necesarias para aplicaciones heredadas; no hay una sesión X11 propia.

Cambios estructurales verificados:

- `apps/wysun/` y `apps/shell/` son las fuentes activas; `config/` contiene las dotfiles y `assets/` los fondos y la apariencia.
- El instalador distribuye la sesión `wayland` por defecto, registra solo sus dos archivos de sesión y no modifica el gestor de acceso.
- Los ajustes del escritorio usan Hyprland (`hyprctl`, `hypr-settings.lua`, `hypr-shortcuts.lua`, `hypr-bar.json`) y el tema canónico es `~/.config/orbit/theme.json`.
- Dunst usa `~/.config/wysun/dunstrc`. La barra y el escritorio de Quickshell se cargan desde `~/.local/share/wysun/quickshell`.
- La captura usa los portales XDG en Wayland: Screenshot para imágenes sin cursor y ScreenCast/PipeWire para grabación, cursor y fuentes de ventana. Las herramientas de atajos basadas en el escritorio X11 se retiraron.

## Suites

| Comprobación | Resultado |
|---|---|
| Suite general (`python3 -m unittest discover -s tests`) | 169 pruebas correctas |
| Aplicaciones Wysun (`test_orbit`, `test_refinement`, `test_v2`, `test_v3`, `test_v4`) | 52 pruebas correctas |
| Lógica del shell (`apps/shell`: `tests.test_logic`) | 14 pruebas correctas |
| Interfaz de utilidades (`tests/utility_ui.py`) | 6 pruebas correctas |
| Captura (`apps/capture/run_tests.py`) | 354 pruebas correctas en 120,487 s |
| Manifiesto (`tests/check_manifest.py`) | `MANIFEST_OK` y `TOOLS_OK` |
| Humo de la instalación (`tests/wysun_installed_smoke.py`) | `WYSUN_INSTALLED_SMOKE_OK` |

Las suites de captura y compositor se ejecutaron en serie. Las pruebas de captura aíslan HOME/XDG y eliminan las variables de la sesión gráfica para no alcanzar el portal ni las preferencias reales.

## Despliegue y sesión activa

- `./instalar.sh --orbit-only` terminó sin conflictos. Respaldo: `~/.local/state/dotifails/backups/20261019T171709Z-b34e4e`.
- `~/.local/bin/orbit reload` completó correctamente y Quickshell mantiene la capa `wysun-desktop`.
- Despliegue posterior de las correcciones de Screenshot y libmpv: respaldo `~/.local/state/dotifails/backups/20261019T194412Z-be2f10` y release `aceb815c873d1b5c38f8`; tras alinear los nombres visibles, respaldo `~/.local/state/dotifails/backups/20261019T195009Z-7a25ea` y release final `6075afe7c99700d9094b`. `orbit reload` correcto y `WYSUN_INSTALLED_SMOKE_OK`.
- Comprobación real en la sesión Wayland activa: se abrió la ventana de Wysun, el menú de acciones, la lista de ventanas de Hyprland, el menú contextual del portapapeles y Ajustes con sus diez secciones.
- Las herramientas instaladas (`wysun-terminal`, `wysun-session`, `wysun-session-services`) coinciden con el repositorio.
- Se detuvo el proceso huérfano de la instalación X11 anterior y se migró Dunst a `~/.config/wysun/dunstrc`; `dunstctl` respondió y se mostró una notificación de prueba.
- Las configuraciones X11 antiguas (`bspwm`, `dunst`, `picom`, `polybar`, `sxhkd`, `xsettingsd`) se conservaron en `~/.local/state/dotifails/backups/host-x11-cleanup-20261019T172249Z/` antes de retirarlas del hogar.
- Tras el reinicio de la sesión se repitieron las comprobaciones reales: la barra de Quickshell mantiene la capa `wysun-desktop`, Dunst arrancó con `~/.config/wysun/dunstrc` y la ventana, los menús y las diez secciones de Ajustes siguen abriéndose.

La retirada de los paquetes del sistema requiere la contraseña del usuario y queda pendiente de ejecutar en una terminal:

```sh
sudo apt-get remove bspwm sxhkd polybar
```

## Prueba E2E de Screenshot

La sonda pública se ejecutó en un Hyprland anidado y aislado con salida sintética `WYSUN-TEST-1`, puntero/teclado virtuales y bus privado. Resultado: `PUBLIC_SCREENSHOT_ROUTE_PASS`.

- Consentimiento real del selector `hyprland-share-picker` y captura por portal.
- Selección de región, editor y guardado directo con píxeles sintéticos uniformes verificados.
- Barra rápida, exportación automática al portapapeles y reapertura mientras el propietario anterior del portapapeles sigue vivo.
- Cancelación con Escape durante una solicitud pendiente: la interfaz permanece visible, el lease se libera y el proveedor se cierra.
- Evidencia privada: `~/.local/state/dotifails/evidence/screenshot-route-20261019T173118Z/`.

## Correcciones posteriores

- **Screenshot sin cursor.** La ruta regional por defecto congela el escritorio con el portal `Screenshot` (XDPH/grim) y muestra el marco propio de Wysun, sin el selector blanco de ScreenCast. La API se midió en la sesión real con respuestas de 0,3–0,5 s después de liberar portales bloqueados. También se abrió el marco real «Recortar imagen autorizada» en la sesión activa, sin selector ScreenCast, y se canceló sin guardar ni inspeccionar el contenido. La preferencia de cursor y las capturas de ventana/monitor conservan ScreenCast y su consentimiento. El caso E2E se actualizó para probar la ruta directa por defecto y mantener el selector para la rama con cursor; esta revisión concreta no se volvió a ejecutar en el compositor anidado.
- **Reproducción de vídeo.** `libmpv` rechazaba `mpv_create()` con cualquier locale numérico distinto de `C` y el reproductor quedaba en duración 0 sin imagen. `MpvSurface.start` normaliza `LC_NUMERIC=C` antes de crear el handle. Verificado con un vídeo sintético de 3 s en la release instalada: duración 3,0 s, posición avanzando y fotograma no nulo.
- **Nombres visibles.** El menú de aplicaciones muestra **Wysun Ajustes** y **Wysun Conexiones**; se retiraron las entradas «Órbita» y las palabras clave antiguas. Se conservan las rutas, los identificadores y el comando técnico `orbit` por compatibilidad.

## Límites

Las suites no capturaron una pantalla física, micrófono ni cámara, y no validan rendimiento de sesiones largas. La comprobación manual del marco de Screenshot abrió una captura del escritorio activo y la canceló sin guardar ni inspeccionar el contenido. El teclado y el puntero de la prueba E2E son sintéticos. Las revisiones anteriores del escritorio X11 quedan documentadas únicamente en el historial de Git.

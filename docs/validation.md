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
| Aplicaciones Wysun (`tests/wysun_app/`) | 52 pruebas correctas |
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

## Runtime privado · P2-B, 20 de octubre de 2026

La suite general incluye ahora `tests/wysun_app` y `tests/shell_bridge`:
`QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` ejecuta
374 pruebas antes de integrar P2-A (correctas con acceso a sockets locales). La comprobación independiente
del puente del shell ejecuta 16 pruebas; `tests/utility_ui.py`, 7. El humo instalado devuelve `WYSUN_INSTALLED_SMOKE_OK` en 3,173 s,
con HOME/XDG temporales y sin reconstruir el runtime. El manifiesto
y la guarda de identidad del shell también pasan. Los errores `EPERM` de sockets
bajo confinamiento requieren repetir esa validación con acceso de sesión.

La prueba de construcción del runtime tiene una entrada reproducible que sólo
acepta un contenedor Debian 13 desechable. No monta HOME, cachés ni runtime del host:

```sh
podman run --rm --label ao.session="$AO_SESSION_ID" \
  -e WYSUN_CONTAINER_TEST=1 -e WYSUN_BUILD_JOBS=2 \
  -v "$PWD:/src:ro" docker.io/library/debian:13 \
  sh /src/tests/container-runtime.sh
```

Reserva al menos 12 GB de disco para el almacén del contenedor y la compilación.
En entornos donde `/tmp` es tmpfs, el almacén debe vivir en disco. Se puede aislar
con `podman --root "$HOME/.cache/wysun-runtime-validation/storage"
--runroot /tmp/wysun-runtime-validation/run --storage-driver vfs ...`.
Si no hay un gestor de cgroups accesible, usa `--cgroup-manager cgroupfs` como
opción global y `--cgroups disabled` en `run`; los dos trabajos de compilación
siguen limitados por `WYSUN_BUILD_JOBS`.

La prueba instala sólo las dependencias declaradas, descarga Qt 6.9.3, compila
libcava, M3Shapes, Quickshell y el plugin Wysun. Comprueba `--version`, bibliotecas
con `ldd`, sellos completos y una segunda ejecución sin reconstrucciones.
El marcador final es `WYSUN_RUNTIME_CONTAINER_OK`. Esto valida la construcción
y los enlaces del runtime; no prueba login, renderizado ni dispositivos físicos.


## Integración A+B · 21 de octubre de 2026

Desplegada la integración `092d27fa`: base P2-B `9481005c` y cambios P2-A
`0b4e8157` + `87304965`. Se conservaron el runtime privado `Wysun.*`, la
migración de nombres, los guards de selección y la recuperación cooperativa.

- Checks dirigidos: instalador 20/20, Screenshot 76/76 antes del follow-up,
  recovery final 4/4, guard final 12/12 y humo integrado correcto (2,92 s).
- Instalador acotado sin conflictos; respaldo final
  `~/.local/state/dotifails/backups/20261021T113642Z-a04229`.
  El respaldo anterior `20261021T113509Z-2fa8d6` incluye en `manual/` la preimagen
  de `hyprland.lua` antes de añadir únicamente el atajo de recuperación.
- No se reconstruyó el runtime: su sello de plugin coincidía con la fuente.
  No se instalaron ni retiraron paquetes y no se reinició Hyprland.
- Sesión física actual: tres monitores, siete menús abiertos y comprobados por
  IPC, cierre del picker correcto, selección real en las tres salidas.
  Escape dirigido a la ventana propia termina con código 0 y sin ventanas.
  `wysun recover` confirma una selección cerrada, cero pendientes, salida 0 y
  cero ventanas restantes. No se guardó ni inspeccionó contenido de pantalla.
- La respuesta `pending` sigue devolviendo fallo/petición pendiente mientras el
  portal conserva el lease; los tests finales verifican que no se anuncia cierre
  sólo por enviar IPC.
- El supervisor de sesión anterior conserva sus hijos para preservar el
  residente y las aplicaciones. El nuevo auto-reinicio del shell queda instalado
  para el próximo inicio de sesión; el shell actual fue abierto por recovery.

La prueba limpia Debian del runtime permanece pendiente, independiente del
resultado de despliegue. El primer intento agotó el tmpfs de `/tmp`; el segundo
se inició con almacén aislado en disco y no se toma como aprobado sin su marcador
final. La entrada preparada es `tests/container-runtime.sh`.


## Incremento C/D · 21 de octubre de 2026

Código desplegado `88210e18`: commits de lateral y lanzador `e2883e7b` y
`9fdc3266`, integrados como `f7fba72c` y `d6420897`, más corrección de máscara
fullscreen. El dispatcher conserva `wysun recover` y el runtime privado.
Respaldo incremental sin conflictos: `20261021T114343Z-524d46`; en `manual/`
está la preimagen del archivo de Hyprland antes de añadir Ctrl+X.

El puente pasa 26/26 checks. En la sesión real se verificaron cuatro toggles
con Ctrl+X, Escape en lateral y lanzador predeterminado, consulta «foot» y Enter
abriendo una terminal nueva. Sobre esa terminal en fullscreen, launcher y
lateral recibieron Escape y devolvieron el control. La lateral abrió y cerró
con Escape en eDP-1, DP-1 y DP-2. Al limpiar, la dirección y PID de la terminal
de prueba ya no existían: no se cerró ninguna otra ventana. Recovery siguió
respondiendo correctamente y Hyprland no se reinició.

Corrección posterior: Ctrl+X ya no está asignado globalmente (vuelve a ser Cortar). Super+X abre o cierra el panel
lateral de sesión; el menú Qt de energía pasó a Super+Shift+X.

La máscara heredada vacía en fullscreen podía mantener foco sobre un panel
inaccesible. `88210e18` utiliza la región interactiva y capa overlay cuando
hay un panel invocado, y cierra los estados de lateral/utilidades al cambiar
fullscreen. No se modificó ni reconstruyó el plugin C++.


## Cierre de dependencia Debian · 21 de octubre de 2026

El journal conservado del contenedor `wysun-p2b51-clean-disk`
(`5834d751d442`) confirma `RUNTIME_OK /root/rt` y Quickshell 0.3.2,
revision `2b4501a282689792b62e94f3fb30d8f512324fe6`. La construcción original
desde Debian 13 terminó; su verificación final falló porque faltaba
`libpulse.so.0` al enlazar los plugins multimedia.

`715d74fb` añade `libpulse0` al manifiesto consumido por el constructor y el
plan de instalación. Sobre el mismo contenedor y el mismo artefacto se
comprobaron los cinco sellos y el hash del plugin antes de continuar. Se
instalaron únicamente `libpulse0` y su dependencia `libasyncns0`, sin paquetes
del host y sin recompilar. La verificación posterior pasó: versión ejecutable,
`ldd` de todos los plugins y segunda ejecución sin comandos de build ni cambios
en los sellos. Resultado `WYSUN_RUNTIME_CONTAINER_OK`, contenedor `exited 0`.
No es una construcción fría completa repetida después de corregir el manifiesto;
es la corrección de dependencias y validación del artefacto original conservado.
No quedaron procesos propios de validación consumiendo CPU.

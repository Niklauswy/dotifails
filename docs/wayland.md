# Sesión adicional Wysun / Hyprland

Wysun puede preparar una sesión Wayland separada con Hyprland 0.55.x y
Quickshell 0.3.0. BSPWM continúa instalado y sigue siendo la selección
predeterminada del instalador. No se cambia la sesión predeterminada del gestor
de acceso, ni se ejecuta el compositor durante la instalación.

## Preparar y revisar

Desde la copia local completa:

```sh
./instalar.sh --components wayland --plan
./instalar.sh --components wayland --dry-run
```

Para copiar y probar exclusivamente en un hogar temporal, sin paquetes ni
registro de sesión:

```sh
test_home=$(mktemp -d)
./instalar.sh --source "$PWD" --components wayland --config-only --target-home "$test_home"
HOME="$test_home" "$test_home/.local/bin/wysun" --help
python3 installer/session_registration.py install --source installer --root "$test_home/system" --dry-run
```

`--source "$PWD"` evita tomar una fuente anterior guardada en el recibo de una
instalación existente. El HOME temporal contiene solo fixtures y se puede retirar
después de revisar sus respaldos. No uses ese HOME para iniciar un escritorio real.

## Dependencias de Debian y Parrot

Se admiten Debian 13 y Parrot 7 x86_64. Se utilizan los repositorios de la propia
distribución: `trixie-backports` en Debian y `echo-backports` en Parrot. El
instalador **no añade repositorios**, claves, pinning ni paquetes Arch/AUR.

La lista íntegra está en `manifests/packages.json`. Hyprland, Quickshell y el
portal Hyprland y sus diálogos `hyprland-guiutils` se seleccionan explícitamente
desde backports. `hyprpicker` 0.4.x también se selecciona allí para que el portal
devuelva colores RGB mediante su ruta nativa ASCII; no se depende del fallback
PPM de XDPH1.4.1, que produjo valores incorrectos en la prueba real.
`grim` y `slurp` siguen disponibles para Screenshot/selección.
El preflight exige las series comprobadas Hyprland0.55.x, Quickshell0.3.x y
XDPH1.4.x e Hyprpicker0.4.x. Un cambio de serie requiere revisar y ejecutar el smoke antes de
instalar. También se
seleccionan las bibliotecas `xkbcommon` con ABI compatible y sus paquetes de
desarrollo solamente cuando ya están instalados. No se usa un `-t backports`
global: este actualizaría innecesariamente otros paquetes, incluido el audio.

El preflight consulta los paquetes y ejecuta `apt-get --simulate --no-remove
install --no-install-recommends ...` con la lista exacta del plan **antes de
crear el diario o copiar archivos**. Una incompatibilidad detiene la operación.
Se vuelve a resolver después de actualizar los índices y antes de instalar.
La simulación depende de los índices locales y no prueba una instalación limpia.

Fuentes oficiales consultadas el 18 de octubre de 2026:

- [Debian Backports: política e instrucciones](https://backports.debian.org/Instructions/).
- [Hyprland en trixie-backports](https://packages.debian.org/trixie-backports/hyprland).
- [Quickshell en trixie-backports](https://packages.debian.org/trixie-backports/quickshell).
- [Hyprpicker en trixie-backports](https://packages.debian.org/trixie-backports/hyprpicker).
- [Portal Hyprland en trixie-backports](https://packages.debian.org/trixie-backports/xdg-desktop-portal-hyprland).
- [Repositorios oficiales Parrot 7](https://parrotsec.org/docs/configuration/upgrade-from-lorykeet/).
- [Configuración Lua oficial de Hyprland 0.55.2](https://github.com/hyprwm/Hyprland/blob/v0.55.2/example/hyprland.lua).

Antes de aplicar paquetes en una máquina en uso, revisa el plan y el impacto de
sus scripts de instalación sobre servicios de audio, red y portales. Las pruebas
aisladas de este proyecto no ejecutan una instalación en la sesión activa.

## Instalar y seleccionar (cuando se decida activar)

```sh
./instalar.sh --source "$PWD" --components wayland
wysun session-check
```

La primera orden instala dependencias y registra **Wysun / Hyprland** junto a las
sesiones existentes. Cuando el usuario decida cerrar su sesión, podrá elegirla
en un gestor compatible con sesiones Wayland. LightDM/greeter concretos pueden
no ofrecer sesiones Wayland: comprobar su compatibilidad antes de cerrar la
sesión. No se instala ni reemplaza el gestor de acceso automáticamente.

También puede iniciarse `wysun-session` desde una TTY de un inicio limpio. El
comando rechaza su ejecución desde una sesión gráfica existente. `--check`
comprueba ejecutables, versión y configuración; no prueba GPU, bloqueo ni login.

La configuración se guarda en `~/.config/wysun/hyprland.lua`. No se modifica
`~/.config/hypr/`, BSPWM, Picom ni SXHKD. Super+Enter abre terminal; Super+D y Super+Espacio abren el lanzador;
Super+F alterna fullscreen; Super+X abre Power como panel flotante.
Super+E abre Files; Super+L conserva emoji y Super+Ctrl+Alt+L bloquea.
Print abre captura directa de región. Los atajos
Super+Shift+S/Q conservan captura de región al portapapeles y a Screenshots;
Super+Shift+A abre la selección de región. El teclado predeterminado es US.

`wysun shell` abre Quickshell. Sus ventanas y workspaces usan la API nativa de
Wayland/Hyprland. Las aplicaciones Python/PySide6 y sus datos conservan sus rutas
anteriores. La presencia de XWayland no convierte una captura X11 en captura de
Wayland: el backend y la autorización del portal se comprueban por separado.
El instalador administra el código bajo el HOME destino; los wrappers pueden
resolver esa copia aunque los directorios XDG de datos privados sean distintos.

Las preferencias específicas de una máquina pueden vivir en
`~/.config/wysun/local.lua`, cargado al final de la configuración. Es un archivo
de usuario: las actualizaciones normales no lo sustituyen. Ajusta el modo y la
escala de una salida concreta a partir de sus medidas y de la preferencia del
usuario; no presupongas que la escala automática reproduce el escritorio previo.
Antes de cambiarla conserva la regla anterior y un respaldo recuperable.

## Portales, audio y bloqueo

`XDG_CURRENT_DESKTOP=Wysun:Hyprland` selecciona `wysun-portals.conf`: ScreenCast y
Screenshot usan Hyprland; FileChooser usa GTK para admitir padres Wayland.
Los diálogos externos de archivos usan la interfaz GTK; la aplicación Files y
el selector Wysun de BSPWM se conservan. Esta diferencia visual se mantiene
explícita. El archivo global `portals.conf`
se conserva. PipeWire, WirePlumber, GStreamer PipeWire y las bibliotecas Python
D-Bus/GI pertenecen al componente Wayland. No se reinician servicios al copiar
configuración. Los agentes de la sesión se inician después de entrar al nuevo
compositor; no se utilizan `killall` ni reinicios globales de portales.

Importar el entorno no actualiza un portal que ya estaba ejecutándose en otra
sesión. En una sesión Wayland, `wysun session-check` consulta únicamente owners
existentes e interfaces de captura; no activa ni reinicia servicios. Si detecta
un core heredado de X11 sin ScreenCast/Screenshot, muestra un diagnóstico en vez
de dar el portal por listo. La recuperación debe evaluar peticiones/sesiones
existentes: reiniciar sólo el core puede cancelar sus permisos o diálogos, aunque
no cierre las aplicaciones. No se hace automáticamente al entrar ni al instalar.

`wysun lock` usa swaylock, un bloqueador de sesión Wayland con PAM, separado de
la interfaz Quickshell. `wysun lock --suspend` suspende solo si swaylock confirma
la adquisición del bloqueo. swayidle solicita el bloqueo antes de suspensión y
tras diez minutos de inactividad. La autenticación y el comportamiento de cierre
del compositor requieren una comprobación física; un test de comandos no los
demuestra. No se captura la pantalla real para generar un fondo de bloqueo.
Si Quickshell termina, swayidle continúa protegiendo esa sesión; se puede abrir
otra vez con `wysun shell`. Si termina swayidle o falla el arranque parcial de
los servicios, el supervisor solicita el bloqueo antes de retirar sus hijos.

## Actualizar, conflictos y recuperación

Repite `--components wayland` para actualizar también la configuración de esa
sesión. Los archivos administrados modificados se conservan y la propuesta queda
en `incoming/` del respaldo. No se mueven bibliotecas, preferencias ni proyectos
de usuario. `--wysun-only` actualiza las aplicaciones comunes y Quickshell cuando
esa sesión ya está administrada, sin instalar dependencias ni registrar la
sesión; no sustituye la configuración ni los atajos de Hyprland.

```sh
./instalar.sh --source "$PWD" --wysun-only
python3 installer/main.py restore --target-home /ruta/al/hogar
python3 installer/main.py restore ID --target-home /ruta/al/hogar
```

El primer `restore` lista respaldos. La recuperación revierte los archivos del
hogar y rescata las ediciones posteriores en `changes-before-restore/`. Las
versiones inmutables de captura se retienen, incluso al recuperar, para que un
trabajador que siga ejecutándose pueda importar sus módulos. No se desinstalan
paquetes ni se cierran ventanas.

El registro del selector administra solamente `/usr/local/bin/wysun-session` y
`/usr/share/wayland-sessions/wysun-hyprland.desktop`, con recibo bajo
`/var/lib/dotifails/wayland-session/`. Para revisarlo o retirarlo:

```sh
python3 installer/session_registration.py remove --dry-run
sudo python3 installer/session_registration.py remove
```

La retirada comprueba hashes y conserva cualquier edición ajena. No elimina
BSPWM, no cambia LightDM ni la sesión predeterminada y no termina la sesión en
curso. Ante un problema de login, vuelve a seleccionar la entrada BSPWM que ya usabas
(`bspwm` en instalaciones existentes; `Wysun / BSPWM` si se registró con el
instalador). También puedes entrar en una TTY y recuperar el hogar o retirar
solamente el registro adicional. No reinicies el gestor de acceso desde la
sesión activa: terminaría las aplicaciones abiertas.

Antes de salir guarda el identificador REAL de respaldo emitido por el instalador,
el resultado de `wysun session-check` y los comandos de recuperación en una ruta
local accesible sin AO. Desde una TTY, inicia sesión con tu usuario y ejecuta:

```sh
cd /home/nicolas/dotifails # sustituye si clonaste en otra ruta
python3 installer/main.py restore
# Elige el identificador real registrado antes de salir:
python3 installer/main.py restore ID
python3 installer/session_registration.py remove --dry-run
# Solo si necesitas retirar la entrada adicional:
sudo python3 installer/session_registration.py remove
```

En el selector de LightDM elige `bspwm` para retornar. No hace falta retirar los
paquetes de Wayland para usar BSPWM. Si AO o la terminal estaban dentro de la
sesión anterior pueden haberse cerrado: la recuperación no depende de ellos.
El login, los permisos reales del portal y el desbloqueo son acciones humanas;
una prueba anidada no los acredita.

## Verificación reproducible

```sh
python3 -m unittest discover -s tests -p test_wayland_install.py -v
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 tests/utility_ui.py
python3 tests/check_manifest.py
python3 apps/capture/run_tests.py
python3 -m unittest discover -s apps/quickshell/tests -v
```

Usa HOME/XDG desechables y medios sintéticos. Serializa las pruebas de medios y
compositor con otros agentes. Unit, offscreen, compositor anidado, portal real y
login físico son niveles distintos; consulta el informe de ejecución para saber
cuáles se realizaron. Las mediciones anidadas no predicen consumo ni latencia de
una sesión física.


## Efectos del ratón: instalación separada en revisión

El helper opcional de botones del ratón no se instala con `--components wayland`.
Su registro es una operación separada: ejecutable administrado por root en
`/usr/libexec/wysun-pointer-helper`, política en
`/usr/share/polkit-1/actions/org.wysun.pointer.policy` y recibo propio bajo
`/var/lib/dotifails/pointer-helper`. La política exige autorización del usuario
activo en cada ejecución, sin autorización persistente. No habilita lectura de
teclado, no cambia grupos/ACL ni toma control de la sesión.

Mientras no se haya revisado y probado su frontera, usar solo el plan o un root
temporal; el plan no abre dispositivos ni invoca polkit:

```sh
python3 installer/pointer_registration.py install --source "$PWD" --dry-run
python3 installer/pointer_registration.py install --source "$PWD" --root "$test_home/helper-system"
python3 installer/pointer_registration.py remove --root "$test_home/helper-system"
```

El registro real y la lectura física del ratón requieren una decisión posterior
sobre esa operación concreta. Su preparación no acredita efectos en vivo ni
acceso físico, y no cambia el funcionamiento de BSPWM.

## Prueba real de paquetes en un contenedor desechable

`tests/container-wayland.sh` usa el instalador común con un usuario/HOME nuevo,
fixtures de datos y configuración, repetición, actualización, conflicto y
recuperación. Instala paquetes dentro del contenedor y comprueba los comandos
públicos sin iniciar una sesión gráfica. Requiere Podman rootless configurado,
red hacia los repositorios oficiales y aproximadamente 3 GiB libres. No lo
ejecutes a la vez que las pruebas de medios/compositor.

```sh
test_store=$(mktemp -d)
podman --root "$test_store/storage" --runroot "$test_store/run" --storage-driver vfs \
  run --name wysun-install-test --label "ao.session=${AO_SESSION_ID:-local-wysun-test}" \
  --cap-add SYS_NICE --memory 768m --cpus 1 --pids-limit 256 \
  --network slirp4netns:allow_host_loopback=false -e WYSUN_CONTAINER_TEST=1 \
  -v "$PWD/installer:/src/installer:ro" -v "$PWD/manifests:/src/manifests:ro" \
  -v "$PWD/apps:/src/apps:ro" -v "$PWD/bin:/src/bin:ro" \
  -v "$PWD/home:/src/home:ro" -v "$PWD/backgrounds:/src/backgrounds:ro" \
  -v "$PWD/tests/container-wayland.sh:/test:ro" \
  docker.io/library/debian:13-slim /bin/sh /test
```

Comprueba previamente que Podman informa `rootless: true`; no sustituyas esta
prueba por un contenedor privilegiado. `SYS_NICE` queda dentro del user namespace:
el paquete stock Hyprland tiene `cap_sys_nice=ep` y su ejecución produce `EPERM`
si esa capacidad falta en el bounding set. No se quita el filecap para declarar
un resultado exitoso. Se conservan imagen, versiones y diarios del ensayo;
`WYSUN_CLEAN_CONTAINER_OK` solo aparece tras completar todas sus comprobaciones.
No se monta `.git`, el HOME real, dispositivos físicos ni el bus de sesión.


## Compatibilidad de atajos del escritorio previo

`manifests/wayland-shortcuts.json` enumera cada combinación pública, acción,
semántica y límites. `installer/shortcut_audit.py` expande los grupos, rangos,
modificadores y teclado numérico de SXHKD sin ejecutar comandos. Se comparan el
archivo instalado, el snapshot y la distribución: no deben confundirse.
Los destinos personales de captura se conservan en `wysun/local.lua`, con
`hl.unbind` específico antes de cada override; nunca se copian al manifiesto.

Cerrar/forzar cierre, tiled/flotante/fullscreen, foco/intercambio por dirección,
workspaces1–10 y sus equivalentes numéricos tienen acciones nativas. El cierre
forzado nativo mata el proceso propietario y puede afectar sus otras ventanas.
No se prueba contra aplicaciones del usuario. `wysun-wm` implementa operaciones
finitas de mayor ventana, historial por identidades y desplazamiento/tamaño;
no añade un daemon ni usa X11. El historial usa un snapshot nativo propio y los
cambios de foco invalidan una navegación anterior; no es el árbol de BSPWM.

Las26 combinaciones que dependen de preselección, nodos/flags exclusivos,
monocle o reinicio de BSPWM no se presentan como equivalentes. Al pulsarlas se
explica el límite y una alternativa concreta. Super+Escape recarga configuración
sin reiniciar Hyprland; no se simula el apagado del compositor Wayland.
Sticky/pin requiere una ventana flotante: Super+S, después Super+Ctrl+Y.
El manifiesto distingue equivalentes, adaptaciones, overrides privados y aliases.

Volumen y brillo usan `wysun-control`: un proceso breve por tecla, OSD Dunst,
lectura posterior del valor real y canales separados. El brillo no baja del5%.
Los controles multimedia conservan preferencia por MPD activo y seleccionan un
único reproductor MPRIS de fallback antes de actuar; no saltan a otro si falla
una acción. `--dry-run` sólo consulta/describe, no cambia volumen, brillo ni
reproducción. La sesión reutiliza el dunstrc previo cuando existe, sin mover
historial ni reiniciar Dunst al actualizar aplicaciones.

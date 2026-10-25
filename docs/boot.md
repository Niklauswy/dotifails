# Arranque · la cinta de formación y la terminal

El arranque está inspirado en *Severance*, sin repetir la terminal de refinamiento (que es solo del bloqueo).
Usa la paleta **Severance** de `apps/shell/modules/lockscreen/severance-scheme.json`, fija: no depende
del tema del escritorio; el azul de la tarjeta es una excepción declarada en `system/boot/render_assets.py`.

- **GRUB · la cinta de formación**: una tarjeta azul «WYSUN MANAGEMENT PROGRAM» con el globo de Wysun, como un
  fotograma de VHS en un tubo (`apps/shell/modules/bootart/shaders/vhs.frag`: imagen blanda de baja resolución,
  blancos que se corren, color desplazado, franja de tracking, dithering ordenado, scanlines y esquinas curvas).
  Las entradas son los programas impresos bajo el título; la cuenta atrás dice «THE PROGRAM BEGINS IN %d SECONDS».
  GRUB no anima: solo se redibuja al pulsar teclas y con la cuenta atrás. Su terminal (los mensajes «Loading Linux…», la consola y el
  editor de entradas) usa como fondo el propio recorte de la tarjeta, así que al elegir una entrada no aparece un
  recuadro negro: el texto sale impreso sobre la tarjeta. El kernel hereda el modo gráfico de GRUB
  (`GRUB_GFXPAYLOAD_LINUX=keep`) y no muestra el cursor de texto (`vt.global_cursor_default=0`, solo si no lo
  tenías definido). El fondo pesa menos de 400 KB (el
  decodificador PNG de GRUB es lento; la compilación de recursos y `tests/test_boot.py` lo impiden).
- **Plymouth · la terminal**: un CRT de oficina (`crt.frag`) y, en su cristal, todo en fósforo (`phosphor.frag`:
  píxeles gruesos, dithering ordenado, scanlines). La terminal hojea el índice de proyectos como un tablero de
  tarjetas: es una sola carpeta y su tarjeta superior cae sobre la bisagra y descubre la siguiente (Allentown,
  Astoria, Bellingham, Cielo, Tumwater; `filebox.frag`). Se detiene en **Cold Harbor**, el cursor la pulsa, la
  carpeta se deshace en el campo de datos y el progreso real llena el indicador de la cabecera. Las contraseñas de
  discos cifrados las pide el propio programa de la terminal (una ventana en fósforo, con los puntos tecleados), y
  la secuencia espera mientras tanto. Al apagar o reiniciar los datos se apagan y entra caminando una mascota de oficina
  original, al estilo de los dibujos animados de goma de los años 30 (un reloj redondo con piernas cortas, zapatos
  grandes y guantes). Tiene caras de temperamento: alegre al saludar («GOODBYE!»), triste con una lágrima
  («I'LL MISS YOU...»), juguetona con guiño y lengua al brincar («SEE YOU TOMORROW!») y asustada
  («LIGHTS OUT?!»). Se voltea, salta aplastándose y estirándose y recorre el cristal con un globo de diálogo que
  la sigue con retraso; al reiniciar dice «BE RIGHT BACK!» y «JUST A MOMENT...».
  **Nunca queda la pantalla en negro**. Los mensajes son «GOOD WORK. HAVE A GREAT DAY.» y
  «GOOD WORK. SEE YOU IN A MOMENT.».
- **Pantalla de acceso (greetd, experimental)**: la misma terminal del bloqueo como login. **No se instala por
  defecto**: en la primera prueba real las sesiones no llegaban a abrirse y hubo que volver a LightDM. Solo con
  `--boot-components grub,plymouth,greeter` y tras validarla en una consola aparte; ver más abajo.

### Transiciones

- GRUB: `/etc/grub.d/06_wysun` da a su terminal el propio recorte de la tarjeta como fondo y hace que los mensajes
  «Loading Linux…» / «Loading initial ramdisk…» se impriman en el azul de la tarjeta (redefine `load_video`, que
  las entradas de Linux llaman primero): no aparece el recuadro negro. La consola y el editor conservan sus
  colores. Probado con el tema real en QEMU/OVMF.
- Plymouth aparece sin retraso (`ShowDelay=0` en `plymouthd.conf`).
- greetd salta a su VT (la 7, vacía y sin cursor) antes de arrancar (`greetd.service.d/wysun-vt.conf`), así no se
  ve el login de texto de la VT 1 entre la animación y la pantalla de acceso.
- No se usa `plymouth quit --retain-splash`: deja la VT 1 en modo gráfico y greetd se queda esperando para cambiar
  a la suya, sin pantalla de acceso (pasó en la primera prueba real).
- Apagar y reiniciar esperan a la despedida hasta 12 s (`wysun-farewell.service`, que solo actúa si Plymouth está en
  pantalla); cualquier tecla la salta. Se indica con «PRESS ANY KEY TO SKIP».

## Instalar o actualizar

```sh
sudo apt install greetd qt6-shader-baker        # solo para la pantalla de acceso, si aún no están
./instalar.sh --boot-only --dry-run
./instalar.sh --boot-only
./instalar.sh --boot-only --boot-components grub,plymouth,greeter   # experimental, ver abajo
```

`--boot-only` no instala paquetes. Si falta greetd, la pantalla de acceso se omite y se indica cómo instalarlo. Pide
autenticación con sudo, no reinicia ni detiene el gestor de acceso y no cierra la sesión: todo se ve en el próximo
arranque. No se ejecuta `grub-install`, no se toca el cargador EFI ni las particiones. GRUB se genera en un archivo
temporal y se verifica con `grub-script-check` antes de sustituir el menú; después se regeneran las imágenes de
inicio. Si el sistema aún no usa splash, se añade `quiet splash`; las consolas seriales se conservan.

### Pantalla de acceso con greetd (experimental)

No forma parte de la instalación por defecto. Antes de usarla de nuevo debe validarse lanzando greetd en otra VT sin
desactivar LightDM (por ejemplo `sudo greetd --vt 8 --config <prueba>.toml`), comprobando que la sesión se abre.
La VT de prueba debe estar libre: comprobar la sesión activa con `loginctl` antes de elegirla; no asumir que es la 8.

La entrega del comando a greetd se hace como una línea completa (`Greetd.launch([session.exec], ...)`).
greetd une los elementos de `cmd` con espacios y los ejecuta mediante `sh`; envolverlo como un argv
`["/bin/sh", "-c", "exec …"]` hacía que el shell interior ejecutara solamente `exec` y terminara sin abrir el escritorio.
`python3 tests/greeter_runtime.py` prueba rechazo, reintento y lanzamiento con el Quickshell real en un compositor
anidado, y ejecuta una sesión sintética con argumentos entrecomillados; también reproduce el fallo anterior.
No introduce contraseñas reales ni inicia una sesión de escritorio del usuario.
Los registros del greeter se conservan, con permisos privados, en
`/var/lib/greetd/.local/state/wysun/greeter.log` y `greeter.previous.log`.

- Archivos: `/usr/local/share/wysun/greeter` (la escena portable, sin el plugin de Wysun; paleta Severance; shaders
  compilados con el `qsb` del sistema; `hyprland.conf` con la distribución de teclado de `/etc/default/keyboard`),
  `/usr/local/libexec/wysun-greeter` y `/etc/greetd/config.toml` (usuario `_greetd`, VT 7).
- Se ejecuta con el Quickshell de Debian dentro de un Hyprland mínimo. La autenticación es la de greetd
  (`/etc/pam.d/greetd`, que incluye `login`); la contraseña va del campo oculto a greetd y no se guarda.
- Si el compositor o la escena fallan, el lanzador cae al login de texto `agreety` de greetd.
- El cambio de gestor: `/etc/X11/default-display-manager` pasa a greetd, se deshabilita el anterior (por ejemplo
  LightDM, que no se desinstala) y se habilita `greetd.service`. Ambos quedan en el diario.

## Respaldos y recuperación

Los respaldos del sistema viven en `/var/lib/dotifails/boot/backups/ID` (distintos de los del hogar). En el
instalador: **Recuperación → Arranque…**. Desde la terminal:

```sh
sudo python3 installer/boot.py --list
sudo python3 installer/boot.py --restore ID
sudo python3 installer/boot.py --verify
```

La restauración recupera el `grub.cfg` original, reconstruye la imagen de inicio y, si se cambió el gestor de acceso,
vuelve a habilitar el anterior. Los cambios hechos después se guardan en `changes-before-restore/`. Al actualizar se
conservan los archivos administrados que hayas modificado: el instalador se detiene y muestra el conflicto.

Si la pantalla de acceso no aparece: cambia a una TTY (Ctrl+Alt+F3), inicia sesión y ejecuta
`sudo python3 ~/.local/share/dotifails/installer/boot.py --restore ID`, o habilita de nuevo el gestor anterior con
`sudo systemctl disable greetd && sudo systemctl enable --force lightdm` y reinicia.

## Recursos y vistas previas

Los PNG, `theme.txt` y `orbit.script` ya están incluidos; una instalación nueva no genera nada. Para regenerarlos
(en una sesión Wysun con el runtime del shell):

```sh
python3 system/boot/render_assets.py --farewell-only  # solo mascota y despedidas; preserva el monitor
python3 system/boot/render_assets.py        # tarjeta, terminal, carpetas y textos en fósforo; piezas con Qt; fuentes; plantillas
python3 tests/grub_preview.py grub.png      # GRUB tal como lo compone theme.txt, sin reiniciar
python3 tests/plymouth_preview.py salida/   # el script real en el intérprete de Plymouth, fotograma a fotograma
```

`theme.txt.in` y `orbit.script.in` son plantillas (no se instalan). El script de Plymouth usa su propio generador
Park–Miller: el `Math.Random()` de Plymouth en Debian devuelve valores cercanos a 1e-10. Las fuentes GRUB derivan de
DejaVu y su licencia se incluye con el tema. Pruebas: `tests/test_boot.py` (incluye el intérprete real de Plymouth y la
verificación de la configuración del greeter con `Hyprland --verify-config`).

Referencias: [formato de temas de GRUB](https://www.gnu.org/software/grub/manual/grub/html_node/Theme-file-format.html),
[Plymouth](https://gitlab.freedesktop.org/plymouth/plymouth), [greetd](https://sr.ht/~kennylevinsen/greetd/).

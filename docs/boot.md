# Arranque y acceso

El inicio usa Blue CRT: azul clásico de BIOS/GRUB, tipografía monoespaciada, marco de tubo y líneas de barrido. Es independiente del tema del escritorio.

- GRUB: fondo CRT original, tipografía monoespaciada, panel gris biselado con sombra dura, selección azul, ordenador CRT, iconos por clase de sistema, teclas en relieve y barra de cuenta regresiva. Las entradas, recuperación, timeout y sistema predeterminado se conservan.
- Plymouth: Tux, ventana gris, 72 fotogramas de carga, 16 capas de ruido, barrido móvil y encendido desde el centro, sin el loro. El apagado y el reinicio usan otros 48 fotogramas cada uno, con sus títulos correctos, un indicador de energía ámbar y el ordenador CRT. `Plymouth.GetMode()` selecciona la secuencia y admite cambios de modo durante la ejecución. Incluye los avisos del sistema, preguntas y contraseña para discos cifrados.
- LightDM: fondo CRT azul, controles con biseles clásicos y Tux con ocho poses (parpadeo y saludo), respiración suave y una capa CRT animada que cubre también los controles, sin cuadrícula ni marca de Parrot. Conserva las cuentas, sesiones y opciones de accesibilidad. El bloqueo de la sesión continúa usando `orbit-lock`.

La selección completa lo incluye. En el instalador visual puedes elegir GRUB, Plymouth y acceso por separado. Para actualizar únicamente estas pantallas desde la terminal:

```sh
./instalar.sh --boot-only --dry-run
./instalar.sh --boot-only
./instalar.sh --boot-only --boot-components grub,plymouth
```

El segundo comando pide autenticación de administrador mediante sudo. No reinicia LightDM ni cierra la sesión; los cambios se ven en el próximo arranque. En equipos sin GRUB o con otro gestor de acceso, se omite ese componente. Las consolas seriales se conservan.

No se ejecuta `grub-install`, no se modifica el cargador EFI ni las particiones. El cambio visual añade `quiet splash` si el sistema aún no usa splash. GRUB se genera primero en un archivo temporal y se verifica con `grub-script-check` antes de sustituir el menú; después se regeneran las imágenes de inicio de los kernels instalados.

Los respaldos del sistema viven en `/var/lib/dotifails/boot/backups/ID`. Son distintos de los respaldos del hogar. En el instalador visual, **Respaldos → Respaldos del arranque Blue CRT** permite consultarlos, verificarlos y restaurarlos con autorización de administrador. Desde la terminal:

```sh
sudo python3 installer/boot.py --list
sudo python3 installer/boot.py --restore ID
```

La restauración recupera también el `grub.cfg` original y reconstruye la imagen de inicio. Los cambios hechos después de la instalación se guardan en `changes-before-restore/`. Si falla la aplicación, intenta recuperar automáticamente los archivos anteriores; un fallo persistente al reconstruir initramfs se informa y deja el diario en estado `restoring` para repetir la recuperación.

Al actualizar se conservan los archivos administrados que hayas modificado: el instalador detiene el cambio y muestra el conflicto. No escribe preferencias personales en el repositorio.

GRUB muestra una interfaz estática con cuenta regresiva: no admite animación continua de fondos. Plymouth reproduce la secuencia de carga; LightDM conserva sus transiciones nativas y añade un módulo GTK3 decorativo: encendido CRT, barrido, máscara de fósforo, ruido, pérdida breve de sincronía y un indicador de actividad al escribir. No lee ni guarda el contenido de los campos. Respeta `gtk-enable-animations=false`; `BLUE_CRT_REDUCED_MOTION=1` también desactiva su movimiento.

Para comprobar el despliegue y que cada kernel incluye la animación:

```sh
sudo python3 installer/boot.py --verify
```

Los PNG y las fuentes GRUB ya están incluidos: una PC nueva no necesita Pillow, descargar fondos ni generar imágenes. Para modificar el arte original, `system/boot/generate_assets.py` requiere Pillow, `grub-mkfont` y `gdk-pixbuf-thumbnailer`. Los 72 fotogramas del panel pueden revisarse en `system/boot/preview.gif`; el barrido y el encendido se componen durante la ejecución. Las fuentes derivan de DejaVu; su licencia se incluye con el tema.

El instalador compila `native/blue-crt/blue-crt.c` para la arquitectura de destino con GTK3, GCC y pkg-config (incluidos en el manifiesto). El módulo se carga únicamente en la sesión `blue-crt.desktop`, que ejecuta Slick Greeter. PAM y la autenticación siguen siendo los originales. Sus archivos y la selección de sesión se incluyen en el respaldo y la restauración.

El Tux fue generado con la herramienta integrada de imágenes; el original RGBA se conserva sin retoque en `system/boot/greeter/assets/tux.png` y se incluye también con Plymouth. El prompt está en `system/boot/ASSETS.md`. Los demás PNG se regeneran con el script local.

Referencias de compatibilidad: [formato de temas de GRUB](https://www.gnu.org/software/grub/manual/grub/html_node/Theme-file-format.html), [Plymouth](https://gitlab.freedesktop.org/plymouth/plymouth) y [configuración de Slick Greeter](https://github.com/linuxmint/slick-greeter#configuration).

Las pruebas de `tests/plymouth_runtime.py` ejecutan el intérprete nativo de Plymouth con dobles de pantalla: verifican el arranque, apagado, reinicio, cambio de modo y pausa para contraseñas, sin apagar el equipo. La vista previa de carga compone los mismos assets; la confirmación del apagado físico requiere un apagado real.

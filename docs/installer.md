# Instalador visual de Wysun

Ejecuta `./instalar.sh` desde el proyecto. Con una sesión gráfica se abre la aplicación nativa; con opciones de instalación o sin pantalla se utiliza la CLI. `--gui` y `--cli` permiten elegirlo explícitamente. En una instalación administrada también puedes abrir **Instalador de Wysun** desde el menú de aplicaciones o ejecutar `dotifails gui`.

## Recorrido

1. **Bienvenida:** confirma la carpeta del proyecto que se va a instalar. Puedes elegir otra copia local.
2. **Apariencia:** Severance, Tokyo o Space Black, con el fondo real y una composición orientativa. Al actualizar está seleccionada la opción de conservar el tema y el fondo actuales.
3. **Componentes:** escritorio, terminal, Neovim, herramientas y Blue CRT. «Esencial» prepara escritorio, terminal y arranque. «Completa» incluye esos cinco. Wysun / Hyprland es un componente adicional opcional y conserva la configuración de BSPWM; consulta [Wayland](wayland.md). El escritorio y Neovim requieren la terminal; desmarcar un componente no lo desinstala.
4. **Opciones:** Brave, Discord y Obsidian mediante Flatpak para el usuario; selección independiente de GRUB, Plymouth y LightDM; preparación diferida de lenguajes de Neovim. El perfil Samsung defectuoso es opcional y nunca se aplica automáticamente.
5. **Revisión:** sistema, arquitectura, archivos del proyecto, permisos, espacio disponible y otra operación activa. El plan detalla paquetes y versiones. La disponibilidad de Internet se comprueba durante la descarga, no se presenta como verificada en esta pantalla.
6. **Instalación:** etapas comunicadas por el motor, tiempo transcurrido, operación actual, conflictos y registro. El progreso cuenta etapas completadas; no estima porcentajes de tiempo ni simula descargas.
7. **Resultado:** estado real, respaldo, recuperación y primeros atajos. Los conflictos y las interrupciones tienen estados distintos del éxito.

La ventana se puede redimensionar y el contenido largo se desplaza verticalmente. Los controles admiten Tab, Espacio y Enter. `ORBIT_REDUCED_MOTION=1 ./instalar.sh` desactiva las transiciones.

## Preparación y autorización

La interfaz requiere `python3-pyside6.qtwidgets`. En una computadora nueva, el lanzador ofrece instalar este entorno mínimo desde una terminal antes de abrir la ventana; también se puede usar `--cli`. Qt y las dependencias de la aplicación quedan incluidos en el plan común.

La aplicación se ejecuta como usuario normal. Las operaciones del sistema utilizan `sudo -A` con un diálogo de contraseña separado. La contraseña se entrega a sudo por una tubería y no se incorpora al plan, a argumentos de comandos ni al registro. Los comandos de APT conservan los archivos de configuración existentes al resolver preguntas de dpkg.

## Detener, repetir y recuperar

«Detener después de esta operación» crea una solicitud que el motor comprueba entre operaciones. No mata APT, una copia de archivos en curso ni la reconstrucción de initramfs. La ventana permanece abierta hasta que el proceso termine. Repetir la instalación reutiliza el motor idempotente y conserva las ediciones locales. No se afirma que una instalación detenida haya sido deshecha.

**Respaldos** muestra los diarios del hogar y permite recuperar el más reciente pendiente. Las modificaciones posteriores se guardan en `changes-before-restore/`. No elimina los paquetes instalados. **Respaldos del arranque Blue CRT** consulta, verifica y restaura los respaldos del sistema mediante autorización; no reinicia el equipo ni LightDM.

Cada operación gráfica conserva su `plan.json`, cuando corresponde, y su `console.log` en `~/.local/state/dotifails/runs/ID/`. La carpeta tiene permisos 0700 y los archivos 0600. Estos registros y los datos personales están fuera del proyecto. Los respaldos anteriores permanecen disponibles; la limpieza del repositorio no los elimina.

## CLI y mantenimiento

```sh
./instalar.sh --components terminal,editor --plan
./instalar.sh --components desktop,boot --theme space-black
./instalar.sh --components boot --boot-components grub,plymouth
./instalar.sh --components terminal --config-only
./instalar.sh --installer-only
```

`--components` no se combina con los modos `--orbit-only`, `--scripts-only`, `--boot-only` o `--installer-only`. Los modos originales conservan su propósito. `--installer-only` actualiza la interfaz, la CLI, los manifiestos y el acceso del menú con respaldo; conserva el resto de la instalación. La interfaz instala la copia local seleccionada. Para descargar una revisión publicada se mantiene `dotifails update`.

El modo **Solo copiar configuraciones** exige dependencias ya instaladas, omite paquetes y registro de sesión y desactiva arranque y aplicaciones opcionales. Una instalación solo de terminal conserva los archivos del escritorio y del editor.

## Organización

- `launcher.py`: selección del modo visual o CLI y preparación inicial de Qt.
- `gui.py` y `visual_widgets.py`: recorrido, controles y vistas previas.
- `install_model.py`: selección, dependencias, plan y comprobaciones sin escrituras.
- `main.py`: instalación y recuperación del hogar, con diario previo a cada modificación.
- `install_events.py` y `process_runner.py`: progreso estructurado, proceso Qt, registros y cancelación entre operaciones.
- `askpass.py`: autorización de sudo.
- `boot.py` y `boot_recovery.py`: instalación, comprobación y recuperación del arranque.
- `manifests/packages.json`: una única lista de paquetes por componente y pantalla de arranque.

Comprobaciones del instalador:

```sh
python3 -m unittest discover -s tests -p test_visual_installer.py -v
python3 -m unittest discover -s tests -p test_boot.py -v
QT_QPA_PLATFORM=offscreen python3 tests/installer_ui.py
python3 tests/check_manifest.py
```

Las pruebas gráficas ejecutan instalación y restauración reales de configuraciones en un hogar temporal mediante QProcess. Comprueban teclado, cancelación, errores, permisos de registros y ausencia de desbordamiento a 800 × 600 y 1100 × 780. No ejecutan APT en el equipo anfitrión ni reinician el sistema. La instalación completa en una máquina nueva y el arranque físico tienen un alcance distinto; consulta [Validación](validation.md).

API de procesos: [documentación de QProcess de Qt](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QProcess.html).
